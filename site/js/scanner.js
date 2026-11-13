/* Scanner pages (swing first), tracked trades and the trade page. */
'use strict';
(function () {
const SC = App.scanner = {};
/* A swing setup your rules hold back (ran away, sector falling, under 2R room, ...) stays listed with its reason but is not counted as actionable. */
SC.held = s => (s.holds || []).length > 0 || String(s.status || '').startsWith('WATCH');
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
function card(sec, it) {
  /* The condensed card: name and score, one status line, a thin chart, three levels, one footer line. Everything else (T2/T3, the full
     checklist, every caution) is on the trade page, one tap away. */
  const d = dec(it), hot = it.status === 'TRIGGERED', href = `#/trade?s=${sec}&id=${encodeURIComponent(it.symbol + '|' + it.direction)}`, tracked = App.LED(sec).signals.some(s => s.id === key(sec, it));
  const ot = it.options_trade, stage = it.stage, cautions = [...(it.holds || []).map(x => 'Held: ' + x), ...(it.notes || [])];
  const sub = sec === 'options' ? (ot ? `${esc(ot.instrument)} · Δ ${fmt(ot.delta)} · ₹${fmt(ot.premium)}` : 'Nifty 50 index') : [it.sector, it.rs_rank != null ? 'RS ' + it.rs_rank : ''].filter(Boolean).map(esc).join(' · ');
  const sp = it.spark || (it.candles ? it.candles.slice(-60).map(c => c[3]) : null), spark = sp && sp.length ? App.charts.spark(sp, { lo: it.zone_bot, hi: it.zone_top, sl: it.sl }) : '';
  const lv = it.entry != null ? [['e', hot || stage >= 5 ? 'Entry' : 'Plan', it.entry], ['s', 'Stop', it.sl], ['t', 'T1', it.t1]] : [['', 'CHoCH', it.choch_level], ['', 'Price', it.price]];
  const ticks = (it.ticks || []).length, foot = [ticks ? `<span class="cf" title="${esc((it.ticks || []).join(', '))}">${'●'.repeat(ticks)}${'○'.repeat(Math.max(0, 3 - ticks))}<em>context</em></span>` : '',
    it.risk_pct != null ? `<span>risk ${fmt(it.risk_pct, 1)}%</span>` : '', tracked ? '<span class="trk">tracked</span>' : '', App.journal.findByTag(key(sec, it)) ? '<span class="trk">in journal</span>' : '',
    cautions.length ? `<span class="cau" title="${esc(cautions.join(' · '))}">⚠ ${cautions.length}</span>` : ''].filter(Boolean).join('');
  const full = String(it.status || ''), held_ = sec === 'swing' && (it.holds || []).length;      // the card shows the stage; the full status is on hover and on the trade page
  const label = held_ ? 'HELD · ' + (it.holds || [])[0] : full.startsWith('WATCH') ? full.replace(/ \(/, ' · ').replace(/\)$/, '') : full.split(' (')[0];
  return `<a class="sc${hot ? ' hot' : ''}" href="${href}"><div class="sc-h"><div class="nm"><b>${esc(it.symbol)}${sec !== 'swing' ? ` <span class="tag ${it.direction}">${esc(it.label)}</span>` : ''}</b><small>${sub || '&nbsp;'}</small></div>
    <div class="sc-score" title="Score ${it.score}/10, grade ${esc(it.grade)}"><b>${it.score}</b><span class="g ${String(it.grade).replace('+', 'p').toLowerCase()}">${esc(it.grade)}</span></div></div>
    <div class="sc-st ${stCls(it)}" title="${esc(full)}"><i></i><span>${esc(label)}</span>${stage ? `<span class="dots${stage === 5 ? ' s5' : ''}" title="Playbook stage ${stage} of 5">${[1, 2, 3, 4, 5].map(k => `<b class="${k <= stage ? 'on' : ''}"></b>`).join('')}</span>` : ''}</div>
    ${spark}<div class="sc-lv">${lv.map(([c, l, v]) => `<span class="${c}"><small>${l}</small><b>${fmt(v, d)}</b></span>`).join('')}</div>
    ${foot ? `<div class="sc-f">${foot}</div>` : ''}</a>`;
}

/* ---------- tracked trades (signals) ---------- */
function ledgerView(sec, view) {
  const L = App.LED(sec), act = L.signals.filter(s => s.status === 'ACTIVE'), clo = L.signals.filter(s => s.status === 'CLOSED').sort((a, b) => (b.closed || '').localeCompare(a.closed || '')), drop = (L.dropped || []).slice().reverse();
  const row = s => { const closed = s.status === 'CLOSED', r = closed ? s.r_final : s.r_now, nt = nextT(s), d = sec === 'options' ? 1 : 2;
    return `<tr class="click" data-href="#/trade?s=${sec}&sig=${encodeURIComponent(s.id)}"><td><b>${esc(s.instrument || s.symbol)}</b> ${sec !== 'swing' ? `<span class="tag ${s.direction}">${esc(s.label)}</span>` : ''}<br><small class="muted">${closed ? 'closed ' + esc((s.closed || '').replace('T', ' ').slice(5, 16)) : 'since ' + esc((s.created || '').replace('T', ' ').slice(5, 16))} · ${esc(s.grade)} ${s.score}/10</small></td>
      <td><span class="st ${closed ? (r > 0 ? 's4' : 'closed') : 's3'}">${esc(sigStatus(s))}</span></td><td class="n">${fmt(s.entry, d)}</td><td class="n">${fmt(closed ? s.sl : s.stop, d)}</td><td class="n">${closed ? fmt(s.exit, d) : fmt(nt[1], d) + ' <small class="muted">' + nt[0] + '</small>'}</td><td class="n">${fmt(closed ? s.exit : s.last, d)}</td><td class="n ${cls(r)}"><b>${rr(r)}</b></td></tr>`; };
  const tbl = (rows, head) => `<div class="tbl-wrap"><table class="tbl"><thead><tr>${head.map((h, i) => `<th class="${i >= 2 ? 'n' : ''}">${h}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div>`;
  if (view === 'active') return `<div class="card"><div class="bd">${act.length ? tbl(act.map(row).join(''), ['Trade', 'Status', 'Entry', 'Stop now', 'Next target', 'Last', 'R now']) + `<p class="help" style="margin-top:10px">Every triggered setup is followed on closed candles until the final target, the stop or the trailing stop${sec === 'swing' ? ' (swing: no breakeven at T1, stop to entry at T2)' : ', or 15:15'}. Tap a row for its timeline.</p>` : App.ui.empty('No open trades', 'When a setup triggers it moves here and is followed every run until it closes.')}</div></div>`;
  return `<div class="card"><div class="hd"><h2>Closed trades</h2></div><div class="bd">${clo.length ? tbl(clo.map(row).join(''), ['Trade', 'Outcome', 'Entry', 'Stop', 'Exit', 'Exit', 'Result']) : App.ui.empty('Nothing closed yet', '')}</div></div>
    <div class="card" style="margin-top:14px"><div class="hd"><h2>Invalidated before triggering</h2></div><div class="bd">${drop.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Setup</th><th>Reason</th><th class="n">Zone</th><th class="n">Plan entry</th><th class="n">When</th></tr></thead><tbody>${drop.map(w => `<tr class="click" data-href="#/trade?s=${sec}&id=${encodeURIComponent(w.symbol + '|' + w.direction)}"><td><b>${esc(w.symbol)}</b> <small class="muted">was ${esc(w.status || '')} · ${esc(w.grade || '')}</small></td><td style="white-space:normal;min-width:220px">${esc(w.reason || '')}</td><td class="n">${fmt(w.zone_bot)}–${fmt(w.zone_top)}</td><td class="n">${fmt(w.entry)}</td><td class="n">${esc((w.dropped || '').replace('T', ' ').slice(5, 16))}</td></tr>`).join('')}</tbody></table></div>` : App.ui.empty('None', 'Setups that disappear before triggering are listed here with the reason.')}</div></div>`;
}
const viewSeg = (sec, view) => { const L = App.LED(sec), a = L.signals.filter(s => s.status === 'ACTIVE').length, c = L.signals.filter(s => s.status === 'CLOSED').length + (L.dropped || []).length;
  return App.ui.seg('view_' + sec, [['setups', 'Setups'], ['active', `Open trades ${a}`], ['closed', `Closed / invalidated ${c}`]], view); };
const meta = d => d ? `<span class="pill info">${esc(dateIST(d.generated_at))} ${esc(hmIST(d.generated_at))} · ${esc(ago(d.generated_at))}</span>${d.fast_at ? `<span class="pill" title="Between the hourly scans the 1H-confirmed setups are re-checked for a 15m entry every 15 minutes">15m entries checked ${esc(hmIST(d.fast_at))}</span>` : ''}` : '';

/* ---------- swing ---------- */
const SU = () => App.ui.sw || (App.ui.sw = { view: 'setups', stage: 'all', grade: 'all', q: '' });
App.pages.swing = () => {
  const u = SU(), d = App.data.swing;
  let h = `<div class="ph"><div><h1>Swing scanner</h1><p>Your swing playbook on the Nifty 500, long only: Weekly location → 1D CHoCH, BOS, FVG + OB, fib → 1H rejection and 9 EMA close on volume → 15m precision entry. Each setup shows how far along the playbook it is.</p></div><span class="sp"></span>${meta(d)}</div>`;
  h += `<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px">${viewSeg('swing', u.view)}</div>`;
  if (u.view !== 'setups') return h + ledgerView('swing', u.view);
  if (!d) return h + `<div class="card"><div class="bd">${App.ui.empty('No swing data yet', 'The swing scan runs before the open, right after each 1H candle closes and after the close.')}</div></div>`;
  const S = d.setups, cnt = k => S.filter(s => s.stage === k && !SC.held(s)).length, nHeld = S.filter(s => s.stage >= 3 && SC.held(s)).length;
  /* the playbook as a node graph (desktop): the scanned universe as an orb, a filament to each stage, the counts on the stage cards and a summary
     panel. The stage cards are the same buttons as before (they filter the list); on a phone it falls back to the strip of five. */
  const ready = cnt(5) + cnt(4), inplay = [5, 4, 3, 2].reduce((n, k) => n + cnt(k), 0), act = ready, sel = String(u.stage), ys = [10, 30, 50, 70, 90];
  const links = [5, 4, 3, 2, 1].map((k, i) => `<path d="M0,50 C55,50 45,${ys[i]} 100,${ys[i]}" class="${sel === String(k) ? 'on' : ''}${k >= 4 && cnt(k) ? ' live' : ''}"/>`).join('');
  h += `<div class="hero-pipe" style="margin-bottom:14px"><div class="hp-orb"><canvas data-orb data-energy="${Math.min(1, (ready * 3 + inplay / 6) / 12).toFixed(2)}" aria-hidden="true"></canvas><div class="hp-cap"><b>Nifty 500</b><small>${d.scanned || ''} scanned</small></div></div>
    <svg class="hp-links" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">${links}</svg>
    <div class="pipeline hp-nodes">${[5, 4, 3, 2, 1].map(k => `<button class="pipe p${k}" type="button" data-stage="${k}" aria-pressed="${String(u.stage) === String(k)}"><div class="k">${k}. ${STG[k][0]}</div><div class="v">${cnt(k)}</div><div class="d">${STG[k][1]}</div></button>`).join('')}</div>
    <div class="hp-panel"><div class="cap">Swing scan</div><div class="big">${ready}</div><div class="sub">ready: 1H confirmed or entry</div>
      <div class="hp-kv"><span>In play</span><b>${inplay}</b><span>Listed</span><b>${S.length}</b><span>Held back</span><b>${nHeld}</b><span>Full scan</span><b>${esc(hmIST(d.generated_at))}</b><span>15m entries</span><b>${d.fast_at ? esc(hmIST(d.fast_at)) : 'hourly'}</b></div></div></div>`;
  const short = S.filter(s => s.stage >= 3 && !(s.holds || []).length && !s.status.startsWith('WATCH')).sort((a, b) => b.stage - a.stage || b.score - a.score).slice(0, 5);
  if (short.length) h += App.ui.callout('good', `<b>Today's shortlist (max 5, pick 1 or 2):</b> ${short.map(s => `<a href="#/trade?s=swing&id=${encodeURIComponent(s.symbol + '|long')}"><b>${esc(s.symbol)}</b></a> <small>${STG[s.stage][0]} · ${s.grade} ${s.score}/10</small>`).join(' &nbsp;·&nbsp; ')}`) + '<div style="height:12px"></div>';
  let L = S.filter(s => (u.stage === 'all' ? s.stage >= 2 : u.stage === 'held' ? s.stage >= 3 && SC.held(s) : s.stage === +u.stage && !SC.held(s)) && (u.grade === 'all' || (u.grade === 'A' ? ['A', 'A+'].includes(s.grade) : s.grade === 'A+')) && (!u.q || s.symbol.includes(u.q.toUpperCase()) || (s.sector || '').toLowerCase().includes(u.q.toLowerCase())));
  h += `<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:12px">${App.ui.seg('swstage', [['all', 'All listed'], ...[5, 4, 3, 2, 1].map(k => [k, STG[k][0]]), ['held', 'Held back ' + nHeld]], u.stage)}${App.ui.seg('swgrade', [['all', 'Any grade'], ['A', 'A and A+'], ['A+', 'A+ only']], u.grade)}<input class="inp" style="width:180px" id="swQ" placeholder="Symbol or sector" value="${esc(u.q)}" aria-label="Filter"></div>`;
  L = L.slice().sort((a, b) => SC.held(a) - SC.held(b) || b.stage - a.stage || b.score - a.score);                // actionable first, held-back ones after them
  h += L.length ? `<div class="cards">${L.map(s => card('swing', s)).join('')}</div>` : `<div class="card"><div class="bd">${App.ui.empty('Nothing at this stage right now', u.stage === 'all' ? 'No stock is past the BOS with a pullback zone. Developing setups (CHoCH only) are in stage 1.' : u.stage === 'held' ? 'No setup is being held back by your rules right now.' : '')}</div></div>`;
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
  if (u.why && App.lazyAge('explain') > 60000) App.lazy('explain').then(() => { if (App.route().page === 'swing') App.render(); });
  const f = $('#whyF'); if (f) { const go = v => { u.why = v; App.render(); App.lazy('explain').then(() => App.render()); };
    f.onsubmit = e => { e.preventDefault(); go($('#whyQ').value); }; $$('[data-why]').forEach(a => a.onclick = e => { e.preventDefault(); go(a.dataset.why); }); }
  $$('[data-stage]').forEach(b => b.onclick = () => { u.stage = String(u.stage) === b.dataset.stage ? 'all' : b.dataset.stage; App.render(); });
  $$('[data-seg="swstage"]').forEach(b => b.onclick = () => { u.stage = b.dataset.v; App.render(); });
  $$('[data-seg="swgrade"]').forEach(b => b.onclick = () => { u.grade = b.dataset.v; App.render(); });
  const q = $('#swQ'); if (q) { let t; q.oninput = () => { clearTimeout(t); t = setTimeout(() => { u.q = q.value; App.render(); const z = $('#swQ'); if (z) { z.focus(); z.setSelectionRange(z.value.length, z.value.length); } }, 250); }; }
};
function bindView(sec, u) { $$(`[data-seg="view_${sec}"]`).forEach(b => b.onclick = () => { u.view = b.dataset.v; App.render(); }); $$('tr[data-href]').forEach(tr => tr.onclick = () => location.hash = tr.dataset.href); }

/* ---------- options ---------- */
const OU = () => App.ui.op || (App.ui.op = { view: 'setups' });
App.pages.options = () => {
  const u = OU(), d = App.data.options;
  let h = `<div class="ph"><div><h1>Nifty options</h1><p>Your options playbook: 1H alignment → 15m bias (CHoCH, previous-day sweep, 9 EMA) → 5m CHoCH + BOS, FVG + OB, fib, pullback, 9 EMA close. Strike by delta with India VIX. No volume or open-interest rules.</p></div><span class="sp"></span>${meta(d)}</div>
    <div style="margin-bottom:14px">${viewSeg('options', u.view)}</div>`;
  if (u.view !== 'setups') return h + ledgerView('options', u.view);
  if (!d) return h + `<div class="card"><div class="bd">${App.ui.empty('No options data yet', 'Runs every 5 minutes during market hours.')}</div></div>`;
  const p = d.snapshot || {};
  h += `<div class="kpis" style="margin-bottom:14px">${App.ui.kpi('Nifty', fmt(p.spot, 1), `${sg(p.change_pct)}% · VIX ${fmt(p.vix, 1)}`, cls(p.change_pct))}${App.ui.kpi('1H alignment', p.above_1h == null ? '-' : p.above_1h ? 'Above 9 EMA' : 'Below 9 EMA', p.above_1h == null ? '' : p.above_1h ? 'calls only' : 'puts only', p.above_1h ? 'good' : p.above_1h === false ? 'bad' : '')}
    ${App.ui.kpi('15m bias', p.bias_up ? 'Up (calls)' : p.bias_down ? 'Down (puts)' : 'None', p.bias_up || p.bias_down ? 'CHoCH intact' : 'no intact CHoCH', p.bias_up ? 'good' : p.bias_down ? 'bad' : '')}${App.ui.kpi('5m / 15m 9 EMA', `${fmt(p.ema_5m, 1)} / ${fmt(p.ema_15m, 1)}`, `price ${p.above_5m ? 'above' : 'below'} / ${p.above_15m ? 'above' : 'below'}`)}
    ${App.ui.kpi('Prev day H / L', (p.pdh_pdl || []).map(x => fmt(x, 0)).join(' / ') || '-', `today ${fmt(p.day_low, 0)}–${fmt(p.day_high, 0)}`)}${p.vix_pct != null ? App.ui.kpi('VIX percentile', p.vix_pct, p.vix_pct >= 80 ? 'options are expensive: smaller size' : p.vix_pct <= 20 ? 'options are cheap' : 'within its 1-year range', p.vix_pct >= 80 ? 'bad' : '') : ''}${App.ui.kpi('Losses today', p.losses_today || 0, p.losses_today >= 2 ? 'stop for the day' : 'stop after two', p.losses_today >= 2 ? 'bad' : '')}</div>`;
  if (p.expiry_afternoon) h += App.ui.callout('warn', '<b>Expiry afternoon:</b> your rule is to skip new option buys now.') + '<div style="height:10px"></div>';
  if (p.losses_today >= 2) h += App.ui.callout('bad', '<b>Two losing trades today:</b> your rule says stop for the day.') + '<div style="height:10px"></div>';
  h += d.setups.length ? `<div class="cards">${d.setups.map(s => card('options', s)).join('')}</div>` : `<div class="card"><div class="bd">${App.ui.empty('No setup on Nifty right now', Object.entries(p.why_none || {}).map(([k, v]) => `<div><b style="display:inline;font-size:14px">${k}:</b> ${esc(v)}</div>`).join(''))}</div></div>`;
  h += `<p class="help" style="margin-top:12px">Lot size ${d.lot_size}. Weekly expiry Tuesday (previous trading day if it is a holiday). Convert the index stop to premium (points × delta) and size so the loss is your fixed risk. Not investment advice.</p>`;
  return h;
};
App.binds.options = () => bindView('options', OU());

/* ---------- intraday ---------- */
const IU = () => App.ui.in || (App.ui.in = { view: 'setups', side: 'all' });
App.pages.intraday = () => {
  const u = IU(), d = App.data.intraday;
  let h = `<div class="ph"><div><h1>Intraday</h1><p>The most liquid Nifty 500 stocks, long and short: 15m CHoCH → 5m CHoCH + BOS → FVG + OB pullback → 5m 9 EMA close on 1.5x volume. MIS, SL-M, square off by 15:10, two trades a day, more only if A+.</p></div><span class="sp"></span>${meta(d)}</div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px">${viewSeg('intraday', u.view)}${u.view === 'setups' ? App.ui.seg('inside', [['all', 'Both'], ['long', 'Long'], ['short', 'Short']], u.side) : ''}</div>`;
  if (u.view !== 'setups') return h + ledgerView('intraday', u.view);
  if (!d) return h + `<div class="card"><div class="bd">${App.ui.empty('No intraday data yet', '')}</div></div>`;
  const rs = App.journal.riskStatus(); if (rs.trades >= rs.S.maxIntra) h += App.ui.callout(rs.over ? 'bad' : 'warn', `<b>${rs.trades} trades today</b>: your base limit is ${rs.S.maxIntra}. Another one only if it is A+.`) + '<div style="height:10px"></div>';
  const L = d.setups.filter(s => u.side === 'all' || s.direction === u.side);
  return h + (L.length ? `<div class="cards">${L.map(s => card('intraday', s)).join('')}</div>` : `<div class="card"><div class="bd">${App.ui.empty('No intraday setups right now', '')}</div></div>`) + `<p class="help" style="margin-top:12px">${esc(d.note || '')}</p>`;
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
  const plan = [['Entry', it.entry, 'brand', 0, 3], ['SL', it.sl, 'bad', 0, 3], ['T1', it.t1, 'good', 1, 2], ['T2', it.t2, 'good', 1, 2], ['T3', it.t3, 'good', 1, 1]];
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
  plan.forEach(([l, p, c, dash, k]) => { if (isNum(p) && (tf !== '15m' || l === 'Entry' || l === 'SL')) lv.push({ p, c, dash, label: (hit(l) ? '✓ ' : '') + l, k, w: l === 'Entry' || l === 'SL' ? 1.6 : 1.1, scale: tf === '15m' ? l === 'Entry' : l !== 'T3' && l !== 'T2' }); });
  return { zones: z, levels: lv, marks: mk };
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
  return App.charts.candles(data, { W, levels: s.levels, zones: s.zones, marks: s.marks, label: `${it.symbol} ${tf} chart` });
}
function checklistCard(it) {
  if (!it.checklist) return '';
  const mk = ok => ok === true ? '<span class="mk y">✓</span>' : ok === false ? '<span class="mk n">✗</span>' : '<span class="mk q">?</span>';
  const done = it.checklist.filter(c => c.ok === true).length;
  return `<div class="card"><div class="hd"><h2>Playbook checklist</h2><span class="cap">${done} of ${it.checklist.length} ticked · ? = check yourself</span></div><div class="bd"><ul class="checks">${it.checklist.map(c => `<li>${mk(c.ok)}<span class="tf">${esc(c.tf)}</span><div><b>${esc(c.title)}</b><p>${esc(c.text)}</p></div></li>`).join('')}</ul></div></div>`;
}
function scoreCard(it) {
  const parts = [['Structure', it.structure, 2], ['Zone', it.zone_q, 2], ['Confirmation', it.confirm, 3], ['Context', it.context, 3]];
  return `<div class="card"><div class="hd"><h2>Scorecard</h2><span class="sp"></span>${App.ui.grade(it.grade)}<b style="font:750 18px var(--disp)">${it.score}/10</b></div><div class="bd"><div class="scorebars">${parts.map(([l, v, m]) => `<div class="sbar"><span>${l}</span><span class="tr"><i style="width:${100 * v / m}%"></i></span><b>${v}/${m}</b></div>`).join('')}</div>
    <div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:10px">${(it.ticks || []).map(t => `<span class="tick">✓ ${esc(t)}</span>`).join('') || '<span class="muted">No confluence ticks</span>'}</div><p class="help" style="margin-top:8px">A+ 8–10 · A 6–7 · B 4–5 observe · under 4 no trade.</p></div></div>`;
}
function planCard(it) {
  const d = dec(it), risk = isNum(it.entry) && isNum(it.sl) ? Math.abs(it.entry - it.sl) : null, R = p => risk ? Math.abs(p - it.entry) / risk : null, p = it.plan || {};
  const lvls = [['Entry', it.entry, 'brand'], ['Stop-loss', it.sl, 'bad'], ['T1', it.t1, 'good'], ['T2', it.t2, 'good'], ['T3', it.t3, 'good']].filter(x => isNum(x[1]));
  const trail = (p.trail || []).map(t => typeof t === 'string' ? t : `<b>${esc(t.when)}:</b> ${esc(t.action)}`);
  return `<div class="card"><div class="hd"><h2>Trade plan</h2>${it.risk_pct != null ? `<span class="cap">risk ${it.risk_pct.toFixed(2)}% of price</span>` : ''}</div><div class="bd">
    <table class="tbl"><tbody>${lvls.map(([l, v, c], i) => `<tr><td><b class="${c === 'bad' ? 'bad' : c === 'good' ? 'good' : 'brand'}">${l}</b></td><td class="n"><b>${fmt(v, d)}</b></td><td class="n muted">${i === 0 ? '' : i === 1 ? '−1R · ' + fmt(risk, d) + ' pts' : (R(v) || 0).toFixed(1) + 'R'}</td></tr>`).join('')}</tbody></table>
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
   in that sector, stocks that move with it) and your daily rule (2 trades a day, more only if A+). Review it before you place the order. */
SC.preCheck = function (it, sec) {
  const d = App.data.swing || {}, ht = d.heat || {}, map = (App.lazyNow('sectors') || {}).map || {}, sym = (it.symbol || '').toUpperCase(), sector = it.sector || map[sym] || '';
  const lines = [], rs = App.journal.riskStatus(); let lvl = 'ok';
  const warn = (m, bad) => { lines.push([bad ? 'bad' : 'warn', m]); lvl = bad || lvl === 'bad' ? 'bad' : 'warn'; };
  if (rs.trades >= rs.S.maxIntra) { if (it.grade === 'A+') lines.push(['good', `${rs.trades} trades today: past your base ${rs.S.maxIntra}, allowed because this one is A+.`]); else warn(`${rs.trades} trades today and this one is ${esc(it.grade || 'ungraded')}: past ${rs.S.maxIntra} a day only A+ is allowed. Skip it.`, true); }
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
      <div class="card" style="margin-top:14px"><div class="bd"><div class="kv"><span>Last status</span><b>${esc(w.status || '')}</b><span>Grade / score</span><b>${esc(w.grade || '')} ${w.score || ''}/10</b><span>Zone</span><b>${fmt(w.zone_bot)} – ${fmt(w.zone_top)}</b><span>Plan entry / SL / T1</span><b>${fmt(w.entry)} / ${fmt(w.sl)} / ${fmt(w.t1)}</b></div><p class="help" style="margin-top:8px">If you entered anyway, manage it with the original stop and log it as a rule break ("No confirmation").</p></div></div>` : App.ui.empty('Setup not found', 'It is no longer in the scan and never triggered.')); }
  const it = R.it, sig = R.sig, d = dec(it), inJ = App.journal.findByTag(sig ? sig.id : key(sec, it)), tfs = it.charts ? Object.keys(it.charts) : it.tfs && it.tfs.length ? it.tfs : [it.tf_structure || '5m'];
  const tf = App.ui.tf && tfs.includes(App.ui.tf) ? App.ui.tf : (tfs.includes('15m') && it.stage >= 5 ? '15m' : tfs[0]); App.ui.tfCur = tf;
  const role = { '1D': 'Structure and zone', '1H': 'Confirmation', '15m': 'Precision entry', '5m': 'Setup and trigger' };
  const news = ((App.data.news || {}).by_symbol || {})[it.symbol] || [];
  let h = back + `<div class="thead"><h1>${esc(it.symbol)}</h1>${sec !== 'swing' ? `<span class="tag ${it.direction}">${esc(it.label)}</span>` : ''}<span class="st ${sig ? (sig.status === 'CLOSED' ? 'closed' : 's5') : stCls(it)}">${esc(sig ? sigStatus(sig) : it.status)}</span>${App.ui.grade(it.grade)}<b>${it.score}/10</b>${inJ ? '<span class="pill info">in your journal</span>' : ''}<span style="flex:1"></span>
    <a class="btn" href="${App.tv(it.symbol)}" target="_blank" rel="noopener">${ic('ext')} TradingView</a><button class="btn primary" id="logT" type="button">${ic('plus')} ${inJ ? 'Log again' : 'Log trade'}</button></div>
    <p class="help" style="margin:4px 0 14px">${[it.sector, it.stage ? `Stage ${it.stage} of 5: ${STG[it.stage][0]}` : '', it.price != null ? 'last ' + fmt(it.price, d) : '', it.results && it.results.date ? `results ${it.results.date} (${it.results.days} d)` : '', sig ? 'triggered ' + sig.created.replace('T', ' ').slice(0, 16) : ''].filter(Boolean).map(esc).join(' · ')}</p>`;
  if ((it.holds || []).length) h += App.ui.callout('warn', `<b>Held back:</b> ${it.holds.map(esc).join(', ')}. The entry is not valid until this clears.`) + '<div style="height:12px"></div>';
  h += `<div class="grid g-main"><div class="stack"><div class="card"><div class="hd"><div class="tftabs">${tfs.map(t => `<button class="tftab" type="button" data-tf="${t}" aria-pressed="${t === tf}"><b>${t}</b><small>${role[t] || ''}</small></button>`).join('')}</div></div>
    <div class="bd" id="chBox">${chartFor(it, tf, sig, 700)}</div><div class="bd legend" style="padding-top:0"><span><i style="background:var(--c6)"></i>9 EMA</span><span><i style="background:var(--good)"></i>FVG</span><span><i style="background:var(--c1)"></i>OB</span><span><i style="background:var(--sun)"></i>Fib</span><span><i style="background:var(--brand)"></i>Entry / zone</span><span><i style="background:var(--bad)"></i>Stop</span></div></div>
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
  $$('[data-tf]').forEach(b => b.onclick = () => { App.ui.tf = b.dataset.tf; App.render(); });
  const draw = () => { const b = $('#chBox'); if (b) b.innerHTML = chartFor(R.it, App.ui.tfCur, R.sig, b.clientWidth - 32); };
  draw();
  if (!R.it.charts && R.it.section === 'swing' && R.it.tfs) {
    const sw_ = App.data.swing || {}, gen = sw_.charts_at || sw_.generated_at, have = App.lazyNow('swing_charts');
    App.lazy('swing_charts', have && (have.charts_at || have.generated_at) === gen ? 3600e3 : 0).then(draw);       // loads once per swing scan, and again when the fast lane refreshes the charts
  } let t; window.onresize = () => { clearTimeout(t); t = setTimeout(draw, 150); };
};
SC.card = card; SC.STG = STG;
})();
