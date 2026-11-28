/* DownerStuff: Backtest lab (one view per trading style), the XAUUSD gold lab, Weekly review with the rule-based coach,
   learning from your journal and the tax-ready export. Loaded after the other pages. */
(() => {
const JR = App.journal, kpi = App.ui.kpi, empty = App.ui.empty, callout = App.ui.callout;
const card = (title, body, cap = '', extra = '') => `<div class="card"><div class="hd"><h2>${title}</h2>${cap ? `<span class="cap">${cap}</span>` : ''}${extra}</div><div class="bd">${body}</div></div>`;
const rv = v => isNum(v) ? (v > 0 ? '+' : '') + v.toFixed(2) + 'R' : '-';
const dl = (name, text, type = 'text/csv') => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500); };
const weekStart = s => JR.weekStart(s);
const addDays = (s, n) => { const d = new Date(s + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const csvCell = v => { const s = v == null ? '' : String(v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
const lazyPage = (name, page, maxAge = 600000) => { if (App.lazyAge(name) > maxAge) App.lazy(name, maxAge).then(() => App.soon(page)).catch(() => { }); };

/* ============================== Backtest lab ============================== */
/* One reusable view per style. Stocks: Intraday, Swing, Positional and Nifty options. Gold (XAUUSD): intraday, swing and positional on its own page.
   Every view counts A+ setups only (score 8 to 10), from 1 April 2026, with your rule "a strict 2 trades a day" (even an A+ waits for tomorrow). */
const BT = {
  intraday: { file: 'backtest_intraday', title: 'Intraday', wf: 'backtest-intraday.yml', mins: true, grows: '5-minute history reaches back about 60 days' },
  swing: { file: 'backtest', title: 'Swing', wf: 'backtest.yml' },
  positional: { file: 'backtest_positional', title: 'Positional', wf: 'backtest.yml' },
  options: { file: 'backtest_options', title: 'Nifty options', wf: 'backtest-intraday.yml', mins: true, grows: '5-minute history reaches back about 60 days' },
  gold_intraday: { file: 'backtest_gold_intraday', title: 'Gold intraday', tab: 'Intraday', wf: 'backtest-intraday.yml', mins: true, gold: true, grows: '5-minute history reaches back about 60 days' },
  gold_swing: { file: 'backtest_gold_swing', title: 'Gold swing', tab: 'Swing', wf: 'backtest.yml', gold: true },
  gold_positional: { file: 'backtest_gold_positional', title: 'Gold positional', tab: 'Positional', wf: 'backtest.yml', gold: true } };
const STOCK_TABS = ['intraday', 'swing', 'positional', 'options'], GOLD_TABS = ['gold_intraday', 'gold_swing', 'gold_positional'];
const ruleName = r => (String(r).startsWith('lux') ? 'LuxAlgo order block' : 'old order block') + (String(r).endsWith('+v2') ? ' · updated strategy' : ' · previous strategy');
const SCN = { all: ['every A+ signal', 'var(--ink-3)', 1.6], ap: ['your rules', 'var(--brand)', 2.6], ap2: ['old rule: A+ extras', 'var(--sun)', 1.8], p10: ['perfect 10', 'var(--good)', 1.8] };
const BT_LEGACY = [['grade', 'By grade', '', 'Grade'], ['score', 'By score', '', 'Score /10'], ['regime', 'By market regime', 'the regime on the day before entry', 'Regime'], ['confirm', 'By confirmation', 'rejection, 9 EMA reclaim, volume', 'Confirmation'],
  ['volume', 'By volume on the confirmation', '', 'Relative volume'], ['zone', 'By zone quality', '', 'Zone'], ['context', 'By context', 'key level, fib, MTF EMA', 'Context ticks'], ['stop', 'By stop width', '', 'Stop'], ['weekday', 'By weekday of entry', '', 'Day'], ['sector', 'By sector', 'largest 14', 'Sector'], ['month', 'By month', 'month the trade closed', 'Month']];
const btSeg = () => { const s = App.ui.btseg || 'swing'; return STOCK_TABS.includes(s) ? s : 'swing'; };
const goldSeg = () => { const s = App.ui.goldseg || 'gold_intraday'; return GOLD_TABS.includes(s) ? s : 'gold_intraday'; };
const btTabs = (tabs, seg, attr) => `<div class="seg" role="tablist" aria-label="Trading style" style="margin-bottom:14px">${tabs.map(k => `<button type="button" role="tab" aria-selected="${k === seg}" aria-pressed="${k === seg}" ${attr}="${k}">${BT[k].tab || BT[k].title}</button>`).join('')}</div>`;
const statTable = (title, rows, cap, first = '') => !rows || !rows.length ? '' : card(title, `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${first}</th><th class="n">Trades</th><th class="n">Win</th><th class="n">Avg R</th><th class="n">Profit factor</th><th class="n">Total R</th></tr></thead><tbody>
  ${rows.map(r => `<tr><td><b>${esc(r.k)}</b></td><td class="n">${r.n}</td><td class="n">${r.win == null ? '-' : r.win + '%'}</td><td class="n ${cls(r.avg)}">${rv(r.avg)}</td><td class="n">${r.pf == null ? '-' : r.pf}</td><td class="n ${cls(r.total)}">${rv(r.total)}</td></tr>`).join('')}</tbody></table></div>`, cap);
const holdText = (S, seg) => BT[seg].mins ? (S.avg_hold_min == null ? '-' : S.avg_hold_min + ' min') : (S.avg_hold_days == null ? '-' : S.avg_hold_days + ' d');
const OUT = (seg, o) => ({ TARGET: 'T3 reached', TRAIL: 'Trailing stop', SL: 'Stop-loss', EXPIRED: BT[seg].mins ? 'Squared off' : 'Expired' })[o] || o || '';

/* gold lot size: XAUUSD 1 standard lot = 100 ounces, so a 1-dollar move is 100 dollars a lot. Settings stay on this device. */
const GS = () => Object.assign({ acct: 10000, risk: 0.5, riskA: 0.75 }, store.get('ds_gold_v1', {}) || {});
const lotsCell = v => { const l = goldLots(v); return !isNum(v) ? '-' : l >= 0.01 ? l.toFixed(2) : '<span class="bad" title="Even 0.01 lot risks more than your A+ risk: skip it or wait for a tighter setup">too wide</span>'; };
const goldLots = (stopUsd, aplus = true) => { const g = GS(), riskD = g.acct * (aplus ? g.riskA : g.risk) / 100; return stopUsd > 0 ? Math.floor(riskD / (stopUsd * 100) * 100) / 100 : 0; };

function forwardTest(B, seg) {
  const led = seg === 'swing' ? 'swing' : seg === 'intraday' ? 'intraday' : null;
  if (!led) return card('Live forward test', `<p class="help" style="margin:0">${seg === 'options' ? 'Live option signals are tracked on the index, and this backtest measures the option premium, so the two cannot be compared one to one. Judge the options playbook by the Journal once you have logged option trades.' : BT[seg].gold ? 'Gold is not scanned live yet (it trades mostly outside the Indian market loop\'s hours). Judge it by the Journal once you log gold trades.' : 'This style is not tracked live yet.'}</p>`, 'is the live scanner behaving like the backtest?');
  const live = App.LED(led).signals.filter(s => s.status === 'CLOSED' && isNum(s.r_final) && (s.score || 0) >= 8), n = live.length;
  if (!n) return card('Live forward test', empty('No tracked A+ ' + led + ' trade has closed yet', 'Every setup the scanner triggers is tracked with the same rules. As A+ trades close, this card compares them with the backtest.'), 'is the live scanner behaving like the backtest?');
  const avg = live.reduce((a, s) => a + s.r_final, 0) / n, win = 100 * live.filter(s => s.r_final > 0).length / n, b = B.summary.gross;
  const verdict = n < 20 ? ['info', `Only ${n} live A+ trade${n > 1 ? 's' : ''} so far. Fewer than 20 says very little: keep tracking before you judge.`]
    : avg >= b.avg - 0.25 ? ['good', 'Live results are in line with the backtest (or better).'] : ['warn', 'Live results are clearly below the backtest. That can be bad luck over a small sample, or a market regime the backtest saw little of.'];
  return card('Live forward test', `<div class="kpis">${kpi('Live A+ trades closed', n)}${kpi('Live win rate', win.toFixed(0) + '%', `backtest ${b.win}%`)}${kpi('Live average', rv(avg), `backtest ${rv(b.avg)} before costs`, cls(avg))}</div><div style="height:10px"></div>${callout(verdict[0], verdict[1])}`, 'tracked A+ signals against the backtest');
}

/* The trade log of one style: the trades your rules took (default) or every A+ signal, newest first, 25 at a time. */
const LOGU = () => (App.ui.btlog = App.ui.btlog || { mode: 'rules', n: 25 });
function tradeLog(B, seg) {
  const u = LOGU(), ap = (B.scenarios || []).find(r => r.key === 'ap'), rules = ap && ap.log ? ap.log : null, mode = rules && u.mode === 'rules' ? 'rules' : 'all';
  const rows = (mode === 'rules' ? rules : (B.trades || [])).slice().reverse(), shown = rows.slice(0, u.n), gold = BT[seg].gold;
  const name = t => seg === 'options' && t.strike ? `${t.sym} ${t.strike} ${t.side === 'short' ? 'PE' : 'CE'}` : t.sym;
  const head = `<th>${seg === 'options' ? 'Option' : gold ? 'Gold' : 'Stock'}</th><th>Entry (IST)</th><th>Exit</th><th class="n">Score</th>${gold ? '<th class="n">Stop</th><th class="n">Lots*</th>' : ''}<th>Result</th><th class="n">R net</th>${mode === 'rules' ? '<th class="n">Account</th>' : ''}`;
  const tr = t => `<tr><td><b>${esc(name(t))}</b> <small class="muted">${t.side === 'short' ? 'short' : gold || seg === 'options' ? 'long' : ''} ${esc(t.sector || '')}</small></td><td class="nw"><small>${esc(sd(t.entry_t))}</small></td><td class="nw"><small>${esc(sd(t.exit_t))}${t.hold_min != null ? ' · ' + t.hold_min + ' min' : t.hold_days != null ? ' · ' + t.hold_days + 'd' : ''}</small></td>
    <td class="n">${t.score}</td>${gold ? `<td class="n">${isNum(t.risk_usd) ? '$' + t.risk_usd.toFixed(2) : '-'}</td><td class="n">${lotsCell(t.risk_usd)}</td>` : ''}<td class="nw"><small>${esc(OUT(seg, t.outcome))}</small></td><td class="n ${cls(t.r_net)}">${rv(t.r_net)}</td>${mode === 'rules' ? `<td class="n ${cls(t.pnl_pct)}">${isNum(t.pnl_pct) ? sg(t.pnl_pct) + '%' : '-'}</td>` : ''}</tr>`;
  const seg2 = rules ? App.ui.seg('btlog', [['rules', `Taken with your rules ${rules.length}`], ['all', `Every A+ signal ${(B.trades || []).length}`]], mode) : '';
  const open = (B.open_now || []).length ? `<p class="help" style="margin-top:10px">Still open when the run ended (not counted): ${B.open_now.map(t => `<b>${esc(t.sym)}</b> ${esc(t.entry_t.slice(5))}`).join(' · ')}</p>` : '';
  return card('Trade log', `${seg2 ? `<div style="margin-bottom:10px">${seg2}</div>` : ''}${rows.length ? `<div class="tbl-wrap" style="max-height:560px;overflow:auto"><table class="tbl"><thead><tr>${head}</tr></thead><tbody>${shown.map(tr).join('')}</tbody></table></div>
    <div style="display:flex;gap:8px;align-items:center;margin-top:10px;flex-wrap:wrap"><small class="muted">Showing ${shown.length} of ${rows.length}, newest first</small><span style="flex:1"></span>${rows.length > shown.length ? '<button class="btn sm" type="button" id="btMore">Show 25 more</button>' : ''}<button class="btn sm ghost" type="button" id="btCsv">${ic('download')} CSV</button></div>
    ${gold ? `<p class="help" style="margin-top:8px">*Lots for your gold settings (${inr0usd(GS().acct)} account, ${GS().riskA}% risk on A+): risk ÷ (stop in dollars × 100 ounces). Change them in the Lot size card.</p>` : ''}` : empty('No trades in this view yet', '')}${open}`, mode === 'rules' ? 'the trades your rules would have taken' : 'every A+ signal, before your rules');
}
const sd = t => { const s = String(t || ''); return s.length >= 16 ? `${+s.slice(8, 10)} ${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][+s.slice(5, 7) - 1]} ${s.slice(11, 16)}` : s; };
const inr0usd = v => '$' + Math.round(v).toLocaleString('en-US');

/* 18 Nov 2026: evidence is reported by window, never pooled. Development = in-sample (the hold-backs were chosen on it); validation and
   out-of-sample are the only independent evidence. Paper trades are their own category, per frozen strategy version. */
function evidenceCard(B) {
  const E = B.evaluation; if (!E || !E.windows) return '';
  const row = (k, w) => `<tr><td><b>${esc(w.label)}</b><br><small class="muted">${esc(w.bounds[0] || '')} to ${esc(w.bounds[1] || 'now')}</small></td><td><span class="pill ${w.untouched ? 'ok' : w.independent ? 'info' : 'warn'}">${w.untouched ? 'untouched' : w.independent ? 'independent of hold-backs' : 'in-sample'}</span></td><td class="n">${w.taken.n}</td><td class="n">${w.taken.win == null ? '-' : w.taken.win + '%'}</td><td class="n ${cls(w.taken.avg)}">${rv(w.taken.avg)}</td><td class="n">${w.taken.pf == null ? '-' : w.taken.pf}</td><td class="n ${cls(w.held.avg)}">${w.held.n ? rv(w.held.avg) + ' <small class="muted">(' + w.held.n + ')</small>' : '-'}</td></tr>`;
  const wf = (B.walk_forward || []).map(x => `<tr><td>${esc(x.test_from)} to ${esc(x.test_to)}</td><td><small>${esc(x.window.replace('_', ' '))}</small></td><td class="n">${x.n}</td><td class="n ${cls(x.avg)}">${rv(x.avg)}</td><td class="n">${x.pf == null ? '-' : x.pf}</td></tr>`).join('');
  return card('Evidence by window', `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Window</th><th></th><th class="n">Taken</th><th class="n">Win</th><th class="n">Avg R</th><th class="n">PF</th><th class="n">Held back, avg R</th></tr></thead><tbody>${['validation', 'development', 'out_of_sample'].map(k => row(k, E.windows[k])).join('')}</tbody></table></div>
    <p class="help" style="margin-top:8px">${esc(E.note)} Strategy version ${esc(E.version || '-')} frozen ${esc(E.frozen_at || '-')}. Windows were fixed on 18 Nov 2026, before any validation run. If held-back trades do as well as taken ones in the independent windows, the hold-backs were fitted to noise.</p>
    ${wf ? `<details style="margin-top:8px"><summary>Walk-forward: the frozen rules, 3 months at a time (no re-fitting)</summary><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Test window</th><th>Kind</th><th class="n">Trades</th><th class="n">Avg R</th><th class="n">PF</th></tr></thead><tbody>${wf}</tbody></table></div></details>` : ''}`, 'never pooled into one number') + '<div style="height:14px"></div>';
}
function paperCard(seg) {
  const led = { swing: 'swing', intraday: 'intraday', options: 'options' }[seg] || (seg.startsWith('gold') ? 'gold_' + seg.slice(5) : null); if (!led) return '';
  const L = seg.startsWith('gold') ? (App.lazyNow('signals_' + led) || {}) : App.LED(led), P = (L.paper || []).filter(p => !p.futures_based);
  if (!P.length) return card('Paper trading', empty('No paper trade has closed yet', 'Every trigger the live scan takes is recorded with its sealed original signal, the frozen strategy version and the costs assumed. Results appear here, apart from any backtest.'), 'separate from backtests') + '<div style="height:14px"></div>';
  const by = {}; P.forEach(p => { (by[p.strategy_version || 'unknown'] = by[p.strategy_version || 'unknown'] || []).push(p); });
  return card('Paper trading', `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Strategy version</th><th class="n">Closed</th><th class="n">Win</th><th class="n">Avg R net</th><th class="n">Total R net</th></tr></thead><tbody>${Object.entries(by).map(([v, a]) => { const r = a.map(p => p.r_net != null ? p.r_net : p.r_gross).filter(isNum), n = r.length; return `<tr><td><b>${esc(v)}</b>${a.some(p => p.rules_frozen === false) ? ' <small class="warn">rules changed during it</small>' : ''}</td><td class="n">${a.length}</td><td class="n">${n ? Math.round(100 * r.filter(x => x > 0).length / n) + '%' : '-'}</td><td class="n ${cls(n ? r.reduce((x, y) => x + y, 0) / n : 0)}">${n ? rv(r.reduce((x, y) => x + y, 0) / n) : '-'}</td><td class="n">${n ? rv(r.reduce((x, y) => x + y, 0)) : '-'}</td></tr>`; }).join('')}</tbody></table></div>
    <p class="help" style="margin-top:8px">${seg === 'options' ? 'Options paper trades are measured on the index (R on index levels); premium costs are not modelled.' : 'Net of the same cost allowance as the backtest.'} Each version is judged on its own trades only. Fewer than 30 trades says little.</p>`, 'live signals, frozen rules, separate from backtests') + '<div style="height:14px"></div>';
}

/* The whole view of one style. */
function labView(seg) {
  const M = BT[seg], B = App.lazyNow(M.file);
  if (!B || !B.summary) return App.lazyAge(M.file) === Infinity ? App.ui.skel(3) : `<div class="card"><div class="bd">${empty( 'No ' + M.title.toLowerCase() + ' backtest yet', `It runs every Saturday. To run it now, open <a href="${App.actionsUrl()}/workflows/${M.wf}" target="_blank" rel="noopener">GitHub → ${M.wf.replace('.yml', '')} → Run workflow</a>. ${M.mins ? 'It takes about 10 to 30 minutes.' : 'It takes 30 to 90 minutes.'} This page fills in when it finishes.`)}</div></div>`;
  const s = B.summary.net, g = B.summary.gross, S = B.summary, mc = B.montecarlo || {}, o = S.outcomes || {}, W = B.window || {}, AC = B.account || {}, RU = B.rules || {}, small = !!M.grows;
  if (M.gold && !isSpot((B.params || {}).source)) return `<div class="card"><div class="bd">${callout('warn', '<b>Historical futures-based analysis (COMEX GC=F), not XAUUSD spot.</b> This saved result was made before 18 Nov 2026 from gold FUTURES. It is excluded from XAUUSD statistics and not shown as one. The next gold backtest (Saturday, or GitHub → ' + esc(M.wf.replace('.yml', '')) + ' → Run workflow) replays XAUUSD spot and archives this file unchanged.')}</div></div>`;
  const what = seg === 'options' ? 'Nifty 50 index' : M.gold ? goldInst() : `${B.universe} most liquid Nifty 500 stocks${['swing', 'positional'].includes(seg) ? ', long only' : ''}`;
  const EV = B.evaluation || {}, ver = EV.version || (B.params || {}).strategy_version;
  let h = `<div style="display:flex;gap:6px;flex-wrap:wrap;margin:-4px 0 12px"><span class="pill ver" title="Every number on this page comes from this frozen version of your rules">Strategy v${esc(ver || '?')}${EV.frozen_at ? ' · frozen ' + esc(EV.frozen_at) : ''}</span><span class="pill ${M.gold ? 'gold' : 'info'}">${esc(RU.text || 'all grades')}</span>${(B.params || {}).rule ? `<span class="pill" title="Which rules produced these trades">${esc(ruleName((B.params || {}).rule))}</span>` : ''}<span class="pill">${AC.max_per_day || 2} a day${AC.aplus_overflow !== false ? ', more only if A+' : ''}</span><span class="pill">${esc(W.from || '')} to ${esc(W.to || '')}</span><span class="pill">${what}</span><span class="pill">run ${esc(dateIST(B.generated_at))} · ${esc(ago(B.generated_at))}</span></div>`;
  if (!RU.text) h += callout('warn', '<b>This result is from an older run</b> that counted every grade and all history. The next run (or Actions → backtest → quick) shows A+ only from 1 April 2026.') + '<div style="height:10px"></div>';
  if (seg === 'options') h += callout('bad', '<b>THEORETICAL SIMULATION, not historical trading performance.</b> No real option prices were available: the index signals are real, the premiums are Black-Scholes estimates on the previous day\'s India VIX held constant. These numbers cannot prove an options edge and are never combined with price-verified results.') + (B.methodology ? card('How each number was made', `<div class="tbl-wrap"><table class="tbl"><tbody>${B.methodology.map(m => `<tr><td><b>${esc(m.item)}</b></td><td><span class="pill ${m.used ? 'warn' : ''}">${m.used ? 'used' : 'not used'}</span></td><td><small>${esc(m.how)}</small></td></tr>`).join('')}</tbody></table></div>`, 'sources and limits') : '') + '<div style="height:10px"></div>';
  if (small) h += callout('info', `<b>Starts small, grows every Saturday</b> (${s.n} A+ trades so far): a hint, not a verdict yet.`) + '<div style="height:10px"></div>';
  if (seg === 'positional' || seg === 'gold_positional') h += callout('info', '<b>Positional trades last weeks to months (up to 120 days),</b> so a window that starts on 1 April has few finished trades and many still open. Judge positional over a longer window too: set the repo variable <code>BACKTEST_FROM</code> to <code>all</code> and run quick mode.') + '<div style="height:10px"></div>';
  if (seg === 'positional') h += callout('info', `<b>Positional rules are my reading of your playbook,</b> not rules you gave me (see "How to read this"). If yours differ, tell me and I will change the engine.`) + '<div style="height:10px"></div>';
  h += `<div class="sec-h" style="margin-top:4px"><h2>Every A+ signal</h2><small class="muted">no daily limit, no risk rules: the engine's raw edge</small></div><div class="kpis" style="margin-bottom:14px">${kpi('Trades', s.n, M.mins ? `about ${Math.round(S.trades_per_year / 252 * 10) / 10} a trading day` : `about ${Math.round(S.trades_per_year)} a year`)}${kpi('Win rate', s.win == null ? '-' : s.win + '%', `win ${rv(s.avg_win)} · loss ${rv(s.avg_loss)}`)}${kpi('Expectancy', rv(s.avg), `after costs · ${rv(g.avg)} before`, cls(s.avg))}
    ${kpi('Profit factor', s.pf == null ? '-' : s.pf, 'wins ÷ losses', s.pf == null ? '' : s.pf >= 1 ? 'good' : 'bad')}${kpi('Max drawdown', s.max_dd + 'R', `longest losing run ${s.streak}`)}${kpi('Average hold', holdText(S, seg), `${o.TARGET || 0} T3 · ${o.SL || 0} stopped`)}</div>`;
  const verdict = s.n < 50 ? ['warn', `<b>Only ${s.n} A+ trades in this window.</b> That is too few to trust any number on this page.${small ? ' It grows every week.' : ''}`]
    : s.avg >= 0.2 ? ['good', `<b>A+ setups had a positive edge after costs:</b> ${rv(s.avg)} per trade over ${s.n} trades. Expect losing runs of about ${mc.streak_p50 || s.streak} trades in a normal year.`]
    : s.avg > 0 ? ['info', `<b>A thin edge after costs:</b> ${rv(s.avg)} per trade. At this level costs and slippage decide the result.`]
    : ['bad', `<b>Every A+ signal together lost money after costs in this window:</b> ${rv(s.avg)} per trade. A+ alone is not the edge here: see "With your rules" and the tables below for where the loss sits.`];
  h += callout(seg === 'options' ? 'info' : verdict[0], seg === 'options' ? `<b>Simulated result:</b> ${rv(s.avg)} per trade over ${s.n} modelled trades. Judge the options playbook by paper trades with real quotes, not by this.` : verdict[1] + ' <small class="muted">(development window: in-sample)</small>') + '<div style="height:14px"></div>' + evidenceCard(B) + paperCard(seg);
  const SC = B.scenarios || [], CV = B.scenario_curves || {};
  const notTaken = r => !r.rules ? 'none: every trade taken' : `${r.skipped.day_cap} over the daily limit · ${r.skipped.open_cap} over open risk · ${r.skipped.loss_limit} stopped by loss limits${r.aplus_extra ? ` · <b>${r.aplus_extra} A+ extras</b> taken past 2 a day` : ''}`;
  const scRow = r => `<tr${r.key === 'ap' ? ' class="hl"' : ''}><td><b>${esc(r.name)}</b></td><td class="n">${r.n}<br><small class="muted">${r.per_year} a year</small></td><td class="n">${r.win == null ? '-' : r.win + '%'}</td><td class="n ${cls(r.avg)}">${rv(r.avg)}</td><td class="n">${r.pf == null ? '-' : r.pf}</td>
    <td class="n ${cls(r.ret)}">${r.n ? sg(r.ret) + '%' : '-'}${r.cagr != null ? `<br><small class="muted">${sg(r.cagr)}% a year</small>` : ''}</td><td class="n">${r.n ? '-' + r.max_dd + '%' : '-'}</td><td class="n">${r.streak}</td><td><small class="muted">${notTaken(r)}</small></td></tr>`;
  const mine = SC.find(r => r.key === 'ap');
  if (SC.length) h += card('With your rules', `${App.ui.chips([`${AC.max_per_day} a day, strict${AC.aplus_overflow ? ', more only if A+ (old rule on)' : ''}`, `A+ risk ${AC.risk_aplus}%`, `Open risk cap ${AC.open_cap}%`, `Stop at −${AC.day_stop}% day · −${AC.week_stop}% week · −${AC.month_stop}% month`, `Half size at −${AC.month_half}% month`].concat(AC.stop_after_losses ? [`Done after ${AC.stop_after_losses} losers`] : []))}<div style="height:10px"></div>
    <div class="tbl-wrap"><table class="tbl"><thead><tr><th>View</th><th class="n">Trades</th><th class="n">Win</th><th class="n">Avg R</th><th class="n">Profit factor</th><th class="n">Account</th><th class="n">Max drawdown</th><th class="n">Worst run</th><th>Not taken</th></tr></thead><tbody>${SC.map(scRow).join('')}</tbody></table></div>
    ${(CV.labels || []).length > 2 ? `<div style="margin-top:12px"><div id="btSc"></div><div style="display:flex;gap:14px;flex-wrap:wrap;margin-top:6px">${SC.filter(r => SCN[r.key]).map(r => `<span class="help" style="margin:0"><b style="color:${SCN[r.key][1]}">&#9632;</b> ${SCN[r.key][0]}</span>`).join('')}</div></div>` : '<p class="help" style="margin-top:8px">The account curve appears once the trades span more than two months.</p>'}
    ${mine ? `<div style="height:10px"></div>${callout(mine.n < 30 ? 'warn' : mine.avg > 0.05 ? 'good' : mine.avg > -0.05 ? 'info' : 'bad', mine.n < 30 ? `<b>Only ${mine.n} trades with your rules.</b> Too few to judge: a couple of lucky or unlucky trades move the result.` : `<b>With your rules:</b> ${mine.n} trades, ${rv(mine.avg)} per trade after costs, ${sg(mine.ret)}% on the account with a worst fall of -${mine.max_dd}%.`)}` : ''}`,
    'the P&L of the way you trade', `<span class="sp"></span><span class="pill info">quick re-run: Actions &gt; backtest &gt; quick</span>`) + '<div style="height:14px"></div>';
  const order = (B.by_order && B.by_order.length) ? B.by_order : BT_LEGACY.filter(x => (B.by || {})[x[0]]).map(x => ({ key: x[0], title: x[1], cap: x[2], first: x[3] })), tbl = x => statTable(x.title, (B.by || {})[x.key], x.cap, x.first);
  h += `<div class="grid g-main" style="margin-bottom:14px"><div class="stack">${card('Equity curve', '<div id="btEq"></div>', 'every A+ signal, running total in R after costs')}${order.slice(0, 3).map(tbl).join('')}</div>
    <div class="stack">${forwardTest(B, seg)}
    ${card('What a year can look like', mc.sims ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Risk per trade</th><th class="n">Typical year</th><th class="n">Bad year</th><th class="n">Good year</th><th class="n">Typical drawdown</th><th class="n">Bad drawdown</th><th class="n">Losing year</th></tr></thead><tbody>
      ${Object.entries(mc.risks).map(([k, r]) => `<tr><td><b>${k}%</b></td><td class="n ${cls(r.ret_p50)}">${sg(r.ret_p50)}%</td><td class="n ${cls(r.ret_p5)}">${sg(r.ret_p5)}%</td><td class="n ${cls(r.ret_p95)}">${sg(r.ret_p95)}%</td><td class="n">-${r.dd_p50}%</td><td class="n bad">-${r.dd_p95}%</td><td class="n">${r.losing_year}%</td></tr>`).join('')}</tbody></table></div>
      <p class="help" style="margin-top:8px">${mc.sims.toLocaleString()} simulated years of ${mc.trades_per_year} trades, drawn at random from these A+ results. "Bad" is the worst 1 year in 20. Expect a losing run of about <b>${mc.streak_p50}</b> trades in a normal year and <b>${mc.streak_p95}</b> in a bad one. The window is under a year, so treat this as rough.</p>` : empty('Not enough trades to simulate', mc.note || ''), 'Monte Carlo')}
    ${B.split ? card('Did it hold up over time? (in-sample)', `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Period</th><th class="n">Trades</th><th class="n">Win</th><th class="n">Avg R</th><th class="n">Profit factor</th></tr></thead><tbody>
      ${[['First 60% of the window', B.split.train], ['Last 40% (most recent)', B.split.test]].map(([n, r]) => `<tr><td><b>${n}</b></td><td class="n">${r.n}</td><td class="n">${r.win == null ? '-' : r.win + '%'}</td><td class="n ${cls(r.avg)}">${rv(r.avg)}</td><td class="n">${r.pf == null ? '-' : r.pf}</td></tr>`).join('')}</tbody></table></div>
      <p class="help" style="margin-top:8px">Both halves are inside the window the 18 Nov 2026 hold-backs were chosen on, so this is NOT an independent test. See "Evidence by window".</p>`) : ''}
    ${S.held_back && S.held_back.n ? card('Your hold-back rules', `<p style="margin:0">Trades your rules held back (weekly trend against, less than 2R of room, a stop under 7%, a weak zone, 1H volume under 2x, or a Mixed market) averaged <b class="${cls(S.held_back.avg)}">${rv(S.held_back.avg)}</b> over ${S.held_back.n} trades, against <b class="${cls(s.avg)}">${rv(s.avg)}</b> for the trades taken. <b>This comparison proves nothing on its own:</b> the hold-backs were chosen by looking at these same trades (in-sample), so the held-back ones are worse here by construction. Whether they really help shows only in the validation and out-of-sample windows (card "Evidence by window").</p>`) : ''}</div></div>`;
  if ((B.variants || []).length) { const vb = B.variant_base || { all: B.base, train: (B.split || {}).train || {}, test: (B.split || {}).test || {} };
    h += card('Would a different rule have been better?', `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Rule</th><th class="n">Trades</th><th class="n">Avg R, all</th><th class="n">First 60%</th><th class="n">Last 40%</th><th>Verdict</th></tr></thead><tbody>
      <tr><td><b>Your current rules</b><br><small class="muted">${String((B.params || {}).rule || '').endsWith('+v2') ? 'volume above its 20-bar average' : (B.params || {}).holdbacks ? '1.5x volume to confirm (2x to take it), stop 7% or more, zone 2/2, no Mixed market' : '1.5x volume'}, 0.25 ATR stop buffer</small></td><td class="n">${vb.all.n}</td><td class="n ${cls(vb.all.avg)}">${rv(vb.all.avg)}</td><td class="n">${rv(vb.train.avg)}</td><td class="n">${rv(vb.test.avg)}</td><td><span class="pill info">baseline</span></td></tr>
      ${B.variants.map(v => `<tr><td><b>${esc(v.name)}</b><br><small class="muted">${esc(v.desc)}</small></td><td class="n">${v.all.n}</td><td class="n ${cls(v.all.avg)}">${rv(v.all.avg)}</td><td class="n">${rv(v.train.avg)}</td><td class="n">${rv(v.test.avg)}</td><td><span class="pill ${v.better ? 'ok' : 'info'}">${v.better ? 'Better in both halves' : 'Keep your rule'}</span></td></tr>`).join('')}</tbody></table></div>
      <p class="help" style="margin-top:8px">A variant is only called better when it beats your rule in <b>both</b> halves of the window with at least 20 recent trades. Tested on the ${(B.params || {}).variant_universe || 120} most liquid stocks.</p>`, 'one change at a time') + '<div style="height:14px"></div>'; }
  const rest = order.slice(3).map(tbl).join('');
  if (rest) h += `<div class="grid g2x" style="margin-bottom:14px">${rest}</div>`;
  h += `<div class="grid g-main"><div class="stack">${tradeLog(B, seg)}</div><div class="stack">${card('How to read this', `<ul class="ins">${(B.assumptions || []).map(a => `<li><i></i><span>${esc(a)}</span></li>`).join('')}</ul>`, 'what the replay does and does not include')}</div></div>`;
  return h;
}
function labBind(seg, page) {
  const M = BT[seg]; lazyPage(M.file, page);
  const B = App.lazyNow(M.file); if (!B) return;
  $$('[data-seg="btlog"]').forEach(b => b.onclick = () => { LOGU().mode = b.dataset.v; LOGU().n = 25; App.render(); });
  if ($('#btMore')) $('#btMore').onclick = () => { LOGU().n += 25; App.render(); };
  if ($('#btCsv')) $('#btCsv').onclick = () => { const ap = (B.scenarios || []).find(r => r.key === 'ap'), rules = LOGU().mode === 'rules' && ap && ap.log, rows = rules ? ap.log : (B.trades || []);
    dl(`${M.file}-${rules ? 'your-rules' : 'all-aplus'}.csv`, '\ufeff' + [['Symbol', 'Side', 'Score', 'Entry time', 'Exit time', 'Entry', 'Stop', 'Outcome', 'R net', rules ? 'Account %' : 'Hold'].join(','),
      ...rows.map(t => [t.sym, t.side || 'long', t.score, t.entry_t, t.exit_t, t.entry, t.sl, t.outcome, t.r_net, rules ? t.pnl_pct : (t.hold_min != null ? t.hold_min + ' min' : (t.hold_days != null ? t.hold_days + ' d' : ''))].map(csvCell).join(','))].join('\n')); App.toast('Trade log downloaded'); };
  const sc = $('#btSc'), CV = B.scenario_curves;
  if (sc && CV && (CV.labels || []).length > 2) sc.innerHTML = App.charts.line(['all', 'p10', 'ap2', 'ap'].filter(k => CV.series[k]).map(k => ({ pts: CV.series[k], c: SCN[k][1], w: SCN[k][2] })), { W: sc.clientWidth || 640, H: 220, labels: CV.labels, fmt: v => v.toFixed(0), label: 'Account value with each set of rules, starting at 100' });
  const el = $('#btEq'); if (!el || !(B.equity || []).length) return;
  const draw = () => { el.innerHTML = App.charts.line([{ pts: [0].concat(B.equity.map(x => x[1])), c: B.summary.net.total >= 0 ? 'good' : 'bad', area: true }], { W: el.clientWidth || 640, H: 230, zero: true, labels: [B.equity[0][0]].concat(B.equity.map(x => x[0])), fmt: v => v.toFixed(0) + 'R', label: 'Backtest equity curve in R' }); };
  draw();
}

App.pages.backtest = () => {
  const seg = btSeg();
  return `<div class="ph"><div><h1>Backtest lab</h1><p>Each style replayed with the live engine. Evidence, not a promise.</p>${App.ui.chips(['A+ only · 8 to 10', 'From 1 Apr 2026', 'Your rules: a strict 2 a day'])}</div><span class="sp"></span><a class="btn sm gold-btn" href="#/gold">XAUUSD Gold lab</a></div>` + btTabs(STOCK_TABS, seg, 'data-btseg') + labView(seg);
};
App.binds.backtest = () => {
  $$('[data-btseg]').forEach(b => b.onclick = () => { App.ui.btseg = b.dataset.btseg; LOGU().n = 25; App.render(); });
  labBind(btSeg(), 'backtest');
};

/* ============================== XAUUSD gold ============================== */

/* ---------- live gold: what the gold loop found (every 5 minutes through every session), and the trades it is tracking ---------- */
const GOLD_LIVE = ['gold', 'signals_gold_intraday', 'signals_gold_swing', 'signals_gold_positional', 'health/gold_loop'];
/* XAUUSD spot only (18 Nov 2026): anything not from the verified spot source is historical futures-based analysis. */
const SPOT_ID = 'spot:Twelve Data:XAU/USD', isSpot = s => s === SPOT_ID;
const goldInst = () => 'Instrument: XAUUSD Spot · quote currency USD · USD per troy ounce · Spot Gold · data: Twelve Data XAU/USD (verified spot)';
const GSTY = { intraday: 'Intraday', swing: 'Swing', positional: 'Positional' }, GTF = { intraday: '5 MINS', swing: '1 HOUR', positional: 'Daily' };
const gnum = v => isNum(v) ? v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '-';
const gside = d => `<span class="tag ${d === 'short' ? 'short' : 'long'}">${d === 'short' ? 'SHORT' : 'LONG'}</span>`;
/* gold sessions in IST (winter times; London and New York move an hour earlier in their summer): Asia 04:30-13:30, London 13:30-22:00, New York 18:30-03:30 (items 43, 129, 275) */
const GSESS = [['asia', 'Asia', 270, 810], ['london', 'London', 810, 1320], ['ny', 'New York', 1110, 1650]];
const gSessAt = mins => GSESS.filter(([, , a, b]) => (mins >= a && mins < b) || (mins + 1440 >= a && mins + 1440 < b)).map(x => x[0]);
function goldSessions() { const t = istNow(), m = t.getUTCHours() * 60 + t.getUTCMinutes(), on = gSessAt(m), x = v => ((v - 240) % 1440) / 1440 * 100;
  return `<div class="gsess" aria-label="Gold sessions now"><div class="gs-track">${GSESS.map(([k, l, a, b]) => `<span class="gs-seg ${k}${on.includes(k) ? ' on' : ''}" style="left:${x(a)}%;width:${(b - a) / 1440 * 100}%">${l}</span>`).join('')}<i class="gs-now" style="left:${x(m < 240 ? m + 1440 : m)}%"></i></div>
    <small class="muted">${on.length ? 'Now: ' + on.map(k => GSESS.find(g => g[0] === k)[1]).join(' + ') : 'Between sessions'} · times in IST</small></div>`; }
/* gold 5-minute chart with session shading, day high/low and round numbers (129, 130, 178, 179) */
function goldChart(G) { const c = G.chart; if (!c || !c.candles || !c.candles.length) return '';
  const day = c.times[c.times.length - 1].slice(0, 10), tod = c.candles.filter((_, i) => c.times[i].startsWith(day)), dh = Math.max(...tod.map(x => x[1])), dl = Math.min(...tod.map(x => x[2])), last = c.candles[c.candles.length - 1][3];
  const rnd = Math.round(last / 50) * 50, near = Math.abs(last - rnd) / last < .001, lv = [{ p: dh, c: 'good', dash: 1, label: 'Day H', k: 2, w: 1 }, { p: dl, c: 'bad', dash: 1, label: 'Day L', k: 2, w: 1 }];
  if (near) lv.push({ p: rnd, c: 'sun', dash: 1, label: 'Round ' + rnd, k: 2, w: 1, why: 'Price is within 0.1% of a round number. Gold often pauses at these.' });
  const opens = GSESS.map(([k, l, a]) => { const hh = String(Math.floor(a % 1440 / 60)).padStart(2, '0') + ':' + String(a % 60).padStart(2, '0'); const i = c.times.findIndex(t => t.startsWith(day) && t.slice(11, 16) === hh); return i >= 0 ? { i, p: c.candles[i][0], label: l + ' open', c: 'ink3', below: true } : null; }).filter(Boolean);
  const sess = t => { const mm = +t.slice(11, 13) * 60 + +t.slice(14, 16), s = gSessAt(mm); return s.includes('ny') ? 'ny' : s.includes('london') ? 'london' : s.includes('asia') ? 'asia' : 'off'; };
  const W = Math.min(1100, (document.querySelector('#page') || { clientWidth: 900 }).clientWidth - 60);
  return card('XAUUSD 5-minute', App.charts.candles(c, { id: 'gold:5m', W, levels: lv, marks: opens, sessions: sess, noVolNote: 'Spot gold has no exchange volume, so there is no volume panel.', volume: true, label: 'XAUUSD 5-minute chart', head: `XAUUSD 5m · ${gnum(last)} USD/oz`, frame: { title: 'XAUUSD 5-minute', sub: 'Spot gold · ' + dateIST(new Date()) },
    onAlert: p => { App.journal.addAlert('XAUUSD', p, last); App.toast('Gold alert set at ' + gnum(p) + '. It fires while the app is open.'); App.render(); }, onNote: p => { const t = prompt('Note at ' + gnum(p)); if (t) { App.journal.addNote('XAUUSD', p, t); App.render(); } } }), 'Asia · London · New York shaded') + '<div style="height:14px"></div>'; }
/* the gold volume-rule decision: recorded in your journal, never applied by the tool on its own (item 20) */
function goldDecision(G, nHeld) { const J = App.journal.J(), dcs = (J.decisions || {}).gold_volume;
  return card('Your decision: the gold volume rule', `<p class="help" style="margin:0 0 10px">${nHeld} A+ trigger${nHeld === 1 ? '' : 's'} withheld recently because XAUUSD spot has no volume. Choose what you want; nothing changes in the scanner until you apply it yourself.</p>
    <div class="grid g2"><div class="opt ${dcs && dcs.choice === 'keep' ? 'on' : ''}"><b>Keep the rule</b><p class="help">Your strategy stays exactly as frozen. Gold stays mostly empty because the volume condition can never pass on spot.</p><button class="btn sm" type="button" data-gdec="keep">Choose this</button></div>
    <div class="opt ${dcs && dcs.choice === 'new-version' ? 'on' : ''}"><b>Approve a new strategy version for gold</b><p class="help">Gold triggers on price action only (the 9 EMA close), with no volume condition. This is a strategy change: it gets its own frozen version and a backtest first.</p><button class="btn sm" type="button" data-gdec="new-version">Choose this</button></div></div>
    ${dcs ? `<p class="help" style="margin-top:10px"><b>Recorded ${esc(String(dcs.at).slice(0, 10))}:</b> ${dcs.choice === 'keep' ? 'keep the volume rule. Nothing to do.' : 'new version wanted. To apply it: ask for "gold volume rule off as a new frozen version", run the gold backtest, and only after you are happy set the repository variable GOLD_VOLUME_RULE=off (GitHub → Settings → Secrets and variables → Actions → Variables).'}</p>` : ''}`, 'needs you'); }
function goldLive() {
  const G = App.lazyNow('gold'), hb = App.lazyNow('health/gold_loop'), wf = `${App.actionsUrl()}/workflows/gold-loop.yml`;
  if (!G && App.lazyAge('gold') === Infinity) return App.ui.skel(2);
  if (!G) return card('Live gold', empty('No live gold scan yet', `The gold loop scans every 5 minutes through every session, Sunday night to Friday night. It starts on its own schedule, or open <a href="${wf}" target="_blank" rel="noopener">GitHub → gold-loop → Run workflow</a>.`), 'A+ setups, long and short') + '<div style="height:14px"></div>';
  const age = (Date.now() - new Date(G.generated_at)) / 6e4, stale = G.market_open && age > 12, L = s => { const x = App.lazyNow('signals_gold_' + s) || { signals: [] }; return { signals: (x.signals || []).filter(z => !z.futures_based) }; };
  const FUT = Object.keys(GSTY).reduce((n, k) => n + ((App.lazyNow('signals_gold_' + k) || {}).signals || []).filter(z => z.futures_based).length, 0);
  if (!isSpot(G.source)) return card('Live gold', callout('warn', '<b>This gold scan is from the old futures feed (COMEX GC=F).</b> It is not shown. The next run of the gold loop scans XAUUSD spot.'), 'XAUUSD spot only') + '<div style="height:14px"></div>';
  let h = `<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px"><span class="pill ${G.market_open ? 'gold' : ''}"><i></i>${G.market_open ? 'Gold open · ' + esc(G.session) : 'Gold market closed'}</span>
    <span class="pill" title="${esc(goldInst())}">XAUUSD Spot ${gnum(G.price)} <small class="muted">&nbsp;USD/oz</small></span><span class="pill ${stale ? 'bad' : ''}">${stale ? `<a href="${wf}" target="_blank" rel="noopener">scan ${Math.round(age)} min old: start the loop</a>` : 'scanned ' + esc(ago(G.generated_at))}</span>
    ${G.feed && G.feed.last_5m ? `<span class="pill ${G.market_open && G.feed.lag_min > 12 ? 'bad' : ''}" title="${G.feed.lag_min > 12 ? 'The free gold feed is running late, so triggers show up late too' : 'The newest 5-minute gold candle the feed had at the last scan'}">5-min candle ${esc(ago(G.feed.last_5m))}</span>` : ''}<span class="pill ${G.open_now >= G.max_open ? 'warn' : ''}">open ${G.open_now} of ${G.max_open}</span><span class="pill">${G.trades_today} today · past ${G.max_day} only A+</span>${G.market_open && !G.entry_window ? '<span class="pill warn">no new intraday entries until 04:00 IST</span>' : ''}</div>`;
  h += goldSessions() + `<details class="ginfo"><summary>Instrument and data source</summary><p class="help">${esc(goldInst())}${G.volume ? ' · volume: ' + esc(G.volume.note) : ''}${FUT ? ` · ${FUT} older trade(s) from the futures feed are archived and excluded` : ''}</p></details>`;
  h += goldChart(G);
  if (G.feed && G.feed.ok === false) h += callout('bad', `<b>XAUUSD SPOT DATA UNAVAILABLE: NO GOLD RECOMMENDATION.</b> ${esc(G.feed.reason || '')}. Nothing is scanned or opened until verified spot data is back; there is no futures fallback.`) + '<div style="height:14px"></div>';
  const rows = []; Object.keys(GSTY).forEach(k => ((G.styles || {})[k] || {}).setups && G.styles[k].setups.forEach(x => rows.push(Object.assign({ style: k }, x))));
  rows.sort((a, b) => (b.status === 'TRIGGERED') - (a.status === 'TRIGGERED') || b.score - a.score); App.ui._gl = rows;
  const st = x => x === 'TRIGGERED' ? '<span class="pill ok">TRIGGERED</span>' : x.startsWith('TRIGGERED') ? `<span class="pill warn" title="${esc(x)}">not taken</span>` : x.startsWith('HELD') ? `<span class="pill warn" title="${esc(x)}">held back</span>` : `<small class="muted">${esc(x)}</small>`;
  h += card('A+ setups now', rows.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Style</th><th>Side</th><th>Status</th><th class="n">Score</th><th class="n">Entry</th><th class="n">Stop</th><th class="n">T1</th><th class="n">T2</th><th class="n">T3</th><th class="n">Stop $</th><th class="n">Lots A+</th><th></th></tr></thead><tbody>
    ${rows.map((x, i) => `<tr><td><b>${GSTY[x.style]}</b></td><td>${gside(x.direction)}</td><td class="nw">${st(x.status)}</td><td class="n">${x.score}</td><td class="n">${gnum(x.entry)}</td><td class="n bad">${gnum(x.sl)}</td><td class="n good">${gnum(x.t1)}</td><td class="n good">${gnum(x.t2)}</td><td class="n good">${gnum(x.t3)}</td><td class="n">$${gnum(x.risk_usd)}</td><td class="n">${lotsCell(x.risk_usd)}</td><td><button class="btn sm" type="button" data-glog="${i}">Log</button></td></tr>`).join('')}</tbody></table></div>
    ${rows.some(x => x.status.startsWith('TRIGGERED (')) ? `<p class="help" style="margin-top:8px">Not taken: ${rows.filter(x => x.status.startsWith('TRIGGERED (')).map(x => esc(GSTY[x.style] + ' ' + x.direction + ': ' + x.status.slice(11, -1))).join(' · ')}</p>` : ''}` : empty('No A+ gold setup right now', 'Waiting is part of the plan.'), 'long and short, A+ only', `<span class="sp"></span><a class="btn sm ghost" href="https://www.tradingview.com/chart/?symbol=OANDA%3AXAUUSD" target="_blank" rel="noopener">${ic('ext')} TradingView</a>`) + '<div style="height:14px"></div>';
  /* Triggers that fired but were withheld because spot gold has no volume. Display only: the rule is unchanged. */
  const lowv = x => String((x && x.status) || '').includes('low volume'), held = Object.keys(GSTY).flatMap(k => (((App.lazyNow('signals_gold_' + k) || {}).dropped) || []).filter(lowv).map(x => Object.assign({ style: k }, x))).sort((a, b) => (b.first_seen || '') < (a.first_seen || '') ? -1 : 1);
  if (held.length || rows.some(lowv)) h += `<div style="height:14px"></div>` + card('Triggers withheld: no volume on spot gold',  `<p class="help" style="margin:0 0 10px">${rows.filter(lowv).length ? `<b>${rows.filter(lowv).length} right now.</b> ` : ''}${held.length} A+ setup${held.length === 1 ? '' : 's'} reached the trigger candle recently and ${held.length === 1 ? 'was' : 'were'} not shown as a trade. Your rule needs the trigger on 1.5x volume, and XAUUSD spot has no exchange volume, so it can never pass. This is why gold looks empty although setups formed. Nothing here was taken or tracked.</p>
    ${held.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>First seen (IST)</th><th>Style</th><th>Side</th><th class="n">Score</th><th class="n">Entry</th><th class="n">Stop</th><th>What happened next</th></tr></thead><tbody>${held.slice(0, 12).map(x => `<tr><td class="nw"><small>${esc(String(x.first_seen || '').replace('T', ' ').slice(5, 16))}</small></td><td>${GSTY[x.style]}</td><td>${gside(x.direction)}</td><td class="n">${x.score}</td><td class="n">${gnum(x.entry)}</td><td class="n bad">${gnum(x.sl)}</td><td><small class="muted">${esc(x.reason || '')}</small></td></tr>`).join('')}</tbody></table></div>` : ''}
    <p class="help" style="margin-top:10px"><b>Your decision, not mine:</b> turning the volume rule off for gold (GOLD_VOLUME_RULE=off) would change your strategy, so it needs a new frozen strategy version and your approval. Until then these stay withheld.</p>`, 'live and last few days').replace('<div class="card', '<div class="card withheld');
  h += `<div style="height:14px"></div>` + goldDecision(G, held.length);
  const WHY = Object.keys(GSTY).flatMap(k => { const w = ((G.styles || {})[k] || {}).why || {}; return ['long', 'short'].filter(sd => w[sd]).map(sd => [GSTY[k], sd, w[sd]]); });
  if (WHY.length && !rows.some(x => x.status === 'TRIGGERED')) h += `<div style="height:14px"></div>` + card('Why no trade now', `<div class="kv gwhy">${WHY.map(([s, sd, tx]) => `<span>${s} ${sd}</span><b>${esc(tx)}</b>`).join('')}</div><p class="help" style="margin-top:8px">A+ is 8 to 10 out of 10. It is normal for gold to wait: the engines are strict and the backtests show only a few A+ setups a week.</p>`, 'what each side is waiting for') + `<div style="height:14px"></div>`;
  const sig = Object.keys(GSTY).flatMap(k => L(k).signals.map(s => Object.assign({ style: k }, s))), act = sig.filter(s => s.status === 'ACTIVE'), done = sig.filter(s => s.status === 'CLOSED').sort((a, b) => (b.closed || '') < (a.closed || '') ? -1 : 1).slice(0, 10);
  const tm = t => esc(String(t || '').replace('T', ' ').slice(5, 16));
  h += `<div class="grid g-main" style="margin-bottom:14px"><div class="stack">${card('Tracked gold trades', act.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Style</th><th>Side</th><th>Opened</th><th class="n">Entry</th><th class="n">Stop now</th><th class="n">Last</th><th class="n">R now</th></tr></thead><tbody>
      ${act.map(s => `<tr><td><b>${GSTY[s.style]}</b></td><td>${gside(s.direction)}</td><td class="nw"><small>${tm(s.created)}</small></td><td class="n">${gnum(s.entry)}</td><td class="n">${gnum(s.stop)}${s.stop !== s.sl ? ' <small class="muted">moved</small>' : ''}</td><td class="n">${gnum(s.last)}</td><td class="n ${cls(s.r_now)}">${rv(s.r_now)}</td></tr>`).join('')}</tbody></table></div>` : empty('Nothing open', 'Triggers are tracked here: half off at T1, a quarter at T2.'), 'the loop follows them; you place the orders')}</div>
    <div class="stack">${card('Closed gold trades', done.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Style</th><th>Side</th><th>Closed</th><th>Result</th><th class="n">R</th></tr></thead><tbody>
      ${done.map(s => `<tr><td><b>${GSTY[s.style]}</b></td><td>${gside(s.direction)}</td><td class="nw"><small>${tm(s.closed)}</small></td><td><small>${esc(OUT('gold_' + s.style, s.outcome))}</small></td><td class="n ${cls(s.r_final)}">${rv(s.r_final)}</td></tr>`).join('')}</tbody></table></div>` : empty('No closed gold trades yet', ''), 'last 10')}</div></div>`;
  return h;
}
/* the gold trading day as a 24-hour band from 04:00 IST, with the sessions and a marker for now */
function goldClock() {
  const B = [['Asia', 4, 12.5, 'a'], ['London', 12.5, 17.5, 'b'], ['Overlap', 17.5, 21.5, 'c'], ['New York', 21.5, 24.5, 'b'], ['No new entries', 24.5, 26, 'd'], ['Closed', 26, 28, 'e']];
  const ist = new Date(Date.now() + 5.5 * 3600e3), hr = ist.getUTCHours() + ist.getUTCMinutes() / 60, x = ((hr - 4 + 24) % 24) / 24 * 100;
  const cur = B.find(b => { const h = hr < 4 ? hr + 24 : hr; return h >= b[1] && h < b[2]; });
  const lbl = h => { const v = h % 24; return String(Math.floor(v)).padStart(2, '0') + ':' + (v % 1 ? '30' : '00'); };
  return `<div class="gclock"><div class="gc-band">${B.map(([n, s, e, k]) => `<span class="gc-${k}" style="left:${((s - 4) / 24 * 100).toFixed(2)}%;width:${((e - s) / 24 * 100).toFixed(2)}%" title="${n} ${lbl(s)} to ${lbl(e)}"><em>${k === 'e' || k === 'd' ? '' : n}</em></span>`).join('')}<i class="gc-now" style="left:${x.toFixed(2)}%"></i></div>
    <div class="gc-ticks">${[4, 8, 12, 16, 20, 24, 28].map(h => `<span style="left:${((h - 4) / 24 * 100).toFixed(2)}%">${lbl(h)}</span>`).join('')}</div>
    <div class="gc-now-t">Now ${String(ist.getUTCHours()).padStart(2, '0')}:${String(ist.getUTCMinutes()).padStart(2, '0')} IST · <b>${cur ? cur[0] : ''}</b>${cur && cur[0] === 'Overlap' ? ' · usually the busiest' : ''}</div>
    <div class="gc-leg"><span><i class="gc-c"></i>Overlap 17:30 to 21:30</span><span><i class="gc-d"></i>Entries stop 00:30</span><span><i class="gc-e"></i>Square-off 02:00</span></div></div>`;
}
App.pages.gold = q => {
  if (q && q.get && GOLD_TABS.includes(q.get('s'))) App.ui.goldseg = q.get('s');
  const seg = goldSeg(), g = GS(), B = App.lazyNow(BT[seg].file), last = B && (B.trades || []).slice(-1)[0];
  let h = `<div class="gold-zone"><div class="ph gold-head"><div><h1><span class="gold-coin" aria-hidden="true">Au</span>XAUUSD Gold</h1><p>Live every 5 minutes, every session · long and short · you place the orders.</p>${App.ui.chips(['A+ only', 'Intraday · swing · positional', 'Max 2 open', 'A strict 2 a day', 'Entries 04:00 to 00:30 IST', 'Square-off 02:00'])}</div></div>`;
  h += `<div class="sec-h" style="margin-top:4px"><h2>Live</h2><small class="muted">every 5 minutes, every session, Sunday night to Friday night</small></div>` + goldLive();
  h += `<div class="grid g-main" style="margin-bottom:14px"><div class="stack">${card('Sessions in IST', goldClock() + `<p class="help" style="margin-top:10px">Summer hours (about April to October); in winter London and New York open about an hour later. The backtest uses fixed UTC hours.</p>`, 'when the loop takes intraday trades')}</div>
    <div class="stack">${card('Lot size', `<div class="fields"><div class="field"><label for="gAcct">Account ($)</label><input id="gAcct" type="number" inputmode="decimal" min="0" step="100" value="${g.acct}"></div><div class="field"><label for="gRisk">Risk per trade (%)</label><input id="gRisk" type="number" inputmode="decimal" min="0" step="0.05" value="${g.risk}"></div><div class="field"><label for="gRiskA">A+ risk (%)</label><input id="gRiskA" type="number" inputmode="decimal" min="0" step="0.05" value="${g.riskA}"></div><div class="field"><label for="gStop">Stop distance ($ per oz)</label><input id="gStop" type="number" inputmode="decimal" min="0" step="0.1" value="${last && isNum(last.risk_usd) ? last.risk_usd : 5}"></div></div>
      <div class="kv" style="margin-top:10px" id="gOut"></div><p class="help" style="margin-top:8px">1 lot = 100 oz · lots = risk ÷ (stop × 100) · never widen the stop to fit size · saved on this device.</p>`, 'from your gold account and risk')}</div></div>`;
  h += `<div class="sec-h" style="margin-top:8px"><h2>Backtests</h2><small class="muted">the same engines on past gold data</small></div>` + btTabs(GOLD_TABS, seg, 'data-goldseg') + labView(seg) + '</div>';
  return h;
};
App.binds.gold = () => {
  $$('[data-gdec]').forEach(b => b.onclick = () => { const J = App.journal.J(); J.decisions = J.decisions || {}; J.decisions.gold_volume = { choice: b.dataset.gdec, at: new Date().toISOString() }; App.journal.touch(); App.journal.persist(); App.toast('Decision recorded. The scanner is unchanged until you apply it.'); App.render(); });
  $$('[data-goldseg]').forEach(b => b.onclick = () => { App.ui.goldseg = b.dataset.goldseg; LOGU().n = 25; App.render(); });
  const calc = () => { const v = id => +($('#' + id) || {}).value || 0, acct = v('gAcct'), risk = v('gRisk'), riskA = v('gRiskA'), stop = v('gStop'), out = $('#gOut'); if (!out) return;
    const lots = r => stop > 0 ? Math.floor(acct * r / 100 / (stop * 100) * 100) / 100 : 0, L = lots(risk), LA = lots(riskA);
    out.innerHTML = `<span>Risk budget</span><b>${inr0usd(acct * risk / 100)} <small class="muted">A+ ${inr0usd(acct * riskA / 100)}</small></b><span>Lots</span><b>${L.toFixed(2)} <small class="muted">A+ ${LA.toFixed(2)}</small></b><span>Loss at the stop</span><b class="bad">${inr0usd(L * stop * 100)} <small class="muted">A+ ${inr0usd(LA * stop * 100)}</small></b>${LA > 0 && LA < 0.01 ? '' : L === 0 && stop > 0 ? '<span></span><b class="bad">Stop too wide for this risk: even 0.01 lot risks more. Skip it.</b>' : ''}`;
    if (acct > 0) store.set('ds_gold_v1', { acct, risk, riskA }); };
  ['gAcct', 'gRisk', 'gRiskA', 'gStop'].forEach(id => { const i = $('#' + id); if (i) i.oninput = calc; });
  ['gAcct', 'gRisk', 'gRiskA'].forEach(id => { const i = $('#' + id); if (i) i.onchange = () => App.render(); });
  $$('[data-glog]').forEach(btn => btn.onclick = () => { const x = (App.ui._gl || [])[+btn.dataset.glog]; if (!x) return;
    App.journal.openForm(null, { inst: 'XAUUSD', cat: 'Commodity', setup: 'Pullback from OB', tf: GTF[x.style], dir: x.direction === 'short' ? 'Short' : 'Long', grade: x.grade, entry: x.entry, sl: x.sl, tgt: x.t2,
      note: `DS:${x.section}|XAUUSD|${x.direction}|${x.bos_date} | ${x.score}/10 ${x.grade} | gold ${x.style}, XAUUSD spot (USD per troy ounce): edit to your broker's XAUUSD fill; enter quantity in ounces and P&L in rupees` }); });
  GOLD_LIVE.forEach(n => { if (App.lazyAge(n) > 60000) App.lazy(n, 60000).then(() => App.soon('gold')).catch(() => { }); });
  clearInterval(App._goldT); App._goldT = setInterval(() => { if (App.route().page !== 'gold') { clearInterval(App._goldT); return; }
    if (!document.hidden && !$('.modal-bg') && !(document.activeElement && /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName))) Promise.all(GOLD_LIVE.map(n => App.lazy(n, 0))).then(() => App.soon('gold')); }, 60000);
  calc(); labBind(goldSeg(), 'gold');
};
/* Dashboard card: one line per gold style, from the last runs (loads in the background). */
App.goldCard = () => {
  const rows = GOLD_TABS.map(k => [k, App.lazyNow(BT[k].file)]);
  GOLD_TABS.forEach(k => { if (App.lazyAge(BT[k].file) > 600000) App.lazy(BT[k].file, 600000).then(() => App.soon('dashboard')).catch(() => { }); });
  const line = ([k, B]) => { const ap = B && (B.scenarios || []).find(r => r.key === 'ap'), s = B && B.summary && B.summary.net;
    return `<tr class="click" data-href="#/gold?s=${k}"><td><b>${BT[k].tab}</b></td><td class="n">${s ? s.n : '-'}${s && B.summary.held_back && B.summary.held_back.n ? ` <small class="muted" title="A+ setups your hold-back rules kept you out of">+${B.summary.held_back.n} held</small>` : ''}</td><td class="n ${s ? cls(s.avg) : ''}">${s ? rv(s.avg) : '-'}</td><td class="n ${ap ? cls(ap.ret) : ''}">${ap && ap.n ? sg(ap.ret) + '%' : '-'}</td></tr>`; };
  return `<div class="card gold-card"><div class="hd"><h2><span class="gold-coin sm" aria-hidden="true">Au</span>XAUUSD Gold</h2><span class="cap">live scan and A+ backtests</span><span class="sp"></span><a class="btn sm gold-btn" href="#/gold">Open</a></div><div class="bd">${(() => { const G = App.lazyNow('gold'); if (App.lazyAge('gold') > 120000) App.lazy('gold', 120000).then(() => App.soon('dashboard')).catch(() => { });
      if (!G) return ''; const n = Object.values(G.styles || {}).reduce((a, x) => a + ((x && x.setups) || []).filter(s => s.status === 'TRIGGERED').length, 0);
      return `<p class="help" style="margin:0 0 10px"><b>Live:</b> ${G.market_open ? esc(G.session) : 'market closed'} · XAUUSD ${gnum(G.price)} · ${n} A+ trigger${n === 1 ? '' : 's'} · ${G.open_now} of ${G.max_open} open · scanned ${esc(ago(G.generated_at))}</p>`; })()}<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Backtest</th><th class="n">A+ trades</th><th class="n">Avg R</th><th class="n">Your rules</th></tr></thead><tbody>${rows.map(line).join('')}</tbody></table></div></div></div>`;
};

