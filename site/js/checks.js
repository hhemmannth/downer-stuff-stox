/* DownerStuff browser-side checks (25 Nov 2026, items 431-462, 486, 490, 494, 497-500). Loaded after journal3.js.
   Reads only. The journal checks list problems and point to the trade; they never change or delete a trade. */
(() => {
'use strict';
const JR = App.journal;
const day = s => /^\d{4}-\d{2}-\d{2}$/.test(String(s || ''));

/* ---------- journal integrity (431-445) ---------- */
JR.integrity = () => { const j = JR.J(), T = j.trades || [], out = [], today = todayIST(), add = (sev, t, what) => out.push({ sev, id: t && t.id, inst: t ? t.inst : '', d: t ? t.d : '', what });
  const ids = {}; T.forEach(t => { if (ids[t.id]) add('bad', t, 'two trades share one id (the second may overwrite the first when it syncs)'); ids[t.id] = 1; });
  T.forEach(t => { const e = +t.entry, s = +t.sl, x = t.exit != null && t.exit !== '' ? +t.exit : null, q = +t.qty;
    if (!day(t.d)) add('bad', t, 'entry date is missing or not a date');
    else if (t.d > today) add('warn', t, 'entry date is in the future');
    if (t.xd && day(t.d) && t.xd < t.d) add('bad', t, 'exit date is before the entry date');
    if (x != null && !t.xd && !t.xd_unknown) add('warn', t, 'exit price without an exit date (it is left out of daily and monthly totals)');
    if (!(q > 0)) add('bad', t, 'quantity is zero, negative or missing');
    if (!(e > 0)) add('bad', t, 'entry price is zero, negative or missing');
    if (e > 0 && s > 0) { if (e === s) add('bad', t, 'stop equals the entry, so R cannot be worked out'); else if ((t.dir === 'Short') !== (s > e)) add('bad', t, `stop is on the wrong side for a ${t.dir === 'Short' ? 'short' : 'long'} trade`); }
    if (e > 0 && x != null && x > 0 && (x / e > 5 || x / e < .2)) add('warn', t, 'exit is more than five times away from the entry: a typo?');
    if (Array.isArray(t.parts) && t.parts.length) { const pq = t.parts.reduce((a, p) => a + (+p.qty || 0), 0); if (pq > q) add('bad', t, `partial exits (${pq}) are more than the quantity (${q})`); }
    ['entry', 'sl', 'tgt', 'exit', 'qty', 'chg'].forEach(k => { if (t[k] != null && t[k] !== '' && !isFinite(+t[k])) add('bad', t, `${k} is not a number`); });
    if (x == null && day(t.d) && (Date.parse(today) - Date.parse(t.d)) / 864e5 > 90) add('warn', t, 'open for more than 90 days: still open, or the exit was never logged?');
    if (t.setup && !(j.lists && j.lists.setups || []).includes(t.setup)) add('info', t, `setup "${t.setup}" is not in your setups list`); });
  const dups = {}; T.forEach(t => { const k = [t.d, t.tm, String(t.inst).toUpperCase(), t.entry, t.qty].join('|'); if (dups[k]) add('warn', t, 'looks like a duplicate of another trade (same day, time, instrument, entry and quantity)'); dups[k] = 1; });
  return out; };

/* ---------- this device and the site (446-462, 494) ---------- */
let skew = null;
const clockSkew = async () => { try { const r = await fetch('index.html?skew=' + Date.now(), { method: 'HEAD', cache: 'no-store' }), d = r.headers.get('date'); if (d) skew = Math.round((Date.now() - new Date(d)) / 1000); } catch (e) { } return skew; };
App.clockSkew = () => skew;
const C = async () => { const R = [], add = (name, ok, detail, fix) => R.push({ name, ok, detail, fix });
  try { localStorage.setItem('ds_probe', '1'); const okS = localStorage.getItem('ds_probe') === '1'; localStorage.removeItem('ds_probe'); add('Browser storage works', okS, okS ? 'read and write' : 'cannot write', 'Private browsing blocks storage; open the app normally.'); } catch (e) { add('Browser storage works', false, 'blocked: ' + e.name, 'Private browsing blocks storage; open the app normally.'); }
  let used = 0; try { for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); used += (k.length + (localStorage.getItem(k) || '').length) * 2; } } catch (e) { }
  add('Journal storage space', used < 4e6, `${(used / 1048576).toFixed(2)} MB used of about 5 MB`, 'Download a backup, then empty the recycle bin and remove old screenshots.');
  try { if (navigator.storage && navigator.storage.persisted) { const p = await navigator.storage.persisted(); add('Storage kept by the browser', p ? true : null, p ? 'persistent' : 'the browser may clear it if space runs low', 'Add the app to your Home Screen; the cloud copy also protects you.'); } } catch (e) { }
  const sw = navigator.serviceWorker && navigator.serviceWorker.controller; add('Offline copy (service worker)', sw ? true : null, sw ? 'active' : 'not active yet (first visit, or the browser blocks it)', 'Reload once; it starts on the second visit.');
  const vs = [...document.querySelectorAll('script[src*="?v="],link[href*="?v="]')].map(e => ((e.src || e.href).match(/v=(\d+)/) || [])[1]), uv = new Set(vs);
  add('All page files are the same version', uv.size === 1, uv.size === 1 ? 'version ' + vs[0] : 'mixed: ' + [...uv].join(', '), 'Hard refresh (Cmd+Shift+R) or reopen the app.');
  const er = (App.errors ? App.errors() : []).filter(e => Date.now() - new Date(e.at) < 864e5); add('No errors on this device today', !er.length, er.length ? `${er.length}: ${esc(String(er[er.length - 1].msg || '').slice(0, 80))}` : 'none', 'Settings → Copy error log, and send it to me.');
  const s = await clockSkew(); add('Device clock is right', s == null ? null : Math.abs(s) < 120, s == null ? 'could not compare' : Math.abs(s) < 5 ? 'matches the server' : `${s > 0 ? 'ahead' : 'behind'} by ${Math.abs(s)} s`, 'Set the date and time to automatic; data ages and alerts depend on it.');
  add('Online', navigator.onLine, navigator.onLine ? 'yes' : 'offline: showing the last data saved on this device', '');
  const ages = ['swing', 'options', 'intraday', 'market'].map(k => { const d = App.data[k]; return d && d.generated_at ? [k, Math.round((Date.now() - (skew || 0) * 1000 - new Date(d.generated_at)) / 6e4)] : [k, null]; });
  const open = App.marketOpen && App.marketOpen() && App.tradingDay && App.tradingDay(), late = ages.filter(([k, a]) => open && a != null && a > (k === 'swing' ? 100 : 15));
  add('Scan data is fresh', open ? !late.length : null, ages.map(([k, a]) => `${k} ${a == null ? '-' : a < 120 ? a + ' min' : Math.round(a / 60) + ' h'}`).join(' · '), 'System health says which workflow to run.');
  const bad = ['swing', 'options', 'intraday'].filter(k => App.data[k] && !Array.isArray(App.data[k].setups)); add('Data files have the expected shape', !bad.length, bad.length ? 'unexpected: ' + bad.join(', ') : 'setups lists present', 'Run the scan workflow again.');
  const ji = JR.integrity(), jb = ji.filter(x => x.sev === 'bad').length; add('Journal entries are consistent', !jb, `${jb} problem(s), ${ji.filter(x => x.sev === 'warn').length} to look at`, 'Open each one below and fix it in the trade form.');
  add('Journal saved to the cloud', JR.cloudUser && JR.cloudUser() ? true : null, JR.syncText ? JR.syncText().slice(0, 80) : '', 'Settings → sign in to keep a cloud copy.');
  return R; };
