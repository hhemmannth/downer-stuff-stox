/* Scanner pages (swing first), tracked trades and the trade page. */
'use strict';
(function () {
const SC = App.scanner = {};
/* A swing setup your rules hold back (ran away, sector falling, under 2R room, ...) stays listed with its reason but is not counted as actionable. */
SC.held = s => (s.holds || []).length > 0 || String(s.status || '').startsWith('WATCH');
const STG_V2 = { 5: ['Entry', '1H closed above the 9 EMA on volume: take it if the checklist is clean'], 4: ['1H confirmed', 'entry window passed: wait for a new pullback'] };       // your updated rule (the 1H reclaim is the entry); swing.json says playbook v2
const STG = { 5: ['Entry', '15m trigger fired: take it if the checklist is clean'], 4: ['1H confirmed', 'wait for the 15m precision entry'], 3: ['In zone', 'wait for the 1H confirmation'], 2: ['Set alert', 'BOS done: wait for the pullback'], 1: ['Developing', 'CHoCH only: wait for the BOS'] };
const stCls = it => it.status.startsWith('WATCH') ? 'hold' : 's' + (it.stage || (it.status === 'TRIGGERED' ? 5 : it.status.startsWith('WATCH') ? 3 : 2));
const key = (sec, it) => `${sec}|${it.symbol}|${it.direction}|${it.bos_date}`;
const dec = it => it.section === 'options' ? 1 : 2;
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const toLbl = s => { if (!s || s.length < 16) return s; return `${s.slice(8, 10)} ${MON[+s.slice(5, 7) - 1]} ${s.slice(11, 16)}`; };
const outcomeTxt = { TARGET: 'Target hit', TRAIL: 'Trailing stop', SL: 'Stopped out', EXPIRED: 'Squared off / expired' };
const nextT = s => { const lv = [['T1', s.t1], ['T2', s.t2], ['T3', s.t3]].sort((a, b) => s.direction === 'long' ? a[1] - b[1] : b[1] - a[1]); return lv.find(x => !(s.hits || {})[x[0]]) || lv[2]; };
const sigStatus = s => s.status === 'CLOSED' ? (outcomeTxt[s.outcome] || 'Closed') : (Object.keys(s.hits || {}).length ? `${Object.keys(s.hits).join(' + ')} hit · stop ${fmt(s.stop, s.section === 'options' ? 1 : 2)}` : 'Open · waiting for T1');
SC.sigStatus = sigStatus;

/* ---------- setup card ---------- */
/* "I took this" on any card, held back or not, so nothing you act on disappears from your sight (item 22) */
document.addEventListener('click', e => { const b = e.target.closest && e.target.closest('[data-took]'); if (!b) return; e.preventDefault(); e.stopPropagation();
  const [sec, sym, dir] = b.dataset.took.split('|'), it = ((App.data[sec] || {}).setups || []).find(x => x.symbol === sym && x.direction === dir); if (!it) return;
  const pre = App.journal.fromScanner(it, App.LED(sec).signals.find(x => x.id === key(sec, it) && x.status === 'ACTIVE'));
  if ((it.holds || []).length || it.stage < 5) pre.note = (pre.note || '') + ` | taken at stage ${it.stage || '-'}${(it.holds || []).length ? ' while held back (' + it.holds.join(', ') + ')' : ''}`;
  App.journal.openForm(null, pre); }, true);
document.addEventListener('keydown', e => { if ((e.key === 'Enter' || e.key === ' ') && e.target.matches && e.target.matches('[data-took]')) e.target.click(); });
/* ---------- card helpers (batch 4) ---------- */
/* the one missing condition, in plain words (item 34) */
SC.nextStep = (sec, it) => {
  const st = String(it.status || ''), par = (st.match(/\(([^)]*)\)/) || [])[1] || '', v2 = ((App.data[sec] || {}).playbook === 'v2');
  if (st === 'TRIGGERED') return 'Triggered: manage it with the stop';
  if (sec === 'swing') {
    if ((it.holds || []).length) return 'Held back: ' + it.holds[0] + '. Wait until it clears';
    if (st.startsWith('WATCH')) return 'Trigger seen but not taken' + (par ? ': ' + par : '');
    const dz = SC.dist(it);
    return { 1: 'Waiting for the pullback to start', 2: 'Waiting for price to reach the zone' + (dz && dz.zone != null ? ` (${dz.zone.toFixed(1)}% away)` : ''), 3: v2 ? 'Needs a 1H close above the 9 EMA, volume above its 20-bar average' : 'Needs a 1H close above the 9 EMA on 1.5× volume', 4: 'Needs the 15m trigger candle', 5: 'Entry: take it if the checklist is clean' }[it.stage] || par || st;
  }
  if (st.startsWith('WATCH')) return 'Trigger seen but not taken' + (par ? ': ' + par : '');
  if (/IN ZONE/i.test(st)) return `Needs the 5m close ${it.direction === 'short' ? 'below' : 'above'} the 9 EMA on volume`;
  if (/APPROACH|SET ALERT/i.test(st)) return 'Waiting for the pullback into the FVG + OB';
  return par || st.split(' (')[0];
};
/* distance to the zone and the stop, in % and ATR (item 35) */
SC.dist = it => { const p = it.price, a = it.atr; if (!isNum(p)) return null; const long = it.direction !== 'short';
  const zone = isNum(it.zone_top) && isNum(it.zone_bot) ? (p > it.zone_top ? (p - it.zone_top) / p * 100 : p < it.zone_bot ? (it.zone_bot - p) / p * 100 : 0) * (long ? 1 : 1) : null;
  const za = isNum(a) && a > 0 && isNum(it.zone_top) ? (p > it.zone_top ? (p - it.zone_top) / a : p < it.zone_bot ? (it.zone_bot - p) / a : 0) : null;
  const stop = isNum(it.sl) ? Math.abs(p - it.sl) / p * 100 : null, sa = isNum(a) && a > 0 && isNum(it.sl) ? Math.abs(p - it.sl) / a : null; return { zone, za, stop, sa }; };
/* a thin bar: stop, entry and targets, with where price is now (item 85) */
SC.rBar = it => { if (!isNum(it.sl) || !isNum(it.entry) || !isNum(it.t1)) return ''; const top = isNum(it.t2) ? it.t2 : it.t1, lo = Math.min(it.sl, top), hi = Math.max(it.sl, top), span = hi - lo || 1, x = v => Math.max(0, Math.min(100, (v - lo) / span * 100)), flip = it.sl > top;
  const xe = x(it.entry), xt = x(it.t1), xp = isNum(it.price) ? x(it.price) : null, a = flip ? 100 - xe : xe;
  return `<div class="rbar" title="Stop ${fmt(it.sl)} · entry ${fmt(it.entry)} · T1 ${fmt(it.t1)}${isNum(it.t2) ? ' · T2 ' + fmt(it.t2) : ''}${xp != null ? ' · now ' + fmt(it.price) : ''}"><i class="rk" style="left:0;width:${a}%"></i><i class="rw" style="left:${a}%;width:${100 - a}%"></i><b style="left:${flip ? 100 - xt : xt}%"></b>${xp != null ? `<em style="left:${flip ? 100 - xp : xp}%"></em>` : ''}</div>`; };
SC.isNew = (sec, it) => { const seen = store.get('tji_seen_' + sec, null); return !!(seen && seen.st && it.stage >= 3 && seen.st[it.symbol] == null); };
function card(sec, it) {
  /* The condensed card: name and score, one status line, a thin chart, three levels, one footer line. Everything else (T2/T3, the full
     checklist, every caution) is on the trade page, one tap away. */
  const d = dec(it), hot = it.status === 'TRIGGERED', href = `#/trade?s=${sec}&id=${encodeURIComponent(it.symbol + '|' + it.direction)}`, tracked = App.LED(sec).signals.some(s => s.id === key(sec, it));
  const ot = it.options_trade, stage = it.stage, cautions = [...(it.holds || []).map(x => 'Held: ' + x), ...(it.notes || [])];
  const sub = sec === 'options' ? (ot ? `${esc(ot.instrument)} · Δ ${fmt(ot.delta)} · ₹${fmt(ot.premium)}` : 'Nifty 50 index') : [it.sector, it.rs_rank != null ? 'RS ' + it.rs_rank : ''].filter(Boolean).map(esc).join(' · ');
  const sp = it.spark || (it.candles ? it.candles.slice(-60).map(c => c[3]) : null), spark = sp && sp.length ? App.charts.spark(sp, { lo: it.zone_bot, hi: it.zone_top, sl: it.sl }) : '';
  const lv = it.entry != null ? [['e' + (hot || stage >= 5 ? '' : ' planned'), hot || stage >= 5 ? 'Entry' : 'Planned', it.entry], ['s', 'Stop', it.sl], ['t', 'T1', it.t1]] : [['', 'CHoCH', it.choch_level], ['', 'Price', it.price]];
  const tr = ((App.LED(sec).watch || {})[key(sec, it)] || {}).trail || [], prev = tr.length > 1 ? tr[tr.length - 2] : null, back = prev && prev.stage != null && it.stage != null && prev.stage > it.stage && (Date.now() - new Date(tr[tr.length - 1].at).getTime()) < 36e5 * 36;
  const moved = back ? `<span class="cau" title="Moved back on the ${esc(toLbl(String(tr[tr.length - 1].at).replace('T', ' ')))} scan: was ${esc(prev.status)}${prev.held ? ' (held back)' : ''}">↓ was ${esc((STG[prev.stage] || [prev.stage])[0])}${prev.held ? ' · held' : ''}</span>` : '';
  const ticks = (it.ticks || []).length, foot = [ticks ? `<span class="cf" title="${esc((it.ticks || []).join(', '))}">${'●'.repeat(ticks)}${'○'.repeat(Math.max(0, 3 - ticks))}<em>context</em></span>` : '',
    it.risk_pct != null ? `<span>risk ${fmt(it.risk_pct, 1)}%</span>` : '', tracked ? '<span class="trk">tracked</span>' : '', App.journal.findByTag(key(sec, it)) ? '<span class="trk">in journal</span>' : '',
    cautions.length ? `<span class="cau" title="${esc(cautions.join(' · '))}">⚠ ${cautions.length}</span>` : '', moved, SC.isNew(sec, it) ? '<span class="cau new">NEW</span>' : ''].filter(Boolean).join('');
  const dz = SC.dist(it), dline = dz ? [dz.zone != null ? (dz.zone === 0 ? 'in the zone' : `zone ${dz.zone.toFixed(1)}%${dz.za != null ? ' · ' + dz.za.toFixed(1) + ' ATR' : ''}`) : '', dz.stop != null ? `stop ${dz.stop.toFixed(1)}%${dz.sa != null ? ' · ' + dz.sa.toFixed(1) + ' ATR' : ''}` : ''].filter(Boolean).join(' · ') : '';
  const full = String(it.status || ''), held_ = sec === 'swing' && (it.holds || []).length;      // the card shows the stage; the full status is on hover and on the trade page
  const label = held_ ? 'HELD · ' + (it.holds || [])[0] : full.startsWith('WATCH') ? full.replace(/ \(/, ' · ').replace(/\)$/, '') : full.split(' (')[0];
  return `<a class="sc${hot ? ' hot' : ''} dir-${it.direction === 'short' ? 'short' : 'long'}${SC.isNew(sec, it) ? ' is-new' : ''}" href="${href}"><div class="sc-h"><div class="nm"><b>${esc(it.symbol)}${sec !== 'swing' ? ` <span class="tag ${it.direction}">${esc(it.label)}</span>` : ''}</b><small>${sub || '&nbsp;'}</small></div>
    <div class="sc-score" title="Score ${it.score}/10, grade ${esc(it.grade)}"><b>${it.score}</b><span class="g ${String(it.grade).replace('+', 'p').toLowerCase()}">${esc(it.grade)}</span></div></div>
    <div class="sc-st ${stCls(it)}" title="${esc(full)}"><i></i><span>${esc(label)}</span>${stage ? `<span class="dots${stage === 5 ? ' s5' : ''}" title="Playbook stage ${stage} of 5">${[1, 2, 3, 4, 5].map(k => `<b class="${k <= stage ? 'on' : ''}"></b>`).join('')}</span>` : ''}</div>
    <div class="sc-next" title="What is still needed">${esc(SC.nextStep(sec, it))}</div>
    ${spark}${SC.rBar(it)}<div class="sc-lv">${lv.map(([c, l, v]) => `<span class="${c}"><small>${l}</small><b>${fmt(v, d)}</b></span>`).join('')}</div>
    ${dline ? `<div class="sc-d">${dline}</div>` : ''}<div class="sc-f">${foot}<span class="sp"></span><span class="took" role="button" tabindex="0" data-took="${esc(sec + '|' + it.symbol + '|' + it.direction)}" title="Log this setup in your journal">I took this</span></div></a>`;
}

/* ---------- tracked trades (signals) ---------- */
/* Your own open journal trades for this section that the scanner is NOT following (taken from a held-back or planned setup, or logged by hand). A trade the scanner tracks is
   already in the table above it, so it is left out here. */
function mineOpen(sec) {
  const L = App.LED(sec), ids = L.signals.filter(s => s.status === 'ACTIVE').map(s => s.id);
  return ((App.journal && App.journal.openFor) ? App.journal.openFor(sec) : []).filter(t => !ids.some(id => (t.note || '').includes('DS:' + id)));
}
function mineCard(sec) {
  const M = mineOpen(sec); if (!M.length) return '';
  const d = sec === 'options' ? 1 : 2;
  return `<div class="card" style="margin-top:14px"><div class="hd"><h2>Your open trades in the journal</h2><span class="cap">${M.length} · not tracked by the scanner</span></div><div class="bd"><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Trade</th><th class="n">Entry</th><th class="n">Stop</th><th class="n">Target</th><th class="n">Last · R now</th></tr></thead><tbody>${M.map(t => { const lp = App.journal.livePx(t);
    return `<tr class="click" data-jopen="${esc(t.id)}"><td><b>${esc(t.inst)}</b> <span class="tag ${t.dir === 'Short' ? 'short' : 'long'}">${t.dir === 'Short' ? 'SHORT' : 'LONG'}</span><br><small class="muted">opened ${esc(t.d.slice(5))}${t.grade ? ' · ' + esc(t.grade) : ''} · from your journal</small></td><td class="n">${fmt(t.entry, d)}</td><td class="n">${fmt(t.sl, d)}</td><td class="n">${fmt(t.tgt, d)}</td><td class="n">${lp.txt}</td></tr>`; }).join('')}</tbody></table></div>
    <p class="help" style="margin-top:10px">These are trades you logged yourself, for example one you took from a held-back or planned setup. The scanner only follows a setup once it is TRIGGERED, so it does not follow these; your journal does. Tap a row to edit or close it.</p></div></div>`;
}
function ledgerView(sec, view) {
  const hq = String((App.ui.hq || {})[sec] || '').trim().toUpperCase(), mt = x => !hq || String(x.symbol || '').toUpperCase().includes(hq) || String(x.instrument || '').toUpperCase().includes(hq) || String(x.reason || '').toUpperCase().includes(hq);
  const L = App.LED(sec), act = L.signals.filter(s => s.status === 'ACTIVE'), clo = L.signals.filter(s => s.status === 'CLOSED' && mt(s)).sort((a, b) => (b.closed || '').localeCompare(a.closed || '')), drop = (L.dropped || []).filter(mt).slice().reverse();
  const row = s => { const closed = s.status === 'CLOSED', r = closed ? s.r_final : s.r_now, nt = nextT(s), d = sec === 'options' ? 1 : 2;
    return `<tr class="click" data-href="#/trade?s=${sec}&sig=${encodeURIComponent(s.id)}"><td><b>${esc(s.instrument || s.symbol)}</b> ${sec !== 'swing' ? `<span class="tag ${s.direction}">${esc(s.label)}</span>` : ''}<br><small class="muted">${closed ? 'closed ' + esc((s.closed || '').replace('T', ' ').slice(5, 16)) : 'since ' + esc((s.created || '').replace('T', ' ').slice(5, 16))} · ${esc(s.grade)} ${s.score}/10</small></td>
      <td><span class="st ${closed ? (r > 0 ? 's4' : 'closed') : 's3'}">${esc(sigStatus(s))}</span></td><td class="n">${fmt(s.entry, d)}</td><td class="n">${fmt(closed ? s.sl : s.stop, d)}</td><td class="n">${closed ? fmt(s.exit, d) : fmt(nt[1], d) + ' <small class="muted">' + nt[0] + '</small>'}</td><td class="n">${fmt(closed ? s.exit : s.last, d)}</td><td class="n ${cls(r)}"><b>${rr(r)}</b></td></tr>`; };
  const tbl = (rows, head) => `<div class="tbl-wrap"><table class="tbl"><thead><tr>${head.map((h, i) => `<th class="${i >= 2 ? 'n' : ''}">${h}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div>`;
  if (view === 'active') return (act.length || !mineOpen(sec).length ? `<div class="card"><div class="bd">${act.length ? tbl(act.map(row).join(''), ['Trade', 'Status', 'Entry', 'Stop now', 'Next target', 'Last', 'R now']) + `<p class="help" style="margin-top:10px">Every triggered setup is followed on closed candles until the final target, the stop or the trailing stop${sec === 'swing' ? ' (swing: no breakeven at T1, stop to entry at T2)' : ', or 15:15'}. Tap a row for its timeline.</p>` : App.ui.empty('No open trades', 'Triggered setups are followed here until they close.')}</div></div>` : '') + mineCard(sec);
  return `<div class="filters-sticky"><input id="hq" type="search" placeholder="Search past setups (symbol or reason)" value="${esc(hq)}" aria-label="Search past setups" style="flex:1;min-width:200px;max-width:420px"><small class="muted">${clo.length} closed · ${drop.length} invalidated${hq ? ' matching' : ''}</small></div>
    <div class="card"><div class="hd"><h2>Closed trades</h2></div><div class="bd">${clo.length ? tbl(clo.map(row).join(''), ['Trade', 'Outcome', 'Entry', 'Stop', 'Exit', 'Exit', 'Result']) : App.ui.empty('Nothing closed yet', '')}</div></div>
    <div class="card" style="margin-top:14px"><div class="hd"><h2>Invalidated before triggering</h2></div><div class="bd">${drop.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Setup</th><th>Reason</th><th class="n">Zone</th><th class="n">Plan entry</th><th class="n">When</th></tr></thead><tbody>${drop.map(w => `<tr class="click" data-href="#/trade?s=${sec}&id=${encodeURIComponent(w.symbol + '|' + w.direction)}"><td><b>${esc(w.symbol)}</b> <small class="muted">was ${esc(w.status || '')} · ${esc(w.grade || '')}</small></td><td style="white-space:normal;min-width:220px">${esc(w.reason || '')}</td><td class="n">${fmt(w.zone_bot)}–${fmt(w.zone_top)}</td><td class="n">${fmt(w.entry)}</td><td class="n">${esc((w.dropped || '').replace('T', ' ').slice(5, 16))}</td></tr>`).join('')}</tbody></table></div>` : App.ui.empty('None', 'Setups cancelled before triggering show here.')}</div></div>`;
}
const viewSeg = (sec, view) => { const L = App.LED(sec), a = L.signals.filter(s => s.status === 'ACTIVE').length + mineOpen(sec).length, c = L.signals.filter(s => s.status === 'CLOSED').length + (L.dropped || []).length;
  return App.ui.seg('view_' + sec, [['setups', 'Setups'], ['active', `Open trades ${a}`], ['closed', `Closed / invalidated ${c}`]], view); };
const fresh_ = d => { if (!d || !d.generated_at) return ''; const lim = d.mode === 'swing' ? 100 : 12, age = (Date.now() - new Date(d.generated_at)) / 6e4; if (!App.marketOpen()) return '<span class="pill fresh-q" title="Market closed: the last scan stands">market closed</span>';
  return age <= lim ? '<span class="pill ok fresh-q" title="Data is fresh">fresh</span>' : age <= lim * 3 ? `<span class="pill warn fresh-q" title="Expected every ${lim === 12 ? 5 : 60} min">late</span>` : '<a class="pill bad fresh-q" href="#/health" title="Open System health">stale</a>'; };
const meta = d => d ? `${fresh_(d)}<span class="pill info">${esc(dateIST(d.generated_at))} ${esc(hmIST(d.generated_at))} · ${esc(ago(d.generated_at))}</span>${d.fast_at ? `<span class="pill" title="Between the hourly scans the 1H-confirmed setups are re-checked for a 15m entry every 15 minutes">15m entries checked ${esc(hmIST(d.fast_at))}</span>` : ''}` : '';

/* ---------- swing ---------- */
const SU = () => App.ui.sw || (App.ui.sw = { view: 'setups', stage: 'all', grade: 'all', q: '' });
App.pages.swing = () => {
  const u = SU(), d = App.data.swing;
  let h = `<div class="ph"><div><h1>Swing scanner</h1><p>Nifty 500 · long only</p>${App.ui.flow((d || {}).playbook === 'v2' ? ['Weekly location', '1D CHoCH · BOS', 'FVG + OB · fib', '1H 9 EMA close · vol above 20-bar avg = entry'] : ['Weekly location', '1D CHoCH · BOS', 'FVG + OB · fib', '1H 9 EMA close · 1.5× vol', '15m entry'])}</div><span class="sp"></span>${meta(d)}</div>`;
  h += `<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px">${viewSeg('swing', u.view)}</div>`;
  if (u.view !== 'setups') return h + ledgerView('swing', u.view);
  if (!d) return h + `<div class="card"><div class="bd">${App.ui.loadingOr('No swing data yet', 'Scans run before the open, after each 1H close and after the close.')}</div></div>`;
  const S = d.setups, cnt = k => S.filter(s => s.stage === k && !SC.held(s)).length, nHeld = S.filter(s => s.stage >= 3 && SC.held(s)).length;
  /* the playbook as a node graph (desktop): the scanned universe as an orb, a filament to each stage, the counts on the stage cards and a summary
     panel. The stage cards are the same buttons as before (they filter the list); on a phone it falls back to the strip of five. */
  const ready = cnt(5) + cnt(4), inplay = [5, 4, 3, 2].reduce((n, k) => n + cnt(k), 0), act = ready, sel = String(u.stage), ys = [10, 30, 50, 70, 90];
  const links = [5, 4, 3, 2, 1].map((k, i) => `<path d="M0,50 C55,50 45,${ys[i]} 100,${ys[i]}" class="${sel === String(k) ? 'on' : ''}${k >= 4 && cnt(k) ? ' live' : ''}"/>`).join('');
  h += `<div class="hero-pipe" style="margin-bottom:14px"><div class="hp-orb"><canvas data-orb data-energy="${Math.min(1, (ready * 3 + inplay / 6) / 12).toFixed(2)}" data-lit="${S.length ? ((cnt(5) + cnt(4)) / S.length).toFixed(3) : 0},${S.length ? (cnt(3) / S.length).toFixed(3) : 0}" data-sectors="${esc(JSON.stringify((() => { const o = {}; S.filter(s => s.stage >= 2).forEach(s => { const k = s.sector || 'Other'; o[k] = (o[k] || 0) + 1; }); return Object.entries(o).sort((a, b) => b[1] - a[1]).slice(0, 8).map(x => x[0]); })()))}" title="Lit points: setups at 1H confirmed or entry (green) and in the zone. Tap a part of the sphere to filter by that sector."></canvas><div class="hp-cap"><b>Nifty 500</b><small>${d.scanned || ''} scanned</small></div></div>
    <svg class="hp-links" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">${links}</svg>
    <div class="pipeline hp-nodes">${[5, 4, 3, 2, 1].map(k => `<button class="pipe p${k}" type="button" data-stage="${k}" aria-pressed="${String(u.stage) === String(k)}"><div class="k">${k}. ${STG[k][0]}</div><div class="v">${cnt(k)}</div><div class="d">${(((d || {}).playbook === 'v2' && STG_V2[k]) || STG[k])[1]}</div></button>`).join('')}</div>
    <div class="hp-panel"><div class="hp-main"><div class="cap">Swing scan</div><div class="big">${ready}</div><div class="sub">ready: 1H confirmed or entry</div>
      <div class="hp-kv"><span>In play</span><b>${inplay}</b><span>Listed</span><b>${S.length}</b><span>Held back</span><b>${nHeld}</b><span>Full scan</span><b>${esc(hmIST(d.generated_at))}</b><span>15m entries</span><b>${d.fast_at ? esc(hmIST(d.fast_at)) : 'hourly'}</b></div></div>
      ${(() => { const P = S.filter(s => s.stage >= 2 && !SC.held(s)), sec = {}; P.forEach(s => { const k = s.sector || 'Other'; sec[k] = (sec[k] || 0) + 1; });         // what the in-play setups are made of
        const top = Object.entries(sec).sort((a, b) => b[1] - a[1]).slice(0, 4);
        return P.length ? `<div class="hp-ana"><div class="cap">Score mix · in play</div>${App.ui.minibars([['10', P.filter(s => s.score >= 10).length], ['9', P.filter(s => s.score === 9).length], ['8', P.filter(s => s.score === 8).length], ['7 or less', P.filter(s => s.score <= 7).length]], 'good')}
          <div class="cap" style="margin-top:14px">Leading sectors</div>${App.ui.minibars(top)}</div>` : ''; })()}</div></div>`;
  const short = S.filter(s => s.stage >= 3 && !(s.holds || []).length && !s.status.startsWith('WATCH')).sort((a, b) => b.stage - a.stage || b.score - a.score).slice(0, 5);
  if (short.length) { const ds = App.journal.dayStatus(), ap = short.filter(s => s.grade === 'A+'), rest = short.filter(s => s.grade !== 'A+'), lk = s => `<a href="#/trade?s=swing&id=${encodeURIComponent(s.symbol + '|long')}"><b>${esc(s.symbol)}</b></a> <small>${esc(STG[s.stage][0])} · ${esc(s.grade)} ${s.score}/10</small>`;
    h += `<details class="shortlist ${ds.blocked ? 'blocked' : ''}" ${store.get('ds_short_open', true) ? 'open' : ''}><summary><b>Today's shortlist</b> · ${ds.blocked ? `<span class="warn">daily limit reached (${esc(ds.why)}): these wait for tomorrow</span>` : `${ap.length} A+ · you can take ${ds.left} more today (A+ only)`}</summary>
      <div class="sl-body">${ap.length ? `<div>${ap.map(lk).join(' &nbsp;·&nbsp; ')}</div>` : '<div class="muted">No A+ setup in the shortlist.</div>'}${rest.length ? `<div class="muted" style="margin-top:6px">Watch only (not A+): ${rest.map(lk).join(' &nbsp;·&nbsp; ')}</div>` : ''}</div></details>`; }
  h += SC.sectorHeat(S);
  h += sinceStrip(S, 'swing');
  let L = S.filter(s => (u.stage === 'all' ? s.stage >= 2 : u.stage === 'held' ? s.stage >= 3 && SC.held(s) : s.stage === +u.stage && !SC.held(s)) && (u.grade === 'all' || (u.grade === 'A' ? ['A', 'A+'].includes(s.grade) : s.grade === 'A+')) && (!u.q || s.symbol.includes(u.q.toUpperCase()) || (s.sector || '').toLowerCase().includes(u.q.toLowerCase())));
  h += `<div class="filters-sticky">${App.ui.seg('swstage', [['all', 'All listed'], ...[5, 4, 3, 2, 1].map(k => [k, STG[k][0]]), ['held', 'Held back ' + nHeld]], u.stage)}${App.ui.seg('swgrade', [['all', 'Any grade'], ['A', 'A and A+'], ['A+', 'A+ only']], u.grade)}<input class="inp" style="width:180px" id="swQ" placeholder="Symbol or sector" value="${esc(u.q)}" aria-label="Filter">${(u.stage !== 'all' || u.grade !== 'all' || u.q) ? '<button class="btn sm ghost" type="button" id="swReset">Reset</button>' : ''}</div>`;
  L = L.slice().sort((a, b) => SC.held(a) - SC.held(b) || b.stage - a.stage || b.score - a.score);                // actionable first, held-back ones after them
  h += L.length ? `<div class="cards">${L.map(s => card('swing', s)).join('')}</div>` : `<div class="card"><div class="bd">${App.ui.empty('Nothing at this stage right now', u.stage === 'all' ? 'No stock is past the BOS with a pullback zone. Developing setups (CHoCH only) are in stage 1.' : u.stage === 'held' ? 'No setup is being held back by your rules right now.' : `Last full scan ${hmIST(d.generated_at)}. A setup is listed here the moment it reaches this stage.`)}</div></div>`;
  h += whyCard();
  h += `<p class="help" style="margin-top:12px">${d.scanned}/${d.universe} stocks scanned (${esc(d.note || '')}). Nifty ${d.nifty_trend ? 'is above' : 'is below'} its 21 EMA. Stages 1 and 2 never alert; only a 15m entry with a clean checklist does.</p>`;
  return h;
};
const WHY_TONE = { listed: 'good', score: 'warn', ranked: 'warn', weekly: 'warn' };
function whyCard() {
  const u = SU(), q = (u.why || '').trim().toUpperCase(), ex = App.lazyNow('explain');
  let out = '';
  if (q) {
    if (!ex) out = `<p class="help">Loading the scan details…</p>`;
    else { const row = ex.rows[q], near = row ? [] : Object.keys(ex.rows).filter(k => k.startsWith(q.slice(0, 3))).slice(0, 8);
      if (row) { const [stage, code, text, score, px, ind] = row;
        out = App.ui.callout(WHY_TONE[code] || 'bad', `<b>${esc(q)}</b>${ind ? ` <small class="muted">${esc(ind)}</small>` : ''}${px != null ? ` · last ${fmt(px)}` : ''}<br>${esc(text)}${code === 'listed' ? ` <a href="#/trade?s=swing&id=${encodeURIComponent(q + '|long')}">Open it</a>` : ''}`); }
      else out = App.ui.callout('info', `<b>${esc(q)}</b> is not in the Nifty 500 list this scan used.${near.length ? ` Did you mean ${near.map(k => `<a href="#" data-why="${k}">${k}</a>`).join(', ')}?` : ' Check the NSE symbol (for example, BANKBARODA, not Bank of Baroda).'}`); }
  }
  return `<div class="card" style="margin-top:14px"><div class="hd"><h2>Why isn't a stock here?</h2><span class="cap">every stock the scan checked, and the step where it stopped</span></div><div class="bd">
    <form id="whyF" style="display:flex;gap:8px;margin-bottom:${out ? 12 : 0}px"><input class="inp" id="whyQ" placeholder="NSE symbol, e.g. COFORGE" value="${esc(u.why || '')}" autocapitalize="characters" autocomplete="off" spellcheck="false" style="max-width:260px"><button class="btn" type="submit">Check</button></form>${out}</div></div>`;
}
App.binds.swing = () => {
  const u = SU(); bindView('swing', u);
  if (u.why && App.lazyAge('explain') > 60000) App.lazy('explain').then(() => App.soon('swing'));
  const f = $('#whyF'); if (f) { const go = v => { u.why = v; App.render(); App.lazy('explain').then(() => App.render()); };
    f.onsubmit = e => { e.preventDefault(); go($('#whyQ').value); }; $$('[data-why]').forEach(a => a.onclick = e => { e.preventDefault(); go(a.dataset.why); }); }
  const sb = $('#seenBtn'); if (sb) sb.onclick = () => { const d0 = App.data.swing; store.set('tji_seen_swing', { at: new Date().toISOString(), st: Object.fromEntries(((d0 || {}).setups || []).filter(x => x.stage >= 3).map(x => [x.symbol, x.stage * 10 + (SC.held(x) ? 1 : 0)])) }); App.render(); };
  $$('[data-stage]').forEach(b => b.onclick = () => { u.stage = String(u.stage) === b.dataset.stage ? 'all' : b.dataset.stage; App.render(); });
  $$('[data-seg="swstage"]').forEach(b => b.onclick = () => { u.stage = b.dataset.v; App.render(); });
  $$('[data-seg="swgrade"]').forEach(b => b.onclick = () => { u.grade = b.dataset.v; App.render(); });
  const rs = $('#swReset'); if (rs) rs.onclick = () => { u.stage = 'all'; u.grade = 'all'; u.q = ''; App.render(); };
  $$('details.shortlist').forEach(d => d.ontoggle = () => store.set('ds_short_open', d.open)); $$('details.sheat').forEach(d => d.ontoggle = () => store.set('ds_heat_open', d.open));
  $$('tr[data-sector]').forEach(tr => tr.onclick = () => { u.q = tr.dataset.sector; u.stage = 'all'; App.render(); });
  const q = $('#swQ'); if (q) { let t; q.oninput = () => { clearTimeout(t); t = setTimeout(() => { u.q = q.value; App.render(); const z = $('#swQ'); if (z) { z.focus(); z.setSelectionRange(z.value.length, z.value.length); } }, 250); }; }
};
function bindView(sec, u) { const hq = $('#hq'); if (hq) { let t; hq.oninput = () => { clearTimeout(t); t = setTimeout(() => { App.ui.hq = App.ui.hq || {}; App.ui.hq[sec] = hq.value; App.render(); const z = $('#hq'); if (z) { z.focus(); z.setSelectionRange(z.value.length, z.value.length); } }, 250); }; } $$(`[data-seg="view_${sec}"]`).forEach(b => b.onclick = () => { u.view = b.dataset.v; App.render(); }); $$('tr[data-href]').forEach(tr => tr.onclick = () => location.hash = tr.dataset.href); $$('tr[data-jopen]').forEach(tr => tr.onclick = () => App.journal.openForm(tr.dataset.jopen)); }

/* ---------- options ---------- */
const OU = () => App.ui.op || (App.ui.op = { view: 'setups' });
App.pages.options = () => {
  const u = OU(), d = App.data.options;
  let h = `<div class="ph"><div><h1>Nifty options</h1><p>Nifty · strike by delta and India VIX</p>${App.ui.flow((d || {}).playbook === 'v2' ? ['1H trend', '15m CHoCH + BOS', 'FVG + OB + fib pullback', '5m 9 EMA close'] : ['1H alignment', '15m bias', '5m CHoCH + BOS', 'FVG + OB pullback', '9 EMA close'])}</div><span class="sp"></span>${meta(d)}</div>
    <div style="margin-bottom:14px">${viewSeg('options', u.view)}</div>`;
  if (u.view !== 'setups') return h + ledgerView('options', u.view);
  if (!d) return h + `<div class="card"><div class="bd">${App.ui.loadingOr('No options data yet', 'Runs every 5 minutes during market hours.')}</div></div>`;
  const p = d.snapshot || {};
  /* four numbers that decide the trade (270); the rest one tap away */
  h += `<div class="kpis k4" style="margin-bottom:10px">${App.ui.kpi('Nifty', fmt(p.spot, 1), `${sg(p.change_pct)}% · VIX ${fmt(p.vix, 1)}`, cls(p.change_pct))}${App.ui.kpi('1H alignment', p.above_1h == null ? '-' : p.above_1h ? 'Above 9 EMA' : 'Below 9 EMA', p.above_1h == null ? '' : p.above_1h ? 'calls only' : 'puts only', p.above_1h ? 'good' : p.above_1h === false ? 'bad' : '')}
    ${App.ui.kpi('15m bias', p.bias_up ? 'Up (calls)' : p.bias_down ? 'Down (puts)' : 'None', p.bias_up || p.bias_down ? 'CHoCH intact' : 'no intact CHoCH', p.bias_up ? 'good' : p.bias_down ? 'bad' : '')}${App.ui.kpi('Losses today', p.losses_today || 0, p.losses_today >= 2 ? 'stop for the day' : 'stop after two', p.losses_today >= 2 ? 'bad' : '')}</div>
    <details class="more-kpi"><summary>More numbers</summary><div class="kv" style="margin-top:8px"><span>5m / 15m 9 EMA</span><b class="n">${fmt(p.ema_5m, 1)} / ${fmt(p.ema_15m, 1)} <small class="muted">price ${p.above_5m ? 'above' : 'below'} / ${p.above_15m ? 'above' : 'below'}</small></b><span>Prev day H / L</span><b class="n">${(p.pdh_pdl || []).map(x => fmt(x, 0)).join(' / ') || '-'}</b><span>Today</span><b class="n">${fmt(p.day_low, 0)}–${fmt(p.day_high, 0)}</b>${p.vix_pct != null ? `<span>VIX percentile</span><b>${p.vix_pct}</b>` : ''}<span>1H 9 EMA</span><b class="n">${fmt(p.ema_1h, 1)}</b></div></details>`;
  h += SC.nextCheck(d);
  if (p.expiry_afternoon) h += App.ui.callout('warn', '<b>Expiry afternoon:</b> your rule is to skip new option buys now.') + '<div style="height:10px"></div>';
  if (p.losses_today >= 2) h += App.ui.callout('bad', '<b>Two losing trades today:</b> your rule says stop for the day.') + '<div style="height:10px"></div>';
  /* call and put side by side, each with its five steps filling as they pass (269, 271, 42) and what it waits for (19) */
  const side = (nm, dir) => { const up = dir === 'long', st = d.setups.filter(x => x.direction === dir), best = st.sort((a, b) => (b.status === 'TRIGGERED') - (a.status === 'TRIGGERED') || b.score - a.score)[0], ss = String((best || {}).status || '');
    const steps = [['1H alignment', up ? p.above_1h === true : p.above_1h === false], ['15m bias', up ? !!p.bias_up : !!p.bias_down], ['5m CHoCH + BOS', !!best], ['FVG + OB pullback', !!best && /IN ZONE|TRIGGER|WATCH/i.test(ss)], ['9 EMA close', ss === 'TRIGGERED']];
    const n = steps.findIndex(x => !x[1]), done = n < 0 ? 5 : n;
    return `<div class="card side-card ${up ? 'call' : 'put'}"><div class="hd"><h2>${nm}</h2><span class="cap">${done} of 5 steps</span></div><div class="bd"><div class="steps5">${steps.map(([l, ok], k) => `<span class="${k < done ? 'ok' : k === done ? 'now' : ''}"><i></i>${esc(l)}</span>`).join('')}</div>
      <p class="help" style="margin-top:10px">${done === 5 ? '<b>Triggered.</b> Check the card below.' : `<b>Waiting for:</b> ${esc(steps[done][0])}${!best && (p.why_none || {})[nm] ? ' · ' + esc(p.why_none[nm]) : best ? ' · ' + esc(SC.nextStep('options', best)) : ''}`}</p>
      <small class="muted">checked ${esc(hmIST(d.generated_at))}</small></div></div>`; };
  h += `<div class="grid g2" style="margin-bottom:14px">${side('CALL', 'long')}${side('PUT', 'short')}</div>`;
  if (d.setups.length) h += `<div class="cards">${d.setups.map(s => card('options', s)).join('')}</div>`;
  h += SC.closedToday('options') + SC.nearMiss('options') + SC.replayCard();
  h += `<div style="margin-top:12px">${App.ui.chips([`Lot ${d.lot_size}`, 'Weekly expiry Tuesday', 'Premium stop = index points × delta', 'Size to your fixed risk', 'Not investment advice'])}</div>`;
  return h;
};
App.binds.options = () => { bindView('options', OU()); const r = $('#rpDay'); if (r) r.onchange = () => { App.ui.rp.day = r.value; App.ui.rp.open = true; App.render(); }; $$('details.replay').forEach(d => d.ontoggle = () => { App.ui.rp = App.ui.rp || {}; App.ui.rp.open = d.open; }); };

/* ---------- intraday ---------- */
const IU = () => App.ui.in || (App.ui.in = { view: 'setups', side: 'all' });
App.pages.intraday = () => {
  const u = IU(), d = App.data.intraday;
  let h = `<div class="ph"><div><h1>Intraday</h1><p>Liquid Nifty 500 · long and short · MIS, out by 15:10</p>${App.ui.flow((d || {}).playbook === 'v2' ? ['1H trend', '15m CHoCH + BOS', 'FVG + OB + fib pullback', '5m 9 EMA close · vol above 20-bar avg'] : ['15m CHoCH', '5m CHoCH + BOS', 'FVG + OB pullback', '9 EMA close · 1.5× vol'])}</div><span class="sp"></span>${meta(d)}</div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px">${viewSeg('intraday', u.view)}${u.view === 'setups' ? App.ui.seg('inside', [['all', 'Both'], ['long', 'Long'], ['short', 'Short']], u.side) : ''}</div>`;
  if (u.view !== 'setups') return h + ledgerView('intraday', u.view);
  if (!d) return h + `<div class="card"><div class="bd">${App.ui.loadingOr('No intraday data yet', 'Runs every 5 minutes during market hours.')}</div></div>`;
  const rs = App.journal.riskStatus(); if (rs.trades >= rs.S.maxIntra) h += App.ui.callout(rs.over ? 'bad' : 'warn', `<b>${rs.trades} trades today</b>: your base limit is ${rs.S.maxIntra}. Another one only if it is A+.`) + '<div style="height:10px"></div>';
  const L = d.setups.filter(s => u.side === 'all' || s.direction === u.side);
  h += SC.nextCheck(d);
  return h + (L.length ? `<div class="cards">${L.map(s => card('intraday', s)).join('')}</div>` : `<div class="card"><div class="bd">${App.ui.empty('No intraday setups right now', `Waiting for a 15m CHoCH, then a 5m CHoCH + BOS and a pullback into the FVG + OB. Last checked ${esc(hmIST(d.generated_at))}${d.scanned ? ' across ' + d.scanned + ' stocks' : ''}.`)}</div></div>`) + SC.closedToday('intraday') + SC.nearMiss('intraday') + `<p class="help" style="margin-top:12px">${esc(d.note || '')}</p>`;
};
App.binds.intraday = () => { const u = IU(); bindView('intraday', u); $$('[data-seg="inside"]').forEach(b => b.onclick = () => { u.side = b.dataset.v; App.render(); }); };

/* ---------- trade page ---------- */
function resolve(q) {
  const sec = q.get('s') || 'swing', d = App.data[sec], L = App.LED(sec); let it = null, sig = null, drop = null;
  if (q.get('sig')) { sig = L.signals.find(s => s.id === q.get('sig')) || null; it = sig && sig.item; }
  else { const [sym, dir] = (q.get('id') || '').split('|'); it = d && d.setups.find(s => s.symbol === sym && s.direction === dir);
    if (it) sig = L.signals.find(s => s.id === key(sec, it)) || null;
    else { sig = L.signals.filter(s => s.symbol === sym && s.direction === dir).sort((a, b) => (b.created || '').localeCompare(a.created || ''))[0] || null; it = sig && sig.item; if (!it) drop = (L.dropped || []).filter(w => w.symbol === sym && w.direction === dir).pop() || null; } }
  return { sec, it, sig, drop };
}
function chartSpec(it, tf, sig) {
  const z = [], lv = [], mk = [];
  const planned = !sig && it.status !== 'TRIGGERED', plan = [['Entry', it.entry, 'brand', 0, 3], ['SL', it.sl, 'bad', 0, 3], ['T1', it.t1, 'good', 1, 2], ['T2', it.t2, 'good', 1, 2], ['T3', it.t3, 'good', 1, 1]];
  if (sig && isNum(sig.stop) && sig.stop !== it.sl) plan.push(['Stop now', sig.stop, 'warn', 0, 3]);
  const hit = t => sig && sig.hits && sig.hits[t];
  if (tf === '1D' || tf === '5m') {
    if (isNum(it.ob_low)) z.push({ lo: it.ob_low, hi: it.ob_high, c: 'c1', label: 'OB', k: 2 });
    if (isNum(it.fvg_low)) z.push({ lo: it.fvg_low, hi: it.fvg_high, c: 'good', label: 'FVG', k: 2 });
    if (isNum(it.fib_lo)) z.push({ lo: it.fib_lo, hi: it.fib_hi, c: 'sun', label: 'Fib .618–.705', k: 1, scale: false });
    if (isNum(it.choch_level)) lv.push({ p: it.choch_level, c: 'ink3', dash: 1, label: 'CHoCH', k: 1 });
    if (isNum(it.bos_level)) lv.push({ p: it.bos_level, c: 'good', dash: 1, label: 'BOS', k: 1 });
    if (isNum(it.resistance)) lv.push({ p: it.resistance, c: 'warn', dash: 1, label: 'Resistance', k: 1, scale: false });
    if (it.sweep && it.sweep_date) mk.push({ t: it.sweep_date, p: it.sweep_low, label: 'Sweep', c: 'bad', below: true });
  } else if (tf === '1H') {
    z.push({ lo: it.zone_bot, hi: it.zone_top, c: 'brand', label: '1D zone', k: 2 }); if (isNum(it.fib_lo)) z.push({ lo: it.fib_lo, hi: it.fib_hi, c: 'sun', label: 'Fib', k: 1, scale: false });
    const h1 = it.h1 || {}; if (h1.t_touch) mk.push({ t: toLbl(h1.t_touch), p: it.pullback_low, label: 'Pullback', c: 'good', below: true }); if (h1.t_confirm) mk.push({ t: toLbl(h1.t_confirm), p: (((chartsOf(it) || {})['1H'] || { candles: [] }).candles[(((chartsOf(it) || {})['1H'] || { times: [] }).times || []).indexOf(toLbl(h1.t_confirm))] || [])[3], label: 'Confirm', c: 'good' });
  } else if (tf === '15m') {
    const m = it.m15 || {}; z.push({ lo: it.zone_bot, hi: it.zone_top, c: 'brand', label: '1D zone', k: 1, scale: false });
    if (m.fvg && isNum(m.fvg.low)) z.push({ lo: m.fvg.low, hi: m.fvg.high, c: 'good', label: '15m FVG', k: 2 }); if (m.ob && isNum(m.ob.low)) z.push({ lo: m.ob.low, hi: m.ob.high, c: 'c1', label: '15m OB', k: 2 });
    if (m.choch) lv.push({ p: m.choch.level, c: 'ink3', dash: 1, label: '15m CHoCH', k: 1 }); if (m.bos) lv.push({ p: m.bos.level, c: 'good', dash: 1, label: '15m BOS', k: 1 });
    if (m.trigger) mk.push({ t: toLbl(m.trigger), p: m.entry, label: 'Entry', c: 'brand' }); if (m.retest) mk.push({ t: toLbl(m.retest), p: m.fvg && m.fvg.high, label: 'Retest', c: 'good', below: true });
  }
  plan.forEach(([l, p, c, dash, k]) => { if (isNum(p) && (tf !== '15m' || l === 'Entry' || l === 'SL')) lv.push({ p, c, dash: l === 'Entry' && planned ? 1 : dash, label: (hit(l) ? '✓ ' : '') + (l === 'Entry' && planned ? 'Planned entry' : l), k, w: l === 'Entry' || l === 'SL' ? 1.6 : 1.1, scale: tf === '15m' ? l === 'Entry' : l !== 'T3' && l !== 'T2' }); });
  /* clean/full filtering now happens in the chart itself (App.charts.pref) */       // 'Key levels only': drop the minor ones (fib, CHoCH, BOS, T3...), keep zone, entry, stop, T1, T2
  return { zones: z, levels: lv, marks: mk };
}
/* Everything the rebuilt chart can show beyond the plan levels (batch 3): your own trade (32, 120), how earlier setups in this zone ended (119),
   your alerts and notes (166, 167), the trigger candle (106), stage changes (107), results and news dates (170), the weekly trend and sector ribbons
   (126, 127), the Nifty trend (176), the daily-limit note (169), the stop's swing (168) and a late-data tint (180). */
function chartExtras(it, tf, sig, data, s) {
  const sec = it.section || 'swing', T = data.times || [], o = { id: `${sec}:${it.symbol}:${it.direction}:${tf}`, zoomGroup: `${sec}:${it.symbol}`, entryRef: { entry: sig && isNum(sig.entry) ? sig.entry : it.entry, sl: it.sl, t1: it.t1 } };
  o.head = `${it.symbol} ${tf} · ${it.grade || ''} · entry ${fmt(it.entry, dec(it))} · stop ${fmt(it.sl, dec(it))} · T1 ${fmt(it.t1, dec(it))}`;
  o.frame = { title: `${it.symbol} · ${tf} · ${it.grade || ''} ${it.score != null ? it.score + '/10' : ''}`, sub: `${String(it.status || '').slice(0, 60)} · ${dateIST(new Date())}` };
  const h1 = it.h1 || {}, m = it.m15 || {}, tt = tf === '1H' ? h1.t_confirm : tf === '15m' ? m.trigger : tf === '5m' ? (sig && sig.created) : null;
  if (tt) o.trigger = { t: toLbl(String(tt).replace('T', ' ').slice(0, 16)) };
  const tr = ((App.LED(sec).watch || {})[key(sec, it)] || {}).trail || [];
  o.stageMarks = tr.slice(1).map(x => { const t = String(x.at || '').replace('T', ' ').slice(0, 16); const lab = tf === '1D' ? t.slice(0, 10) : toLbl(t); const i = T.findIndex(v => String(v) >= lab); return i >= 0 ? { t: T[i], label: `Stage ${x.stage}: ${x.status}` } : null; }).filter(Boolean);
  const ev = []; if (it.results && it.results.date) ev.push({ t: tf === '1D' ? it.results.date : toLbl(it.results.date + ' 09:15').slice(0, 6), label: 'Results ' + it.results.date, c: 'warn' });
  (((App.data.news || {}).by_symbol || {})[it.symbol] || []).slice(0, 6).forEach(n => { const dd = String(n.date || n.published || '').slice(0, 10); if (dd) ev.push({ t: tf === '1D' ? dd : toLbl(dd + ' 09:15').slice(0, 6), label: (n.title || 'News').slice(0, 90) }); });
  o.events = ev;
  if (sec === 'swing') { o.ribbons = []; if (it.weekly) o.ribbons.push({ c: it.weekly.up ? 'good' : 'bad', t: it.weekly.text || (it.weekly.up ? 'Weekly trend up' : 'Weekly trend not up') }); if (it.sector_state) o.ribbons.push({ c: it.sector_state === 'strong' ? 'good' : it.sector_state === 'weak' ? 'warn' : 'ink3', t: 'Sector ' + it.sector_state + (it.index_check && it.index_check.sector_index ? ' (' + it.index_check.sector_index + ')' : '') }); }
  const ot = it.options_trade; if (ot) { o.corner = `${ot.instrument} · Δ ${fmt(ot.delta)} · premium ₹${fmt(ot.premium)} · lot ${ot.lot_size || (App.data.options || {}).lot_size || 65} · Nifty ${fmt(it.price, 1)}`; o.head = `${ot.instrument} on Nifty ${tf} · premium ₹${fmt(ot.premium)} · stop ₹${fmt(ot.premium_sl)} · Δ ${fmt(ot.delta)}`; }
  else { const sw = App.data.swing; if (sw && sw.nifty_trend != null) o.corner = 'Nifty ' + (sw.nifty_trend ? '↑ above' : '↓ below') + ' its 21 EMA'; }
  const ds = App.journal && App.journal.dayStatus ? App.journal.dayStatus() : null; if (ds && ds.blocked && !sig) o.block = 'Daily limit reached: no new entry today';
  const age = data && T.length ? null : null; const gen = (App.data[sec] || {}).generated_at; if (gen && App.marketOpen() && (Date.now() - new Date(gen)) / 6e4 > (sec === 'swing' ? 100 : 12)) o.stale = true;
  /* your own trades in this symbol (32, 120) */
  if (App.journal) App.journal.enrich().filter(t => t.inst === it.symbol).slice(-2).forEach(t => {
    s.levels.push({ p: t.entry, c: 'c2', dash: 1, label: 'My entry', k: 2, w: 1, scale: false }); if (isNum(t.sl)) s.levels.push({ p: t.sl, c: 'c2', dash: 1, label: 'My stop', k: 2, w: 1, scale: false });
    if (isNum(t.exit)) s.levels.push({ p: t.exit, c: t.exit >= t.entry === (t.dir !== 'Short') ? 'good' : 'bad', dash: 1, label: 'My exit', k: 2, w: 1, scale: false });
    const di = T.findIndex(v => String(v).startsWith(tf === '1D' ? t.d : toLbl(t.d + ' ' + (t.tm || '09:15')).slice(0, 6))); if (di >= 0) s.marks.push({ i: di + (data.candles.length - T.length), p: t.entry, label: 'You', c: 'c2', below: t.dir !== 'Short' });
  });
  /* earlier setups in the same zone (119) */
  const L = App.LED(sec); (L.signals || []).filter(x => x.symbol === it.symbol && x.status === 'CLOSED' && isNum(x.entry) && x.entry >= (it.zone_bot || -1e9) * .98 && x.entry <= (it.zone_top || 1e9) * 1.02).slice(-3).forEach(x => {
    const di = T.findIndex(v => String(v) >= String(x.created || '').slice(0, tf === '1D' ? 10 : 16).replace('T', ' ')); if (di >= 0) s.marks.push({ i: di, p: x.entry, label: (x.r_final >= 0 ? '+' : '') + (x.r_final || 0).toFixed(1) + 'R before', c: x.r_final >= 0 ? 'good' : 'bad', below: true }); });
  /* previous-day high and low on intraday charts, last completed week's high and low on the daily chart: optional, shown in Full view (114) */
  const day = t => String(t).slice(0, 6), Cs = data.candles || [];
  if (tf !== '1D' && T.length) { const days = [...new Set(T.map(day))]; if (days.length > 1) { const pd = days[days.length - 2], ix = T.map((t, i) => day(t) === pd ? i : -1).filter(i => i >= 0); if (ix.length) { s.levels.push({ p: Math.max(...ix.map(i => Cs[i + (Cs.length - T.length)][1])), c: 'ink3', dash: 1, label: 'PDH', k: 1, scale: false }); s.levels.push({ p: Math.min(...ix.map(i => Cs[i + (Cs.length - T.length)][2])), c: 'ink3', dash: 1, label: 'PDL', k: 1, scale: false }); } } }
  if (tf === '1D' && T.length > 10) { const wk = t => { const d = new Date(String(t).slice(0, 10) + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7)); return d.toISOString().slice(0, 10); }, ws = [...new Set(T.map(wk))]; if (ws.length > 1) { const pw = ws[ws.length - 2], ix = T.map((t, i) => wk(t) === pw ? i : -1).filter(i => i >= 0), off0 = Cs.length - T.length; s.levels.push({ p: Math.max(...ix.map(i => Cs[i + off0][1])), c: 'ink3', dash: 1, label: 'Week H', k: 1, scale: false }); s.levels.push({ p: Math.min(...ix.map(i => Cs[i + off0][2])), c: 'ink3', dash: 1, label: 'Week L', k: 1, scale: false }); } }
  /* the swing the stop sits beyond (168) */
  const sref = it.sweep_low || it.pullback_low; if (isNum(sref) && tf === '1D' && !s.levels.some(l => Math.abs(l.p - sref) < 1e-6)) s.levels.push({ p: sref, c: 'ink3', dash: 1, label: 'Swing low', k: 1, scale: false, why: 'The swing low the stop sits beyond. If it breaks, the structure is gone.' });
  /* alerts and notes you pinned (166, 167) */
  if (App.journal && App.journal.lvxFor) { const X = App.journal.lvxFor(it.symbol); X.alerts.forEach(a => s.levels.push({ p: a.p, c: 'sun', dash: 1, label: 'Alert', k: 2, w: 1, scale: false })); X.notes.forEach(n => s.levels.push({ p: n.p, c: 'ink3', dash: 1, label: 'Note', k: 2, w: 1, scale: false, why: n.text })); }
  o.onAlert = p => { App.journal.addAlert(it.symbol, p, it.price); App.toast(`Alert set at ${fmt(p, dec(it))}. It fires while the app is open.`); App.render(); };
  o.onNote = p => { const t = prompt(`Note at ${fmt(p, dec(it))}`); if (t) { App.journal.addNote(it.symbol, p, t); App.render(); } };
  return o;
}
function chartsOf(it) {
  if (it.charts) return it.charts;
  if (it.section === 'swing' && it.tfs) { const all = App.lazyNow('swing_charts'); return all && all.charts ? all.charts[it.symbol] || null : null; }
  return { [it.tf_structure || '5m']: { times: it.times, candles: it.candles, ema: it.ema } };
}
function chartFor(it, tf, sig, W) {
  const ch = chartsOf(it);
  if (!ch) return `<div class="empty" style="min-height:220px"><b>Loading the chart…</b></div>`;
  if (!ch[tf]) return App.ui.empty('Chart not available', 'This timeframe was not in the last swing scan. It refreshes at the next hourly scan.');
  const data = ch[tf], s = chartSpec(it, tf, sig);
  return App.charts.candles(data, Object.assign({ W, levels: s.levels, zones: s.zones, marks: s.marks, label: `${it.symbol} ${tf} chart` }, chartExtras(it, tf, sig, data, s)));
}
function checklistCard(it) {
  if (!it.checklist) return '';
  const mk = ok => ok === true ? '<span class="mk y">✓</span>' : ok === false ? '<span class="mk n">✗</span>' : '<span class="mk q">?</span>';
  const done = it.checklist.filter(c => c.ok === true).length;
  return `<div class="card"><div class="hd"><h2>Playbook checklist</h2><span class="cap">${done} of ${it.checklist.length} ticked · ? = check yourself</span></div><div class="bd"><ul class="checks">${it.checklist.map((c, i) => `<li class="${i === it.checklist.findIndex(x => x.ok === false) ? 'next' : ''}">${mk(c.ok)}<span class="tf">${esc(c.tf)}</span><div><b>${esc(c.title)}</b><p>${esc(c.text)}</p></div></li>`).join('')}</ul></div></div>`;
}
function scoreCard(it) {
  const parts = [['Structure', it.structure, 2], ['Zone', it.zone_q, 2], ['Confirmation', it.confirm, 3], ['Context', it.context, 3]];
  return `<div class="card"><div class="hd"><h2>Scorecard</h2><span class="sp"></span>${App.ui.grade(it.grade)}<b style="font:750 18px var(--disp)">${it.score}/10</b></div><div class="bd"><div class="scorebars">${parts.map(([l, v, m]) => `<div class="sbar"><span>${l}</span><span class="tr"><i style="width:${100 * v / m}%"></i></span><b>${v}/${m}</b></div>`).join('')}</div>
    <div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:10px">${(it.ticks || []).map(t => `<span class="tick">✓ ${esc(t)}</span>`).join('') || '<span class="muted">No confluence ticks</span>'}</div><p class="help" style="margin-top:8px">A+ 8–10 · A 6–7 · B 4–5 observe · under 4 no trade.</p></div></div>`;
}
function planCard(it) {
  const d = dec(it), risk = isNum(it.entry) && isNum(it.sl) ? Math.abs(it.entry - it.sl) : null, R = p => risk ? Math.abs(p - it.entry) / risk : null, p = it.plan || {};
  const planned = it.status !== 'TRIGGERED', lvls = [[planned ? 'Planned entry' : 'Entry', it.entry, 'brand'], ['Stop-loss', it.sl, 'bad'], ['T1', it.t1, 'good'], ['T2', it.t2, 'good'], ['T3', it.t3, 'good']].filter(x => isNum(x[1]));
  const trail = (p.trail || []).map(t => typeof t === 'string' ? t : `<b>${esc(t.when)}:</b> ${esc(t.action)}`);
  return `<div class="card${planned ? ' planned-card' : ''}"><div class="hd"><h2>${planned ? 'Trade plan (planned, not triggered)' : 'Trade plan'}</h2>${it.risk_pct != null ? `<span class="cap">risk ${it.risk_pct.toFixed(2)}% of price</span>` : ''}</div><div class="bd">
    ${planned ? `<p class="help" style="margin:0 0 10px"><b>Planned entry, not a signal.</b> This is where the plan puts the entry inside the zone, so the stop and targets can be sized. It is not a trigger and price does not have to reach it. The trade only starts when the status turns <b>TRIGGERED</b> (${it.section === 'swing' ? 'a 1H close above the 9 EMA on volume, then the 15m entry' : 'the 5m trigger candle closing above the 9 EMA on volume'}).</p>` : ''}
    <table class="tbl"><tbody>${lvls.map(([l, v, c], i) => `<tr${i === 0 && planned ? ' class="planned"' : ''}><td><b class="${c === 'bad' ? 'bad' : c === 'good' ? 'good' : 'brand'}">${l}</b></td><td class="n"><b>${fmt(v, d)}</b></td><td class="n muted">${i === 0 ? '' : i === 1 ? '−1R · ' + fmt(risk, d) + ' pts' : (R(v) || 0).toFixed(1) + 'R'}</td></tr>`).join('')}</tbody></table>
    ${(p.execution || []).length ? `<div class="fsec" style="margin-top:14px">Execution</div><ol class="steps">${p.execution.map(x => `<li>${typeof x === 'string' ? esc(x) : esc(x.action || '')}</li>`).join('')}</ol>` : ''}
    ${trail.length ? `<div class="fsec">Managing it</div><ol class="steps">${trail.map(x => `<li>${typeof x === 'string' && !x.startsWith('<b>') ? esc(x) : x}</li>`).join('')}</ol>` : ''}</div></div>`;
}
/* Item 11: are the candidates and open trades really one bet? Sector clusters and correlated pairs from the scan, plus your open journal trades. */
SC.heat = function (d) {
  const ht = d && d.heat; if (!ht) return '';
  const map = (App.lazyNow('sectors') || {}).map || {}, open = App.journal.enrich().filter(t => t.open), mine = {};
  open.forEach(t => { const sec = map[(t.inst || '').toUpperCase()]; if (sec) (mine[sec] = mine[sec] || []).push(t.inst.toUpperCase()); });
  const lines = [];
  (ht.clusters || []).forEach(c => lines.push(`<b>${esc(c.sector)}</b>: ${c.n} candidates or tracked trades (${c.symbols.map(esc).join(', ')}). Taking several is one sector bet: pick the best one or split your risk.`));
  Object.entries(mine).forEach(([sec, v]) => { const also = (d.setups || []).filter(s => s.stage >= 3 && s.sector === sec && !v.includes(s.symbol)).map(s => s.symbol);
    if (also.length) lines.push(`You already hold <b>${v.map(esc).join(', ')}</b> in ${esc(sec)}; ${also.map(esc).join(', ')} ${also.length > 1 ? 'are' : 'is'} in the same sector.`); });
  (ht.pairs || []).slice(0, 4).forEach(p => lines.push(`<b>${esc(p.a)}</b> and <b>${esc(p.b)}</b> have moved together (correlation ${p.corr.toFixed(2)} over 60 sessions): treat them as one position for risk.`));
  if (!lines.length) return '';
  return `<div class="card" style="margin-bottom:14px"><div class="hd"><h2>Portfolio heat</h2><span class="cap">are these separate bets?</span></div><div class="bd"><ul class="ins">${lines.map(l => `<li class="warn"><i></i><span>${l}</span></li>`).join('')}</ul></div></div>`;
};

/* Item 20: a ready-to-copy order ticket (you place the order yourself), and item 17: the levels as a TradingView Pine script. */
function ticketText(it) {
  const ot = it.options_trade, sz = App.journal.sizeFor(ot ? ot.premium : it.entry, ot ? ot.premium_sl : it.sl, it.grade), d = dec(it);
  let qty = sz.qty; if (ot) { const lot = ot.lot_size || 65, per = Math.max(ot.premium - ot.premium_sl, .01); qty = Math.max(1, Math.floor(sz.risk / (per * lot))) * lot; }
  const L = ot ? [`BUY ${ot.instrument}`, `Quantity: ${qty} (${qty / (ot.lot_size || 65)} lot${qty / (ot.lot_size || 65) > 1 ? 's' : ''})`, `Entry (limit): around ${fmt(ot.live && ot.live.ltp ? ot.live.ltp : ot.premium)} premium`, `Stop-loss (SL-M): ${fmt(ot.premium_sl)} premium`, `Targets: ${(ot.premium_targets || []).map(x => fmt(x)).join(' / ')}`, `Index levels: entry ${fmt(it.entry, d)}, stop ${fmt(it.sl, d)}`, 'Product: MIS, square off by 15:10']
    : [`${it.direction === 'long' ? 'BUY' : 'SELL'} ${it.symbol}`, `Quantity: ${qty}`, `Entry: ${fmt(it.entry, d)}`, `Stop-loss (SL-M): ${fmt(it.sl, d)}`, `T1 ${fmt(it.t1, d)} (book half) · T2 ${fmt(it.t2, d)} (book a quarter, stop to entry) · T3 ${fmt(it.t3, d)}`, `Product: ${it.section === 'intraday' ? 'MIS, square off by 15:10' : 'CNC (delivery)'}`];
  L.push(`Risk: ${inr(sz.risk)} (${pct(sz.rp, 2)} of capital) · ${it.grade} ${it.score}/10`);
  return L.join('\n');
}
function pineText(it) {
  const d = dec(it), n = v => (+v).toFixed(d), L = ['//@version=5', `indicator("DownerStuff ${it.symbol} levels", overlay=true)`];
  if (isNum(it.zone_bot) && isNum(it.zone_top)) L.push(`zb = hline(${n(it.zone_bot)}, "Zone low", color=color.gray, linestyle=hline.style_dotted)`, `zt = hline(${n(it.zone_top)}, "Zone high", color=color.gray, linestyle=hline.style_dotted)`, 'fill(zb, zt, color=color.new(color.gray, 88))');
  [['entry', 'Entry', 'color.black', 'hline.style_solid'], ['sl', 'Stop', 'color.red', 'hline.style_dashed'], ['t1', 'T1', 'color.green', 'hline.style_dashed'], ['t2', 'T2', 'color.green', 'hline.style_dashed'], ['t3', 'T3', 'color.green', 'hline.style_dotted']]
    .forEach(([k, name, c, st]) => { if (isNum(it[k])) L.push(`hline(${n(it[k])}, "${name}", color=${c}, linestyle=${st}, linewidth=${k === 'entry' || k === 'sl' ? 2 : 1})`); });
  return L.join('\n');
}
/* Pre-trade check: a compact badge in the corner of the order ticket. Portfolio heat for THIS symbol (its sector cluster, what you already hold
   in that sector, stocks that move with it) and your daily rule (a strict 2 trades a day). Review it before you place the order. */
SC.preCheck = function (it, sec) {
  const d = App.data.swing || {}, ht = d.heat || {}, map = (App.lazyNow('sectors') || {}).map || {}, sym = (it.symbol || '').toUpperCase(), sector = it.sector || map[sym] || '';
  const lines = [], rs = App.journal.riskStatus(); let lvl = 'ok';
  const warn = (m, bad) => { lines.push([bad ? 'bad' : 'warn', m]); lvl = bad || lvl === 'bad' ? 'bad' : 'warn'; };
  if (rs.trades >= rs.S.maxIntra) warn(`${rs.trades} trades today: your limit is ${rs.S.maxIntra} a day, strict. Skip it, even an A+ waits for tomorrow.`, true);
  else lines.push(['good', `${rs.trades} of ${rs.S.maxIntra} trades today.`]);
  if (it.grade !== 'A+') warn(`Grade ${esc(it.grade || '-')} ${it.score}/10: your backtests count A+ only (8 to 10).`);
  if (sec === 'swing' || sec === 'positional') {
    const cl = (ht.clusters || []).find(c => c.sector === sector && (c.symbols || []).length);
    if (cl) { const others = cl.symbols.filter(x => x !== sym); if (others.length) warn(`<b>${esc(sector)}</b>: ${cl.n} candidates or tracked trades (${others.map(esc).join(', ')} besides this one). Several of them are one sector bet: pick the best or split your risk.`); }
    const held = App.journal.enrich().filter(t => t.open && map[(t.inst || '').toUpperCase()] === sector && (t.inst || '').toUpperCase() !== sym).map(t => t.inst.toUpperCase());
    if (sector && held.length) warn(`You already hold <b>${held.map(esc).join(', ')}</b> in ${esc(sector)}.`);
    (ht.pairs || []).filter(p => p.a === sym || p.b === sym).slice(0, 3).forEach(p => warn(`Moves with <b>${esc(p.a === sym ? p.b : p.a)}</b> (correlation ${p.corr.toFixed(2)} over 60 sessions): treat them as one position for risk.`));
    if (lvl === 'ok' || !lines.some(l => l[0] !== 'good')) lines.push(['good', sector ? `No crowding in ${esc(sector)} and no correlated pair.` : 'No sector crowding found.']);
  }
  if (rs.openRisk > rs.S.openMax * 0.75) warn(`Open risk is ${pct(rs.openRisk, 2)} of your ${pct(rs.S.openMax, 1)} cap: this trade may not fit.`, rs.openRisk >= rs.S.openMax);
  const label = lvl === 'ok' ? 'Pre-trade check: clear' : lvl === 'bad' ? 'Pre-trade check: stop' : `Pre-trade check: ${lines.filter(l => l[0] === 'warn').length} to review`;
  return `<details class="precheck"><summary class="pill ${lvl === 'ok' ? 'ok' : lvl}" title="Review before placing the order"><i></i>${label}</summary><div class="precheck-pop"><b>Before you place it</b><ul class="ins">${lines.map(([k, m]) => `<li class="${k}"><i></i><span>${m}</span></li>`).join('')}</ul></div></details>`;
};
function ticketCard(it, sec) {
  if (!isNum(it.entry) || !isNum(it.sl)) return '';
  return `<div class="card"><div class="hd"><h2>Order ticket</h2><span class="cap">you place it yourself</span><span class="sp"></span>${SC.preCheck(it, sec || it.section)}</div><div class="bd"><pre class="ticket" id="tkt">${esc(ticketText(it))}</pre>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px"><button class="btn sm" type="button" id="tktCopy">Copy ticket</button><button class="btn sm" type="button" id="pineCopy">Copy TradingView levels (Pine)</button></div>
    <p class="help" style="margin-top:8px">The quantity uses your capital and risk per trade from Settings. For TradingView: open the Pine Editor, paste, and click Add to chart.</p></div></div>`;
}
function copyText(t, okMsg) { const done = () => App.toast(okMsg);
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done, () => App.toast('Could not copy: select the text and copy it'));
  else { const a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); try { document.execCommand('copy'); done(); } catch (e) { App.toast('Could not copy'); } a.remove(); } }