/* ============================== Weekly review, coach, learning, tax ============================== */
function coach(t, S) {
  const L = []; let tone = 'good'; const bad = m => { L.push(m); tone = 'bad'; }, warn = m => { L.push(m); if (tone === 'good') tone = 'warn'; };
  if (t.sl == null) bad('No stop-loss recorded. Every trade needs one before entry.');
  if (t.riskP != null && t.riskP > S.riskC + 1e-5) bad(`Risked ${pct(t.riskP, 2)} of capital, above your ${pct(S.riskC, 2)} ceiling.`);
  if (t.brkd) bad(`Rule break logged: ${t.brk}.`);
  if (t.chk && t.chk.skipped && t.chk.skipped.length) warn(`Entered with ${t.chk.skipped.length} checklist rule${t.chk.skipped.length > 1 ? 's' : ''} unticked: ${t.chk.skipped.slice(0, 2).join('; ')}${t.chk.skipped.length > 2 ? '…' : ''}.`);
  if (t.didx > S.maxIntra) bad(`Trade number ${t.didx} that day was past your limit of ${S.maxIntra} a day: strict, even an A+ waits for tomorrow.`);
  if (t.closed && t.r != null) {
    if (t.r < -1.15) bad(`Lost ${rv(t.r)}, more than the planned 1R: the stop was moved, skipped or slipped.`);
    else if (t.res === 'Loss' && tone === 'good') L.push(`A ${rv(t.r)} loss inside the plan. If the setup was valid, this is a good loss.`);
    if (t.res === 'Win' && t.prr != null && t.r < Math.min(1, t.prr * 0.5)) warn(`Closed at ${rv(t.r)} when the plan was ${t.prr.toFixed(1)}R: profit taken early.`);
    if (t.res === 'Win' && t.r >= 2) L.push(`${rv(t.r)}: you let it run.`);
  }
  if (t.mfer != null && t.r != null && t.mfer >= 2 && t.r < 0.5) warn(`It went ${t.mfer.toFixed(1)}R in your favour and closed at ${rv(t.r)}: review the exit (half at T1, a quarter at T2 with the stop to entry).`);
  if (t.grade === 'B') warn('B-grade setup: your plan is to observe these, not trade them.'); else if (!t.grade) warn('No grade recorded: grade every trade before entry.');
  if (t.ec === 'Risky') warn(`Emotion logged: ${t.emo}.`);
  if (t.evt === 'Yes') warn('Taken with event risk nearby (results or a major event).');
  if (!L.length) L.push('Followed the plan: graded setup, risk inside your limits, no rule break.');
  return { tone, lines: L };
}
function oneThing(T, S) {
  const cats = [['Rule breaks', t => t.brkd], ['Skipped checklist rules', t => t.chk && t.chk.skipped && t.chk.skipped.length], ['Losses bigger than 1R', t => t.r != null && t.r < -1.15], ['B-grade or ungraded trades', t => t.grade === 'B' || !t.grade],
    ['Trades taken in a risky emotional state', t => t.ec === 'Risky'], ['Profit taken early', t => t.res === 'Win' && t.prr != null && t.r != null && t.r < Math.min(1, t.prr * 0.5)], ['Oversized trades', t => t.riskP != null && t.riskP > S.riskC + 1e-5]];
  const rows = cats.map(([n, f]) => { const x = T.filter(f); return { n, c: x.length, net: x.reduce((a, t) => a + (t.net || 0), 0) }; }).filter(r => r.c);
  rows.sort((a, b) => a.net - b.net || b.c - a.c); return rows;
}
function scannerLearning(all) {
  const X = all.filter(t => t.closed && t.r != null && /DS:/.test(t.note || '')).map(t => { const m = (t.note || '').match(/\|\s*(\d+)\/10\s+(A\+|A|B)/), tk = ((t.note || '').split('|')[2] || ''); return { r: t.r, score: m ? +m[1] : null, key: /Key level/.test(tk), fib: /Fib/.test(tk), ema: /MTF EMA/.test(tk) }; });
  if (X.length < 5) return card('What your own trades say about the scorecard', empty(`${X.length} of 5 closed scanner trades`, 'Log trades from a setup (Log trade on its page) and close them. After five, this card shows which scores and context ticks have actually worked for you.'), 'learning from your journal');
  const st = a => ({ n: a.length, win: a.length ? Math.round(100 * a.filter(x => x.r > 0).length / a.length) : null, avg: a.length ? a.reduce((s, x) => s + x.r, 0) / a.length : null });
  const rows = [['Score 8 to 10 (A+)', X.filter(x => x.score >= 8)], ['Score 6 to 7 (A)', X.filter(x => x.score >= 6 && x.score < 8)], ['Score 4 to 5 (B)', X.filter(x => x.score != null && x.score < 6)],
    ['With a key level', X.filter(x => x.key)], ['Without a key level', X.filter(x => !x.key)], ['With fib 0.618', X.filter(x => x.fib)], ['Without fib 0.618', X.filter(x => !x.fib)], ['With MTF EMA', X.filter(x => x.ema)], ['Without MTF EMA', X.filter(x => !x.ema)]].map(([k, a]) => [k, st(a)]).filter(r => r[1].n);
  return card('What your own trades say about the scorecard', `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Your scanner trades</th><th class="n">Trades</th><th class="n">Win</th><th class="n">Avg R</th></tr></thead><tbody>${rows.map(([k, s]) => `<tr><td><b>${k}</b></td><td class="n">${s.n}</td><td class="n">${s.win}%</td><td class="n ${cls(s.avg)}">${rv(s.avg)}</td></tr>`).join('')}</tbody></table></div>
    <p class="help" style="margin-top:8px">All time, ${X.length} closed trades logged from the scanner. Small groups (under 10 trades) are a hint, not a finding: compare with the Backtest lab.</p>`, 'learning from your journal');
}
/* Tax-ready P&L (item 24). Financial year April to March. */
const fyOf = d => { const y = +d.slice(0, 4), m = +d.slice(5, 7); return m >= 4 ? y : y - 1; };
const taxClass = t => /(\bCE\b|\bPE\b|FUT)/i.test(t.inst || '') || t.cat === 'Options' ? 'F&O' : t.cat === 'Intraday' ? 'Intraday equity' : 'Delivery equity';
function taxRows(all, fy) {
  const T = all.filter(t => t.closed && t.net != null && fyOf(t.d) === fy), B = { 'Intraday equity': { head: 'Speculative business income', n: 0, net: 0, turn: 0, chg: 0 }, 'F&O': { head: 'Non-speculative business income', n: 0, net: 0, turn: 0, chg: 0 }, 'Delivery equity': { head: 'Capital gains (short-term assumed for swing trades)', n: 0, net: 0, turn: 0, chg: 0 } };
  T.forEach(t => { const k = taxClass(t), b = B[k]; b.n++; b.net += t.net; b.chg += t.chg || 0; b.turn += k === 'Delivery equity' ? (t.exit != null && t.q ? t.exit * t.q : 0) : Math.abs(t.gross != null ? t.gross : t.net); });
  return { T, B };
}
function taxCsv(all, fy) {
  const { T, B } = taxRows(all, fy), L = [[`DownerStuff tax P&L, financial year ${fy}-${String(fy + 1).slice(2)}`], ['Prepared from your journal. Confirm the classification and turnover method with your tax adviser.'], [],
    ['Section', 'Tax head', 'Trades', 'Net P&L (after charges)', 'Turnover', 'Charges'], ...Object.entries(B).map(([k, b]) => [k, b.head, b.n, b.net.toFixed(2), b.turn.toFixed(2), b.chg.toFixed(2)]),
    [], ['Turnover method: intraday and F&O = sum of the absolute profit and loss of each trade; delivery = sale value.'], [],
    ['Date', 'Instrument', 'Section', 'Direction', 'Quantity', 'Entry', 'Exit', 'Gross P&L', 'Charges', 'Net P&L', 'Turnover counted']];
  T.forEach(t => { const k = taxClass(t); L.push([t.d, t.inst, k, t.dir, t.q, t.entry, t.exit, t.gross != null ? t.gross.toFixed(2) : '', (t.chg || 0).toFixed(2), t.net.toFixed(2), (k === 'Delivery equity' ? (t.exit != null && t.q ? t.exit * t.q : 0) : Math.abs(t.gross != null ? t.gross : t.net)).toFixed(2)]); });
  return L.map(r => r.map(csvCell).join(',')).join('\n');
}