App.runChecks = async () => { const R = await C(); store.set('ds_checks_last', { at: new Date().toISOString(), R }); return R; };

/* ---------- self-healing on this device (490): reload data and re-sync when the phone wakes or comes back online ---------- */
let hidAt = 0;
document.addEventListener('visibilitychange', () => { if (document.hidden) { hidAt = Date.now(); return; } if (hidAt && Date.now() - hidAt > 5 * 6e4) { try { App.reload && App.reload(); } catch (e) { } try { JR.cloudUser && JR.cloudUser() && JR.syncNow && JR.syncNow(); } catch (e) { } } });
addEventListener('online', () => { setTimeout(() => { try { App.reload && App.reload(); } catch (e) { } try { JR.cloudUser && JR.cloudUser() && JR.syncNow && JR.syncNow(); } catch (e) { } }, 1500); });
setTimeout(clockSkew, 2500);

/* ---------- System health: run all checks now (498), browser checks, journal checks, errors history (497), alert log (486) ---------- */
const hp0 = App.pages.health, hb0 = App.binds.health;
const mk = ok => ok === true ? '<span class="mk y">✓</span>' : ok === false ? '<span class="mk n">✗</span>' : '<span class="mk q">?</span>';
App.pages.health = q => { let h = hp0(q); ['health/checks_history', 'health/alerts_log'].forEach(n => { if (!App.lazyNow(n) && App.lazyAge(n) === Infinity) App.lazy(n).then(() => App.soon('health')).catch(() => { }); });
  const last = store.get('ds_checks_last', null), R = last ? last.R : null, ji = JR.integrity(), hist = ((App.lazyNow('health/checks_history') || {}).items || []).slice(-20).reverse(), al = ((App.lazyNow('health/alerts_log') || {}).items || []).slice(-15).reverse(), wf = App.actionsUrl ? App.actionsUrl() : '';
  h += `<div class="card" id="runAll" style="margin-top:14px"><div class="hd"><h2>Run all checks now</h2><span class="cap">${last ? 'last run ' + hmIST(new Date(last.at)) : 'not run on this device yet'}</span><span class="sp"></span><button class="btn sm primary" type="button" id="runChecks">Run checks</button>${wf ? `<a class="btn sm ghost" href="${esc(wf)}/workflows/scan.yml" target="_blank" rel="noopener">Re-run the server checks (scan)</a>` : ''}</div><div class="bd">
      ${R ? `<ul class="checks">${R.map(r => `<li>${mk(r.ok)}<span class="tf"></span><div><b>${esc(r.name)}</b><p>${esc(r.detail || '')}${r.ok === false && r.fix ? ` <span class="muted">· ${esc(r.fix)}</span>` : ''}</p></div></li>`).join('')}</ul>` : '<p class="help">Checks this device, the site files, the data ages, the device clock and your journal. The server-side checks run after every scan and are listed above.</p>'}</div></div>
    <div class="card" style="margin-top:14px"><div class="hd"><h2>Journal checks</h2><span class="cap">${ji.length ? ji.length + ' found' : 'nothing found'}</span></div><div class="bd">${ji.length ? `<ul class="checks">${ji.slice(0, 40).map(x => `<li>${mk(x.sev === 'bad' ? false : null)}<span class="tf"></span><div><b>${x.id ? `<a href="#" data-jfix="${esc(x.id)}">${esc(x.inst || '?')}</a>` : esc(x.inst || '')} <small class="muted">${esc(x.d || '')}</small></b><p>${esc(x.what)}</p></div></li>`).join('')}</ul>${ji.length > 40 ? `<p class="help">and ${ji.length - 40} more</p>` : ''}`: '<p class="help">Every trade has a date, quantity, entry, a stop on the right side, and exits that add up.</p>'}</div></div>
    <div class="grid g2" style="margin-top:14px"><div class="card"><div class="hd"><h2>Errors history</h2><span class="cap">server checks, last ${hist.length} runs</span></div><div class="bd">${hist.length ? `<ul class="checks">${hist.map(x => `<li>${mk(x.level === 'fail' ? false : x.level === 'pass' ? true : null)}<span class="tf"></span><div><b>${esc(String(x.at || '').slice(0, 16).replace('T', ' '))}</b><p>${x.failing && x.failing.length ? 'failing: ' + esc(x.failing.join(', ')) : x.warning && x.warning.length ? 'to look at: ' + esc(x.warning.slice(0, 3).join(', ')) : 'all passing'}</p></div></li>`).join('')}</ul>` : '<p class="help">Filled after the next scan.</p>'}</div></div>
    <div class="card"><div class="hd"><h2>Phone alerts sent</h2><span class="cap">from the scan runs</span></div><div class="bd">${al.length ? `<ul class="checks">${al.map(x => `<li>${mk(x.ok ? (x.held ? null : true) : false)}<span class="tf"></span><div><b>${esc(String(x.at || '').slice(5, 16).replace('T', ' '))}</b> ${esc(x.title || '')}<p>${x.ok ? (x.held ? 'held back (quiet hours)' : 'sent to ' + esc((x.channels || []).join(' and '))) : 'failed: ' + esc(x.error || '')}</p></div></li>`).join('')}</ul>` : '<p class="help">Filled after the next scan that sends an alert.</p>'}</div></div></div>`;
  return h; };
App.binds.health = q => { if (hb0) hb0(q); const b = $('#runChecks'); if (b) b.onclick = async () => { b.disabled = true; b.textContent = 'Checking…'; try { await App.runChecks(); } finally { App.render(); } };
  $$('[data-jfix]').forEach(a => a.onclick = e => { e.preventDefault(); JR.openForm(a.dataset.jfix); }); };

/* launch checklist (500): include this device's checks */
addEventListener('DOMContentLoaded', () => { const lp0 = App.pages.launch; if (lp0) App.pages.launch = q => { const h = lp0(q), last = store.get('ds_checks_last', null), bad = last ? last.R.filter(r => r.ok === false).length : null;
  const row = `<li>${mk(last ? !bad : null)}<span class="tf"></span><div><b>This device's checks pass</b><p>${last ? `${bad} failing, run ${hmIST(new Date(last.at))}` : 'run them on System health'} · <a href="#/health">System health</a></p></div></li>`;
  return h.replace(/<\/ul>/, row + '</ul>'); }; });          // ux2.js (loaded later) defines the launch page
})();