SC.copyText = copyText;

function sizeCard(it) {
  const ot = it.options_trade; if (!isNum(it.entry) || !isNum(it.sl)) return '';
  const sz = App.journal.sizeFor(ot ? ot.premium : it.entry, ot ? ot.premium_sl : it.sl, it.grade);
  let body;
  if (ot) { const lot = ot.lot_size || 65, per = Math.max(ot.premium - ot.premium_sl, .01), lots = Math.max(0, Math.floor(sz.risk / (per * lot)));
    body = `<div class="kv"><span>Risk budget (${pct(sz.rp, 2)})</span><b>${inr(sz.risk)}</b><span>Premium stop distance</span><b>₹${fmt(per)} × ${lot}</b><span>Lots</span><b>${lots} (${lots * lot} qty)</b><span>Premium outlay</span><b>${inr(lots * lot * ot.premium)}</b></div>`; }
  else body = `<div class="kv"><span>Capital</span><b>${inr(sz.capital)}</b><span>Risk budget (${pct(sz.rp, 2)}${it.grade === 'A+' ? ', A+' : ''})</span><b>${inr(sz.risk)}</b><span>Stop distance</span><b>${fmt(Math.abs(it.entry - it.sl))}</b><span>Quantity</span><b>${fmt0(sz.qty)}</b><span>Position value</span><b>${inr(sz.qty * it.entry)}</b></div>`;
  return `<div class="card"><div class="hd"><h2>Position size</h2><span class="cap">from your journal settings</span></div><div class="bd">${body}<p class="help" style="margin-top:8px">Structure → stop → size. Never widen the stop to fit a bigger size. Change capital and risk in Settings.</p></div></div>`;
}
function optionCard(it) {
  const o = it.options_trade; if (!o) return '';
  const L = o.live, spr = L && L.bid && L.ask ? (L.ask - L.bid) / ((L.ask + L.bid) / 2) * 100 : null, liveAny = (o.candidates || []).some(c => c.live);
  return `<div class="card"><div class="hd"><h2>${esc(o.instrument)}</h2><span class="cap">expiry ${esc(o.expiry)} · ${o.dte_days != null ? o.dte_days + ' days' : ''}</span>${L ? '<span class="sp"></span><span class="pill ok">live prices</span>' : ''}</div><div class="bd"><div class="kv">
    ${L ? `<span>Live last price</span><b>₹${fmt(L.ltp)}${o.live_at ? ` <small class="muted">${esc(hmIST(o.live_at))}</small>` : ''}</b><span>Bid / Ask</span><b>${L.bid ? '₹' + fmt(L.bid) : '-'} / ${L.ask ? '₹' + fmt(L.ask) : '-'}${spr != null ? ` <small class="${spr > 2 ? 'bad' : 'muted'}">spread ${spr.toFixed(1)}%</small>` : ''}</b>` : ''}
    <span>${L ? 'Model premium at entry' : 'Model premium'}</span><b>₹${fmt(o.premium)}</b><span>Delta / Gamma</span><b>${fmt(o.delta)} / ${fmt(o.gamma, 4)}</b><span>Theta per day / Vega</span><b>${fmt(o.theta_day)} / ${fmt(o.vega)}</b><span>Premium stop</span><b class="bad">₹${fmt(o.premium_sl)}</b><span>Premium targets</span><b class="good">${(o.premium_targets || []).map(x => '₹' + fmt(x)).join(' · ')}</b><span>Volatility</span><b>${fmt(o.iv, 1)}% <small class="muted">${esc(o.iv_source || '')}</small></b></div>
    ${(o.candidates || []).length ? `<hr class="sep"><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Strike</th><th class="n">Delta</th><th class="n">Model</th>${liveAny ? '<th class="n">Live</th><th class="n">Bid / Ask</th>' : ''}<th class="n">Theta/day</th></tr></thead><tbody>${o.candidates.map(c => `<tr${c.strike === o.strike ? ' style="font-weight:700"' : ''}><td>${c.strike}</td><td class="n">${fmt(c.delta)}</td><td class="n">${fmt(c.premium)}</td>${liveAny ? `<td class="n">${c.live ? fmt(c.live.ltp) : '-'}</td><td class="n">${c.live && c.live.bid ? fmt(c.live.bid) + ' / ' + fmt(c.live.ask) : '-'}</td>` : ''}<td class="n">${fmt(c.theta_day)}</td></tr>`).join('')}</tbody></table></div>` : ''}
    <p class="help" style="margin-top:8px">${L ? 'Volatility comes from the live option price (Angel One). Stop and target premiums are model estimates around it: place the order on the live price.' : 'Black-Scholes with India VIX: a model price, check the live premium before you buy.'}</p></div></div>`;
}
/* Where a setup has been: its stage and status on each scan it changed on (so a setup that moves from 1H confirmed / held back to In zone is not just 'gone'). */
/* "Since you last looked": what moved among the setups at stage 3 or later since the snapshot you took (it is only re-taken when you press "Mark as seen", never behind your back). */
/* "replay this day": what the live options engine would have said at each 5-minute candle of a past day (item 18) */
SC.replayCard = () => { const idx = App.lazyNow('replay/index'), U = App.ui.rp || (App.ui.rp = { day: null }); if (!idx && App.lazyAge('replay/index') === Infinity) App.lazy('replay/index').then(() => App.soon('options'));
  const days = (idx && idx.days) || [], day = U.day || days[0], doc = day ? App.lazyNow('replay/options_' + day) : null; if (day && !doc && App.lazyAge('replay/options_' + day) === Infinity) App.lazy('replay/options_' + day).then(() => App.soon('options'));
  const wf = `${App.actionsUrl()}/workflows/replay.yml`, side = (nm) => { const rows = ((doc || {}).sides || {})[nm] || []; return `<div><h3 style="font-size:14px;margin:0 0 6px">${nm}${doc && doc.first_trigger && doc.first_trigger[nm] ? ` <span class="pill ok">triggered ${esc(doc.first_trigger[nm].t)}</span>` : ' <span class="pill">no trigger</span>'}</h3><ul class="ins rp">${rows.slice(0, 30).map(r => `<li class="${r.status === 'TRIGGERED' ? 'good' : /^WATCH/.test(r.status) ? 'warn' : ''}"><i></i><span><b>${esc(r.t)}</b> ${esc(r.status)}${r.score != null && r.grade ? ` <small class="muted">${r.grade} ${r.score}/10</small>` : ''}</span></li>`).join('') || '<li class="muted">Nothing recorded.</li>'}</ul></div>`; };
  const ch = doc && doc.chart && doc.chart.candles && doc.chart.candles.length ? App.charts.candles(doc.chart, { id: 'replay:' + day, W: Math.min(1000, ((document.querySelector('#page') || {}).clientWidth || 900) - 70), label: 'Nifty 5-minute ' + day, marks: ['CALL', 'PUT'].map(nm => { const f = (doc.first_trigger || {})[nm]; if (!f) return null; const i = doc.chart.times.findIndex(t => t.slice(11, 16) >= f.t) - 1; return i >= 0 ? { i, p: doc.chart.candles[i][3], label: nm + ' trigger', c: nm === 'CALL' ? 'good' : 'bad', below: nm === 'PUT' } : null; }).filter(Boolean) }) : '';
  return `<details class="card replay" style="margin-top:14px" ${U.open ? 'open' : ''}><summary class="hd"><h2>Replay a day</h2><span class="cap">what the live engine said at each candle</span></summary><div class="bd">
    ${days.length ? `<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px"><label class="muted" for="rpDay">Day</label><select id="rpDay">${days.map(d => `<option ${d === day ? 'selected' : ''}>${esc(d)}</option>`).join('')}</select><a class="btn sm ghost" href="${wf}" target="_blank" rel="noopener">Replay another day on GitHub</a></div>
      ${doc ? `${ch}<div class="grid g2" style="margin-top:10px">${side('CALL')}${side('PUT')}</div><p class="help" style="margin-top:8px">${esc(doc.note || '')}</p>` : '<p class="help">Loading…</p>'}`
      : `<p class="help">No replay yet. One runs after every close (16:11 IST). For any day in the last ~60 days: <a href="${wf}" target="_blank" rel="noopener">Actions → replay → Run workflow</a>, then enter the date.</p>`}</div></details>`; };
