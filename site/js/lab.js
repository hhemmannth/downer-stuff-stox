/* DownerStuff: Backtest lab (items 2a-2e, 14), Weekly review with the rule-based coach (22, 32), learning from your journal (9),
   the tax-ready export (24) and Investments (25). Loaded after the other pages; it only adds pages, it changes none. */
(() => {
const JR = App.journal, kpi = App.ui.kpi, empty = App.ui.empty, callout = App.ui.callout;
const card = (title, body, cap = '', extra = '') => `<div class="card"><div class="hd"><h2>${title}</h2>${cap ? `<span class="cap">${cap}</span>` : ''}${extra}</div><div class="bd">${body}</div></div>`;
const rv = v => isNum(v) ? (v > 0 ? '+' : '') + v.toFixed(2) + 'R' : '-';
const dl = (name, text, type = 'text/csv') => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500); };
const weekStart = s => JR.weekStart(s);
const addDays = (s, n) => { const d = new Date(s + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const csvCell = v => { const s = v == null ? '' : String(v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
const lazyPage = (name, page, maxAge = 600000) => { if (App.lazyAge(name) > maxAge) App.lazy(name, maxAge).then(() => { if (App.route().page === page) App.render(); }).catch(() => { }); };

/* ============================== Backtest lab ============================== */
/* Four playbooks, each with its own result file: swing, positional (weekly structure), intraday (stocks, long and short) and Nifty options (modelled premiums). */
const BT_FILES = { swing: 'backtest', positional: 'backtest_positional', intraday: 'backtest_intraday', options: 'backtest_options' };
const BT_TITLES = { swing: 'Swing', positional: 'Positional', intraday: 'Intraday', options: 'Nifty options' };
const BT_WORKFLOW = { swing: 'backtest.yml', positional: 'backtest.yml', intraday: 'backtest-intraday.yml', options: 'backtest-intraday.yml' };
const BT_LEGACY = [['grade', 'By grade', 'does your scorecard separate good setups from weak ones?', 'Grade'], ['score', 'By score', '', 'Score /10'], ['regime', 'By market regime', 'the regime on the day before entry', 'Regime'], ['confirm', 'By confirmation', 'rejection, 9 EMA reclaim, volume', 'Confirmation'],
  ['volume', 'By volume on the confirmation', '', 'Relative volume'], ['zone', 'By zone quality', '', 'Zone'], ['context', 'By context', 'key level, fib, MTF EMA', 'Context ticks'], ['stop', 'By stop width', '', 'Stop'], ['weekday', 'By weekday of entry', '', 'Day'], ['sector', 'By sector', 'largest 14', 'Sector'], ['month', 'By month', 'month the trade closed', 'Month']];
const btSeg = () => { const s = App.ui.btseg || 'swing'; return BT_FILES[s] ? s : 'swing'; };
const btTabs = seg => `<div class="seg" role="tablist" aria-label="Playbook" style="margin-bottom:14px">${Object.keys(BT_FILES).map(k => `<button type="button" role="tab" aria-selected="${k === seg}" aria-pressed="${k === seg}" data-btseg="${k}">${BT_TITLES[k]}</button>`).join('')}</div>`;
const statTable = (title, rows, cap, first = '') => !rows || !rows.length ? '' : card(title, `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${first}</th><th class="n">Trades</th><th class="n">Win</th><th class="n">Avg R</th><th class="n">Profit factor</th><th class="n">Total R</th></tr></thead><tbody>
  ${rows.map(r => `<tr><td><b>${esc(r.k)}</b></td><td class="n">${r.n}</td><td class="n">${r.win == null ? '-' : r.win + '%'}</td><td class="n ${cls(r.avg)}">${rv(r.avg)}</td><td class="n">${r.pf == null ? '-' : r.pf}</td><td class="n ${cls(r.total)}">${rv(r.total)}</td></tr>`).join('')}</tbody></table></div>`, cap);
const holdText = (S, seg) => seg === 'intraday' || seg === 'options' ? (S.avg_hold_min == null ? '-' : S.avg_hold_min + ' min') : (S.avg_hold_days == null ? '-' : S.avg_hold_days + ' d');

function forwardTest(B, seg) {
  const led = seg === 'swing' ? 'swing' : seg === 'intraday' ? 'intraday' : null;
  if (!led) return card('Live forward test', `<p class="help" style="margin:0">${seg === 'options' ? 'Live option signals are tracked on the index, and this backtest measures the option premium, so the two cannot be compared one to one. Judge the options playbook by the Journal once you have logged option trades.' : 'Positional trades are not tracked live yet.'}</p>`, 'is the live scanner behaving like the backtest?');
  const live = App.LED(led).signals.filter(s => s.status === 'CLOSED' && isNum(s.r_final)), n = live.length;
  if (!n) return card('Live forward test', empty('No tracked ' + led + ' trade has closed yet', 'Every setup the scanner triggers is tracked with the same rules. As they close, this card compares real results with the backtest.'), 'is the live scanner behaving like the backtest?');
  const avg = live.reduce((a, s) => a + s.r_final, 0) / n, win = 100 * live.filter(s => s.r_final > 0).length / n, b = B.summary.gross;
  const verdict = n < 20 ? ['info', `Only ${n} live trade${n > 1 ? 's' : ''} so far. Fewer than 20 says very little: keep tracking before you judge.`]
    : avg >= b.avg - 0.25 ? ['good', 'Live results are in line with the backtest (or better).'] : ['warn', 'Live results are clearly below the backtest. That can be bad luck over a small sample, or a market regime the backtest saw little of.'];
  return card('Live forward test', `<div class="kpis">${kpi('Live trades closed', n)}${kpi('Live win rate', win.toFixed(0) + '%', `backtest ${b.win}%`)}${kpi('Live average', rv(avg), `backtest ${rv(b.avg)} before costs`, cls(avg))}</div><div style="height:10px"></div>${callout(verdict[0], verdict[1])}`, 'tracked signals against the backtest');
}

App.pages.backtest = () => {
  const seg = btSeg(), B = App.lazyNow(BT_FILES[seg]), T = BT_TITLES[seg];
  let h = `<div class="ph"><div><h1>Backtest lab</h1><p>Each playbook replayed on past data with the same engine and the same trade rules the live scanner uses, kept apart. The first view of each takes <b>every</b> signal; "With your rules" then trades it the way your journal rules say. Evidence to tune your rules with, not a promise about the future.</p></div></div>` + btTabs(seg);
  if (!B || !B.summary) return h + `<div class="card"><div class="bd">${empty('No ' + T.toLowerCase() + ' backtest yet', `It runs every Saturday. To run it now, open <a href="${App.actionsUrl()}/workflows/${BT_WORKFLOW[seg]}" target="_blank" rel="noopener">GitHub → ${BT_WORKFLOW[seg].replace('.yml', '')} → Run workflow</a>. ${seg === 'intraday' || seg === 'options' ? 'It takes about 10 to 30 minutes.' : 'It takes 30 to 90 minutes.'} This page fills in when it finishes.`)}</div></div>`;
  const s = B.summary.net, g = B.summary.gross, S = B.summary, mc = B.montecarlo || {}, o = S.outcomes || {}, W = B.window || {}, small = seg === 'intraday' || seg === 'options';
  h += `<p class="help" style="margin:-4px 0 12px">${esc(W.from || '')} to ${esc(W.to || '')} · ${seg === 'options' ? 'Nifty 50 index' : seg === 'positional' ? `${B.universe} most liquid Nifty 500 stocks, long only` : `${B.universe} most liquid Nifty 500 stocks`} · run ${esc(dateIST(B.generated_at))} <small class="muted">${esc(ago(B.generated_at))}</small></p>`;
  if (seg === 'options') h += callout('warn', '<b>Modelled premiums, not real option prices.</b> There is no free historical option data, so each trade picks the strike by delta like the live app and prices the option with Black-Scholes on the previous day\'s India VIX. Real fills differ with changing volatility, skew and the bid-ask spread. The index signals are real; the premium results are an estimate.') + '<div style="height:10px"></div>';
  if (small) h += callout('info', `<b>This view starts small and grows.</b> Free 5-minute history only reaches back about 60 days, so each Saturday run adds the new days to the trades already saved (${s.n} so far). Until it has a few hundred trades, read the numbers as a hint, not a verdict.`) + '<div style="height:10px"></div>';
  if (seg === 'positional') h += callout('info', '<b>Positional here means the swing playbook one timeframe up:</b> structure on the weekly chart, trigger on the daily chart, long only, held for weeks to months (up to 120 days). This is my reading of it: if your positional rules differ, tell me and I will change the engine.') + '<div style="height:10px"></div>';
  h += `<p class="help" style="margin:0 0 8px"><b>Every ${({ swing: 'swing', positional: 'positional', intraday: 'intraday', options: 'Nifty options' })[seg]} signal the engine produced</b> (all grades from 4 up, no daily limit, no risk rules). This is the engine's raw edge, not your trading.</p>`;
  h += `<div class="kpis" style="margin-bottom:14px">${kpi('Trades', s.n, small ? `about ${Math.round(S.trades_per_year / 252 * 10) / 10} a trading day` : `about ${Math.round(S.trades_per_year)} a year`)}${kpi('Win rate', s.win == null ? '-' : s.win + '%', `win ${rv(s.avg_win)} · loss ${rv(s.avg_loss)}`)}${kpi('Expectancy', rv(s.avg), `after costs · ${rv(g.avg)} before`, cls(s.avg))}
    ${kpi('Profit factor', s.pf == null ? '-' : s.pf, 'wins ÷ losses', s.pf >= 1 ? 'good' : 'bad')}${kpi('Max drawdown', s.max_dd + 'R', `longest losing run ${s.streak}`)}${kpi('Average hold', holdText(S, seg), `${o.TARGET || 0} T3 · ${o.SL || 0} stopped`)}</div>`;
  const SC = B.scenarios || [], AC = B.account || {}, CV = B.scenario_curves || {};
  const scRow = r => `<tr><td><b>${esc(r.name)}</b></td><td class="n">${r.n}<br><small class="muted">${r.per_year} a year</small></td><td class="n">${r.win == null ? '-' : r.win + '%'}</td><td class="n ${cls(r.avg)}">${rv(r.avg)}</td><td class="n">${r.pf == null ? '-' : r.pf}</td>
    <td class="n ${cls(r.ret)}">${r.n ? sg(r.ret) + '%' : '-'}${r.cagr != null ? `<br><small class="muted">${sg(r.cagr)}% a year</small>` : ''}</td><td class="n">${r.n ? '-' + r.max_dd + '%' : '-'}</td><td class="n">${r.streak}</td>
    <td><small class="muted">${r.rules ? `${r.skipped.day_cap} over the daily cap · ${r.skipped.open_cap} over open risk · ${r.skipped.loss_limit} stopped by loss limits` : 'none: every trade taken'}</small></td></tr>`;
  const SLAB = { all: 'every signal', a: 'A and A+', ap: 'A+ only', p10: 'perfect 10' };
  const best = SC.filter(r => r.rules && r.n >= 30).sort((a, b) => b.avg - a.avg)[0], few = SC.filter(r => r.rules && r.n > 0 && r.n < 30);
  let acct = '';
  if (SC.length) acct = card('With your rules', `<p class="help" style="margin:0 0 10px">The same trades, taken the way you trade: only setups at or above the score, the first ${AC.max_per_day} to trigger each day, ${AC.risk}% risk (${AC.risk_aplus}% for A+), open risk up to ${AC.open_cap}%, no more entries after a ${AC.day_stop}% losing day, a ${AC.week_stop}% losing week or a ${AC.month_stop}% losing month, half size once a month is down ${AC.month_half}%${AC.stop_after_losses ? `, and no more trades for the day after ${AC.stop_after_losses} losing trades` : ''}. A 100-unit account that compounds.</p>
    <div class="tbl-wrap"><table class="tbl"><thead><tr><th>Scenario</th><th class="n">Trades</th><th class="n">Win</th><th class="n">Avg R</th><th class="n">Profit factor</th><th class="n">Account</th><th class="n">Max drawdown</th><th class="n">Worst run</th><th>Not taken</th></tr></thead><tbody>${SC.map(scRow).join('')}</tbody></table></div>
    ${(CV.labels || []).length > 2 ? `<div style="margin-top:12px"><div id="btSc"></div><div style="display:flex;gap:14px;flex-wrap:wrap;margin-top:6px">${SC.map(r => `<span class="help" style="margin:0"><b style="color:${({ all: 'var(--sun)', a: 'var(--ink-2)', ap: 'var(--brand)', p10: 'var(--good)' })[r.key]}">&#9632;</b> ${esc(SLAB[r.key])}</span>`).join('')}</div></div>` : ''}
    <div style="height:10px"></div>${best ? callout(best.avg > 0.05 ? 'good' : best.avg > -0.05 ? 'info' : 'bad', `<b>Best with your rules: ${esc(best.name)}.</b> ${best.n} trades, ${rv(best.avg)} per trade after costs, ${sg(best.ret)}% on the account with a worst fall of -${best.max_dd}%. Taking every signal: ${rv(s.avg)} per trade.${best.avg > s.avg + 0.05 ? ' Being selective is what separates a loss from a profit here.' : ''}${best.n < 100 ? ` With only ${best.n} trades this is a lead, not proof: a few lucky trades can move the average.` : ''}`)
      : callout('warn', 'None of your rule sets has 30 trades yet, which is too few to judge.')}
    ${few.length ? `<p class="help" style="margin-top:8px">Fewer than 30 trades, so read as a hint only: ${few.map(r => esc(r.name) + ' (' + r.n + ')').join('; ')}.</p>` : ''}`, 'the same trades, your way', `<span class="sp"></span><span class="pill info">quick re-run: Actions &gt; backtest &gt; quick</span>`);
  const verdict = s.n < 50 ? ['warn', `<b>Only ${s.n} trades.</b> That is too few to trust any number on this page.${small ? ' It grows every week.' : ' Run the backtest on more stocks (set "top" to 0 for all 500).'}`]
    : s.avg >= 0.2 ? ['good', `<b>The playbook had a positive edge after costs:</b> ${rv(s.avg)} per trade over ${s.n} trades. Expect losing runs of about ${mc.streak_p50 || s.streak} trades in a normal year.`]
    : s.avg > 0 ? ['info', `<b>A thin edge after costs:</b> ${rv(s.avg)} per trade. Costs and slippage matter a lot at this level: look at which grades, regimes and filters below carry the result.`]
    : ['bad', `<b>Taking every signal, there was no edge after costs on this window:</b> ${rv(s.avg)} per trade. That is not how you trade: see "With your rules" below, and the tables further down, where the loss is often concentrated in a few conditions you can simply skip.`];
  h += callout(verdict[0], verdict[1]) + '<div style="height:14px"></div>' + (acct ? acct + '<div style="height:14px"></div>' : '');
  const order = (B.by_order && B.by_order.length) ? B.by_order : BT_LEGACY.filter(x => (B.by || {})[x[0]]).map(x => ({ key: x[0], title: x[1], cap: x[2], first: x[3] })), tbl = x => statTable(x.title, (B.by || {})[x.key], x.cap, x.first);
  h += `<div class="grid g-main" style="margin-bottom:14px"><div class="stack">${card('Equity curve', '<div id="btEq"></div>', 'running total in R, after costs, one unit of risk per trade')}${order.slice(0, 3).map(tbl).join('')}</div>
    <div class="stack">${forwardTest(B, seg)}
    ${card('What a year can look like', mc.sims ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Risk per trade</th><th class="n">Typical year</th><th class="n">Bad year</th><th class="n">Good year</th><th class="n">Typical drawdown</th><th class="n">Bad drawdown</th><th class="n">Losing year</th></tr></thead><tbody>
      ${Object.entries(mc.risks).map(([k, r]) => `<tr><td><b>${k}%</b></td><td class="n ${cls(r.ret_p50)}">${sg(r.ret_p50)}%</td><td class="n ${cls(r.ret_p5)}">${sg(r.ret_p5)}%</td><td class="n ${cls(r.ret_p95)}">${sg(r.ret_p95)}%</td><td class="n">-${r.dd_p50}%</td><td class="n bad">-${r.dd_p95}%</td><td class="n">${r.losing_year}%</td></tr>`).join('')}</tbody></table></div>
      <p class="help" style="margin-top:8px">${mc.sims.toLocaleString()} simulated years of ${mc.trades_per_year} trades, drawn at random from the backtest results. "Bad" is the worst 1 year in 20. Expect a losing run of about <b>${mc.streak_p50}</b> trades in a normal year and <b>${mc.streak_p95}</b> in a bad one: choose a risk per trade you can sit through.${small ? ' The window is short, so treat the yearly numbers as rough.' : ''}</p>` : empty('Not enough trades to simulate', mc.note || ''), 'Monte Carlo')}
    ${B.split ? card('Did it hold up over time?', `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Period</th><th class="n">Trades</th><th class="n">Win</th><th class="n">Avg R</th><th class="n">Profit factor</th></tr></thead><tbody>
      ${[['First 60% of the window', B.split.train], ['Last 40% (most recent)', B.split.test]].map(([n, r]) => `<tr><td><b>${n}</b></td><td class="n">${r.n}</td><td class="n">${r.win == null ? '-' : r.win + '%'}</td><td class="n ${cls(r.avg)}">${rv(r.avg)}</td><td class="n">${r.pf == null ? '-' : r.pf}</td></tr>`).join('')}</tbody></table></div>
      <p class="help" style="margin-top:8px">An edge that shows in both halves is more believable than one that only shows in the first.</p>`) : ''}
    ${S.held_back && S.held_back.n ? card('Your hold-back rules', `<p style="margin:0">Trades your rules held back (weekly trend against, or less than 2R of room) averaged <b class="${cls(S.held_back.avg)}">${rv(S.held_back.avg)}</b> over ${S.held_back.n} trades, against <b class="${cls(s.avg)}">${rv(s.avg)}</b> for the trades taken. ${S.held_back.avg < s.avg ? 'The rules kept you out of worse trades: keep them.' : 'The held-back trades did no worse here: the rules cost you opportunities on this window.'}</p>`) : ''}</div></div>`;
  if ((B.variants || []).length) { const vb = B.variant_base || { all: B.base, train: (B.split || {}).train || {}, test: (B.split || {}).test || {} };
    h += card('Would a different rule have been better?', `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Rule</th><th class="n">Trades</th><th class="n">Avg R, all</th><th class="n">First 60%</th><th class="n">Last 40%</th><th>Verdict</th></tr></thead><tbody>
      <tr><td><b>Your current rules</b><br><small class="muted">1.5x volume, 0.25 ATR stop buffer</small></td><td class="n">${vb.all.n}</td><td class="n ${cls(vb.all.avg)}">${rv(vb.all.avg)}</td><td class="n">${rv(vb.train.avg)}</td><td class="n">${rv(vb.test.avg)}</td><td><span class="pill info">baseline</span></td></tr>
      ${B.variants.map(v => `<tr><td><b>${esc(v.name)}</b><br><small class="muted">${esc(v.desc)}</small></td><td class="n">${v.all.n}</td><td class="n ${cls(v.all.avg)}">${rv(v.all.avg)}</td><td class="n">${rv(v.train.avg)}</td><td class="n">${rv(v.test.avg)}</td><td><span class="pill ${v.better ? 'ok' : 'info'}">${v.better ? 'Better in both halves' : 'Keep your rule'}</span></td></tr>`).join('')}</tbody></table></div>
      <p class="help" style="margin-top:8px">A variant is only called better when it beats your rule in <b>both</b> halves of the window with at least 20 recent trades. That guards against a rule that merely fits the past. Tested on the ${(B.params || {}).variant_universe || 120} most liquid stocks.</p>`, 'one change at a time') + '<div style="height:14px"></div>'; }
  h += `<div class="grid g2x" style="margin-bottom:14px">${order.slice(3).map(tbl).join('')}</div>`;
  h += `<div class="grid g-main"><div class="stack">${card('Most recent trades', `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${seg === 'options' ? 'Option' : 'Stock'}</th><th>Entry</th><th>Exit</th><th class="n">Grade</th><th>Result</th><th class="n">R net</th></tr></thead><tbody>
      ${(B.trades || []).slice(-30).reverse().map(t => `<tr><td><b>${esc(seg === 'options' && t.strike ? `${t.sym} ${t.strike} ${t.side === 'short' ? 'PE' : 'CE'}` : t.sym)}</b> <small class="muted">${t.side === 'short' ? 'short' : ''} ${esc(t.sector || '')}</small></td><td><small>${esc(t.entry_t)}</small></td><td><small>${esc(t.exit_t)} · ${t.hold_min != null ? t.hold_min + ' min' : (t.hold_days != null ? t.hold_days + 'd' : '')}</small></td><td class="n">${esc(t.grade)} ${t.score}</td><td>${esc({ TARGET: 'T3 reached', TRAIL: 'Trailing stop', SL: 'Stop-loss', EXPIRED: small ? 'Squared off 15:15' : 'Expired' }[t.outcome] || t.outcome)}</td><td class="n ${cls(t.r_net)}">${rv(t.r_net)}</td></tr>`).join('')}</tbody></table></div>`, 'last 30 of ' + s.n)}</div>
    <div class="stack">${card('How to read this', `<ul class="ins">${(B.assumptions || []).map(a => `<li><i></i><span>${esc(a)}</span></li>`).join('')}</ul>`, 'what the replay does and does not include')}</div></div>`;
  return h;
};
App.binds.backtest = () => {
  const seg = btSeg(); $$('[data-btseg]').forEach(b => b.onclick = () => { App.ui.btseg = b.dataset.btseg; App.render(); });
  lazyPage(BT_FILES[seg], 'backtest');
  const B = App.lazyNow(BT_FILES[seg]), el = $('#btEq'); if (!B || !el || !(B.equity || []).length) return;
  const sc = $('#btSc'), CV = B.scenario_curves;
  if (sc && CV && (CV.labels || []).length > 2) sc.innerHTML = App.charts.line(['all', 'a', 'ap', 'p10'].filter(k => CV.series[k]).map(k => ({ pts: CV.series[k], c: ({ all: 'sun', a: 'ink', ap: 'brand', p10: 'good' })[k], w: k === 'p10' || k === 'ap' ? 2.4 : 1.6 })), { W: sc.clientWidth || 640, H: 220, labels: CV.labels, fmt: v => v.toFixed(0), label: 'Account value by scenario, starting at 100' });
  const draw = () => { el.innerHTML = App.charts.line([{ pts: [0].concat(B.equity.map(x => x[1])), c: B.summary.net.total >= 0 ? 'good' : 'bad', area: true }], { W: el.clientWidth || 640, H: 230, zero: true, labels: [B.equity[0][0]].concat(B.equity.map(x => x[0])), fmt: v => v.toFixed(0) + 'R', label: 'Backtest equity curve in R' }); };
  draw();
};

/* ============================== Weekly review, coach, learning, tax ============================== */
function coach(t, S) {
  const L = []; let tone = 'good'; const bad = m => { L.push(m); tone = 'bad'; }, warn = m => { L.push(m); if (tone === 'good') tone = 'warn'; };
  if (t.sl == null) bad('No stop-loss recorded. Every trade needs one before entry.');
  if (t.riskP != null && t.riskP > S.riskC + 1e-5) bad(`Risked ${pct(t.riskP, 2)} of capital, above your ${pct(S.riskC, 2)} ceiling.`);
  if (t.brkd) bad(`Rule break logged: ${t.brk}.`);
  if (t.chk && t.chk.skipped && t.chk.skipped.length) warn(`Entered with ${t.chk.skipped.length} checklist rule${t.chk.skipped.length > 1 ? 's' : ''} unticked: ${t.chk.skipped.slice(0, 2).join('; ')}${t.chk.skipped.length > 2 ? '…' : ''}.`);
  if (t.cat === 'Intraday' && t.idx > S.maxIntra) bad(`Intraday trade number ${t.idx} that day: your limit is ${S.maxIntra}.`);
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
  let h = `<div class="ph"><div><h1>Weekly review</h1><p>One week at a time: what you made, which rules you kept, what each trade teaches, and the one thing to fix next week. ${esc(J.name)}.</p></div><span class="sp"></span>
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

/* ============================== Investments (item 25) ============================== */
const LT_DAYS = 365, ST_RATE = 0.20, LT_RATE = 0.125, LT_EXEMPT = 125000;
const H = () => { const J = JR.J(); J.lists.holdings = J.lists.holdings || []; J.lists.prices = J.lists.prices || {}; J.lists.alloc = J.lists.alloc || {}; return J.lists; };
const priceOf = (sym, L) => { const q = ((App.lazyNow('quotes') || {}).quotes || {})[sym]; return q && isNum(q.price) ? { p: q.price, src: 'scan ' + (q.date || '') } : isNum(L.prices[sym]) ? { p: L.prices[sym], src: 'entered by you' } : { p: null, src: '' }; };
App.pages.invest = () => {
  const L = H(), today = todayIST(), lots = L.holdings.slice().sort((a, b) => a.sym < b.sym ? -1 : a.sym > b.sym ? 1 : a.d < b.d ? -1 : 1);
  let h = `<div class="ph"><div><h1>Investments</h1><p>Your long-term holdings, kept apart from trading: cost, value, how long each lot has been held, when it becomes long-term for tax, and how far each holding has drifted from your target.</p></div><span class="sp"></span><button class="btn primary" type="button" id="ivAdd">${ic('plus')} Add a lot</button></div>`;
  if (!lots.length) return h + `<div class="card"><div class="bd">${empty('No holdings yet', 'Add each purchase as its own lot (symbol, date, quantity, price). Tax depends on each lot\'s own holding period.')}</div></div>`;
  let cost = 0, costP = 0, val = 0, stG = 0, ltG = 0, missing = 0; const by = {};
  const rows = lots.map(x => { const pr = priceOf(x.sym, L), c = x.qty * x.price, v = pr.p != null ? x.qty * pr.p : null, days = Math.max(0, Math.round((new Date(today) - new Date(x.d)) / 864e5)), lt = days > LT_DAYS, ltOn = addDays(x.d, LT_DAYS + 1), gain = v != null ? v - c : null;
    cost += c; if (v != null) { val += v; costP += c; by[x.sym] = (by[x.sym] || 0) + v; if (lt) ltG += gain; else stG += gain; } else missing++;
    const ann = v != null && days >= 30 && c > 0 ? Math.pow(v / c, 365 / days) - 1 : null;
    return `<tr><td><b>${esc(x.sym)}</b><br><small class="muted">${esc(x.d)} · ${days} d</small><br>${lt ? '<span class="pill ok">Long-term</span>' : `<span class="pill warn">Short-term</span> <small class="muted">long-term from ${esc(ltOn)} (${LT_DAYS + 1 - days} d)</small>`}</td><td class="n">${fmt0(x.qty)}</td><td class="n">${fmt(x.price)}</td><td class="n">${pr.p != null ? fmt(pr.p) : `<button class="btn sm ghost" data-ivp="${esc(x.sym)}" type="button">set price</button>`}</td><td class="n">${v != null ? inr(v) : '-'}</td>
      <td class="n ${cls(gain)}">${gain != null ? inrS(gain) + `<br><small>${sg(100 * gain / c)}%${ann != null ? ' · ' + sg(100 * ann) + '%/yr' : ''}</small>` : '-'}</td><td class="n"><button class="btn sm ghost" data-ivx="${x.id}" type="button" aria-label="Remove this lot" title="Remove this lot">×</button></td></tr>`; }).join('');
  const tax = Math.max(0, stG) * ST_RATE + Math.max(0, ltG - LT_EXEMPT) * LT_RATE;
  h += `<div class="kpis" style="margin-bottom:14px">${kpi('Invested', inr(cost), `${lots.length} lots`)}${kpi('Value now', missing === lots.length ? '-' : inr(val), missing ? `${missing} lot${missing > 1 ? 's' : ''} without a price` : 'all lots priced')}${kpi('Gain', missing === lots.length ? '-' : inrS(val - costP), costP ? sg(100 * (val - costP) / costP) + '% on priced lots' : '', cls(val - costP))}
    ${kpi('Short-term gain', inrS(stG), 'held up to 12 months', cls(stG))}${kpi('Long-term gain', inrS(ltG), 'held over 12 months', cls(ltG))}${kpi('Tax if sold today', inr(tax), 'estimate, see the note')}</div>`;
  const tot = Object.values(by).reduce((a, b) => a + b, 0), syms = Object.keys(by).sort((a, b) => by[b] - by[a]);
  h += `<div class="grid g-main"><div class="stack">${card('Lots', `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Lot</th><th class="n">Qty</th><th class="n">Buy</th><th class="n">Price</th><th class="n">Value</th><th class="n">Gain</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`, 'each purchase on its own')}</div>
    <div class="stack">${card('Allocation', syms.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Holding</th><th class="n">Weight</th><th class="n">Target %</th></tr></thead><tbody>${syms.map(s => { const w = 100 * by[s] / tot, t = L.alloc[s], dr = isNum(t) ? w - t : null;
      return `<tr><td><b>${esc(s)}</b><br>${dr == null ? '<small class="muted">set a target</small>' : Math.abs(dr) <= 5 ? '<span class="pill ok">on target</span>' : `<span class="pill warn">${dr > 0 ? 'over' : 'under'} by ${Math.abs(dr).toFixed(1)} pts</span>`}</td><td class="n">${w.toFixed(1)}%</td><td class="n"><input class="inp" data-ivt="${esc(s)}" type="number" inputmode="decimal" step="any" value="${isNum(t) ? t : ''}" placeholder="-" style="width:68px;text-align:right" aria-label="Target weight for ${esc(s)} in percent"></td></tr>`; }).join('')}</tbody></table></div>
      <p class="help" style="margin-top:8px">A holding more than 5 points from its target is a rule-based reason to trim or add, with no prediction needed.</p>` : empty('Set a price for your lots to see the allocation', ''), 'weights against your targets')}
    ${card('About the numbers', `<ul class="ins"><li><i></i><span><b>Prices</b> come from the scan when the repo variable <code>HOLDING_SYMBOLS</code> lists your symbols (for example <code>NIFTYBEES,JUNIORBEES</code>); otherwise use "set price".</span></li>
      <li><i></i><span><b>Tax estimate</b>: listed equity and equity ETFs, ${ST_RATE * 100}% on short-term gains and ${LT_RATE * 100}% on long-term gains above ₹${LT_EXEMPT.toLocaleString('en-IN')} a year, before cess and without setting off losses. Rates change: check the current ones before you act.</span></li>
      <li><i></i><span>Holdings are saved inside your journal, so they sync and back up with it. Nothing here is published.</span></li></ul>`)}</div></div>`;
  return h;
};
App.binds.invest = () => {
  lazyPage('quotes', 'invest', 300000); const L = H(), save = () => { JR.touch(); JR.persist(); App.render(); };
  if ($('#ivAdd')) $('#ivAdd').onclick = () => {
    const bg = document.createElement('div'); bg.className = 'modal-bg';
    bg.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-label="Add a lot" style="max-width:520px"><div class="mh"><h2>Add a lot</h2><button class="btn sm ghost" data-x>Close</button></div><div class="mb"><div class="fgrid">
      <div class="field w2"><label for="iv-sym">Symbol (NSE)</label><input id="iv-sym" placeholder="NIFTYBEES" autocomplete="off"></div><div class="field w2"><label for="iv-d">Buy date</label><input id="iv-d" type="date" value="${todayIST()}"></div>
      <div class="field w2"><label for="iv-q">Quantity</label><input id="iv-q" type="number" step="any" inputmode="decimal"></div><div class="field w2"><label for="iv-p">Buy price (₹)</label><input id="iv-p" type="number" step="any" inputmode="decimal"></div></div></div>
      <div class="mf"><button class="btn" data-x>Cancel</button><button class="btn primary" data-ok>Add lot</button></div></div>`;
    document.body.appendChild(bg); setTimeout(() => $('#iv-sym', bg).focus(), 30);
    bg.addEventListener('click', e => { if (e.target === bg || e.target.closest('[data-x]')) bg.remove();
      if (e.target.closest('[data-ok]')) { const sym = $('#iv-sym', bg).value.trim().toUpperCase(), d = $('#iv-d', bg).value, q = +$('#iv-q', bg).value, p = +$('#iv-p', bg).value;
        if (!sym || !d || !(q > 0) || !(p > 0)) { App.toast('Fill in the symbol, date, quantity and price'); return; }
        L.holdings.push({ id: 'h' + Date.now().toString(36), sym, d, qty: q, price: p }); bg.remove(); save(); App.toast('Lot added'); } });
  };
  $$('[data-ivx]').forEach(b => b.onclick = () => { if (confirm('Remove this lot?')) { L.holdings = JR.J().lists.holdings = L.holdings.filter(x => x.id !== b.dataset.ivx); save(); } });
  $$('[data-ivp]').forEach(b => b.onclick = () => { const v = prompt(`Current price of ${b.dataset.ivp} (₹)`); if (v && +v > 0) { L.prices[b.dataset.ivp] = +v; save(); } });
  $$('[data-ivt]').forEach(i => i.onchange = () => { const v = i.value === '' ? null : +i.value; if (v == null) delete L.alloc[i.dataset.ivt]; else if (v >= 0 && v <= 100) L.alloc[i.dataset.ivt] = v; save(); });
};

/* the swing page needs the symbol -> sector map for the portfolio heat card */
const swingBind = App.binds.swing;
App.binds.swing = q => { if (swingBind) swingBind(q); if (App.lazyAge('sectors') > 3600000) App.lazy('sectors', 3600000).then(() => { if (App.route().page === 'swing') App.render(); }).catch(() => { }); };
App.lab = { coach, oneThing, taxRows, taxCsv, taxClass, fyOf };
})();