const RU = () => (App.ui.rvw = App.ui.rvw || { wk: weekStart(todayIST()), fy: fyOf(todayIST()) });
App.pages.review = () => {
  const u = RU(), J = JR.J(), S = J.set, all = JR.enrich(J), T = all.filter(t => t.wk === u.wk), C = T.filter(t => t.closed && t.net != null), end = addDays(u.wk, 4), cur = u.wk === weekStart(todayIST());
  let h = `<div class="ph"><div><h1>Weekly review</h1><p>Results, rules kept and the one fix for next week · ${esc(J.name)}</p></div><span class="sp"></span>
    <div style="display:flex;gap:6px;align-items:center"><button class="btn sm" type="button" id="rvPrev">← Earlier</button><b style="white-space:nowrap">${esc(u.wk.slice(5))} to ${esc(end.slice(5))}</b><button class="btn sm" type="button" id="rvNext" ${cur ? 'disabled' : ''}>Later →</button></div></div>`;
  if (!T.length) h += `<div class="card" style="margin-bottom:14px"><div class="bd">${empty('No trades logged in this week', 'Use Earlier to look at another week, or log trades in the journal.')}</div></div>`;
  else {
    const net = C.reduce((a, t) => a + t.net, 0), rs = C.filter(t => t.r != null), rsum = rs.reduce((a, t) => a + t.r, 0), wins = C.filter(t => t.res === 'Win').length, breaks = T.filter(t => t.brkd).length, skipped = T.filter(t => t.chk && t.chk.skipped && t.chk.skipped.length).length;
    const best = C.slice().sort((a, b) => b.net - a.net)[0], worst = C.slice().sort((a, b) => a.net - b.net)[0], fix = oneThing(T, S);
    h += `<div class="kpis" style="margin-bottom:14px">${kpi('Net P&L', inrS(net), pct(net / (S.capital || 1), 2) + ' of capital', cls(net))}${kpi('Total R', rv(rsum), `${rs.length} trades with a stop`, cls(rsum))}${kpi('Trades', T.length, `${C.length} closed · ${T.length - C.length} open`)}
      ${kpi('Win rate', C.length ? Math.round(100 * wins / C.length) + '%' : '-', `${wins} wins of ${C.length}`)}${kpi('Rule breaks', breaks, breaks ? 'see the trades below' : 'none logged', breaks ? 'bad' : 'good')}${kpi('Checklist skipped', skipped, skipped ? 'trades with unticked rules' : 'every rule ticked', skipped ? 'warn' : 'good')}</div>`;
    h += callout(fix.length ? (fix[0].net < 0 ? 'bad' : 'warn') : 'good', fix.length ? `<b>One thing to fix next week: ${esc(fix[0].n)}.</b> ${fix[0].c} trade${fix[0].c > 1 ? 's' : ''}, ${inrS(fix[0].net)} in total.${fix.length > 1 ? ' Also: ' + fix.slice(1, 3).map(f => `${esc(f.n)} (${f.c})`).join(', ') + '.' : ''}` : '<b>Nothing stood out this week.</b> Every trade was graded, inside your risk limits and without a logged rule break. Keep doing exactly this.') + '<div style="height:14px"></div>';
    h += `<div class="grid g-main" style="margin-bottom:14px"><div class="stack">${card('Trade by trade', `<ul class="coach">${T.map(t => { const c = coach(t, S); return `<li class="${c.tone}" data-rid="${t.id}"><div class="ch"><b>${esc(t.inst)}</b><small>${esc(t.d.slice(5))} · ${esc(t.cat || '')}${t.grade ? ' · ' + esc(t.grade) : ''} · ${esc(t.src)}</small><span class="sp"></span><b class="${cls(t.net)}">${t.closed ? inrS(t.net) + (t.r != null ? ' · ' + rv(t.r) : '') : 'open'}</b></div>${c.lines.map(l => `<p>${esc(l)}</p>`).join('')}</li>`; }).join('')}</ul>`, 'what the coach sees in each trade; tap a trade to edit it')}</div>
      <div class="stack">${card('Best and worst', `<div class="kv"><span>Best</span><b class="good">${best ? esc(best.inst) + ' ' + inrS(best.net) : '-'}</b><span>Worst</span><b class="bad">${worst && worst !== best ? esc(worst.inst) + ' ' + inrS(worst.net) : '-'}</b><span>Scanner setups</span><b>${T.filter(t => t.src === 'Scanner').length} of ${T.length}</b><span>A+ and A trades</span><b>${T.filter(t => t.grade === 'A+' || t.grade === 'A').length} of ${T.length}</b></div>`)}
      ${fix.length ? card('What cost you', `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Pattern</th><th class="n">Trades</th><th class="n">Net</th></tr></thead><tbody>${fix.map(f => `<tr><td>${esc(f.n)}</td><td class="n">${f.c}</td><td class="n ${cls(f.net)}">${inrS(f.net)}</td></tr>`).join('')}</tbody></table></div>`) : ''}
      <button class="btn" type="button" id="rvCopy">Copy this review as text</button></div></div>`;
  }
  const fys = [...new Set(all.filter(t => t.closed).map(t => fyOf(t.d)))].sort().reverse(); if (!fys.includes(u.fy) && fys.length) u.fy = fys[0];
  const tx = taxRows(all, u.fy);
  h += `<div class="grid g-main"><div class="stack">${scannerLearning(all)}</div><div class="stack">${card('Tax-ready P&L', fys.length ? `<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px"><label for="rvFy" class="help" style="margin:0">Financial year</label><select id="rvFy" class="inp" style="width:auto">${fys.map(y => `<option value="${y}" ${y === u.fy ? 'selected' : ''}>${y}-${String(y + 1).slice(2)}</option>`).join('')}</select><button class="btn sm primary" type="button" id="rvTax">Download for Excel (CSV)</button></div>
      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>Section</th><th class="n">Trades</th><th class="n">Net P&L</th><th class="n">Turnover</th></tr></thead><tbody>${Object.entries(tx.B).map(([k, b]) => `<tr><td><b>${k}</b><br><small class="muted">${b.head}</small></td><td class="n">${b.n}</td><td class="n ${cls(b.net)}">${inrS(b.net)}</td><td class="n">${inr(b.turn)}</td></tr>`).join('')}</tbody></table></div>
      <p class="help" style="margin-top:8px">Intraday and F&O turnover is the sum of each trade's absolute profit or loss; delivery turnover is the sale value. Swing trades are treated as short-term. Confirm the classification with your tax adviser before filing.</p>` : empty('No closed trades yet', ''), 'intraday, F&O and delivery kept apart')}</div></div>`;
  return h;
};
App.binds.review = () => {
  const u = RU(), J = JR.J(), all = JR.enrich(J);
  if ($('#rvPrev')) $('#rvPrev').onclick = () => { u.wk = addDays(u.wk, -7); App.render(); };
  if ($('#rvNext')) $('#rvNext').onclick = () => { u.wk = addDays(u.wk, 7); App.render(); };
  $$('[data-rid]').forEach(li => li.onclick = () => JR.openForm(li.dataset.rid));
  if ($('#rvFy')) $('#rvFy').onchange = e => { u.fy = +e.target.value; App.render(); };
  if ($('#rvTax')) $('#rvTax').onclick = () => { dl(`tax-pnl-FY${u.fy}-${String(u.fy + 1).slice(2)}.csv`, '\ufeff' + taxCsv(all, u.fy)); App.toast('Tax P&L downloaded'); };
  if ($('#rvCopy')) $('#rvCopy').onclick = () => { const S = J.set, T = all.filter(t => t.wk === u.wk), C = T.filter(t => t.closed && t.net != null), net = C.reduce((a, t) => a + t.net, 0), fix = oneThing(T, S);
    const txt = [`Weekly review ${u.wk} to ${addDays(u.wk, 4)}`, `Net ${inrS(net)} · ${C.length} closed of ${T.length} trades · ${C.filter(t => t.res === 'Win').length} wins`, fix.length ? `Fix next week: ${fix[0].n} (${fix[0].c} trades, ${inrS(fix[0].net)})` : 'Nothing stood out: plan followed.', '',
      ...T.map(t => `${t.d.slice(5)} ${t.inst} ${t.closed ? inrS(t.net) : 'open'}: ${coach(t, S).lines.join(' ')}`)].join('\n');
    App.scanner.copyText(txt, 'Review copied'); };
};

/* the trade page's pre-trade check needs the symbol -> sector map (portfolio heat) */
const tradeBind = App.binds.trade;
App.binds.trade = q => { if (tradeBind) tradeBind(q); if (App.lazyAge('sectors') > 3600000) App.lazy('sectors', 3600000).then(() => App.soon('trade')).catch(() => { }); };
App.lab = { coach, oneThing, taxRows, taxCsv, taxClass, fyOf, BT, labView, goldLots };
})();