/* the conditions under the chart as a strip: zone, 1H close, volume, 15m (item 125) */
SC.condStrip = (it, sec) => { const h1 = it.h1 || {}, m = it.m15 || {}, dz = SC.dist(it);
  const C = sec === 'swing' ? [['Zone', it.stage >= 3 || (dz && dz.zone === 0)], ['1H close > 9 EMA', !!h1.t_confirm || it.stage >= 4], ['Volume ' + ((App.data.swing || {}).playbook === 'v2' ? '> 20-bar avg' : '1.5×'), h1.rvol_ok ? true : it.stage >= 4 ? true : null], ['15m trigger', !!m.trigger || it.stage >= 5], ['No hold-back', !(it.holds || []).length]]
    : [['Zone', /IN ZONE|TRIGGER|WATCH/i.test(it.status)], ['5m close > 9 EMA', it.status === 'TRIGGERED'], ['Volume', it.status === 'TRIGGERED' ? true : /low volume/i.test(it.status) ? false : null]];
  return `<div class="bd cond-strip" style="padding-top:0">${C.map(([l, ok]) => `<span class="${ok === true ? 'ok' : ok === false ? 'no' : ''}">${ok === true ? '✓' : ok === false ? '✗' : '·'} ${esc(l)}</span>`).join('')}</div>`; };
