/* Dashboard, market, news, playbook and settings. */
'use strict';
(function () {
const JR = App.journal, SC = App.scanner;

/* ---------- dashboard ---------- */
App.pages.dashboard = () => {
  const m = App.data.market || {}, idx = m.indices || {}, sw = App.data.swing, nw = App.data.news || {}, rs = JR.riskStatus(), J = JR.J(), T = JR.enrich(J);
  const mo = todayIST().slice(0, 7), M = T.filter(t => t.mkey === mo), st = App.analytics.stats(M, J.set), all = App.analytics.stats(T, J.set);
  const hello = (() => { const h = istNow().getUTCHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'; })();
  let h = `<div class="ph"><div><h1>${hello}</h1><p>${App.marketOpen() ? 'Market is open.' : 'Market is closed.'} ${m.playbook ? esc(m.playbook.headline) + '.' : ''} Your plan for today, your risk and your progress in one place.</p></div></div>`;
  h += `<div class="kpis" style="margin-bottom:14px">${App.ui.kpi('Nifty 50', fmt(idx.nifty && idx.nifty.price, 1), idx.nifty ? sg(idx.nifty.change_pct) + '%' : '', cls(idx.nifty && idx.nifty.change_pct))}${App.ui.kpi('Bank Nifty', fmt(idx.banknifty && idx.banknifty.price, 1), idx.banknifty ? sg(idx.banknifty.change_pct) + '%' : '', cls(idx.banknifty && idx.banknifty.change_pct))}
    ${App.ui.kpi('India VIX', fmt(idx.vix && idx.vix.price, 2), m.expected_move ? `±${fmt0(m.expected_move.daily_pts)} pts expected today` : '')}${App.ui.kpi('Regime', m.daily ? esc(m.daily.label) : '-', m.intraday ? 'today: ' + esc(m.intraday.label) : '')}
    ${App.ui.kpi('This month', inrS(st.net), `${st.n} closed · ${st.n ? pct(st.winRate, 0) + ' wins' : 'no trades yet'}`, cls(st.net))}${App.ui.kpi('Expectancy', rr(all.expR), `all time, ${all.n} trades`, cls(all.expR))}</div>`;
  const lvl = { ok: ['good', 'Normal: trade your plan'], warn: ['warn', 'Caution'], bad: ['bad', 'Stop'] }[rs.level];
  h += `<div class="grid g-main" style="margin-bottom:14px"><div class="stack">`;
  // swing shortlist
  if (sw) { const S = sw.setups, short = S.filter(s => s.stage >= 3 && !(s.holds || []).length && !s.status.startsWith('WATCH')).sort((a, b) => b.stage - a.stage || b.score - a.score).slice(0, 5);
    h += `<div class="card"><div class="hd"><h2>Swing: today's shortlist</h2><span class="cap">max 5, pick 1 or 2 (your stock-selection rule)</span><span class="sp"></span><a class="btn sm" href="#/swing">All swing setups</a></div>
      <div class="bd"><div class="pipeline" style="margin-bottom:12px">${[5, 4, 3, 2, 1].map(k => `<a class="pipe p${k}" href="#/swing" onclick="App.ui.sw=Object.assign(App.ui.sw||{view:'setups',grade:'all',q:''},{stage:'${k}',view:'setups'})" style="text-decoration:none;color:inherit"><div class="k">${SC.STG[k][0]}</div><div class="v">${S.filter(s => s.stage === k).length}</div></a>`).join('')}</div>
      ${short.length ? `<div class="cards">${short.map(s => SC.card('swing', s)).join('')}</div>` : App.ui.empty('No swing setup is in its zone right now', 'Waiting is part of the plan. Stage 2 setups are the ones to set alerts on.')}</div></div>`; }
  // open trades and signals
  const open = T.filter(t => t.open), act = ['swing', 'options', 'intraday'].flatMap(k => App.LED(k).signals.filter(s => s.status === 'ACTIVE').map(s => [k, s]));
  h += `<div class="card"><div class="hd"><h2>Open now</h2><span class="cap">your journal positions and the signals being tracked</span></div><div class="bd">${!open.length && !act.length ? App.ui.empty('Nothing open', '') : `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>What</th><th>Source</th><th class="n">Entry</th><th class="n">Stop</th><th class="n">Status</th></tr></thead><tbody>
    ${open.map(t => `<tr class="click" data-jid="${t.id}"><td><b>${esc(t.inst)}</b> <small class="muted">${esc(t.cat || '')} · ${esc(t.d)}</small></td><td><span class="pill sun">your trade</span></td><td class="n">${fmt(t.entry)}</td><td class="n">${fmt(t.sl)}</td><td class="n">risk ${inr(t.risk)}</td></tr>`).join('')}
    ${act.map(([k, s]) => `<tr class="click" data-href="#/trade?s=${k}&sig=${encodeURIComponent(s.id)}"><td><b>${esc(s.instrument || s.symbol)}</b> <small class="muted">${k}</small></td><td><span class="pill info">signal</span></td><td class="n">${fmt(s.entry)}</td><td class="n">${fmt(s.stop)}</td><td class="n ${cls(s.r_now)}">${rr(s.r_now)} · ${esc(SC.sigStatus(s))}</td></tr>`).join('')}</tbody></table></div>`}</div></div>`;
  h += `</div><div class="stack">`;
  h += `<div class="card"><div class="hd"><h2>Risk status</h2><span class="sp"></span><span class="pill ${lvl[0] === 'good' ? 'ok' : lvl[0]}">${lvl[1]}</span></div><div class="bd"><div class="kv">
    <span>Today</span><b class="${cls(rs.day)}">${pct(rs.day, 2)}</b><span>This week</span><b class="${cls(rs.week)}">${pct(rs.week, 2)}</b><span>This month</span><b class="${cls(rs.month)}">${pct(rs.month, 2)}</b>
    <span>Open risk</span><b>${pct(rs.openRisk, 2)} <small class="muted">of ${pct(rs.S.openMax, 1)}</small></b><span>Intraday trades today</span><b>${rs.intra} / ${rs.S.maxIntra}</b><span>Risk per trade</span><b>${pct(rs.S.riskN, 2)} · A+ ${pct(rs.S.riskA, 2)}</b></div>
    ${rs.msgs.length ? `<ul class="ins" style="margin-top:12px">${rs.msgs.map(([k, t]) => `<li class="${k}"><i></i><span>${esc(t)}</span></li>`).join('')}</ul>` : '<p class="help" style="margin-top:10px">All limits are clear. Success today = following your rules, not P&L.</p>'}</div></div>`;
  h += `<div class="card"><div class="hd"><h2>Insights</h2><span class="sp"></span><a class="btn sm" href="#/analytics">Analytics</a></div><div class="bd"><ul class="ins">${App.analytics.insights(all, all.C, J.set).slice(0, 4).map(([k, t]) => `<li class="${k}"><i></i><span>${t}</span></li>`).join('')}</ul>
    ${all.n >= 2 ? `<div style="margin-top:10px" id="dEq"></div>` : ''}</div></div>`;
  const ev = (nw.events || []).slice(0, 6), flags = nw.risk_flags || [];
  h += `<div class="card"><div class="hd"><h2>Events and risk</h2><span class="sp"></span><a class="btn sm" href="#/news">News</a></div><div class="bd">${flags.map(f => App.ui.callout('warn', esc(f))).join('<div style="height:8px"></div>')}${flags.length ? '<div style="height:10px"></div>' : ''}
    ${ev.length ? `<ul class="timeline">${ev.map(e => `<li class="${e.impact === 'high' ? 'bad' : ''}"><time>${esc(e.date)}${e.time ? ' · ' + esc(e.time) : ''} · ${e.days === 0 ? 'today' : e.days === 1 ? 'tomorrow' : 'in ' + e.days + ' days'}</time>${esc(e.title)}</li>`).join('')}</ul>` : App.ui.empty('No events loaded', '')}</div></div>`;
  h += `</div></div>`;
  if (m.playbook) h += `<div class="card"><div class="hd"><h2>Market playbook for today</h2><span class="cap">${esc(m.playbook.today || '')}</span></div><div class="bd grid g3">${['swing', 'options', 'intraday'].map(k => `<div><div class="fsec" style="margin-top:0">${k === 'options' ? 'Nifty options' : k[0].toUpperCase() + k.slice(1)}</div><ul class="ins">${(m.playbook[k] || []).map(x => `<li><i></i><span>${esc(x)}</span></li>`).join('')}</ul></div>`).join('')}</div></div>`;
  return h;
};
App.binds.dashboard = () => {
  $$('tr[data-href]').forEach(tr => tr.onclick = () => location.hash = tr.dataset.href); $$('tr[data-jid]').forEach(tr => tr.onclick = () => JR.openForm(tr.dataset.jid));
  const el = $('#dEq'); if (el) { const st = App.analytics.stats(JR.enrich(), JR.J().set); el.innerHTML = App.charts.line([{ pts: st.curve, c: st.net >= 0 ? 'good' : 'bad', area: true }], { W: el.clientWidth || 360, H: 120, zero: true, fmt: v => inr(v), label: 'Equity' }); }
};

/* ---------- market ---------- */
App.pages.market = () => {
  const m = App.data.market; if (!m) return `<div class="ph"><h1>Market</h1></div>` + App.ui.empty('No market data yet', '');
  const d = m.daily || {}, i = m.intraday || {}, b = m.breadth || {}, e = m.expected_move || {}, pb = m.playbook || {};
  let h = `<div class="ph"><div><h1>Market</h1><p>Nifty regime on the daily and today, how wide the day can be, breadth of the Nifty 500 and which sectors lead. Use it to size and to choose which playbook to lean on.</p></div><span class="sp"></span><span class="pill info">${esc(hmIST(m.generated_at))}</span></div>`;
  h += `<div class="kpis" style="margin-bottom:14px">${App.ui.kpi('Daily regime', esc(d.label || '-'), `ADX ${fmt(d.adx, 0)} · efficiency ${fmt(d.er10)}`)}${App.ui.kpi('Today', esc(i.label || '-'), i.gap_pct != null ? `gap ${sg(i.gap_pct)}%` : '')}${App.ui.kpi('EMA stack', esc(d.stack || '-'), `9 ${fmt0(d.ema9)} · 21 ${fmt0(d.ema21)} · 50 ${fmt0(d.ema50)}`)}
    ${App.ui.kpi('Expected move', `±${fmt0(e.daily_pts)} pts`, `today (${fmt(e.daily_pct)}%), ±${fmt0(e.weekly_pts)} this week`)}${App.ui.kpi('ATR', fmt0(d.atr), `${fmt(d.atr_pct)}% · ${d.atr_rank}th percentile`)}${App.ui.kpi('India VIX', fmt(d.vix), `${d.vix_rank}th percentile of the year`)}</div>`;
  h += `<div class="grid g2" style="margin-bottom:14px"><div class="card"><div class="hd"><h2>Reading</h2></div><div class="bd"><p>${esc(d.reading || '')}</p><p class="help" style="margin-top:8px">${esc(i.reading || '')}</p>${pb.headline ? `<div style="height:10px"></div>${App.ui.callout('info', `<b>${esc(pb.headline)}</b><br>${(pb.risk || []).map(esc).join(' ')}`)}` : ''}</div></div>
    <div class="card"><div class="hd"><h2>Breadth (Nifty 500)</h2><span class="cap">${b.count || 0} stocks</span></div><div class="bd"><div class="kv"><span>Advancing / declining</span><b>${b.advancers} / ${b.decliners}</b><span>Above 21 / 50 / 200 EMA</span><b>${fmt0(b.above21)}% / ${fmt0(b.above50)}% / ${b.above200 == null ? '-' : fmt0(b.above200) + '%'}</b><span>New 52-week highs / lows</span><b>${b.new_highs} / ${b.new_lows}</b><span>Average stock 5d / 20d</span><b>${sg(b.avg_5d)}% / ${sg(b.avg_20d)}%</b><span>Nifty 20d</span><b>${sg(b.nifty_20d)}%</b></div></div></div></div>`;
  const sec = (m.sectors || []).slice().sort((a, b) => b.rs20 - a.rs20), mx = Math.max(1, ...sec.map(s => Math.abs(s.rs20)));
  h += `<div class="card" style="margin-bottom:14px"><div class="hd"><h2>Sectors</h2><span class="cap">relative strength against Nifty over 20 days: buy pullbacks in the strong ones</span></div><div class="bd tbl-wrap"><table class="tbl"><thead><tr><th>Sector</th><th class="n">Stocks</th><th class="n">Above 50 EMA</th><th class="n">5 days</th><th class="n">20 days</th><th class="n">RS 20d</th><th style="min-width:140px"></th><th>State</th></tr></thead><tbody>
    ${sec.map(s => `<tr><td><b>${esc(s.sector)}</b></td><td class="n">${s.count}</td><td class="n">${s.above50}%</td><td class="n ${cls(s.ret5)}">${sg(s.ret5)}%</td><td class="n ${cls(s.ret20)}">${sg(s.ret20)}%</td><td class="n ${cls(s.rs20)}">${sg(s.rs20)}</td><td class="bar-cell">${App.charts.hbar(s.rs20, mx)}</td><td><span class="pill ${s.state === 'strong' ? 'ok' : s.state === 'weak' ? 'bad' : ''}">${esc(s.state)}</span></td></tr>`).join('')}</tbody></table></div></div>`;
  h += `<div class="card"><div class="hd"><h2>Playbook by segment</h2></div><div class="bd grid g3">${['swing', 'options', 'intraday'].map(k => `<div><div class="fsec" style="margin-top:0">${k === 'options' ? 'Nifty options' : k[0].toUpperCase() + k.slice(1)}</div><ul class="ins">${(pb[k] || []).map(x => `<li><i></i><span>${esc(x)}</span></li>`).join('')}</ul></div>`).join('')}</div></div>`;
  return h;
};

/* ---------- news ---------- */
const NU = () => App.ui.nw || (App.ui.nw = { topic: 'all' });
App.pages.news = () => {
  const n = App.data.news; if (!n) return `<div class="ph"><h1>News & events</h1></div>` + App.ui.empty('No news yet', '');
  const u = NU(), topics = [...new Set((n.headlines || []).flatMap(x => x.topics || []))], H = (n.headlines || []).filter(x => u.topic === 'all' || (x.topics || []).includes(u.topic));
  let h = `<div class="ph"><div><h1>News & events</h1><p>Market headlines tagged by topic and impact, the events calendar (expiries, RBI, Fed, holidays, results of your setups) and today's risk flags.</p></div><span class="sp"></span><span class="pill info">${esc(hmIST(n.generated_at))}</span></div>`;
  h += (n.risk_flags || []).map(f => App.ui.callout('warn', esc(f))).join('<div style="height:8px"></div>') + ((n.risk_flags || []).length ? '<div style="height:14px"></div>' : '');
  h += `<div class="grid g-main"><div class="card"><div class="hd"><h2>Headlines</h2><span class="sp"></span><div class="chips">${['all', ...topics].map(t => `<button class="chip" data-topic="${esc(t)}" aria-pressed="${u.topic === t}">${t === 'all' ? 'All' : esc(t)}</button>`).join('')}</div></div>
    <div class="bd">${H.length ? `<ul class="news">${H.map(x => `<li><span class="imp ${x.impact || ''}"></span><div><a href="${esc(x.link)}" target="_blank" rel="noopener">${esc(x.title)}</a><br><small>${esc(x.source || '')}${x.published ? ' · ' + esc(ago(x.published)) : ''}${(x.topics || []).length ? ' · ' + x.topics.map(esc).join(', ') : ''}</small></div></li>`).join('')}</ul>` : App.ui.empty('No headlines', '')}</div></div>
    <div class="stack"><div class="card"><div class="hd"><h2>Events calendar</h2></div><div class="bd">${(n.events || []).length ? `<ul class="timeline">${n.events.map(e => `<li class="${e.impact === 'high' ? 'bad' : ''}"><time>${esc(e.date)}${e.time ? ' · ' + esc(e.time) + ' IST' : ''} · ${e.days === 0 ? 'today' : e.days === 1 ? 'tomorrow' : 'in ' + e.days + ' days'}</time><b>${esc(e.title)}</b>${e.note ? `<br><small class="muted">${esc(e.note)}</small>` : ''}</li>`).join('')}</ul>` : App.ui.empty('No events', '')}</div></div>
    ${Object.keys(n.by_symbol || {}).length ? `<div class="card"><div class="hd"><h2>Your setups in the news</h2></div><div class="bd"><ul class="news">${Object.entries(n.by_symbol).flatMap(([s, a]) => a.slice(0, 2).map(x => `<li><span class="imp ${x.impact || ''}"></span><div><b>${esc(s)}</b> · <a href="${esc(x.link)}" target="_blank" rel="noopener">${esc(x.title)}</a><br><small>${esc(x.source || '')}</small></div></li>`)).join('')}</ul></div></div>` : ''}</div></div>`;
  return h;
};
App.binds.news = () => $$('[data-topic]').forEach(b => b.onclick = () => { NU().topic = b.dataset.topic; App.render(); });

/* ---------- playbook (your own walk-through) ---------- */
const PBC = { good: 'var(--good)', bad: 'var(--bad)', brand: 'var(--brand)', warn: 'var(--warn)', sun: 'var(--sun)', ink: 'var(--ink-2)', c1: 'var(--c1)', c6: 'var(--c6)' };
const pbEma = cl => { const k = 2 / 10, e = []; cl.forEach((v, i) => e.push(i ? e[i - 1] + k * (v - e[i - 1]) : v)); return e; };
function pbSvg(pb, si) {
  const st = pb.steps[si], tf = st.tf, D = pb.data[tf], n = D.length, up = Math.min(st.up, n - 1), anns = pb.ann[tf].filter(a => a.s <= si + 1);
  let lo = Math.min(...D.map(c => c[2])), hi = Math.max(...D.map(c => c[1])); anns.forEach(a => { if (a.sc) [a.p, a.p1, a.p2].forEach(v => { if (v != null) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }); });
  const pad = (hi - lo) * .07; lo -= pad; hi += pad; const W = 440, PL = 6, PW = 322, PT = 10, PH = 226, VT = 256, VH = 46, RX = PL + PW + 5;
  const X = i => PL + (i + .5) * PW / n, Y = p => PT + (hi - p) / (hi - lo) * PH, bw = PW / n * .62, vmax = Math.max(...D.map(c => c[4])), inr_ = p => p >= lo && p <= hi, g = [], labs = [], col = c => PBC[c] || PBC.ink;
  anns.filter(a => a.k === 'z').forEach(a => { if (a.p2 < lo || a.p1 > hi) return; const y1 = Y(Math.min(a.p2, hi)), y2 = Y(Math.max(a.p1, lo)), x1 = a.a ? X(a.a) - bw / 2 : PL;
    g.push(`<rect x="${x1}" y="${y1}" width="${PL + PW - x1}" height="${Math.max(2, y2 - y1)}" style="fill:${col(a.c)};opacity:.17"/>`); labs.push({ y: (y1 + y2) / 2, t: a.lab, c: col(a.c), s: a.s }); });
  anns.filter(a => a.k === 'h').forEach(a => { if (!inr_(a.p)) return; const x1 = a.a != null ? X(a.a) : PL, x2 = a.b != null ? X(a.b) + PW / n : PL + PW;
    g.push(`<line x1="${x1}" x2="${x2}" y1="${Y(a.p)}" y2="${Y(a.p)}" style="stroke:${col(a.c)};stroke-width:1.1${a.d ? ';stroke-dasharray:4 3' : ''}"/>`); if (a.lab) labs.push({ y: Y(a.p), t: a.lab, c: col(a.c), s: a.s }); });
  for (let i = 0; i <= up; i++) { const [o, h, l, c, v] = D[i], cc = c >= o ? 'var(--good)' : 'var(--bad)', vh = v / vmax * VH;
    g.push(`<line x1="${X(i)}" x2="${X(i)}" y1="${Y(h)}" y2="${Y(l)}" style="stroke:${cc}"/><rect x="${X(i) - bw / 2}" y="${Y(Math.max(o, c))}" width="${bw}" height="${Math.max(1, Math.abs(Y(o) - Y(c)))}" style="fill:${cc}"/><rect x="${X(i) - bw / 2}" y="${VT + VH - vh}" width="${bw}" height="${vh}" style="fill:var(--ink-3);opacity:.32"/>`); }
  const em = pbEma(D.map(c => c[3])); g.push(`<polyline points="${em.slice(0, up + 1).map((v, i) => `${X(i)},${Y(v)}`).join(' ')}" fill="none" style="stroke:var(--c6);stroke-width:1.4"/>`);
  anns.filter(a => a.k === 'v').forEach(a => { if (a.i > up) return; const vh = D[a.i][4] / vmax * VH; g.push(`<rect x="${X(a.i) - bw / 2}" y="${VT + VH - vh}" width="${bw}" height="${vh}" style="fill:var(--brand)"/><text x="${X(a.i)}" y="${VT + VH - vh - 3}" font-size="10.5" font-weight="700" text-anchor="middle" style="fill:var(--brand)">${a.lab}</text>`); });
  anns.filter(a => a.k === 'm').forEach(a => { if (a.i > up) return; const cx = X(a.i), cy = Y(a.p), ty = cy + a.dy + (a.dy > 0 ? 7 : -1);
    g.push(`<circle cx="${cx}" cy="${cy}" r="3.2" style="fill:none;stroke:${col(a.c)};stroke-width:1.3"/><text x="${Math.min(Math.max(cx, 24), PL + PW - 24)}" y="${ty}" font-size="10.5" font-weight="700" text-anchor="middle" style="fill:${col(a.c)}">${a.lab}</text>`); });
  const cur = si + 1; labs.sort((a, b) => ((b.s === cur) - (a.s === cur)) || b.s - a.s); labs.length = Math.min(labs.length, 8); labs.sort((a, b) => a.y - b.y); let last = -99; labs.forEach(l => { l.y = Math.max(l.y, last + 12); last = l.y; });
  return `<svg class="pb-svg" viewBox="0 0 ${W} 316" role="img" aria-label="Illustrative ${tf} chart, step ${si + 1}: ${esc(st.t)}">${g.join('')}${labs.map(l => `<text x="${RX}" y="${l.y + 3.5}" font-size="11" font-weight="650" style="fill:${l.c}">${l.t}</text>`).join('')}<text x="${PL + 2}" y="${VT - 3}" font-size="10" style="fill:var(--ink-3)">Volume</text><text x="${W - 4}" y="312" font-size="10" text-anchor="end" style="fill:var(--ink-3)">${tf} · illustrative</text></svg>`;
}
function pbBody(si) {
  const pb = window.PLAYBOOK.swing, st = pb.steps[si], N = pb.steps.length;
  return `<div class="pb-tabs">${pb.tfs.map(t => `<button type="button" class="pb-tab${t === st.tf ? ' on' : ''}" data-pbtf="${t}"><b>${t}</b><small>${pb.tfRole[t]}</small></button>`).join('')}</div>
    <div class="pb-head"><span class="pb-tf">${st.tf} chart</span><span class="pb-n">Step ${si + 1} of ${N}</span><span class="pb-ttl">${esc(st.t)}</span></div>${pbSvg(pb, si)}
    <div class="pb-leg"><span><i style="background:var(--c6)"></i>9 EMA</span><span><i style="background:var(--good)"></i>FVG</span><span><i style="background:var(--c1)"></i>OB</span><span><i style="background:var(--sun)"></i>Fib zone</span></div>
    <p class="pb-x">${esc(st.x)}</p><div class="pb-ticks">${pb.ticks.map(([l, k]) => `<span class="pb-tick${si + 1 >= k ? ' on' : ''}">${si + 1 >= k ? '✓ ' : ''}${esc(l)}</span>`).join('')}</div>
    <div class="pb-ctl"><button type="button" class="btn sm" data-pbs="prev"${si === 0 ? ' disabled' : ''}>Back</button><button type="button" class="btn sm primary" data-pbs="next"${si === N - 1 ? ' disabled' : ''}>Next</button><button type="button" class="btn sm ghost" data-pbs="${N - 1}">Full plan</button><span class="pb-dots">${pb.steps.map((s, i) => `<button type="button" class="pb-dot${i === si ? ' on' : i < si ? ' done' : ''}" data-pbs="${i}" aria-label="Step ${i + 1}">${i + 1}</button>`).join('')}</span></div>`;
}
App.pages.playbook = () => {
  const S = JR.J().set, rules = (window.RULES || []).map(([n, t]) => [n, t.replace('@RISKSIZING@', `Normal ${pct(S.riskN, 2)}, A+ ${pct(S.riskA, 2)}, hard ceiling ${pct(S.riskC, 1)} of capital (${inr(S.capital)}).`)]);
  const tbl = (head, rows) => `<div class="tbl-wrap"><table class="tbl"><thead><tr>${head.map(x => `<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map((c, i) => `<td>${i === 0 ? '<b>' + c + '</b>' : c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  return `<div class="ph"><div><h1>Playbook & rules</h1><p>The strategy the scanner follows, step by step, and your trading rules. The swing scanner ticks each of these steps on every setup's checklist.</p></div></div>
    <div class="card" style="margin-bottom:14px"><div class="hd"><h2>Swing playbook: 1D, 1H and 15m</h2><span class="cap">illustrative chart, not a forecast</span></div><div class="bd" id="pb">${pbBody(App.ui.pbs || 0)}</div></div>
    <div class="grid g2" style="margin-bottom:14px"><div class="card"><div class="hd"><h2>Swing: timeframes</h2></div><div class="bd">${tbl(['Timeframe', 'Job', 'What you check'], [['Weekly', 'Location', 'Trend up, price near support'], ['1D', 'Structure and zone', 'Sweep, CHoCH, BOS, FVG + OB, fib, round number'], ['1H', 'Confirmation', 'Rejection, 9 EMA reclaim, volume at least 1.5x'], ['15m', 'Precision entry', 'CHoCH, BOS and FVG inside the zone, retest, trigger']])}
      <p class="help" style="margin-top:8px">Plan: stop below the daily OB with a buffer · T1 1R partial · T2 2R · T3 3R · trail by daily structure, never widen. Check results date and futures OI before holding.</p></div></div>
    <div class="card"><div class="hd"><h2>Nifty options: timeframes</h2></div><div class="bd">${tbl(['Timeframe', 'Job', 'What you check'], [['1H', 'Alignment', 'Price on the same side of the 9 EMA as your trade'], ['15m', 'Bias and context', 'Previous-day high or low sweep, CHoCH, 9 EMA'], ['5m', 'Setup and trigger', 'CHoCH + BOS, FVG + OB, fib, pullback, 9 EMA close']])}
      <p class="help" style="margin-top:8px">Skip expiry-day afternoons and big event days. Convert the index stop to premium (points × delta) and size so that loss is your fixed risk. Stop after two losses in a day.</p></div></div></div>
    <div class="card" style="margin-bottom:14px"><div class="hd"><h2>Scorecard</h2></div><div class="bd">${tbl(['Category', 'Points', 'What counts'], [['Structure', '0 to 2', '1D CHoCH + BOS (options: 15m CHoCH + 5m CHoCH + BOS)'], ['Zone', '0 to 2', 'FVG + OB overlap and quality'], ['Confirmation', '0 to 3', '1H rejection + 9 EMA reclaim + relative volume'], ['Context', '0 to 3', 'Key level, fib 0.618, MTF EMA (futures OI: you check), capped at 3']])}<p class="help" style="margin-top:8px">A+ 8–10 · A 6–7 · B 4–5 observe · under 4 no trade.</p></div></div>
    <div class="sec-h"><h2>Your rules</h2><span class="sp"></span><span class="cap muted">${rules.length} rules</span></div><ol class="rules">${rules.map(([n, t]) => `<li><b>${esc(n)}</b><p>${esc(t)}</p></li>`).join('')}</ol>`;
};
App.binds.playbook = () => {
  const host = $('#pb'); if (!host) return;
  host.onclick = e => { const t = e.target.closest('[data-pbs],[data-pbtf]'); if (!t) return; const pb = window.PLAYBOOK.swing, N = pb.steps.length; let si = App.ui.pbs || 0;
    if (t.dataset.pbtf) si = Math.max(0, pb.steps.findIndex(s => s.tf === t.dataset.pbtf)); else { const v = t.dataset.pbs; si = v === 'next' ? Math.min(N - 1, si + 1) : v === 'prev' ? Math.max(0, si - 1) : +v; }
    App.ui.pbs = si; host.innerHTML = pbBody(si); };
};

/* ---------- settings ---------- */
App.pages.settings = () => {
  const J = JR.J(), S = J.set, C = JR.Cloud;
  const acct = C.userId ? `<div class="kv"><span>Signed in as</span><b>${esc(C.email || '')}</b><span>Status</span><b class="${C.mode === 'cloud' ? 'good' : 'bad'}">${C.mode === 'cloud' ? 'Synced' + (C.last ? ' ' + ago(C.last) : '') : 'Paused: ' + esc(C.err)}</b></div><div style="display:flex;gap:8px;margin-top:12px"><button class="btn" id="sSync">${ic('cloud')} Sync now</button><button class="btn danger" id="sOut">Sign out</button></div>`
    : `<p class="help" style="margin-bottom:10px">Sign in with your Trade Insight account: the same journal syncs here, in Trade Insight and on every device.</p><div class="fgrid"><div class="field w2"><label for="sEm">Email</label><input id="sEm" type="email" autocomplete="username"></div><div class="field w2"><label for="sPw">Password</label><input id="sPw" type="password" autocomplete="current-password"></div></div><div style="display:flex;gap:8px;align-items:center;margin-top:12px"><button class="btn primary" id="sIn">Sign in</button><span class="help" id="sMsg"></span></div>`;
  return `<div class="ph"><div><h1>Settings</h1><p>Your account, journals, risk rules and appearance.</p></div></div>
    <div class="grid g2" style="margin-bottom:14px"><div class="card"><div class="hd"><h2>Cloud journal</h2></div><div class="bd">${acct}</div></div>
    <div class="card"><div class="hd"><h2>Journals</h2><span class="sp"></span><button class="btn sm" id="sNew">${ic('plus')} New</button></div><div class="bd"><table class="tbl"><tbody>${JR.E.list.map(j => `<tr><td><b>${esc(j.name)}</b>${j.demo ? ' <span class="pill">sample</span>' : ''}${j.id === J.id ? ' <span class="pill ok">current</span>' : ''}<br><small class="muted">${j.trades.length} trades</small></td><td class="n"><button class="btn sm" data-use="${j.id}"${j.id === J.id ? ' disabled' : ''}>Use</button> <button class="btn sm" data-ren="${j.id}">Rename</button> <button class="btn sm danger" data-del="${j.id}">Delete</button></td></tr>`).join('')}</tbody></table>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap"><button class="btn" id="sExp">${ic('download')} Backup (JSON)</button><button class="btn" id="sCsv">${ic('download')} CSV</button><label class="btn">${ic('upload')} Import backup<input type="file" accept=".json" id="sImp" hidden></label></div></div></div></div>
    <div class="card" style="margin-bottom:14px"><div class="hd"><h2>Risk rules for ${esc(J.name)}</h2><span class="cap">used for position size, the risk status and the analytics</span></div><div class="bd"><div class="fgrid">${JR.SETKEYS.map(([k, l, t]) => `<div class="field"><label for="set-${k}">${l}${t === 'p' ? ' (%)' : ''}</label><input id="set-${k}" data-set="${k}" data-t="${t}" type="number" step="any" inputmode="decimal" value="${t === 'p' ? +(S[k] * 100).toFixed(3) : S[k]}"></div>`).join('')}</div>
      <div style="display:flex;gap:8px;margin-top:12px"><button class="btn primary" id="sSave">Save rules</button><button class="btn" id="sReset">Reset to your defaults</button></div></div></div>
    <div class="grid g2"><div class="card"><div class="hd"><h2>Appearance</h2></div><div class="bd">${App.ui.seg('theme', [['auto', 'Match device'], ['light', 'Light'], ['dark', 'Dark']], (store.get('tji_ui_v1', {}) || {}).theme || 'auto')}</div></div>
    <div class="card"><div class="hd"><h2>Scanner</h2></div><div class="bd"><div class="kv"><span>Nifty options, intraday, market</span><b>every 5 minutes, 09:05–15:40</b><span>Swing (Nifty 500)</span><b>hourly at :25, 08:37 and 16:17</b><span>News</span><b>about every 30 minutes</b><span>Last swing scan</span><b>${App.data.swing ? esc(dateIST(App.data.swing.generated_at) + ' ' + hmIST(App.data.swing.generated_at)) : '-'}</b></div><p class="help" style="margin-top:8px">Runs in GitHub Actions and publishes here. If the header says "Delayed", open the Actions tab of your repo.</p></div></div></div>`;
};
App.binds.settings = () => {
  const J = JR.J();
  const si = $('#sIn'); if (si) si.onclick = async () => { const m = $('#sMsg'); m.textContent = 'Signing in…'; try { await JR.signIn($('#sEm').value.trim(), $('#sPw').value); App.toast('Signed in: journal synced'); } catch (e) { m.textContent = e.message || 'Sign-in failed'; m.className = 'help bad'; } };
  const so = $('#sOut'); if (so) so.onclick = JR.signOut; const sy = $('#sSync'); if (sy) sy.onclick = JR.syncNow;
  $('#sNew').onclick = () => { const n = prompt('Name of the new journal'); if (n) { JR.newJournal(n.trim()); App.render(); } };
  $$('[data-use]').forEach(b => b.onclick = () => JR.setCurrent(b.dataset.use));
  $$('[data-ren]').forEach(b => b.onclick = () => { const j = JR.E.list.find(x => x.id === b.dataset.ren), n = prompt('New name', j.name); if (n) { j.name = n.trim(); j.updated = Date.now(); JR.persist(); App.render(); } });
  $$('[data-del]').forEach(b => b.onclick = () => { const j = JR.E.list.find(x => x.id === b.dataset.del); if (confirm(`Delete the journal "${j.name}" and its ${j.trades.length} trades? Export a backup first if unsure.`)) JR.deleteJournal(j.id); });
  $('#sExp').onclick = JR.exportJSON; $('#sCsv').onclick = JR.exportCSV;
  $('#sImp').onchange = e => { const f = e.target.files[0]; if (f) JR.importFile(f).then(j => { App.toast(`Imported ${j.trades.length} trades as a new journal`); App.render(); }).catch(er => App.toast('Import failed: ' + er.message)); };
  $('#sSave').onclick = () => { $$('[data-set]').forEach(el => { const v = parseFloat(el.value); if (isFinite(v)) J.set[el.dataset.set] = el.dataset.t === 'p' ? v / 100 : v; }); JR.touch(); JR.persist(); App.toast('Risk rules saved'); App.render(); };
  $('#sReset').onclick = () => { if (confirm('Reset the risk rules to your defaults?')) { J.set = { ...JR.SET0 }; JR.touch(); JR.persist(); App.render(); } };
  $$('[data-seg="theme"]').forEach(b => b.onclick = () => App.setTheme(b.dataset.v));
};
})();
