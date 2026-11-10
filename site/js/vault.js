/* DownerStuff: two-factor sign-in settings (item 30) and the broker-fills import card on the Journal page (item 21).
   Loaded after the other pages; it wraps the Settings and Journal pages and changes nothing else. */
(() => {
const JR = App.journal, card = (title, body, cap = '', extra = '') => `<div class="card"><div class="hd"><h2>${title}</h2>${cap ? `<span class="cap">${cap}</span>` : ''}${extra}</div><div class="bd">${body}</div></div>`;

/* ---------------- Two-factor settings ---------------- */
const MF = App.mfa = { factors: null, aal: null, err: null, busy: false };
async function mfaLoad() {
  if (!App.sb || !App.sb.auth || !App.sb.auth.mfa) { MF.err = 'This version of the sign-in library has no two-factor support.'; return; }
  try { const f = await App.sb.auth.mfa.listFactors(), a = await App.sb.auth.mfa.getAuthenticatorAssuranceLevel(); MF.factors = (f.data && f.data.totp) || []; MF.aal = a.data || null; MF.err = f.error ? f.error.message : null; }
  catch (e) { MF.err = e.message || String(e); MF.factors = []; }
}
function mfaCard() {
  return card('Two-factor sign-in', '<div id="mfaBox"><p class="help">Checking…</p></div>', 'a code from your phone, as well as your password');
}
function paintMfa() {
  const box = $('#mfaBox'); if (!box) return;
  if (MF.err && !MF.factors) { box.innerHTML = `<p class="help">${esc(MF.err)}</p>`; return; }
  const on = (MF.factors || []).length > 0;
  box.innerHTML = on ? `<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><span class="pill ok">On</span><span>Signing in asks for a 6-digit code from your authenticator app.</span></div>
      <p class="help" style="margin:10px 0">Session level now: <b>${MF.aal && MF.aal.currentLevel === 'aal2' ? 'code verified' : 'password only'}</b>. To make the database itself refuse your journal without a verified code (so a stolen password alone is useless), run <code>supabase/require_2fa.sql</code> in Supabase once, <b>after</b> you have signed out and back in with your code.</p>
      <button class="btn danger sm" type="button" id="mfaOff">Turn off two-factor</button>`
    : `<p style="margin:0 0 10px">Off. Turn it on, scan a QR code with an authenticator app (Google Authenticator, Authy, 1Password...), and from then on signing in also asks for the 6-digit code.</p>
      <p class="help" style="margin:0 0 10px"><b>Keep the secret key that is shown with the QR code somewhere safe</b> (a password manager). If you lose your phone, it is the way back in. Without it, you would have to remove the factor in the Supabase dashboard.</p>
      <button class="btn primary" type="button" id="mfaOn">Turn on two-factor</button>`;
  if ($('#mfaOn')) $('#mfaOn').onclick = enroll;
  if ($('#mfaOff')) $('#mfaOff').onclick = async () => {
    if (!confirm('Turn off two-factor sign-in? Signing in will only need your password.')) return;
    const f = MF.factors[0]; const { error } = await App.sb.auth.mfa.unenroll({ factorId: f.id });
    if (error) { App.toast(/aal2|verified|AAL/i.test(error.message) ? 'Sign out and sign in again with your code first, then turn it off.' : error.message); return; }
    App.toast('Two-factor is off'); await mfaLoad(); paintMfa(); };
}
async function enroll() {
  const { data, error } = await App.sb.auth.mfa.enroll({ factorType: 'totp', friendlyName: 'DownerStuff ' + new Date().toISOString().slice(0, 16).replace('T', ' ') });
  if (error) { App.toast(error.message); return; }
  const bg = document.createElement('div'); bg.className = 'modal-bg';
  bg.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-label="Turn on two-factor" style="max-width:480px"><div class="mh"><h2>Turn on two-factor</h2></div><div class="mb">
    <ol class="steps"><li><b>Scan this QR code</b> with your authenticator app.<div class="qr"><img alt="QR code to add DownerStuff to your authenticator app" src="${esc(data.totp.qr_code)}"></div></li>
    <li><b>Or type this key into the app</b> and save it somewhere safe:<br><code class="secret">${esc(data.totp.secret)}</code></li>
    <li><b>Enter the 6-digit code</b> the app now shows:<div class="field" style="margin-top:8px"><input id="mfaCode" inputmode="numeric" autocomplete="one-time-code" maxlength="9" placeholder="123456" aria-label="6-digit code"></div></li></ol>
    <p class="help" id="mfaMsg" style="margin:8px 0 0"></p></div><div class="mf"><button class="btn" data-cancel>Cancel</button><button class="btn primary" data-ok>Turn on</button></div></div>`;
  document.body.appendChild(bg); setTimeout(() => $('#mfaCode', bg).focus(), 40);
  const close = async undo => { bg.remove(); if (undo) { try { await App.sb.auth.mfa.unenroll({ factorId: data.id }); } catch (e) { } } };
  bg.addEventListener('click', async e => {
    if (e.target.closest('[data-cancel]')) close(true);
    if (e.target.closest('[data-ok]')) { const code = $('#mfaCode', bg).value.replace(/\s+/g, ''), m = $('#mfaMsg', bg);
      if (!/^\d{6}$/.test(code)) { m.textContent = 'Enter the 6 digits from your app.'; return; }
      try { const ch = await App.sb.auth.mfa.challenge({ factorId: data.id }); if (ch.error) throw ch.error; const v = await App.sb.auth.mfa.verify({ factorId: data.id, challengeId: ch.data.id, code }); if (v.error) throw v.error;
        close(false); App.toast('Two-factor is on'); await mfaLoad(); paintMfa(); }
      catch (err) { m.textContent = 'That code did not work. Wait for the next code in your app and try again.'; $('#mfaCode', bg).value = ''; } } });
}
const sPage = App.pages.settings; App.pages.settings = q => sPage(q) + mfaCard();
const sBind = App.binds.settings; App.binds.settings = q => { if (sBind) sBind(q); mfaLoad().then(paintMfa); };

/* ---------------- Broker fills (Angel One tradebook import) ---------------- */
const FL = App.fills = { rows: null, at: 0, err: null, busy: false };
async function loadFills(force) {
  if (!App.sb || FL.busy || (!force && Date.now() - FL.at < 60000) || !window.Fills) return; FL.busy = true;
  try { const { data, error } = await App.sb.from('broker_fills').select('*').eq('imported', false).order('filled_at', { ascending: true }); FL.err = error ? (error.message || String(error)) : null; FL.rows = error ? [] : (data || []); }
  catch (e) { FL.err = e.message || String(e); FL.rows = []; }
  FL.at = Date.now(); FL.busy = false; if (App.route().page === 'journal' && !$('.modal-bg')) App.render();
}
const markImported = async ids => { try { await App.sb.from('broker_fills').update({ imported: true }).in('fill_id', ids); } catch (e) { } await loadFills(true); };
function proposals() {
  if (!FL.rows || !FL.rows.length || !window.Fills) return { pending: [], done: [] };
  return Fills.split(Fills.propose(FL.rows, JR.enrich().filter(t => t.open)), JR.J().trades);
}
const inr0 = v => v == null ? '-' : fmt(v);
function fillsCard() {
  const P = proposals(); if (!P.pending.length) return '';
  const rows = P.pending.map(p => p.kind === 'trade'
    ? `<tr><td><b>${esc(p.inst)}</b><br><small class="muted">${esc(p.cat)} · ${esc(p.d)} ${esc(p.tm)}</small></td><td>${esc(p.dir)}</td><td class="n">${fmt0(p.qty)}</td><td class="n">${inr0(p.entry)}</td><td class="n">${p.closed ? inr0(p.exit) : '<span class="pill warn">open</span>'}</td>
        <td class="n">${p.partial ? '<small class="muted">partly closed: wait until flat</small>' : `<button class="btn sm primary" type="button" data-fimp="${esc(p.key)}">Import</button>`} <button class="btn sm ghost" type="button" data-fdis="${esc(p.key)}" title="Skip this one" aria-label="Dismiss">×</button></td></tr>`
    : p.kind === 'close'
    ? `<tr><td><b>${esc(p.inst)}</b><br><small class="muted">sold ${esc(p.d)} ${esc(p.tm)}</small></td><td>Exit</td><td class="n">${fmt0(p.qty)}</td><td class="n">${inr0(p.entry)}</td><td class="n">${inr0(p.exit)}</td><td class="n"><button class="btn sm primary" type="button" data-fcls="${esc(p.key)}">Close in journal</button> <button class="btn sm ghost" type="button" data-fdis="${esc(p.key)}" aria-label="Dismiss">×</button></td></tr>`
    : `<tr><td><b>${esc(p.inst)}</b><br><small class="muted">sold ${esc(p.d)}</small></td><td colspan="4"><small class="muted">A sale with no matching open trade in your journal.</small></td><td class="n"><button class="btn sm ghost" type="button" data-fdis="${esc(p.key)}">Dismiss</button></td></tr>`).join('');
  return `<div class="card" style="margin-bottom:14px"><div class="hd"><h2>From Angel One</h2><span class="cap">${P.pending.length} new from today's fills</span></div><div class="bd"><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Trade</th><th>Side</th><th class="n">Qty</th><th class="n">Entry</th><th class="n">Exit</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="help" style="margin-top:8px">Import opens the trade form with the fills filled in. Add your stop-loss and grade, and the charges (the tradebook has none), then save. Nothing is added to your journal until you save.</p></div></div>`;
}
const jPage = App.pages.journal;
App.pages.journal = q => { const h = jPage(q), c = fillsCard(), i = h.indexOf('<div class="kpis"'); return !c ? h : i > 0 ? h.slice(0, i) + c + h.slice(i) : c + h; };      // below the page heading, above the totals
const jBind = App.binds.journal;
App.binds.journal = q => {
  if (jBind) jBind(q); loadFills(false);
  const P = proposals(); if (P.done.length) markImported(P.done.flatMap(p => p.ids));                      // trades you already imported
  const find = k => P.pending.find(p => p.key === k);
  $$('[data-fimp]').forEach(b => b.onclick = () => { const p = find(b.dataset.fimp); if (p) JR.openForm(null, Fills.prefill(p)); });
  $$('[data-fdis]').forEach(b => b.onclick = () => { const p = find(b.dataset.fdis); if (p && confirm(`Dismiss ${p.inst}? It will not be offered again.`)) markImported(p.ids); });
  $$('[data-fcls]').forEach(b => b.onclick = () => { const p = find(b.dataset.fcls); if (!p) return; const t = JR.J().trades.find(x => x.id === p.tradeId); if (!t) return;
    if (!confirm(`Set the exit of ${p.inst} to ${fmt(p.exit)} in your journal?`)) return; t.exit = p.exit; t.note = (t.note || '') + (t.note ? ' | ' : '') + 'BR:' + p.key; JR.touch(); JR.persist(); markImported(p.ids); App.render(); App.toast('Trade closed in your journal'); });
};
})();