/* next check countdown and loop health (272) */
SC.nextCheck = d => { if (!d || !d.generated_at) return ''; const nx = new Date(new Date(d.generated_at).getTime() + 5 * 6e4), mins = Math.round((nx - Date.now()) / 6e4), age = App.loopAge ? App.loopAge() : null, ok = !App.marketOpen() || (age != null && age < 12);
  return `<div class="nextchk"><span class="dot ${ok ? 'ok' : 'bad'}"></span>${App.marketOpen() ? (mins >= 0 ? `Next check ~${esc(hmIST(nx))} (in ${mins} min)` : `Next check was due at ${esc(hmIST(nx))}`) : 'Market closed: checks resume at 09:15'} · ${ok ? '5-minute loop running' : '<a href="#/health">5-minute loop is late</a>'}</div>`; };
/* trades the scanner closed today, with R and how many checklist items were ticked (274) */
SC.closedToday = sec => { const L = App.LED(sec), d = todayIST(), C = (L.signals || []).filter(x => x.status === 'CLOSED' && String(x.closed || x.checked_to || '').slice(0, 10) === d); if (!C.length) return '';
  return `<div class="card" style="margin-top:14px"><div class="hd"><h2>Closed today</h2><span class="cap">${C.length}</span></div><div class="bd"><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Trade</th><th>Outcome</th><th class="n">R</th><th class="n">Rules ticked</th></tr></thead><tbody>${C.map(x => { const ck = x.checklist || [], t = ck.filter(c => c.ok === true).length;
    return `<tr><td><b>${esc(x.instrument || x.symbol)}</b> <small class="muted">${esc(x.label || x.direction || '')}</small></td><td>${esc(x.outcome || '')}</td><td class="n ${cls(x.r_final)}">${rr(x.r_final, 1)}</td><td class="n">${ck.length ? t + '/' + ck.length : '-'}</td></tr>`; }).join('')}</tbody></table></div></div></div>`; };
