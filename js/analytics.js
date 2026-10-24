/* Analytics on your journal: performance, risk, edge, discipline and progress. */
'use strict';
(function () {
const A = App.analytics = {};
const WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const avg = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : null;
A.stats = function (T, S) {
  const C = T.filter(t => t.closed && t.net != null), n = C.length, wins = C.filter(t => t.res === 'Win'), losses = C.filter(t => t.res === 'Loss');
  const net = C.reduce((a, t) => a + t.net, 0), gw = wins.reduce((a, t) => a + t.net, 0), gl = -losses.reduce((a, t) => a + t.net, 0), R = C.filter(t => t.r != null).map(t => t.r);
  let eq = 0, peak = 0, dd = 0, ddP = 0, cur = 0, bestW = 0, bestL = 0, run = 0; const curve = [], ddc = [], rc = []; let rsum = 0;
  C.forEach(t => { eq += t.net; peak = Math.max(peak, eq); dd = Math.min(dd, eq - peak); curve.push(eq); ddc.push(eq - peak); if (t.r != null) rsum += t.r; rc.push(rsum);
    const w = t.res === 'Win' ? 1 : t.res === 'Loss' ? -1 : 0; if (w && Math.sign(run) === w) run += w; else run = w; if (run > bestW) bestW = run; if (-run > bestL) bestL = -run; });
  ddP = S && S.capital ? dd / S.capital : null;
  const chg = C.reduce((a, t) => a + (t.chg || 0), 0), gross = C.reduce((a, t) => a + (t.gross != null ? t.gross : t.net), 0);
  return { C, n, wins: wins.length, losses: losses.length, be: n - wins.length - losses.length, winRate: n ? wins.length / n : null, net, gw, gl, pf: gl > 0 ? gw / gl : (gw > 0 ? Infinity : null),
    expR: avg(R), avgWinR: avg(wins.filter(t => t.r != null).map(t => t.r)), avgLossR: avg(losses.filter(t => t.r != null).map(t => t.r)), avgWin: avg(wins.map(t => t.net)), avgLoss: avg(losses.map(t => t.net)),
    best: C.reduce((m, t) => !m || t.net > m.net ? t : m, null), worst: C.reduce((m, t) => !m || t.net < m.net ? t : m, null), dd, ddP, curve, ddc, rc, streakW: bestW, streakL: bestL,
    chg, chgShare: gross > 0 ? chg / gross : null, comply: n ? C.filter(t => !t.brkd).length / n : null, brkCost: C.filter(t => t.brkd).reduce((a, t) => a + t.net, 0),
    good: losses.filter(t => t.lt === 'Good loss').length, bad: losses.filter(t => t.lt === 'Bad loss').length, R };
};
A.group = function (C, keyFn, minN) {
  const m = new Map(); C.forEach(t => { const k = keyFn(t); if (k == null || k === '') return; if (!m.has(k)) m.set(k, []); m.get(k).push(t); });
  return [...m.entries()].map(([k, a]) => { const w = a.filter(t => t.res === 'Win').length, R = a.filter(t => t.r != null).map(t => t.r);
    return { k, n: a.length, win: a.length ? w / a.length : null, avgR: avg(R), net: a.reduce((x, t) => x + t.net, 0), enough: a.length >= (minN || 5) }; }).sort((a, b) => b.net - a.net);
};
const DIMS = [['setup', 'Setup', t => t.setup || 'No setup'], ['cat', 'Segment', t => t.cat], ['grade', 'Grade', t => t.grade || 'No grade'], ['tf', 'Timeframe', t => t.tf || '-'], ['wd', 'Weekday', t => WD[t.wd]],
  ['hr', 'Hour', t => t.hr != null ? String(t.hr).padStart(2, '0') + ':00' : null], ['emo', 'Emotion', t => t.emo || 'Not logged'], ['brk', 'Rule break', t => t.brk || 'None'], ['reg', 'Regime', t => t.reg || 'Not logged'],
  ['evt', 'Event risk', t => t.evt || 'Not logged'], ['xt', 'Exit type', t => t.xt || 'Not logged'], ['dir', 'Direction', t => t.dir], ['src', 'Source', t => t.src]];

A.insights = function (st, C, S) {
  const out = [], minN = S.minN || 5, add = (k, t) => out.push([k, t]);
  if (!st.n) return [['', 'Close a few trades and the insights appear here: what works, what costs you, and how you are improving.']];
  const bySetup = A.group(C, t => t.setup, minN).filter(g => g.enough), byHr = A.group(C, t => t.hr != null ? t.hr : null, minN).filter(g => g.enough), byGr = A.group(C, t => t.grade, 1);
  if (bySetup.length) { const b = bySetup.slice().sort((a, b) => (b.avgR || 0) - (a.avgR || 0))[0], w = bySetup.slice().sort((a, b) => (a.avgR || 0) - (b.avgR || 0))[0];
    add('good', `Your best setup is <b>${esc(b.k)}</b>: ${rr(b.avgR)} per trade over ${b.n} trades, ${Math.round(100 * b.win)}% wins.`);
    if (w.k !== b.k && (w.avgR || 0) < 0) add('bad', `<b>${esc(w.k)}</b> is losing: ${rr(w.avgR)} per trade over ${w.n} trades. Pause it or go back to the rules.`); }
  if (byHr.length > 1) { const w = byHr.slice().sort((a, b) => a.net - b.net)[0]; if (w.net < 0) add('warn', `Your weakest hour is <b>${String(w.k).padStart(2, '0')}:00</b>: ${inrS(w.net)} over ${w.n} trades.`); }
  const ap = byGr.find(g => g.k === 'A+'), b = byGr.find(g => g.k === 'B' || g.k === 'C'); if (ap && b && ap.avgR != null && b.avgR != null) add(ap.avgR > b.avgR ? 'good' : 'warn', `A+ trades average ${rr(ap.avgR)} against ${rr(b.avgR)} for B/C: ${ap.avgR > b.avgR ? 'your grading works, so skip the B setups' : 'your grading is not separating good from bad yet'}.`);
  if (st.brkCost < 0) add('bad', `Rule breaks cost you ${inr(-st.brkCost)} (${C.filter(t => t.brkd).length} trades). Rule compliance ${pct(st.comply, 0)}.`); else if (st.comply === 1 && st.n >= 5) add('good', 'Every closed trade followed your rules. That is the success metric.');
  if (st.chgShare != null && st.chgShare > .25) add('warn', `Charges are ${pct(st.chgShare, 0)} of your gross P&L: trade less often.`);
  const sc = A.group(C, t => t.src, 1), s1 = sc.find(g => g.k === 'Scanner'), s2 = sc.find(g => g.k === 'Own idea'); if (s1 && s2 && s1.avgR != null && s2.avgR != null) add(s1.avgR >= s2.avgR ? 'good' : 'warn', `Scanner trades average ${rr(s1.avgR)} (${s1.n}) against ${rr(s2.avgR)} (${s2.n}) for your own ideas.`);
  const L = st.C.slice(-20), P = st.C.slice(-40, -20); if (L.length >= 10 && P.length >= 10) { const a = avg(L.filter(t => t.r != null).map(t => t.r)), p = avg(P.filter(t => t.r != null).map(t => t.r)); if (a != null && p != null) add(a >= p ? 'good' : 'warn', `Last 20 trades: ${rr(a)} per trade, ${a >= p ? 'up' : 'down'} from ${rr(p)} in the 20 before.`); }
  if (st.bad > st.good && st.losses >= 3) add('bad', `${st.bad} of your ${st.losses} losses are bad losses (rule break or oversized risk), not normal stop-outs.`);
  if (st.avgWinR != null && st.avgLossR != null && st.avgWinR < Math.abs(st.avgLossR)) add('warn', `Winners average ${rr(st.avgWinR)} but losers ${rr(st.avgLossR)}: let winners run to T2 and trail by structure.`);
  return out.length ? out : [['', 'No strong pattern yet. Keep logging grade, emotion and rule breaks: patterns show after about 20 trades.']];
};

const U = () => App.ui.an || (App.ui.an = { period: 'all', cat: 'all', dim: 'setup', calM: null });
App.pages.analytics = () => {
  const u = U(), J = App.journal.J(), S = J.set, all = App.journal.enrich(J), T = App.journal.period(all, u.period).filter(t => u.cat === 'all' || t.cat === u.cat), st = A.stats(T, S), C = st.C;
  const cats = ['all', ...new Set(all.map(t => t.cat).filter(Boolean))];
  let h = `<div class="ph"><div><h1>Analytics</h1><p>How you are really trading: results, risk, edge by setup and time, discipline, and whether you are improving. ${esc(J.name)}.</p></div><span class="sp"></span>${App.ui.seg('aper', App.journal.PERIODS, u.period)}</div>
    <div class="chips" style="margin-bottom:14px">${cats.map(c => `<button class="chip" data-acat="${c}" aria-pressed="${u.cat === c}">${c === 'all' ? 'All segments' : esc(c)}</button>`).join('')}</div>`;
  if (!st.n) return h + `<div class="card"><div class="bd">${App.ui.empty('No closed trades in this view', 'Change the period or segment, or close a trade (add its exit price) in the journal.')}</div></div>`;
  h += `<div class="kpis" style="margin-bottom:14px">${[
    ['Net P&L', inrS(st.net), pct(st.net / (S.capital || 1), 2) + ' of capital', cls(st.net)], ['Win rate', pct(st.winRate, 0), `${st.wins} W · ${st.losses} L · ${st.be} BE`], ['Expectancy', rr(st.expR), 'average R per trade', cls(st.expR)],
    ['Profit factor', st.pf === Infinity ? '∞' : st.pf != null ? st.pf.toFixed(2) : '-', 'gross win / gross loss', st.pf >= 1.5 ? 'good' : st.pf < 1 ? 'bad' : ''], ['Avg win / loss', `${rr(st.avgWinR, 1)} / ${rr(st.avgLossR, 1)}`, `${inr(st.avgWin)} / ${inr(st.avgLoss)}`],
    ['Max drawdown', inr(st.dd), pct(st.ddP, 2) + ' of capital', st.dd < 0 ? 'bad' : ''], ['Streaks', `${st.streakW}W / ${st.streakL}L`, 'longest win / loss run'], ['Rule compliance', pct(st.comply, 0), `${st.C.filter(t => t.brkd).length} trades broke a rule`, st.comply >= .9 ? 'good' : st.comply < .75 ? 'bad' : 'warn'],
    ['Best trade', st.best ? inrS(st.best.net) : '-', st.best ? esc(st.best.inst + ' · ' + st.best.d) : ''], ['Worst trade', st.worst ? inrS(st.worst.net) : '-', st.worst ? esc(st.worst.inst + ' · ' + st.worst.d) : ''],
    ['Good / bad losses', `${st.good} / ${st.bad}`, 'stop-outs vs rule breaks', st.bad > st.good ? 'bad' : ''], ['Charges', inr(st.chg), st.chgShare != null ? pct(st.chgShare, 0) + ' of gross P&L' : '']].map(k => App.ui.kpi(...k)).join('')}</div>`;
  h += `<div class="grid g-main" style="margin-bottom:14px"><div class="card"><div class="hd"><h2>Equity curve</h2><span class="cap">cumulative net P&L, closed trades in order</span></div><div class="bd" id="chEq" data-w></div></div>
    <div class="card"><div class="hd"><h2>Insights</h2></div><div class="bd"><ul class="ins">${A.insights(st, C, S).map(([k, t]) => `<li class="${k}"><i></i><span>${t}</span></li>`).join('')}</ul></div></div></div>`;
  h += `<div class="grid g2" style="margin-bottom:14px"><div class="card"><div class="hd"><h2>Drawdown</h2><span class="cap">distance below the equity peak</span></div><div class="bd" id="chDd" data-w></div></div>
    <div class="card"><div class="hd"><h2>R curve</h2><span class="cap">cumulative R: skill without position size</span></div><div class="bd" id="chR" data-w></div></div></div>`;
  const months = A.group(C, t => t.mkey, 1).sort((a, b) => a.k < b.k ? -1 : 1);
  h += `<div class="grid g2" style="margin-bottom:14px"><div class="card"><div class="hd"><h2>Monthly P&L</h2></div><div class="bd" id="chMo" data-w></div><div class="bd tbl-wrap" style="padding-top:0"><table class="tbl"><thead><tr><th>Month</th><th class="n">Trades</th><th class="n">Win</th><th class="n">Avg R</th><th class="n">Net</th></tr></thead><tbody>${months.slice().reverse().slice(0, 6).map(g => `<tr><td>${MON[+g.k.slice(5) - 1]} ${g.k.slice(0, 4)}</td><td class="n">${g.n}</td><td class="n">${pct(g.win, 0)}</td><td class="n ${cls(g.avgR)}">${rr(g.avgR)}</td><td class="n ${cls(g.net)}">${inrS(g.net)}</td></tr>`).join('')}</tbody></table></div></div>
    <div class="card"><div class="hd"><h2>Calendar</h2><span class="sp"></span>${calNav(C, u)}</div><div class="bd">${calendar(C, u)}</div></div></div>`;
  h += `<div class="grid g2" style="margin-bottom:14px"><div class="card"><div class="hd"><h2>R distribution</h2><span class="cap">how big your wins and losses are, in R</span></div><div class="bd" id="chHist" data-w></div></div>
    <div class="card"><div class="hd"><h2>Progress</h2><span class="cap">rolling 20-trade expectancy (R) and win rate</span></div><div class="bd" id="chRoll" data-w></div><div class="bd legend" style="padding-top:0"><span><i style="background:var(--brand)"></i>Expectancy R</span><span><i style="background:var(--sun)"></i>Win rate (scaled)</span></div></div></div>`;
  const dim = DIMS.find(d => d[0] === u.dim) || DIMS[0], rows = A.group(C, dim[2], S.minN), mx = Math.max(...rows.map(r => Math.abs(r.net)), 1);
  h += `<div class="card" style="margin-bottom:14px"><div class="hd"><h2>Edge finder</h2><span class="cap">patterns need at least ${S.minN} trades (faded rows have fewer)</span></div><div class="hd" style="padding-top:10px"><div class="chips">${DIMS.map(d => `<button class="chip" data-dim="${d[0]}" aria-pressed="${u.dim === d[0]}">${d[1]}</button>`).join('')}</div></div>
    <div class="bd tbl-wrap"><table class="tbl"><thead><tr><th>${dim[1]}</th><th class="n">Trades</th><th class="n">Win rate</th><th class="n">Avg R</th><th class="n">Net P&L</th><th style="min-width:140px"></th></tr></thead><tbody>
    ${rows.map(g => `<tr style="${g.enough ? '' : 'opacity:.55'}"><td><b>${esc(g.k)}</b></td><td class="n">${g.n}</td><td class="n">${pct(g.win, 0)}</td><td class="n ${cls(g.avgR)}">${rr(g.avgR)}</td><td class="n ${cls(g.net)}">${inrS(g.net)}</td><td class="bar-cell">${App.charts.hbar(g.net, mx)}</td></tr>`).join('')}</tbody></table></div></div>`;
  const W = C.filter(t => t.res === 'Win' && t.mfer != null), Lz = C.filter(t => t.res === 'Loss' && t.maer != null), cap = W.filter(t => t.r != null && t.mfer > 0).map(t => Math.min(1, t.r / t.mfer));
  const brkRows = A.group(C.filter(t => t.brkd), t => t.brk, 1);
  h += `<div class="grid g2" style="margin-bottom:14px"><div class="card"><div class="hd"><h2>Discipline</h2></div><div class="bd"><div class="kv">
      <span>Rule compliance</span><b>${pct(st.comply, 0)}</b><span>Cost of rule breaks</span><b class="${cls(st.brkCost)}">${inrS(st.brkCost)}</b><span>Risky emotions (FOMO, revenge, ...)</span><b>${C.filter(t => t.ec === 'Risky').length} trades, ${inrS(C.filter(t => t.ec === 'Risky').reduce((a, t) => a + t.net, 0))}</b>
      <span>Trades over your 1% risk ceiling</span><b>${C.filter(t => t.riskP != null && t.riskP > S.riskC + 1e-5).length}</b><span>Planned R:R under 2</span><b>${C.filter(t => t.prr != null && t.prr < 2).length}</b></div>
      ${brkRows.length ? `<hr class="sep"><table class="tbl"><thead><tr><th>Rule broken</th><th class="n">Trades</th><th class="n">Net</th></tr></thead><tbody>${brkRows.map(g => `<tr><td>${esc(g.k)}</td><td class="n">${g.n}</td><td class="n ${cls(g.net)}">${inrS(g.net)}</td></tr>`).join('')}</tbody></table>` : ''}</div></div>
    <div class="card"><div class="hd"><h2>Execution (MAE / MFE)</h2></div><div class="bd"><div class="kv">
      <span>Winners: best price reached</span><b>${W.length ? rr(avg(W.map(t => t.mfer)), 1) : '-'}</b><span>Winners: share of the move you kept</span><b>${cap.length ? pct(avg(cap), 0) : '-'}</b>
      <span>Losers: worst price before the stop</span><b>${Lz.length ? rr(-avg(Lz.map(t => t.maer)), 1) : '-'}</b><span>Average planned R:R</span><b>${C.filter(t => t.prr != null).length ? avg(C.filter(t => t.prr != null).map(t => t.prr)).toFixed(1) : '-'}</b></div>
      <p class="help" style="margin-top:10px">Log the worst (MAE) and best (MFE) price of each trade to see if stops are too tight or winners are cut early.</p></div></div></div>`;
  h += systemCard(C);
  return h;
};
function calNav(C, u) { const ms = [...new Set(C.map(t => t.mkey))].sort(); if (!u.calM || !ms.includes(u.calM)) u.calM = ms[ms.length - 1]; const i = ms.indexOf(u.calM);
  return `<button class="btn sm" data-cal="${ms[i - 1] || ''}" ${i > 0 ? '' : 'disabled'} aria-label="Previous month">‹</button><b style="min-width:80px;text-align:center">${MON[+u.calM.slice(5) - 1]} ${u.calM.slice(0, 4)}</b><button class="btn sm" data-cal="${ms[i + 1] || ''}" ${i < ms.length - 1 ? '' : 'disabled'} aria-label="Next month">›</button>`; }
function calendar(C, u) {
  const m = u.calM, y = +m.slice(0, 4), mo = +m.slice(5) - 1, first = new Date(Date.UTC(y, mo, 1)), days = new Date(Date.UTC(y, mo + 1, 0)).getUTCDate(), lead = (first.getUTCDay() + 6) % 7, by = {};
  C.filter(t => t.mkey === m).forEach(t => { by[t.d] = by[t.d] || { net: 0, n: 0 }; by[t.d].net += t.net; by[t.d].n++; }); const mx = Math.max(...Object.values(by).map(x => Math.abs(x.net)), 1);
  let h = WD.map(d => `<div class="dh">${d}</div>`).join('') + '<div class="d x"></div>'.repeat(lead);
  for (let d = 1; d <= days; d++) { const k = `${m}-${String(d).padStart(2, '0')}`, x = by[k], a = x ? .15 + .6 * Math.abs(x.net) / mx : 0;
    h += `<div class="d" style="${x ? `background:color-mix(in srgb,${x.net >= 0 ? 'var(--good)' : 'var(--bad)'} ${Math.round(a * 100)}%,var(--panel-2))` : ''}" title="${k}${x ? ': ' + inrS(x.net) + ', ' + x.n + ' trades' : ''}"><span class="muted">${d}</span>${x ? `<b>${Math.abs(x.net) >= 1000 ? (x.net / 1000).toFixed(1) + 'k' : Math.round(x.net)}</b>` : ''}</div>`; }
  return `<div class="heat">${h}</div>`;
}
function systemCard(C) {
  const rows = ['swing', 'options', 'intraday'].map(k => { const L = App.LED(k), c = L.signals.filter(s => s.status === 'CLOSED'), w = c.filter(s => s.r_final > 0).length, tot = c.reduce((a, s) => a + (s.r_final || 0), 0);
    const mine = C.filter(t => t.src === 'Scanner' && t.cat === { swing: 'Swing', options: 'Options', intraday: 'Intraday' }[k]), mr = mine.filter(t => t.r != null).map(t => t.r);
    return `<tr><td><b>${k === 'options' ? 'Nifty options' : k[0].toUpperCase() + k.slice(1)}</b></td><td class="n">${c.length}</td><td class="n">${c.length ? Math.round(100 * w / c.length) + '%' : '-'}</td><td class="n ${cls(tot)}">${c.length ? rr(tot / c.length) : '-'}</td><td class="n">${mine.length}</td><td class="n ${cls(avg(mr))}">${mr.length ? rr(avg(mr)) : '-'}</td></tr>`; }).join('');
  return `<div class="card"><div class="hd"><h2>Signals vs your execution</h2><span class="cap">what the rules made on every signal, and what you made on the ones you took</span></div><div class="bd tbl-wrap"><table class="tbl"><thead><tr><th>Section</th><th class="n">Signals closed</th><th class="n">Win rate</th><th class="n">Avg R (rules)</th><th class="n">You took</th><th class="n">Avg R (you)</th></tr></thead><tbody>${rows}</tbody></table>
    <p class="help" style="margin-top:8px">Signal results assume half at the first target, a quarter at the second and the rest at exit. Closed signals stay listed for 30 days (swing) or 5 days (options and intraday).</p></div></div>`;
}
App.binds.analytics = () => {
  const u = U(), J = App.journal.J(), all = App.journal.enrich(J), T = App.journal.period(all, u.period).filter(t => u.cat === 'all' || t.cat === u.cat), st = A.stats(T, J.set);
  $$('[data-seg="aper"]').forEach(b => b.onclick = () => { u.period = b.dataset.v; App.render(); });
  $$('[data-acat]').forEach(b => b.onclick = () => { u.cat = b.dataset.acat; App.render(); });
  $$('[data-dim]').forEach(b => b.onclick = () => { u.dim = b.dataset.dim; App.render(); });
  $$('[data-cal]').forEach(b => b.onclick = () => { if (b.dataset.cal) { u.calM = b.dataset.cal; App.render(); } });
  if (!st.n) return;
  const draw = () => {
    const w = id => ($('#' + id) || {}).clientWidth - 32 || 600, lab = st.C.map(t => t.d.slice(5));
    const put = (id, svg) => { const el = $('#' + id); if (el) el.innerHTML = svg; };
    put('chEq', App.charts.line([{ pts: st.curve, c: st.net >= 0 ? 'good' : 'bad', area: true }], { W: w('chEq'), H: 220, zero: true, labels: lab, fmt: v => inr(v), label: 'Equity curve' }));
    put('chDd', App.charts.line([{ pts: st.ddc, c: 'bad', area: true }], { W: w('chDd'), H: 170, zero: true, labels: lab, fmt: v => inr(v), label: 'Drawdown' }));
    put('chR', App.charts.line([{ pts: st.rc, c: 'brand', area: true }], { W: w('chR'), H: 170, zero: true, labels: lab, fmt: v => v.toFixed(1) + 'R', label: 'R curve' }));
    const ms = A.group(st.C, t => t.mkey, 1).sort((a, b) => a.k < b.k ? -1 : 1).slice(-12);
    put('chMo', App.charts.bars(ms.map(g => ({ l: MON[+g.k.slice(5) - 1] + ' ' + g.k.slice(2, 4), v: g.net })), { W: w('chMo'), H: 170, fmt: v => inr(v), label: 'Monthly P&L' }));
    const edges = [-Infinity, -2, -1, -.5, 0, .5, 1, 2, 3, Infinity], lbl = ['<-2', '-2..-1', '-1..-.5', '-.5..0', '0..+.5', '+.5..1', '1..2', '2..3', '>3'];
    put('chHist', App.charts.bars(lbl.map((l, i) => ({ l, v: st.R.filter(r => r > edges[i] && r <= edges[i + 1]).length, c: i < 4 ? 'bad' : 'good' })), { W: w('chHist'), H: 170, fmt: v => String(Math.round(v)), label: 'R distribution' }));
    const N = 20, ex = [], wr = []; st.C.forEach((t, i) => { if (i + 1 < Math.min(N, st.C.length)) { ex.push(null); wr.push(null); return; } const s = st.C.slice(Math.max(0, i + 1 - N), i + 1), R = s.filter(x => x.r != null).map(x => x.r);
      ex.push(R.length ? R.reduce((a, b) => a + b, 0) / R.length : null); wr.push(s.filter(x => x.res === 'Win').length / s.length); });
    const sc = Math.max(1, ...ex.filter(isNum).map(Math.abs));
    put('chRoll', App.charts.line([{ pts: ex, c: 'brand' }, { pts: wr.map(v => v == null ? null : (v - .5) * 2 * sc), c: 'sun', w: 1.5 }], { W: w('chRoll'), H: 170, zero: true, labels: lab, fmt: v => v.toFixed(2) + 'R', label: 'Rolling expectancy' }));
  };
  draw(); let t; window.onresize = () => { clearTimeout(t); t = setTimeout(draw, 150); };
};
})();