/* near misses: setups that reached the trigger but one condition failed, so the rule's strictness can be judged without changing it (44) */
SC.nearMiss = sec => { const L = App.LED(sec), since = new Date(Date.now() - 5 * 864e5).toISOString().slice(0, 10), rows = [...(L.dropped || []), ...Object.values(L.watch || {})].filter(x => /^WATCH/i.test(String(x.status || '')) && String(x.last_seen || x.dropped || x.first_seen || '') >= since).sort((a, b) => String(b.last_seen || b.dropped || '') < String(a.last_seen || a.dropped || '') ? -1 : 1).slice(0, 10);
  if (!rows.length) return ''; return `<details class="card nearmiss" style="margin-top:14px"><summary class="hd"><h2>Near misses</h2><span class="cap">${rows.length} in 5 days · all but one condition met</span></summary><div class="bd"><div class="tbl-wrap"><table class="tbl"><thead><tr><th>When</th><th>Setup</th><th>What was missing</th><th>Then</th></tr></thead><tbody>${rows.map(x => `<tr><td class="nw"><small>${esc(String(x.last_seen || x.first_seen || '').replace('T', ' ').slice(5, 16))}</small></td><td><b>${esc(x.symbol)}</b> <small class="muted">${esc(x.label || x.direction || '')} · ${esc(x.grade || '')}</small></td><td>${esc((String(x.status).match(/\(([^)]*)\)/) || [])[1] || x.status)}</td><td><small class="muted">${esc(x.reason || 'still watched')}</small></td></tr>`).join('')}</tbody></table></div>
    <p class="help" style="margin-top:8px">Shown only so you can judge whether a rule is too strict. Nothing here was taken, and no rule was changed.</p></div></details>`; };
/* sector heat: which sectors have the most setups at each stage (item 36) */
SC.sectorHeat = S => { const rows = {}; S.filter(x => x.stage >= 2).forEach(x => { const k = x.sector || 'Other', r = rows[k] = rows[k] || { 2: 0, 3: 0, 4: 0, 5: 0, held: 0 }; if (SC.held(x)) r.held++; else r[x.stage]++; });
  const list = Object.entries(rows).map(([k, r]) => [k, r, r[5] * 4 + r[4] * 3 + r[3] * 2 + r[2]]).sort((a, b) => b[2] - a[2]).slice(0, 8); if (!list.length) return '';
  const mx = Math.max(...list.map(x => Math.max(x[1][2], x[1][3], x[1][4], x[1][5])), 1), cell = v => `<td class="n"><span class="heat" style="--h:${(v / mx).toFixed(2)}">${v || ''}</span></td>`;
  return `<details class="sheat" ${store.get('ds_heat_open', false) ? 'open' : ''}><summary><b>Sector heat</b> <small class="muted">which sectors hold the setups</small></summary><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Sector</th><th class="n">Entry</th><th class="n">1H conf.</th><th class="n">In zone</th><th class="n">Set alert</th><th class="n">Held</th></tr></thead><tbody>${list.map(([k, r]) => `<tr class="click" data-sector="${esc(k)}"><td>${esc(k)}</td>${cell(r[5])}${cell(r[4])}${cell(r[3])}${cell(r[2])}<td class="n muted">${r.held || ''}</td></tr>`).join('')}</tbody></table></div></details>`; };
function sinceStrip(S, sec) {
  const K = 'tji_seen_' + sec, seen = store.get(K, null), snap = () => ({ at: new Date().toISOString(), st: Object.fromEntries(S.filter(x => x.stage >= 3).map(x => [x.symbol, x.stage * 10 + (SC.held(x) ? 1 : 0)])) });
  if (!seen || !seen.st) { store.set(K, snap()); return ''; }
  const cur = Object.fromEntries(S.filter(x => x.stage >= 3).map(x => [x.symbol, x])), rows = [], lnk = n => `<a href="#/trade?s=${sec}&id=${encodeURIComponent(n + '|long')}"><b>${esc(n)}</b></a>`;
  Object.entries(cur).forEach(([n, x]) => { const p = seen.st[n], held = SC.held(x);
    if (p == null) rows.push(`${lnk(n)} new at ${STG[x.stage][0]}${held ? ' (held back)' : ''}`);
    else { const ps = Math.floor(p / 10), ph = p % 10 === 1;
      if (x.stage > ps) rows.push(`${lnk(n)} moved up: ${STG[ps][0]} to ${STG[x.stage][0]}`); else if (x.stage < ps) rows.push(`${lnk(n)} moved back: ${STG[ps][0]} to ${STG[x.stage][0]}${ph && !held ? ', no longer held back' : ''}`);
      else if (held && !ph) rows.push(`${lnk(n)} is now held back`); else if (!held && ph) rows.push(`${lnk(n)} is no longer held back`); } });
  Object.keys(seen.st).filter(n => !cur[n]).forEach(n => { const x = S.find(y => y.symbol === n); rows.push(`${lnk(n)} ${x ? 'fell back to ' + STG[x.stage][0] : 'left the list (see Closed / invalidated for why)'}`); });
  if (!rows.length) return '';
  return App.ui.callout('info', `<b>Since ${esc(toLbl(String(seen.at).replace('T', ' ')))}:</b> ${rows.slice(0, 8).join(' &nbsp;·&nbsp; ')}${rows.length > 8 ? ` &nbsp;·&nbsp; +${rows.length - 8} more` : ''} <button class="btn sm" id="seenBtn" type="button" style="margin-left:8px">Mark as seen</button>`) + '<div style="height:12px"></div>';
}
function trailCard(sec, it, w) {
  const tr = ((w && w.trail) || (it ? ((App.LED(sec).watch || {})[key(sec, it)] || {}).trail : null) || []).slice(-8).reverse(); if (tr.length < 2 && !(w && w.reason)) return '';
  return `<div class="card"><div class="hd"><h2>Where this setup has been</h2><span class="cap">newest first</span></div><div class="bd"><ul class="ins">${tr.map(x => `<li><i></i><span><b>${esc(toLbl(String(x.at || '').replace('T', ' ')))}</b> · ${x.stage != null && STG[x.stage] ? 'stage ' + x.stage + ' ' + esc(STG[x.stage][0]) + ': ' : ''}${esc(x.status || '')}${x.held ? ' <small class="muted">(held back)</small>' : ''}</span></li>`).join('')}</ul>
    ${w && w.reason ? `<p class="help" style="margin-top:8px"><b>Then:</b> ${esc(w.reason)}</p>` : ''}</div></div>`;
}
function trackCard(sig, it) {
  const d = dec(it), closed = sig.status === 'CLOSED', r = closed ? sig.r_final : sig.r_now;
  return `<div class="card"><div class="hd"><h2>Trade tracking</h2><span class="sp"></span><span class="pill ${closed ? (r > 0 ? 'ok' : 'bad') : 'info'}">${esc(sigStatus(sig))}</span></div><div class="bd">
    <div class="kpis" style="margin-bottom:12px">${App.ui.kpi(closed ? 'Result' : 'R now', rr(r), closed ? '' : 'last ' + fmt(sig.last, d), cls(r))}${App.ui.kpi(closed ? 'Exit' : 'Stop now', fmt(closed ? sig.exit : sig.stop, d), closed ? esc((sig.closed || '').replace('T', ' ').slice(5, 16)) : sig.stop === sig.sl ? 'original stop' : 'trailed')}${App.ui.kpi('Best since trigger', fmt(sig.best, d), 'worst ' + fmt(sig.worst, d))}</div>
    <ul class="timeline">${sig.events.slice().reverse().map(e => `<li class="${['t1', 't2', 'target'].includes(e.kind) ? 'good' : ['sl'].includes(e.kind) ? 'bad' : ''}"><time>${esc(e.t.replace('T', ' ').slice(5, 16))}</time>${esc(e.text)}</li>`).join('')}</ul>
    <p class="help" style="margin-top:10px">Followed on closed candles; the stop is assumed to fill before a target inside the same candle.</p></div></div>`;
}
App.pages.trade = q => {
  const R = resolve(q), sec = R.sec, back = `<a class="back" href="#/${sec}">${ic('back')} ${sec === 'options' ? 'Nifty options' : sec[0].toUpperCase() + sec.slice(1)}</a>`;
  if (!R.it) { const w = R.drop; return back + (w ? `<div class="thead"><h1>${esc(w.symbol)}</h1><span class="pill bad">invalidated</span></div><div style="height:12px"></div>${App.ui.callout('bad', `<b>This setup was cancelled before it triggered</b> (${esc((w.dropped || '').replace('T', ' ').slice(0, 16))}).<br>${esc(w.reason || '')}`)}
      <div class="card" style="margin-top:14px"><div class="bd"><div class="kv"><span>Last status</span><b>${esc(w.status || '')}</b><span>Grade / score</span><b>${esc(w.grade || '')} ${w.score || ''}/10</b><span>Zone</span><b>${fmt(w.zone_bot)} – ${fmt(w.zone_top)}</b><span>Plan entry / SL / T1</span><b>${fmt(w.entry)} / ${fmt(w.sl)} / ${fmt(w.t1)}</b></div><p class="help" style="margin-top:8px">If you entered anyway, manage it with the original stop and log it as a rule break ("No confirmation").</p></div></div>${trailCard(sec, null, w)}` : App.ui.empty('Setup not found', 'It is no longer in the scan and never triggered.')); }
  const it = R.it, sig = R.sig, d = dec(it), inJ = App.journal.findByTag(sig ? sig.id : key(sec, it)), tfs = it.charts ? Object.keys(it.charts) : it.tfs && it.tfs.length ? it.tfs : [it.tf_structure || '5m'];
  const tfMem = App.ui.tf || store.get('ds_tf_' + sec, null), tf = tfMem && tfs.includes(tfMem) ? tfMem : (tfs.includes('15m') && it.stage >= 5 ? '15m' : tfs[0]); App.ui.tfCur = tf;
  const role = { '1D': 'Structure and zone', '1H': 'Confirmation', '15m': 'Precision entry', '5m': 'Setup and trigger' };
  const news = ((App.data.news || {}).by_symbol || {})[it.symbol] || [];
  let h = back + `<div class="thead"><h1>${esc(it.symbol)}</h1>${sec !== 'swing' ? `<span class="tag ${it.direction}">${esc(it.label)}</span>` : ''}<span class="st ${sig ? (sig.status === 'CLOSED' ? 'closed' : 's5') : stCls(it)}">${esc(sig ? sigStatus(sig) : it.status)}</span>${App.ui.grade(it.grade)}<b>${it.score}/10</b>${inJ ? '<span class="pill info">in your journal</span>' : ''}<span style="flex:1"></span>
    <div class="act-bar"><a class="btn" href="${App.tv(it.symbol)}" target="_blank" rel="noopener">${ic('ext')} <span>TradingView</span></a><button class="btn" id="alertT" type="button">Set alert</button><a class="btn" href="#/stock?sym=${encodeURIComponent(it.symbol)}">All of ${esc(it.symbol)}</a><button class="btn" id="shareT" type="button" title="A framed chart with your levels, grade and date; no account details">Share card</button><button class="btn primary" id="logT" type="button">${ic('plus')} ${inJ ? 'Log again' : 'Log trade'}</button></div></div>
    <p class="help" style="margin:4px 0 14px">${[it.sector, it.stage ? `Stage ${it.stage} of 5: ${STG[it.stage][0]}` : '', it.price != null ? 'last ' + fmt(it.price, d) : '', it.results && it.results.date ? `results ${it.results.date} (${it.results.days} d)` : '', sig ? 'triggered ' + sig.created.replace('T', ' ').slice(0, 16) : ''].filter(Boolean).map(esc).join(' · ')}</p>`;
  if ((it.holds || []).length) h += App.ui.callout('warn', `<b>Held back:</b> ${it.holds.map(esc).join(', ')}. The entry is not valid until this clears.`) + '<div style="height:12px"></div>';
  h += `<div class="grid g-main"><div class="stack"><div class="card"><div class="hd"><div class="tftabs">${tfs.map(t => `<button class="tftab" type="button" data-tf="${t}" aria-pressed="${t === tf}"><b>${t}</b><small>${role[t] || ''}</small></button>`).join('')}</div><span class="sp"></span>${tfs.includes('1D') && tfs.includes('1H') ? `<button class="btn sm hide-m" type="button" id="sbsB" aria-pressed="${!!store.get('ds_sbs', false)}" title="1D and 1H side by side">1D + 1H</button>` : ''}</div>
    <div class="bd" id="chBox">${chartFor(it, tf, sig, 700)}</div>${SC.condStrip(it, sec)}<div class="bd legend" style="padding-top:0"><span><i style="background:var(--c6)"></i>9 EMA</span><span><i style="background:var(--good)"></i>FVG</span><span><i style="background:var(--c1)"></i>OB</span><span><i style="background:var(--sun)"></i>Fib</span><span><i style="background:var(--brand)"></i>Entry / zone</span><span><i style="background:var(--bad)"></i>Stop</span></div></div>
    ${sig ? '' : trailCard(sec, it)}
    ${it.checklist ? checklistCard(it) : `<div class="card"><div class="hd"><h2>Why this setup</h2></div><div class="bd"><ul class="checks">${(it.logic || []).map(l => `<li><span class="mk ${l.ok === false ? 'n' : 'y'}">${l.ok === false ? '✗' : '✓'}</span><span class="tf"></span><div><b>${esc(l.title)}</b><p>${esc(l.text)}</p></div></li>`).join('')}</ul></div></div>`}
    ${news.length ? `<div class="card"><div class="hd"><h2>News for ${esc(it.symbol)}</h2></div><div class="bd"><ul class="news">${news.slice(0, 6).map(n => `<li><span class="imp ${n.impact || ''}"></span><div><a href="${esc(n.link)}" target="_blank" rel="noopener">${esc(n.title)}</a><br><small>${esc(n.source || '')}${n.published ? ' · ' + esc(ago(n.published)) : ''}</small></div></li>`).join('')}</ul></div></div>` : ''}</div>
    <div class="stack">${sig ? trackCard(sig, it) : ''}${scoreCard(it)}${planCard(it)}${optionCard(it)}${sizeCard(it)}${ticketCard(it, sec)}
      ${(it.notes || []).length ? `<div class="card"><div class="hd"><h2>Cautions</h2></div><div class="bd"><ul class="ins">${it.notes.map(n => `<li class="warn"><i></i><span>${esc(n)}</span></li>`).join('')}</ul></div></div>` : ''}</div></div>`;
  return h;
};
App.binds.trade = q => {
  const R = resolve(q); if (!R.it) return;
  $('#logT').onclick = () => App.journal.openForm(null, App.journal.fromScanner(R.it, R.sig));
  if ($('#tktCopy')) $('#tktCopy').onclick = () => copyText(ticketText(R.it), 'Order ticket copied');
  if ($('#pineCopy')) $('#pineCopy').onclick = () => copyText(pineText(R.it), 'Pine script copied: paste it in TradingView\'s Pine Editor');
  if (q && q.get && q.get('log') === '1') { try { history.replaceState(null, '', location.href.replace(/[&?]log=1/, '')); } catch (e) { } setTimeout(() => { const b = $('#logT'); if (b && !$('.modal-bg')) b.click(); }, 350); }   // "Log this trade" button in the phone alert
  $$('[data-tf]').forEach(b => b.onclick = () => { App.ui.tf = b.dataset.tf; store.set('ds_tf_' + (App.route().q.get('s') || 'swing'), b.dataset.tf); App.render(); });
  const draw = () => { const b = $('#chBox'); if (!b) return; const sbs = store.get('ds_sbs', false) && innerWidth >= 1280 && (R.it.tfs || []).includes('1D') && (R.it.tfs || []).includes('1H');
    if (sbs) { const w = Math.floor((b.clientWidth - 48) / 2); b.innerHTML = `<div class="sbs"><div>${chartFor(R.it, '1D', R.sig, w)}</div><div>${chartFor(R.it, '1H', R.sig, w)}</div></div>`; } else b.innerHTML = chartFor(R.it, App.ui.tfCur, R.sig, b.clientWidth - 32); };
  const sb = $('#sbsB'); if (sb) sb.onclick = () => { store.set('ds_sbs', !store.get('ds_sbs', false)); App.render(); };
  const shr = $('#shareT'); if (shr) shr.onclick = () => { const svg = $('#chBox svg[data-chart]'); if (!svg) { App.toast('Open a chart first'); return; } const it = R.it; App.charts.share(svg, `${it.symbol}-${App.ui.tfCur || ''}`, { title: `${it.symbol} · ${App.ui.tfCur || ''} · ${it.grade || ''} ${it.score != null ? it.score + '/10' : ''}`, sub: `Entry ${fmt(it.entry, dec(it))} · stop ${fmt(it.sl, dec(it))} · T1 ${fmt(it.t1, dec(it))} · ${String(it.status || '').split(' (')[0]} · ${dateIST(new Date())}` }); };
  const al = $('#alertT'); if (al) al.onclick = () => { const v = prompt(`Alert me when ${R.it.symbol} reaches (price):`, R.it.zone_top || R.it.entry || ''); const p = parseFloat(String(v || '').replace(/,/g, '')); if (isNum(p)) { App.journal.addAlert(R.it.symbol, p, R.it.price); App.toast('Alert set. It fires while the app is open.'); App.render(); } };
  draw();
  if (!R.it.charts && R.it.section === 'swing' && R.it.tfs) {
    const sw_ = App.data.swing || {}, gen = sw_.charts_at || sw_.generated_at, have = App.lazyNow('swing_charts');
    App.lazy('swing_charts', have && (have.charts_at || have.generated_at) === gen ? 3600e3 : 0).then(draw);       // loads once per swing scan, and again when the fast lane refreshes the charts
  } let t; window.onresize = () => { clearTimeout(t); t = setTimeout(draw, 150); };
};
SC.card = card; SC.STG = STG;
/* ---------- pre-market checklist screen (item 37) ---------- */
App.pages.premarket = () => {
  const ds = App.journal.dayStatus(), sw = App.data.swing || {}, S = sw.setups || [], m = App.data.market || {}, o = (App.data.options || {}).snapshot || {}, news = App.data.news || {};
  const short = S.filter(s => s.stage >= 3 && !(s.holds || []).length && !String(s.status).startsWith('WATCH') && s.grade === 'A+').sort((a, b) => b.stage - a.stage || b.score - a.score).slice(0, 5);
  const open = App.journal.enrich().filter(t => t.open), syms = new Set([...short.map(s => s.symbol), ...open.map(t => t.inst)]);
  const res = S.filter(s => syms.has(s.symbol) && s.results && s.results.days != null && s.results.days <= 3);
  const hi = (news.items || []).filter(n => n.impact === 'high').slice(0, 5), hol = (news.holidays || []).filter(x => x >= todayIST()).slice(0, 2);
  const tick = (ok, t, s2) => `<li><span class="mk ${ok === true ? 'y' : ok === false ? 'n' : 'q'}">${ok === true ? '✓' : ok === false ? '✗' : '?'}</span><span class="tf"></span><div><b>${t}</b>${s2 ? `<p>${s2}</p>` : ''}</div></li>`;
  return `<div class="ph"><div><h1>Pre-market</h1><p>Everything to check before 09:15, on one screen.</p></div><span class="sp"></span>${meta(App.data.swing)}</div>
    <div class="kpis k4" style="margin-bottom:14px">${App.ui.kpi('Trades left today', ds.left, ds.blocked ? 'daily limit reached: ' + ds.why : 'A+ only, at most two a day', ds.blocked ? 'bad' : '')}${App.ui.kpi('Open positions', open.length, open.length ? 'check their stops' : 'none')}${App.ui.kpi('Nifty', sw.nifty_trend == null ? '-' : sw.nifty_trend ? 'Above 21 EMA' : 'Below 21 EMA', isNum(o.vix) ? 'VIX ' + fmt(o.vix, 1) : '', sw.nifty_trend ? 'good' : sw.nifty_trend === false ? 'bad' : '')}${App.ui.kpi('A+ shortlist', short.length, short.length ? 'pick one or two at most' : 'nothing to take')}</div>
    <div class="grid g2"><div class="card"><div class="hd"><h2>Checklist</h2></div><div class="bd"><ul class="checks">
      ${tick(!ds.blocked, 'Daily limit', ds.blocked ? 'Two trades or two losses already today: no new trade.' : `You can take ${ds.left} more today, A+ only.`)}
      ${tick(open.every(t => isNum(t.sl)) ? true : false, 'Every open trade has a stop', open.filter(t => !isNum(t.sl)).map(t => esc(t.inst)).join(', ') || 'Place them as GTT/SL orders before the open.')}
      ${tick(res.length ? false : true, 'No results in the next 3 days on your names', res.map(s => `${esc(s.symbol)} on ${esc(s.results.date)}`).join(', ') || 'None found in the scan.')}
      ${tick(hi.length ? null : true, 'High-impact news checked', hi.length ? hi.map(n => esc(n.title)).join(' · ') : 'Nothing high-impact in the feed.')}
      ${tick(hol.includes(todayIST()) ? false : true, 'Market open today', hol.length ? 'Next holiday ' + esc(hol[0]) : '')}
      ${tick(App.marketOpen() || !App.loopAge ? null : true, 'Scanner running', 'The 5-minute loop starts at 09:05. System health shows it.')}
    </ul></div></div>
    <div class="card"><div class="hd"><h2>A+ shortlist</h2><span class="cap">from the last swing scan</span></div><div class="bd">${short.length ? `<div class="cards one">${short.map(s => card('swing', s)).join('')}</div>` : App.ui.empty('No A+ setup ready', 'That is fine: waiting is part of the plan.')}</div></div></div>
    <div class="card" style="margin-top:14px"><div class="hd"><h2>Open positions</h2></div><div class="bd">${open.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Trade</th><th class="n">Entry</th><th class="n">Stop</th><th class="n">Target</th><th class="n">Last · R</th></tr></thead><tbody>${open.map(t => `<tr class="click" data-jopen="${esc(t.id)}"><td><b>${esc(t.inst)}</b> <small class="muted">${esc(t.cat || '')} · ${esc(t.d)}</small></td><td class="n">${fmt(t.entry)}</td><td class="n">${fmt(t.sl)}</td><td class="n">${fmt(t.tgt)}</td><td class="n">${App.journal.livePx(t).txt}</td></tr>`).join('')}</tbody></table></div>` : App.ui.empty('No open positions', '')}</div></div>`;
};
App.binds.premarket = () => { $$('tr[data-jopen]').forEach(tr => tr.onclick = () => App.journal.openForm(tr.dataset.jopen)); };

/* ---------- per-stock page: every setup, trade, note and result for one symbol (item 46) ---------- */
App.pages.stock = q => {
  const sym = String(q.get('sym') || '').toUpperCase(); if (!sym) return App.ui.empty('No symbol', 'Search for a symbol first.');
  const cur = ['swing', 'options', 'intraday'].flatMap(sec => ((App.data[sec] || {}).setups || []).filter(x => x.symbol === sym).map(x => [sec, x]));
  const hist = ['swing', 'options', 'intraday'].flatMap(sec => { const L = App.LED(sec); return [...(L.signals || []).filter(x => x.symbol === sym).map(x => ({ sec, kind: x.status === 'CLOSED' ? 'Tracked, closed' : 'Tracked, open', when: x.created, text: x.status === 'CLOSED' ? `${x.outcome || ''} ${rr(x.r_final, 1)}` : `R now ${rr(x.r_now, 1)}`, x })), ...(L.dropped || []).filter(x => x.symbol === sym).map(x => ({ sec, kind: 'Left the list', when: x.dropped, text: x.reason, x })), ...Object.values(L.watch || {}).filter(x => x.symbol === sym).map(x => ({ sec, kind: 'Watched', when: x.last_seen, text: x.status, x }))]; }).sort((a, b) => String(b.when || '') < String(a.when || '') ? -1 : 1);
  const T = App.journal.enrich().filter(t => String(t.inst || '').toUpperCase() === sym || String(t.inst || '').toUpperCase().startsWith(sym + ' ')), pnl = T.filter(t => !t.open && isNum(t.pnl)).reduce((a, t) => a + t.pnl, 0);
  const X = App.journal.lvxFor(sym), news = ((App.data.news || {}).by_symbol || {})[sym] || [], res = cur.map(c => c[1].results).find(Boolean);
  return `<div class="ph"><div><h1>${esc(sym)}</h1><p>Every setup, trade, note and result for this symbol.</p></div><span class="sp"></span><a class="btn" href="${App.tv(sym)}" target="_blank" rel="noopener">${ic('ext')} TradingView</a></div>
    <div class="kpis k4" style="margin-bottom:14px">${App.ui.kpi('Setups now', cur.length, cur.map(([sec, x]) => sec + ' ' + (x.stage_label || x.status.split(' (')[0])).join(' · ') || 'none')}${App.ui.kpi('Your trades', T.length, T.filter(t => t.open).length + ' open')}${App.ui.kpi('Your P&L here', inr(pnl), 'closed trades', cls(pnl))}${App.ui.kpi('Results', res ? res.date : '-', res ? res.days + ' days away' : 'not in the scan')}</div>
    ${cur.length ? `<div class="cards" style="margin-bottom:14px">${cur.map(([sec, x]) => card(sec, x)).join('')}</div>` : ''}
    <div class="grid g2"><div class="card"><div class="hd"><h2>Scanner history</h2><span class="cap">${hist.length}</span></div><div class="bd">${hist.length ? `<ul class="ins">${hist.slice(0, 20).map(h => `<li><i></i><span><b>${esc(String(h.when || '').replace('T', ' ').slice(0, 16))}</b> · ${esc(h.sec)} · ${esc(h.kind)}: ${esc(h.text || '')}</span></li>`).join('')}</ul>` : App.ui.empty('Nothing recorded yet', 'Setups appear here once the scanner lists them.')}</div></div>
    <div class="card"><div class="hd"><h2>Your trades</h2></div><div class="bd">${T.length ? `<div class="tbl-wrap"><table class="tbl"><tbody>${T.slice().reverse().map(t => `<tr class="click" data-jopen="${esc(t.id)}"><td><b>${esc(t.d)}</b> <small class="muted">${esc(t.cat || '')} · ${esc(t.dir)}</small></td><td class="n">${fmt(t.entry)} → ${t.open ? 'open' : fmt(t.exit)}</td><td class="n ${cls(t.pnl)}">${t.open ? App.journal.livePx(t).txt : inrS(t.pnl)}</td></tr>`).join('')}</tbody></table></div>` : App.ui.empty('No trades in this symbol', '')}</div></div></div>
    <div class="grid g2" style="margin-top:14px"><div class="card"><div class="hd"><h2>Alerts and notes</h2></div><div class="bd">${X.alerts.length + X.notes.length ? `<ul class="ins">${[...X.alerts.map(a => `<li><i></i><span>Alert ${a.dir} <b>${fmt(a.p)}</b> <button class="btn sm ghost" data-lvdel="${esc(a.id)}" type="button">Remove</button></span></li>`), ...X.notes.map(n => `<li><i></i><span>Note at <b>${fmt(n.p)}</b>: ${esc(n.text)} <button class="btn sm ghost" data-lvdel="${esc(n.id)}" type="button">Remove</button></span></li>`)].join('')}</ul>` : App.ui.empty('None', 'Long-press a price on a chart to add one.')}</div></div>
    <div class="card"><div class="hd"><h2>News</h2></div><div class="bd">${news.length ? `<ul class="news">${news.slice(0, 8).map(n => `<li><span class="imp ${n.impact || ''}"></span><div><a href="${esc(n.link)}" target="_blank" rel="noopener">${esc(n.title)}</a><br><small>${esc(n.source || '')}${n.published ? ' · ' + esc(ago(n.published)) : ''}</small></div></li>`).join('')}</ul>` : App.ui.empty('No news in the feed', '')}</div></div></div>`;
};
App.binds.stock = () => { $$('tr[data-jopen]').forEach(tr => tr.onclick = () => App.journal.openForm(tr.dataset.jopen)); $$('[data-lvdel]').forEach(b => b.onclick = () => { App.journal.delLvx(b.dataset.lvdel); App.render(); }); };

/* price alerts from the chart: checked whenever fresh data arrives (item 167) */
App.checkPriceAlerts = () => { if (!App.journal || !App.journal.checkAlerts) return; const px = sym => { for (const sec of ['swing', 'intraday', 'options']) { const it = ((App.data[sec] || {}).setups || []).find(x => x.symbol === sym); if (it && isNum(it.price)) return it.price; } const g = App.lazyNow && App.lazyNow('gold'); if (sym === 'XAUUSD' && g && isNum(g.price)) return g.price; return null; };
  App.journal.checkAlerts(px).forEach(({ a, px: p }) => { const msg = `${a.sym} reached ${fmt(a.p)} (now ${fmt(p)})`; App.toast(msg, 6000); try { if (window.Notification && Notification.permission === 'granted') new Notification('DownerStuff price alert', { body: msg, icon: 'icon-192.png' }); } catch (e) { } }); };
})();
