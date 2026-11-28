/* DownerStuffScreener front end. One script, seven small pages (index, swing, options, intraday, market, news, trade). */
(function () {
'use strict';
const DS = window.DS = { data: {}, pages: {} };
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const store = { get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} } };
DS.store = store; DS.esc = esc;
const fmt = (v, d = 2) => v == null || isNaN(v) ? '-' : Number(v).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });
const sg = (v, d = 2) => v == null ? '-' : (v >= 0 ? '+' : '') + fmt(v, d);
const dec = it => it.section === 'options' ? 1 : 2;
DS.fmt = fmt;
const ist = iso => { try { return new Date(iso).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }); } catch (e) { return '-'; } };
function marketOpenNow() { const p = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false }).formatToParts(new Date()), g = t => p.find(x => x.type === t).value, m = +g('hour') * 60 + +g('minute'); return !['Sat', 'Sun'].includes(g('weekday')) && m >= 555 && m <= 930; }
const kind = s => s.status.startsWith('TRIGGER') ? 't' : s.status.startsWith('WATCH') ? 'w' : 'a';
const gcls = g => g === 'A+' ? 'g-Ap' : g === 'A' ? 'g-A' : 'g-B';
const meter = (n, max = 10) => `<span class="meter${n >= 8 ? ' hi' : ''}" aria-hidden="true">${Array.from({ length: max }, (_, i) => `<i class="${i < n ? 'on' : ''}"></i>`).join('')}</span>`;
const tvSym = s => s === 'NIFTY 50' ? 'NSE:NIFTY' : 'NSE:' + s.replace(/[&-]/g, '_');
const tvUrl = s => 'https://www.tradingview.com/chart/?symbol=' + encodeURIComponent(tvSym(s));

/* ------------------------------------------------------------ icons and shell */
const IC = {
  overview: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  swing: '<path d="M3 17l6-6 4 4 8-9"/><path d="M15 6h6v6"/>', options: '<path d="M5 21V9M12 21V3M19 21v-8"/>', intraday: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
  market: '<path d="M4 18a8 8 0 1 1 16 0"/><path d="M12 18l4-6"/>', news: '<path d="M5 4h12a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2z"/><path d="M9 8h6M9 12h6M9 16h4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>', moon: '<path d="M21 13a9 9 0 1 1-10-10 7 7 0 0 0 10 10z"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>', back: '<path d="M15 5l-7 7 7 7"/>',
  journal: '<path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"/><path d="M9 8h6M9 12h6"/><path d="M5 17a3 3 0 0 1 3-3h11"/>' };
const svgI = k => `<svg viewBox="0 0 24 24" aria-hidden="true">${IC[k]}</svg>`;
const LOGO = '<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="1" y="1" width="30" height="30" rx="8" fill="var(--panel2)" stroke="var(--line)"/><path d="M9 21v-8M9 10v-2M9 21v2" stroke="#ff5d6c" stroke-width="2" stroke-linecap="round"/><rect x="7" y="12" width="4" height="8" rx="1" fill="#ff5d6c"/><path d="M16 22v-2M16 9v-3" stroke="#25c48c" stroke-width="2" stroke-linecap="round"/><rect x="14" y="10" width="4" height="10" rx="1" fill="#25c48c"/><path d="M23 19v-3M23 8v-3" stroke="#5b8cff" stroke-width="2" stroke-linecap="round"/><rect x="21" y="8" width="4" height="8" rx="1" fill="#5b8cff"/></svg>';
const NAV = [['overview', 'Overview', 'index.html'], ['swing', 'Swing', 'swing.html'], ['options', 'Options', 'options.html'], ['intraday', 'Intraday', 'intraday.html'], ['market', 'Market', 'market.html'], ['news', 'News', 'news.html'], ['journal', 'Journal', 'journal.html']];

DS.theme = function () {
  const t = store.get('ds.theme', null) || (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
  document.documentElement.dataset.theme = t; return t;
};
function shell(active) {
  DS.theme();
  document.body.innerHTML = `<div class="app"><header class="top"><a class="brand" href="index.html" aria-label="DownerStuffScreener home">${LOGO}<b>DownerStuff<i>Screener</i></b></a><div class="tick" id="tick"></div><span class="sp"></span><span class="pill" id="upd" hidden></span><span class="pill" id="mkt"><i></i><span>...</span></span>
    <button class="ibtn" id="themeBtn" type="button" aria-label="Switch light or dark theme"></button><button class="ibtn" id="refreshBtn" type="button" aria-label="Refresh data">${svgI('refresh')}</button></header>
    <aside class="side" aria-label="Pages"><nav class="nav" id="nav"></nav><div class="foot">Rules-based candidates, not advice. Check the chart, futures OI, results date and news before you trade.</div></aside>
    <main><div class="wrap" id="page"></div></main></div><nav class="tabbar" id="tabbar" aria-label="Pages"></nav>`;
  const icon = () => { $('#themeBtn').innerHTML = svgI(document.documentElement.dataset.theme === 'dark' ? 'sun' : 'moon'); };
  icon(); $('#themeBtn').onclick = () => { const t = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; store.set('ds.theme', t); document.documentElement.dataset.theme = t; icon(); if (DS.onTheme) DS.onTheme(); };
  $('#refreshBtn').onclick = () => DS.reload();
  DS.navActive = active;
}
function paintChrome() {
  const trig = k => { const d = DS.data[k]; return d ? d.setups.filter(s => kind(s) === 't' && s.score >= 6).length : 0; };
  const link = (k, t, h, tab) => `<a href="${h}" class="${DS.navActive === k || (DS.navActive === 'trade' && DS.parent === k) ? 'on' : ''}">${svgI(k)}<span>${t}</span>${['swing', 'options', 'intraday'].includes(k) && trig(k) ? `<span class="cnt">${trig(k)}</span>` : ''}</a>`;
  $('#nav').innerHTML = NAV.map(([k, t, h]) => link(k, t, h)).join(''); $('#tabbar').innerHTML = NAV.filter(n => n[0] !== 'overview').map(([k, t, h]) => link(k, t, h, true)).join('');
  const m = DS.data.market, o = marketOpenNow(), mk = $('#mkt'); mk.className = 'pill ' + (o ? 'ok' : ''); mk.innerHTML = '<i></i><span>' + (innerWidth < 700 ? (o ? 'Open' : 'Closed') : (o ? 'Market open' : 'Market closed')) + '</span>';
  const live = ['options', 'intraday', 'market'].map(k => DS.data[k]).filter(Boolean), sw = DS.data.swing, upd = $('#upd');
  const page = DS.navActive === 'trade' ? DS.parent : DS.navActive, src = page === 'swing' ? sw : (live.sort((a, b) => new Date(b.generated_at) - new Date(a.generated_at))[0] || sw);
  if (src) {
    const age = (Date.now() - new Date(src.generated_at)) / 6e4, every = page === 'swing' ? 60 : 5, late = o && age > (page === 'swing' ? 100 : 12);
    const nxt = new Date(new Date(src.generated_at).getTime() + every * 6e4), hm = d => d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: 'numeric', minute: '2-digit' });
    upd.hidden = false; upd.className = 'pill ' + (late ? 'bad' : 'info'); upd.title = late ? 'The scanner has not published for a while: check the Actions tab of your repo.' : 'The page re-reads the data every minute while the market is open.';
    upd.innerHTML = late ? `<i></i><a href="${actionsUrl()}" target="_blank" rel="noopener" style="color:inherit">Delayed: last ${hm(new Date(src.generated_at))}</a>` : `<i></i><span>${hm(new Date(src.generated_at))}${o ? ' · next ~' + hm(nxt) : ''}</span>`;
  }
  const tk = (n, x, d = 2, cls = '') => x && x.price != null ? `<span class="tk ${cls}"><small>${n}</small><b class="n">${fmt(x.price, d)}</b><span class="n ${x.change_pct >= 0 ? 'good' : 'bad'}">${sg(x.change_pct)}%</span></span>` : '';
  $('#tick').innerHTML = m && m.indices ? tk('NIFTY', m.indices.nifty, 1) + tk('BANKNIFTY', m.indices.banknifty, 1, 'hide-s') + tk('INDIA VIX', m.indices.vix, 2, 'hide-s') : '';
}

function actionsUrl() { const m = location.hostname.match(/^([^.]+)\.github\.io$/), repo = location.pathname.split('/').filter(Boolean)[0]; return m && repo ? `https://github.com/${m[1]}/${repo}/actions` : 'https://github.com'; }

/* ------------------------------------------------------------ data */
DS.get = async n => { try { const r = await fetch('data/' + n + '.json?' + Date.now(), { cache: 'no-store' }); if (!r.ok) throw new Error(r.status); return await r.json(); } catch (e) { return null; } };
DS.loadAll = async names => { const r = await Promise.all(names.map(DS.get)); names.forEach((n, i) => DS.data[n] = r[i]); };
DS.reload = async function () { await DS.loadAll(DS.need || []); paintChrome(); DS.draw(); };

/* ------------------------------------------------------------ small parts */
const pill = (txt, cls = '') => `<span class="pill ${cls}">${txt}</span>`;
function age(d, live) { if (!d) return ''; const m = (Date.now() - new Date(d.generated_at)) / 6e4, open = marketOpenNow(), stale = live ? (open && m > 15) : (open ? m > 100 : m > 30 * 60); return pill('Updated ' + esc(ist(d.generated_at)) + ' IST' + (m < 120 ? ' · ' + Math.max(0, Math.round(m)) + ' min ago' : ''), stale ? 'bad' : ''); }
function empty(title, text) { return `<div class="card"><div class="empty"><b>${title}</b>${text || ''}</div></div>`; }
const regimeCls = r => ({ trending_up: 'ok', trending_down: 'bad', range: 'info', volatile: 'warn' }[r] || '');
const tile = (k, v, d = '', cls = '') => `<div class="tile"><div class="k">${k}</div><div class="v n ${cls}">${v}</div>${d ? `<div class="d">${d}</div>` : ''}</div>`;
const href = (sec, it) => `trade.html?s=${sec}&id=${encodeURIComponent(it.symbol + '|' + it.direction)}`;

/* ------------------------------------------------------------ screener rows */
const SECT = {
  swing: { title: 'Swing', sub: 'Nifty 500 · 1D structure, 1H trigger, sector index must not be falling · long only · updates every hour', live: false, sides: false, cols: 'minmax(150px,1.5fr) 118px 150px 90px 92px 92px 92px 54px 62px 112px', heads: ['Stock', 'Grade', 'Status', 'LTP', 'Entry', 'SL', 'T1', 'R', 'Risk', 'Results'] },
  options: { title: 'Nifty options', sub: 'Nifty 50 index · 15m CHoCH bias, 5m structure + trigger · calls and puts · updates every 5 minutes', live: true, sides: false, cols: 'minmax(170px,1.6fr) 118px 150px 90px 92px 92px 92px 54px 82px 62px', heads: ['Option', 'Grade', 'Status', 'Index', 'Entry', 'SL', 'T1', 'R', 'Premium', 'Delta'] },
  intraday: { title: 'Intraday', sub: 'Liquid Nifty 500 stocks · 15m CHoCH bias, 5m structure + trigger · long and short · updates every 5 minutes', live: true, sides: true, cols: 'minmax(150px,1.5fr) 118px 150px 90px 92px 92px 92px 54px 62px', heads: ['Stock', 'Grade', 'Status', 'LTP', 'Entry', 'SL', 'T1', 'R', 'Risk'] } };
function rowHtml(sec, it) {
  const d = dec(it), L = (k, v, cls = '') => `<div class="num n ${cls}"><small>${k}</small><b>${fmt(v, d)}</b></div>`;
  let sym, extra = '';
  if (sec === 'options') { const ot = it.options_trade; sym = `<b>${esc(ot ? ot.instrument : 'NIFTY 50 ' + it.label)}</b> <span class="tag t-${it.direction}">${esc(it.label)}</span><small>${ot ? 'weekly ' + esc(ot.expiry) : 'Nifty index'}</small>`; extra = `<div class="num n hide-m">${ot ? fmt(ot.premium, 1) : '-'}</div><div class="num n hide-m">${ot ? ot.delta.toFixed(2) : '-'}</div>`; }
  else { sym = `<b>${esc(it.symbol)}</b>${sec === 'intraday' ? ` <span class="tag t-${it.direction}">${esc(it.label)}</span>` : ''}<small>${esc(it.sector || (sec === 'intraday' ? 'Nifty 500' : ''))}${it.rs20 != null ? ' · RS ' + sg(it.rs20, 1) + '%' : ''}</small>`; extra = `<div class="num n hide-m">${fmt(it.risk_pct, 1)}%</div>` + (sec === 'swing' ? `<div class="hide-m ${it.results && it.results.days != null && it.results.days <= 7 ? 'warn' : 'muted'}">${it.results && it.results.days != null ? 'in ' + it.results.days + ' day(s)' : 'check NSE'}</div>` : ''); }
  return `<a class="row" href="${href(sec, it)}"><div class="sym">${sym}</div><div class="gr"><span class="tag ${gcls(it.grade)}">${it.grade}</span> ${meter(it.score)} <small class="n" style="display:inline">${it.score}/10</small></div>
    <div class="stc"><span class="st ${kind(it)}">${esc(it.status)}</span>${LED(sec).signals.some(s => s.id === sigKey(sec, it)) ? '<small class="good">tracked as a trade</small>' : ''}${it.index_check ? `<small class="${it.index_check.state === 'falling' ? 'bad' : it.index_check.state === 'unknown' ? 'warn' : 'good'}">${esc(it.index_check.sector_index.split(' (')[0])}: ${it.index_check.state}</small>` : ''}</div><div class="ltp num n"><small class="muted" style="display:inline">LTP </small>${fmt(it.price, d)}</div>
    <div class="lvls">${L('Entry', it.entry, 'en')}${L('SL', it.sl, 'sl')}${L('T1', it.t1, 'tg')}<div class="num n"><small>R</small><b>${it.r_t1 == null ? '-' : it.r_t1.toFixed(1)}</b></div>${extra}</div></a>`;
}
const LED = k => DS.data['signals_' + k] || { signals: [], dropped: [], watch: {} };
const sigKey = (sec, it) => `${sec}|${it.symbol}|${it.direction}|${it.bos_date}`;
const outcomeTxt = { TARGET: 'Target hit', TRAIL: 'Trailing stop hit', SL: 'Stopped out', EXPIRED: 'Squared off / expired' };
function nextTarget(s) { const lv = [['T1', s.t1], ['T2', s.t2], ['T3', s.t3]].sort((a, b) => s.direction === 'long' ? a[1] - b[1] : b[1] - a[1]); return lv.find(x => !(s.hits || {})[x[0]]) || lv[2]; }
function sigStatus(s, d) { if (s.status === 'CLOSED') return outcomeTxt[s.outcome] || 'Closed'; const h = Object.keys(s.hits || {}); return h.length ? `Active · ${h.join(' + ')} hit · stop ${fmt(s.stop, d)}` : 'Active · waiting for T1'; }
function sigRow(sec, s) {
  const d = sec === 'options' ? 1 : 2, nt = nextTarget(s), closed = s.status === 'CLOSED', r = closed ? s.r_final : s.r_now, rc = r > 0 ? 'good' : r < 0 ? 'bad' : '';
  const name = s.instrument || s.symbol, when = (closed ? s.closed : s.created || '').replace('T', ' ').slice(5, 16);
  return `<a class="row" href="trade.html?s=${sec}&sig=${encodeURIComponent(s.id)}"><div class="sym"><b>${esc(name)}</b> <span class="tag t-${s.direction}">${esc(s.label)}</span><small>${closed ? 'closed ' : 'triggered '}${esc(when)} · ${s.grade} ${s.score}/10</small></div>
    <div class="gr"><b class="n ${rc}" style="font-size:15px">${r == null ? '-' : sg(r, 2) + 'R'}</b><small style="display:inline"> ${closed ? 'result' : 'now'}</small></div><div class="stc"><span class="st ${closed ? (r > 0 ? 't' : 'a') : 'w'}">${esc(sigStatus(s, d))}</span></div>
    <div class="ltp num n"><small class="muted" style="display:inline">${closed ? 'Exit ' : 'Last '}</small>${fmt(closed ? s.exit : s.last, d)}</div>
    <div class="lvls"><div class="num n en"><small>Entry</small><b>${fmt(s.entry, d)}</b></div><div class="num n sl"><small>Stop</small><b>${fmt(closed ? s.sl : s.stop, d)}</b></div><div class="num n tg"><small>${closed ? 'T1' : 'Next ' + nt[0]}</small><b>${fmt(closed ? s.t1 : nt[1], d)}</b></div><div class="num n"><small>Hits</small><b>${Object.keys(s.hits || {}).length}/3</b></div></div></a>`;
}
function dropRow(sec, w) {
  const d = sec === 'options' ? 1 : 2;
  return `<div class="row" style="cursor:default"><div class="sym"><b>${esc(w.symbol)}</b> <span class="tag t-${w.direction}">${esc(w.label || w.direction.toUpperCase())}</span><small>was ${esc(w.status || '')} · ${w.grade || ''} ${w.score || ''}/10</small></div>
    <div class="gr"><span class="pill bad">invalidated</span></div><div class="stc" style="white-space:normal"><span class="st a">${esc(w.reason || '')}</span></div><div class="ltp num n"><small class="muted" style="display:inline">at </small>${esc((w.dropped || '').replace('T', ' ').slice(5, 16))}</div>
    <div class="lvls"><div class="num n en"><small>Entry</small><b>${fmt(w.entry, d)}</b></div><div class="num n sl"><small>SL</small><b>${fmt(w.sl, d)}</b></div><div class="num n tg"><small>T1</small><b>${fmt(w.t1, d)}</b></div><div class="num n"><small>Zone</small><b>${fmt(w.zone_bot, d)}</b></div></div></div>`;
}
function ledgerView(sec, view) {
  const L = LED(sec), act = L.signals.filter(s => s.status === 'ACTIVE'), clo = L.signals.filter(s => s.status === 'CLOSED').sort((a, b) => (b.closed || '').localeCompare(a.closed || '')), drop = (L.dropped || []).slice().reverse();
  const cols = 'minmax(170px,1.5fr) 110px minmax(170px,1.3fr) 100px 92px 92px 92px 62px', head = h => `<div class="rowh">${h.map((x, i) => `<div class="${i >= 3 ? 'num' : ''}">${x}</div>`).join('')}</div>`;
  if (view === 'active') return act.length ? `<div class="tbl" style="--cols:${cols}">${head(['Trade', 'R now', 'Status', 'Last', 'Entry', 'Stop', 'Next target', 'Hits'])}${act.map(s => sigRow(sec, s)).join('')}</div><p class="help" style="margin-top:8px">Triggered trades stay here until they hit the final target, the stop or the trailing stop${sec === 'swing' ? '' : ', or 15:15'}. Each step is in the trade page timeline.</p>` : empty('No open trades', 'When a setup triggers it moves here and is followed every run until it closes.');
  let h = clo.length ? `<h2 style="margin:4px 0 8px">Closed trades</h2><div class="tbl" style="--cols:${cols}">${head(['Trade', 'Result', 'Outcome', 'Exit', 'Entry', 'SL', 'T1', 'Hits'])}${clo.map(s => sigRow(sec, s)).join('')}</div>` : '';
  h += drop.length ? `<h2 style="margin:16px 0 8px">Invalidated before triggering</h2><div class="tbl" style="--cols:${cols}">${head(['Setup', '', 'Reason', 'When', 'Entry', 'SL', 'T1', 'Zone'])}${drop.map(w => dropRow(sec, w)).join('')}</div>` : '';
  return h || empty('Nothing closed or invalidated yet', 'Closed trades and setups that were cancelled before triggering are listed here with the reason.');
}
function screener(sec) {
  const cfg = SECT[sec], d = DS.data[sec], st = store.get('ds.f.' + sec, { status: 'all', min: 6, side: 'all', sort: 'score' }); const save = () => store.set('ds.f.' + sec, st);
  let h = `<div class="ph"><div><h1>${cfg.title}</h1><p>${cfg.sub}</p></div><span class="sp"></span>${d ? age(d, cfg.live) : ''}${d ? pill(d.scanned + '/' + d.universe + ' scanned') : ''}${d && cfg.live && !d.market_open ? pill('Market closed: last session', 'warn') : ''}</div>`;
  if (!d) return h + empty('Not available yet', 'This section has not run yet. Run the workflow once from the GitHub Actions tab, then refresh.');
  const L = LED(sec), nAct = L.signals.filter(s => s.status === 'ACTIVE').length, nClo = L.signals.filter(s => s.status === 'CLOSED').length + (L.dropped || []).length, view = st.view || 'setups';
  h += `<div class="chips" style="margin-bottom:10px"><button class="chip" type="button" data-k="view" data-v="setups" aria-pressed="${view === 'setups'}">Setups ${d.setups.length}</button><button class="chip" type="button" data-k="view" data-v="active" aria-pressed="${view === 'active'}">Active trades ${nAct}</button><button class="chip" type="button" data-k="view" data-v="closed" aria-pressed="${view === 'closed'}">Closed / invalidated ${nClo}</button></div>`;
  if (view !== 'setups') return h + (sec === 'options' ? optionsTop(d) : '') + ledgerView(sec, view);
  const base = d.setups.filter(s => s.score >= st.min && (st.side === 'all' || s.direction === st.side)), cnt = k => base.filter(s => kind(s) === k).length;
  const chip = (v, t) => `<button class="chip" type="button" data-k="status" data-v="${v}" aria-pressed="${st.status === v}">${t}</button>`, opt = (a, cur) => a.map(([v, t]) => `<option value="${v}"${String(cur) === String(v) ? ' selected' : ''}>${t}</option>`).join('');
  h += `<div class="chips" style="margin-bottom:12px">${chip('all', 'All ' + base.length)}${chip('t', 'Triggered ' + cnt('t'))}${chip('w', 'In zone ' + cnt('w'))}${chip('a', 'Near zone ' + cnt('a'))}<span class="sp"></span>
    <select class="sel" data-s="min" aria-label="Minimum score">${opt([[4, 'Score 4+'], [6, 'Score 6+'], [8, 'Score 8+']], st.min)}</select>${cfg.sides ? `<select class="sel" data-s="side" aria-label="Side">${opt([['all', 'Long + short'], ['long', 'Long'], ['short', 'Short']], st.side)}</select>` : ''}
    <select class="sel" data-s="sort" aria-label="Sort">${opt([['score', 'Sort: score'], ['status', 'Sort: status'], ['risk', 'Sort: smallest risk']], st.sort)}</select></div>`;
  if (sec === 'options') h += optionsTop(d);
  let list = base.filter(s => st.status === 'all' || kind(s) === st.status); const rk = { t: 0, w: 1, a: 2 };
  list.sort(st.sort === 'status' ? (a, b) => rk[kind(a)] - rk[kind(b)] || b.score - a.score : st.sort === 'risk' ? (a, b) => (a.risk_pct || 99) - (b.risk_pct || 99) : (a, b) => b.score - a.score || rk[kind(a)] - rk[kind(b)]);
  h += `<div class="muted help" style="margin:0 0 8px">${esc(d.note || '')}</div>`;
  if (!list.length) {
    let why = d.setups.length ? 'Lower the score filter or change the status.' : 'Nothing met the rules at this run. That is normal on many days.';
    if (sec === 'options' && !d.setups.length && d.snapshot && d.snapshot.why_none) why = Object.entries(d.snapshot.why_none).map(([k, v]) => `<b style="display:inline">${k}:</b> ${esc(v)}`).join('<br>');
    h += empty('No setups match', why);
  } else h += `<div class="tbl" style="--cols:${cfg.cols}"><div class="rowh">${cfg.heads.map((x, i) => `<div class="${i >= 3 ? 'num' : ''}">${x}</div>`).join('')}</div>${list.map(s => rowHtml(sec, s)).join('')}</div>
    <p class="help" style="margin-top:10px">Tap a row for the chart with entry, stop-loss and targets, how to execute, how to trail, and why the trade qualifies.</p>`;
  return h;
}
function bindScreener(sec) {
  const st = store.get('ds.f.' + sec, { status: 'all', min: 6, side: 'all', sort: 'score' });
  document.querySelectorAll('[data-k]').forEach(b => b.onclick = () => { st[b.dataset.k] = b.dataset.v; store.set('ds.f.' + sec, st); DS.draw(); });
  document.querySelectorAll('[data-s]').forEach(s => s.onchange = () => { st[s.dataset.s] = s.dataset.s === 'min' ? +s.value : s.value; store.set('ds.f.' + sec, st); DS.draw(); });
  bindOI();
}

/* ------------------------------------------------------------ open interest */
DS.oiAlign = function (side, entry, sl, t1, oi) {
  if (!oi || oi.call_wall == null || oi.put_wall == null) return { verdict: 'unknown', aligned: false, notes: ['OI not available: enter the walls from your option chain.'] };
  const cw = +oi.call_wall, pw = +oi.put_wall, pcr = oi.pcr == null || oi.pcr === '' ? null : +oi.pcr, n = []; let good = 0, bad = 0, f0 = v => fmt(v, 0);
  if (side === 'long') {
    if (pw <= entry) { good++; n.push(`Put wall ${f0(pw)} is below price: writers defend it, so it acts as support.`); } else { bad++; n.push(`Put wall ${f0(pw)} is above price: support is thin below you.`); }
    if (cw >= t1) { good++; n.push(`Call wall ${f0(cw)} sits at or beyond T1 ${f0(t1)}: the first target is not capped.`); } else if (cw > entry) { bad++; n.push(`Call wall ${f0(cw)} sits before T1 ${f0(t1)}: expect resistance there and take profit.`); }
    if (pcr != null && pcr >= 1.1) { good++; n.push(`PCR ${pcr.toFixed(2)} leans bullish.`); } else if (pcr != null && pcr <= 0.8) { bad++; n.push(`PCR ${pcr.toFixed(2)} leans bearish.`); }
  } else {
    if (cw >= entry) { good++; n.push(`Call wall ${f0(cw)} is above price: writers defend it, so it acts as resistance.`); } else { bad++; n.push(`Call wall ${f0(cw)} is below price: resistance is thin above you.`); }
    if (pw <= t1) { good++; n.push(`Put wall ${f0(pw)} sits at or beyond T1 ${f0(t1)}: the first target is not capped.`); } else if (pw < entry) { bad++; n.push(`Put wall ${f0(pw)} sits before T1 ${f0(t1)}: expect support there and take profit.`); }
    if (pcr != null && pcr <= 0.9) { good++; n.push(`PCR ${pcr.toFixed(2)} leans bearish.`); } else if (pcr != null && pcr >= 1.2) { bad++; n.push(`PCR ${pcr.toFixed(2)} leans bullish.`); }
  }
  const verdict = good >= 2 && bad === 0 ? 'supports' : (bad >= 2 || bad > good) ? 'against' : 'mixed'; return { verdict, aligned: verdict === 'supports', notes: n };
};
DS.oiNow = function () {
  const auto = DS.data.options && DS.data.options.snapshot && DS.data.options.snapshot.oi, man = store.get('ds.oi', {});
  const pick = (m, a) => m !== undefined && m !== '' && m !== null ? +m : (a == null ? null : a);
  return { auto, call_wall: pick(man.call_wall, auto && auto.call_wall), put_wall: pick(man.put_wall, auto && auto.put_wall), pcr: pick(man.pcr, auto && auto.pcr), manual: !!(man.call_wall || man.put_wall || man.pcr) };
};
function oiVerdict(it) {
  const v = DS.oiAlign(it.direction, it.entry, it.sl, it.t1, DS.oiNow());
  return `<div class="callout ${v.verdict === 'supports' ? 'good' : v.verdict === 'against' ? 'bad' : ''}" style="margin-top:10px"><div><b>OI ${v.verdict === 'unknown' ? 'unknown' : v.verdict === 'supports' ? 'supports this ' + esc(it.label) : v.verdict === 'against' ? 'is against this ' + esc(it.label) : 'is mixed for this ' + esc(it.label)}</b><br>${v.notes.map(esc).join('<br>')}</div></div>`;
}
function oiPanel(it) {
  const o = DS.oiNow(), a = o.auto, man = store.get('ds.oi', {}); const verdict = `<div id="oiVerdict">${it ? oiVerdict(it) : ''}</div>`;
  return `<div class="card"><div class="hd"><h2>Open interest (OI)</h2>${a ? pill('Auto: NSE ' + esc(a.timestamp || ''), 'info') : pill('Manual: NSE did not respond', 'warn')}</div><div class="bd">
    ${a ? `<div class="grid g4" style="margin-bottom:10px">${tile('Call wall', fmt(a.call_wall, 0), 'most call OI: resistance')}${tile('Put wall', fmt(a.put_wall, 0), 'most put OI: support')}${tile('PCR', a.pcr == null ? '-' : a.pcr.toFixed(2), 'put OI / call OI')}${tile('Max pain', fmt(a.max_pain, 0), esc(a.expiry))}</div>` : `<p class="help" style="margin-bottom:10px">NSE often blocks cloud servers, so the scanner cannot always read the option chain. Type the numbers from your own chain: the verdict below updates instantly.</p>`}
    <div class="chips"><label class="help">Call wall <input class="inp" id="oiC" inputmode="numeric" value="${man.call_wall ?? ''}" placeholder="${a ? a.call_wall : 'e.g. 22800'}"></label><label class="help">Put wall <input class="inp" id="oiP" inputmode="numeric" value="${man.put_wall ?? ''}" placeholder="${a ? a.put_wall : 'e.g. 22500'}"></label><label class="help">PCR <input class="inp" id="oiR" inputmode="decimal" style="width:80px" value="${man.pcr ?? ''}" placeholder="${a && a.pcr ? a.pcr : '1.1'}"></label><button class="btn" id="oiClear" type="button">Clear</button></div>${verdict}
    <p class="help" style="margin-top:8px">How to read it: for a CALL you want a big put wall below price (support) and the call wall beyond your first target. For a PUT the mirror image.</p></div></div>`;
}
function bindOI() {
  const upd = () => { store.set('ds.oi', { call_wall: $('#oiC').value, put_wall: $('#oiP').value, pcr: $('#oiR').value }); const it = DS.cur, v = $('#oiVerdict');
    if (it && v) { v.innerHTML = oiVerdict(it); const ck = $('#ckOI'); if (ck) ck.className = DS.oiAlign(it.direction, it.entry, it.sl, it.t1, DS.oiNow()).aligned ? 'y' : ''; } };
  ['#oiC', '#oiP', '#oiR'].forEach(s => { const e = $(s); if (e) e.oninput = upd; });
  const c = $('#oiClear'); if (c) c.onclick = () => { ['#oiC', '#oiP', '#oiR'].forEach(s => { $(s).value = ''; }); upd(); };
}
function optionsTop(d) {
  const p = d.snapshot; if (!p) return '';
  const yes = v => v ? '<span class="good">above</span>' : '<span class="bad">below</span>', bias = p.bias_up ? '<span class="good">Up (calls)</span>' : p.bias_down ? '<span class="bad">Down (puts)</span>' : '<span class="muted">None</span>';
  return `<div class="grid g4" style="margin-bottom:12px">${tile('Nifty 50', fmt(p.spot, 1), `<span class="${p.change_pct >= 0 ? 'good' : 'bad'}">${sg(p.change_pct)}%</span> · VIX ${p.vix == null ? '-' : fmt(p.vix, 1)}`)}${tile('15m CHoCH bias', bias, 'CHoCH intact')}${tile('5m / 15m 9 EMA', fmt(p.ema_5m, 1) + ' / ' + fmt(p.ema_15m, 1), 'price ' + yes(p.above_5m) + ' / ' + yes(p.above_15m))}${tile('Prev day high / low', (p.pdh_pdl || []).map(x => fmt(x, 1)).join(' / ') || '-', 'day range ' + fmt(p.day_low, 1) + '-' + fmt(p.day_high, 1))}</div>
    <div class="callout warn" style="margin-bottom:12px"><span class="ic">!</span><div>Volume is not part of the options rules here: check it yourself on the NIFTY1! chart. Weekly expiry is Tuesday (the previous trading day if it is a holiday): skip new buys after lunch on expiry day.</div></div>${oiPanel(null)}<div style="height:12px"></div>`;
}

/* ------------------------------------------------------------ chart */
DS.chart = function (it, W, sig) {
  W = Math.max(300, Math.min(W || 700, 940)); const H = Math.round(Math.max(290, Math.min(W * .62, 460))), PL = 6, PR = W < 520 ? 104 : 140, PT = 12, PB = 22, PW = W - PL - PR, PH = H - PT - PB, d = dec(it);
  const maxN = W < 520 ? 45 : 64, C = it.candles.slice(-maxN), n = C.length, EM = it.ema.slice(-maxN), TM = it.times.slice(-maxN), lv = [['Entry', it.entry, '#5b8cff', 1.6, '6 4'], ['SL', it.sl, '#ff5d6c', 1.8, ''], ['T1', it.t1, '#25c48c', 1.3, '5 4'], ['T2', it.t2, '#25c48c', 1.1, '5 4'], ['T3', it.t3, '#25c48c', 1.1, '5 4']].filter(x => x[1] != null);
  let lo = Math.min(...C.map(c => c[2]), ...lv.map(x => x[1]), it.zone_bot), hi = Math.max(...C.map(c => c[1]), ...lv.map(x => x[1]), it.zone_top); const pad = (hi - lo) * .05; lo -= pad; hi += pad;
  const X = i => PL + (i + .5) * PW / (n + 4), Y = p => PT + (hi - p) / (hi - lo) * PH, bw = Math.max(2, PW / (n + 4) * .62), g = [], dark = document.documentElement.dataset.theme === 'dark';
  const ink3 = dark ? '#6d7992' : '#76829b', upc = dark ? '#25c48c' : '#0d9b6a', dnc = dark ? '#ff5d6c' : '#d6334a';
  g.push(`<rect x="${PL}" y="${Y(it.zone_top)}" width="${PW}" height="${Math.max(2, Y(it.zone_bot) - Y(it.zone_top))}" fill="${it.direction === 'long' ? '#25c48c' : '#ff5d6c'}" opacity=".13"/>`);
  if (it.fib_lo != null) g.push(`<rect x="${PL}" y="${Y(Math.max(it.fib_lo, it.fib_hi))}" width="${PW}" height="${Math.max(2, Math.abs(Y(it.fib_lo) - Y(it.fib_hi)))}" fill="#f4b53d" opacity=".16"/>`);
  for (let k = 0; k <= 4; k++) { const p = lo + (hi - lo) * k / 4, yy = Y(p); g.push(`<line x1="${PL}" x2="${PL + PW}" y1="${yy}" y2="${yy}" stroke="${dark ? '#1a2234' : '#e8ecf4'}"/><text x="${PL + 3}" y="${yy - 3}" font-size="9.5" fill="${ink3}">${fmt(p, d)}</text>`); }
  C.forEach(([o, h, l, c], i) => { const col = c >= o ? upc : dnc; g.push(`<line x1="${X(i)}" x2="${X(i)}" y1="${Y(h)}" y2="${Y(l)}" stroke="${col}" stroke-width="1.2"/><rect x="${X(i) - bw / 2}" y="${Y(Math.max(o, c))}" width="${bw}" height="${Math.max(1, Math.abs(Y(o) - Y(c)))}" fill="${col}"/>`); });
  g.push(`<polyline fill="none" stroke="#a78bfa" stroke-width="1.5" points="${EM.map((v, i) => X(i) + ',' + Y(v)).join(' ')}"/>`);
  const lastC = C[n - 1][3]; g.push(`<line x1="${X(n - 1)}" x2="${PL + PW}" y1="${Y(lastC)}" y2="${Y(lastC)}" stroke="${ink3}" stroke-dasharray="2 3"/>`);
  if (sig && sig.stop != null && sig.stop !== it.sl) { lv.push(['Stop now', sig.stop, '#f4b53d', 2, '']); }
  const hit = t => sig && sig.hits && sig.hits[t];
  const labs = lv.map(([t, p, col, w, da]) => { g.push(`<line x1="${X(Math.max(0, n - 10))}" x2="${PL + PW}" y1="${Y(p)}" y2="${Y(p)}" stroke="${col}" stroke-width="${w}" ${da ? `stroke-dasharray="${da}"` : ''}/>`); return [Y(p), (hit(t) ? '✓ ' : '') + t + ' ' + fmt(p, d) + (W < 520 ? '' : t === 'T1' && it.r_t1 ? ' · ' + it.r_t1.toFixed(1) + 'R' : t === 'T2' ? ' · 2R' : t === 'T3' ? ' · 3R' : ''), col, t]; }).concat([[Y(lastC), 'Now ' + fmt(lastC, d), ink3, 'now']]);
  labs.sort((a, b) => a[0] - b[0]); let last = -99; labs.forEach(l => { l[0] = Math.max(l[0], last + 13); last = l[0]; g.push(`<text x="${PL + PW + 6}" y="${l[0] + 3.5}" font-size="${W < 520 ? 10.5 : 11.5}" font-weight="700" fill="${l[2]}">${esc(l[1])}</text>`); });
  [['T1', '1'], ['T2', '2'], ['T3', '3']].forEach(([t, num]) => { const x = lv.find(a => a[0] === t); if (x) { const cx = PL + PW - 11; g.push(`<circle cx="${cx}" cy="${Y(x[1])}" r="8.5" fill="${dark ? '#0a0d13' : '#fff'}" stroke="#25c48c" stroke-width="1.4"/><text x="${cx}" y="${Y(x[1]) + 3.6}" font-size="10.5" font-weight="800" text-anchor="middle" fill="#25c48c">${num}</text>`); } });
  const ent = lv[0]; if (ent) g.push(`<circle cx="${X(n - 1) + 14}" cy="${Y(ent[1])}" r="8.5" fill="#5b8cff"/><text x="${X(n - 1) + 14}" y="${Y(ent[1]) + 3.6}" font-size="10.5" font-weight="800" text-anchor="middle" fill="#fff">E</text>`);
  g.push(`<text x="${PL + 2}" y="${H - 6}" font-size="10" fill="${ink3}">${esc(TM[0])}</text><text x="${PL + PW - 40}" y="${H - 6}" font-size="10" text-anchor="end" fill="${ink3}">${esc(TM[n - 1])} · ${esc(it.tf_structure)} · purple = 9 EMA</text>`);
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(it.symbol)} chart with entry, stop-loss, targets and the entry zone">${g.join('')}</svg>`;
};

/* ------------------------------------------------------------ trade page */
function qtyBox(it) {
  const risk = store.get('ds.risk', 1000), d = dec(it), unit = Math.abs(it.entry - it.sl); let body;
  if (it.section === 'options') {
    const ot = it.options_trade, lot = store.get('ds.lot', (DS.data.options && DS.data.options.lot_size) || 65), per = ot ? Math.max(ot.premium - ot.premium_sl, 0.01) : null;
    body = ot ? `<label class="help">Risk ₹ <input class="inp" id="riskIn" inputmode="decimal" value="${risk}"></label> <label class="help">Lot size <input class="inp" id="lotIn" style="width:70px" inputmode="numeric" value="${lot}"></label>
      <div class="kv" style="margin-top:10px"><span>Premium risk per unit (model)</span><b class="n">${fmt(per, 1)}</b><span>Risk per lot</span><b class="n">₹${fmt(per * lot, 0)}</b><span>Lots for your risk</span><b class="n" id="qOut">${Math.floor(risk / (per * lot))}</b><span>Cost of one lot (model)</span><b class="n">₹${fmt(ot.premium * lot, 0)}</b></div>` : '<p class="help">No strike estimate available.</p>';
  } else body = `<label class="help">Risk ₹ <input class="inp" id="riskIn" inputmode="decimal" value="${risk}"></label><div class="kv" style="margin-top:10px"><span>Risk per share</span><b class="n">${fmt(unit, d)}</b><span>Quantity</span><b class="n" id="qOut">${unit > 0 ? Math.floor(risk / unit) : 0}</b><span>Position value</span><b class="n" id="qVal">₹${fmt(unit > 0 ? Math.floor(risk / unit) * it.entry : 0, 0)}</b></div>`;
  return `<div class="card"><div class="hd"><h2>Position size</h2></div><div class="bd">${body}</div></div>`;
}
function strikeCard(it) {
  const ot = it.options_trade; if (!ot) return '';
  const rows = ot.candidates.map(c => `<tr class="${c.recommended ? 'rec' : ''}"><td>${c.strike} ${ot.kind} <small class="muted">${esc(c.moneyness)}</small></td><td class="n">${fmt(c.premium, 1)}</td><td class="n">${c.delta.toFixed(2)}</td><td class="n">${c.gamma.toFixed(4)}</td><td class="n">${fmt(c.theta_day, 1)}</td><td class="n">${c.theta_pct_hour.toFixed(1)}%</td><td class="n">${fmt(c.vega, 1)}</td><td class="n">${fmt(c.premium_sl, 1)}</td><td class="n">${fmt(c.premium_targets[0], 1)}</td><td class="n">${c.rr_t1.toFixed(1)}</td></tr>`).join('');
  return `<div class="card"><div class="hd"><h2>Strike and Greeks</h2>${pill('Buy ' + esc(ot.instrument), 'info')}${pill('Expiry ' + esc(ot.expiry) + ' · ' + ot.dte_days.toFixed(1) + ' days')}</div><div class="bd">
    <div class="grid g4" style="margin-bottom:12px">${tile('Premium (model)', fmt(ot.premium, 1))}${tile('Delta / Gamma', ot.delta.toFixed(2) + ' / ' + ot.gamma.toFixed(4))}${tile('Theta / day', fmt(ot.theta_day, 1), fmt(ot.theta_hour, 1) + ' per hour')}${tile('Vega', fmt(ot.vega, 1), 'per 1 vol point')}</div>
    <div class="grid g3" style="margin-bottom:12px">${tile('Premium at SL', fmt(ot.premium_sl, 1), 'index ' + fmt(it.sl, 1), 'bad')}${tile('Premium at T1', fmt(ot.premium_targets[0], 1), 'index ' + fmt(it.t1, 1), 'good')}${tile('Premium at T2 / T3', fmt(ot.premium_targets[1], 1) + ' / ' + fmt(ot.premium_targets[2], 1), '', 'good')}</div>
    <div class="scroll"><table class="cand"><thead><tr><th>Strike</th><th>Premium</th><th>Delta</th><th>Gamma</th><th>Theta/d</th><th>Theta/h</th><th>Vega</th><th>@SL</th><th>@T1</th><th>RR T1</th></tr></thead><tbody>${rows}</tbody></table></div>
    <ol class="steps" style="margin-top:12px">${ot.reasons.map(r => `<li>${esc(r)}</li>`).join('')}</ol><p class="help">Model prices use India VIX (${fmt(ot.iv, 1)}) as the volatility and ignore skew and spreads. Compare with the live chain before you place the order.</p></div></div>`;
}
function indexCard(it) {
  const c = it.index_check; if (!c) return '';
  const cls = c.state === 'falling' ? 'bad' : c.state === 'unknown' ? 'warn' : 'ok';
  return `<div class="card"><div class="hd"><h2>Sector index confirmation</h2>${pill(esc(c.state), cls)}</div><div class="bd"><div class="kv"><span>Index</span><b>${esc(c.sector_index)}</b><span>Source</span><b>${c.source === 'basket' ? 'equal-weight basket of the same industry' : 'NSE index'}</b>
    ${c.close != null ? `<span>Close / 9 EMA / 21 EMA</span><b class="n">${fmt(c.close, 1)} / ${fmt(c.ema9, 1)} / ${fmt(c.ema21, 1)}</b><span>5-day move</span><b class="n ${c.ret5 >= 0 ? 'good' : 'bad'}">${sg(c.ret5)}%</b>${c.today != null ? `<span>Today</span><b class="n ${c.today >= 0 ? 'good' : 'bad'}">${sg(c.today)}%</b>` : ''}` : ''}</div>
    <p class="help" style="margin-top:8px">${c.reasons.map(esc).join('. ')}.</p>${c.state === 'falling' ? '<div class="callout bad" style="margin-top:8px"><span class="ic">!</span><div>The whole index is falling, so the stock is unlikely to sustain a long. The setup is held at WATCH until the index stabilises.</div></div>' : ''}
    <p class="help" style="margin-top:8px">Rule: a long needs its sector index above its 21 EMA (not more than half an ATR below), not down 3% in 5 days and not down 1% today.</p></div></div>`;
}
function resolveTrade() {
  const q = new URLSearchParams(location.search), sec = q.get('s') || 'swing', d = DS.data[sec], L = LED(sec); let it = null, sig = null, drop = null;
  if (q.get('sig')) { sig = L.signals.find(s => s.id === q.get('sig')) || null; it = sig && sig.item; }
  else {
    const [sym, dir] = (q.get('id') || '').split('|'); it = d && d.setups.find(s => s.symbol === sym && s.direction === dir);
    if (it) sig = L.signals.find(s => s.id === sigKey(sec, it)) || null;
    else { sig = L.signals.filter(s => s.symbol === sym && s.direction === dir).sort((a, b) => (b.created || '').localeCompare(a.created || ''))[0] || null; it = sig && sig.item; if (!it) drop = (L.dropped || []).filter(w => w.symbol === sym && w.direction === dir).pop() || null; }
  }
  return { sec, d, it, sig, drop };
}
function trackCard(sig, it) {
  const d = dec(it), closed = sig.status === 'CLOSED', r = closed ? sig.r_final : sig.r_now;
  return `<div class="card"><div class="hd"><h2>Trade tracking</h2>${pill(esc(sigStatus(sig, d)), closed ? (r > 0 ? 'ok' : 'bad') : 'info')}</div><div class="bd">
    <div class="grid g3" style="margin-bottom:10px">${tile(closed ? 'Result' : 'R now', r == null ? '-' : sg(r, 2) + 'R', closed ? esc(outcomeTxt[sig.outcome] || '') : 'last ' + fmt(sig.last, d), r > 0 ? 'good' : r < 0 ? 'bad' : '')}${tile(closed ? 'Exit' : 'Stop now', fmt(closed ? sig.exit : sig.stop, d), closed ? 'closed ' + esc((sig.closed || '').replace('T', ' ').slice(5, 16)) : (sig.stop === sig.sl ? 'original stop' : 'trailed'))}${tile('Best / worst', fmt(sig.best, d) + ' / ' + fmt(sig.worst, d), 'since the trigger')}</div>
    <ol class="steps">${sig.events.slice().reverse().map(e => `<li><span class="when">${esc(e.t.replace('T', ' ').slice(5, 16))}</span>${esc(e.text)}</li>`).join('')}</ol>
    <p class="help">Followed every run on closed candles. The stop is assumed to fill before a target inside the same candle. Result assumes half at the first target, a quarter at the second, the rest at exit.</p></div></div>`;
}
function dropCard(w) {
  const d = w.section === 'options' ? 1 : 2;
  return `<div class="thead"><h1>${esc(w.symbol)}</h1><span class="tag t-${w.direction}">${esc(w.label || w.direction.toUpperCase())}</span><span class="pill bad">invalidated</span></div>
    <div class="callout bad" style="margin:12px 0"><span class="ic">!</span><div><b>This setup was cancelled before it triggered</b> (${esc((w.dropped || '').replace('T', ' ').slice(0, 16))} IST).<br>${esc(w.reason || '')}</div></div>
    <div class="card"><div class="bd"><div class="kv"><span>Last status</span><b>${esc(w.status || '')}</b><span>Grade / score</span><b>${esc(w.grade || '')} ${w.score || ''}/10</b><span>Zone</span><b class="n">${fmt(w.zone_bot, d)} to ${fmt(w.zone_top, d)}</b><span>Planned entry / SL / T1</span><b class="n">${fmt(w.entry, d)} / ${fmt(w.sl, d)} / ${fmt(w.t1, d)}</b><span>First seen</span><b>${esc((w.first_seen || '').replace('T', ' ').slice(5, 16))}</b></div>
    <p class="help" style="margin-top:8px">If you entered anyway, manage it with the original stop and log the trade in your journal as a rule break ("No confirmation").</p></div></div>`;
}
function journalTrades() {
  try { const L = JSON.parse(localStorage.getItem('tji_journals_v1') || '[]'); return (Array.isArray(L) ? L : []).filter(x => !x.demo).flatMap(x => (x.trades || []).map(t => Object.assign({ _j: x.name }, t))); } catch (e) { return []; }
}
const inJournal = k => journalTrades().find(t => (t.note || '').includes('DS:' + k));
DS.logTrade = function (it, sig) {
  if (!it) return; const ot = it.options_trade, m = DS.data.market, sec = it.section, key = sig ? sig.id : sigKey(sec, it);
  const reg = m && m.daily ? ({ trending_up: 'Trending', trending_down: 'Trending', range: 'Range', volatile: 'Volatile' }[m.daily.regime] || null) : null;
  const ist = new Date(Date.now() + 5.5 * 3600e3).toISOString(), risk = store.get('ds.risk', 1000), unit = Math.abs(it.entry - it.sl);
  let qty = unit > 0 ? Math.floor(risk / unit) : null;
  if (ot) { const lot = store.get('ds.lot', (DS.data.options && DS.data.options.lot_size) || 65), per = Math.max(ot.premium - ot.premium_sl, .01); qty = Math.max(1, Math.floor(risk / (per * lot))) * lot; }
  const trade = { d: ist.slice(0, 10), tm: ist.slice(11, 16), inst: ot ? ot.instrument : it.symbol, cat: { swing: 'Swing', options: 'Options', intraday: 'Intraday' }[sec], setup: it.ob_low != null ? 'Pullback from OB' : 'Pullback from FVG',
    tf: sec === 'swing' ? 'Daily' : '5 MINS', dir: it.direction === 'long' ? 'Long' : 'Short', grade: ['A+', 'A', 'B', 'C'].includes(it.grade) ? it.grade : null, qty,
    entry: ot ? +ot.premium.toFixed(2) : it.entry, sl: ot ? +ot.premium_sl.toFixed(2) : it.sl, tgt: ot ? +ot.premium_targets[0].toFixed(2) : it.t1, reg, evt: it.results && it.results.days != null && it.results.days <= 7 ? 'Yes' : 'No', exp: ot ? ot.expiry : null,
    note: `DS:${key} | ${it.score}/10 ${it.ticks.join(', ')}` + (ot ? ` | model premium; index entry ${it.entry} SL ${it.sl} T1 ${it.t1}: edit to your fill` : '') };
  store.set('ds.pendingTrade', { at: Date.now(), trade }); location.href = 'journal.html';
};
function tradePage() {
  const R = resolveTrade(), sec = R.sec, d = R.d; DS.parent = sec;
  const back = `<a class="back" href="${sec}.html">${svgI('back')} Back to ${SECT[sec] ? SECT[sec].title : 'list'}</a>`;
  if (!R.it) return back + (R.drop ? dropCard(R.drop) : empty('Setup not found', 'It is no longer in the scan and was never triggered. Check Closed / invalidated on the list page.'));
  const it = R.it, sig = R.sig, jk = inJournal(sig ? sig.id : sigKey(sec, it));
  const dc = dec(it), nw = DS.data.news && DS.data.news.by_symbol && DS.data.news.by_symbol[it.symbol], risk = Math.abs(it.entry - it.sl), pc = v => v == null ? '-' : (100 * Math.abs(v - it.entry) / it.entry).toFixed(1) + '%';
  const rr = k => k === 'T1' ? it.r_t1 : k === 'T2' ? 2 : 3;
  const lvRows = [['Entry', it.entry, '', 'en'], ['SL', it.sl, '', 'sl'], ['T1', it.t1, 'T1', 'tg'], ['T2', it.t2, 'T2', 'tg'], ['T3', it.t3, 'T3', 'tg']].map(([k, v, r, c]) => `<tr><td><b class="${c === 'en' ? 'good' : c === 'sl' ? 'bad' : 'good'}" style="color:${c === 'en' ? 'var(--brand)' : ''}">${k}</b></td><td class="n"><b>${fmt(v, dc)}</b></td><td class="n">${r ? rr(r).toFixed(1) + 'R' : k === 'SL' ? '1R risk' : '-'}</td><td class="n">${k === 'Entry' ? '-' : pc(v)}</td></tr>`).join('');
  const checks = [['key level', 'Key level'], ['fib', 'Fib 0.618 to 0.705'], ['MTF EMA', 'Timeframes agree (EMA)'], ['order block (15m)', '15m order block'], ['OI wall', 'OI walls agree'], ['weekly trend', 'Weekly trend up'], ['Nifty trend', 'Nifty above 21 EMA']].filter(([k]) => it.section === 'swing' ? !['order block (15m)', 'OI wall'].includes(k) : it.section === 'options' ? ['key level', 'fib', 'MTF EMA', 'order block (15m)', 'OI wall'].includes(k) : ['key level', 'fib', 'MTF EMA'].includes(k));
  const oiYes = it.section === 'options' && DS.oiAlign(it.direction, it.entry, it.sl, it.t1, DS.oiNow()).aligned;
  const stepsOf = (arr, key) => arr.map(x => `<li>${x.when ? `<span class="when">${esc(x.when)}</span>` : ''}${esc(x.action || x)}</li>`).join('');
  return `${back}<div class="thead"><h1>${esc(it.section === 'options' && it.options_trade ? it.options_trade.instrument : it.symbol)}</h1><span class="tag t-${it.direction}">${esc(it.label)}</span><span class="tag ${gcls(it.grade)}">${it.grade}</span><span class="st ${sig ? (sig.status === 'CLOSED' ? 'a' : 't') : kind(it)}">${esc(sig ? sigStatus(sig, dec(it)) : it.status)}</span>${jk ? '<span class="pill ok">in your journal</span>' : ''}
      <div class="score"><b class="n">${it.score}<span class="muted" style="font-size:15px">/10</span></b><small>Structure ${it.structure} · Zone ${it.zone_q} · Confirm ${it.confirm} · Context ${it.context}</small></div></div>
    <p class="help" style="margin:4px 0 12px">${esc(it.tf_structure)} structure, ${esc(it.tf_trigger)} trigger · CHoCH ${esc(it.choch_date)} · BOS ${esc(it.bos_date)} · ${sig ? 'triggered ' + esc(sig.created.replace('T', ' ').slice(0, 16)) : esc(ist(d.generated_at)) + ' IST'}${it.sector ? ' · ' + esc(it.sector) : ''}</p>
    ${it.results && it.results.days != null && it.results.days <= 7 ? `<div class="callout bad" style="margin-bottom:12px"><span class="ic">!</span><div><b>Results in ${it.results.days} day(s) (${esc(it.results.date)}).</b> Your rule is no event risk in the hold: exit or cut the size before the announcement.</div></div>` : ''}
    <div class="grid g2 tr2" style="grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);align-items:start">
      <div class="stack"><div class="card"><div class="hd"><h2>Chart: levels marked</h2><button class="btn primary" id="logBtn" type="button">${jk ? 'Log again' : 'Log in journal'}</button><a class="btn" href="${tvUrl(it.symbol)}" target="_blank" rel="noopener">TradingView</a></div><div class="bd" id="chartBox">${DS.chart(it, 700, sig)}
        <div class="lg"><span><i style="background:#5b8cff"></i>Entry (E)</span><span><i style="background:#ff5d6c"></i>Stop-loss</span><span><i style="background:#25c48c"></i>Targets 1, 2, 3 = trail steps</span><span><i style="background:rgba(37,196,140,.35);height:9px"></i>Entry zone</span><span><i style="background:rgba(244,181,61,.5);height:9px"></i>Fib pocket</span><span><i style="background:#a78bfa"></i>9 EMA</span></div></div></div>
        <div class="card"><div class="hd"><h2>Why this trade</h2></div><div class="bd logic">${it.logic.map(s => `<div class="step"><h3>${esc(s.title)}</h3><p>${esc(s.text)}</p></div>`).join('')}<div class="ck" style="margin-top:12px">${checks.map(([k, t]) => k === 'OI wall' ? `<div id="ckOI" class="${oiYes ? 'y' : ''}">${t}</div>` : `<div class="${it.ticks.includes(k) ? 'y' : ''}">${t}</div>`).join('')}</div></div></div></div>
      <div class="stack">${sig ? trackCard(sig, it) : ''}<div class="card"><div class="hd"><h2>Levels</h2></div><div class="bd"><table class="lv"><thead><tr><th>Level</th><th class="n">Price</th><th class="n">Reward</th><th class="n">Distance</th></tr></thead><tbody>${lvRows}</tbody></table><p class="help" style="margin-top:8px">Risk to the stop ${fmt(risk, dc)} (${it.risk_pct == null ? '-' : it.risk_pct.toFixed(1)}%). T1 is the previous swing, T2 and T3 are 2R and 3R.</p></div></div>
        ${qtyBox(it)}${indexCard(it)}<div class="card"><div class="hd"><h2>How to execute</h2></div><div class="bd"><ol class="steps">${stepsOf(it.plan.execution)}</ol></div></div>
        <div class="card"><div class="hd"><h2>How to trail</h2></div><div class="bd"><ol class="steps">${stepsOf(it.plan.trail)}</ol><div class="callout" style="margin-top:6px"><div><b>Rules</b><br>${it.plan.rules.map(esc).join('<br>')}</div></div></div></div></div></div>
    <div class="stack" style="margin-top:12px">${strikeCard(it)}${it.section === 'options' ? oiPanel(it) : ''}
      <div class="card"><div class="hd"><h2>News for ${esc(it.symbol)}</h2></div><div class="bd news">${nw && nw.length ? nw.map(n => `<a class="it" href="${esc(n.link)}" target="_blank" rel="noopener">${esc(n.title)}<small><span>${esc(n.source)}</span><span>${esc((n.published || '').slice(0, 16).replace('T', ' '))}</span></small></a>`).join('') : '<p class="help">No headlines found for this symbol in the last run. Check the exchange announcements for results dates and corporate actions.</p>'}</div></div></div>`;
}
function bindTrade() {
  const r = $('#riskIn'); if (r) r.oninput = () => { const v = Math.max(0, +r.value || 0); store.set('ds.risk', v); const it = DS.cur; if (!it) return; const u = Math.abs(it.entry - it.sl);
    if (it.section === 'options' && it.options_trade) { const ot = it.options_trade, lot = store.get('ds.lot', 65), per = Math.max(ot.premium - ot.premium_sl, .01); $('#qOut').textContent = Math.floor(v / (per * lot)); } else { $('#qOut').textContent = u > 0 ? Math.floor(v / u) : 0; $('#qVal').textContent = '₹' + fmt(u > 0 ? Math.floor(v / u) * it.entry : 0, 0); } };
  const l = $('#lotIn'); if (l) l.oninput = () => { store.set('ds.lot', Math.max(1, +l.value || 65)); if (r) r.oninput(); };
  const lb = $('#logBtn'); if (lb) lb.onclick = () => DS.logTrade(DS.cur, DS.curSig);
  bindOI(); let t; window.onresize = () => { clearTimeout(t); t = setTimeout(sizeChart, 150); }; sizeChart();
}
function sizeChart() { const b = $('#chartBox'), it = DS.cur; if (!b || !it) return; const w = b.clientWidth - 28, svg = b.querySelector('svg'); if (svg) svg.outerHTML = DS.chart(it, w, DS.curSig); }
DS.onTheme = () => { if (DS.navActive === 'trade') sizeChart(); };

/* ------------------------------------------------------------ market page */
function marketPage() {
  const m = DS.data.market; let h = `<div class="ph"><div><h1>Market</h1><p>How the market is behaving, so you can pick the right kind of trade today: trending, range-bound or volatile.</p></div><span class="sp"></span>${m ? age(m, true) : ''}</div>`;
  if (!m) return h + empty('Not available yet', 'Run the workflow once (mode all) and refresh.');
  const dl = m.daily, it = m.intraday, ix = m.indices || {}, em = m.expected_move, pb = m.playbook, T = (n, x, d = 1) => x ? tile(n, fmt(x.price, d), `<span class="${x.change_pct >= 0 ? 'good' : 'bad'}">${sg(x.change_pct)}%</span>`) : '';
  h += `<div class="grid g4" style="margin-bottom:12px">${T('Nifty 50', ix.nifty)}${T('Bank Nifty', ix.banknifty)}${T('India VIX', ix.vix, 2)}${em ? tile('VIX implies', '±' + fmt(em.daily_pts, 0) + ' pts', `a day (${em.daily_pct}%) · ±${fmt(em.weekly_pts, 0)} a week`) : ''}</div>
    <div class="card" style="margin-bottom:12px"><div class="hd"><h2>${esc(pb.headline)}</h2>${pill(esc(dl.label), regimeCls(dl.regime))}${it.regime !== 'unclear' ? pill('Today: ' + esc(it.label), regimeCls(it.regime)) : pill('Today: too early', '')}${pill('Volatility ' + esc(dl.volatility), dl.volatility === 'high' ? 'warn' : '')}</div><div class="bd"><p style="color:var(--ink2)">${esc(dl.reading)}</p>${pb.today ? `<p style="color:var(--ink2);margin-top:6px"><b>Today:</b> ${esc(pb.today)}. ${esc(it.reading || '')}</p>` : it.reading ? `<p style="color:var(--ink2);margin-top:6px"><b>Today:</b> ${esc(it.reading)}</p>` : ''}${pb.risk.map(r => `<div class="callout warn" style="margin-top:8px"><span class="ic">!</span><div>${esc(r)}</div></div>`).join('')}</div></div>
    <div class="grid g3" style="margin-bottom:12px">${[['Swing', pb.swing, 'swing.html'], ['Nifty options', pb.options, 'options.html'], ['Intraday', pb.intraday, 'intraday.html']].map(([t, a, u]) => `<div class="card"><div class="hd"><h2>${t}</h2><a href="${u}">Open</a></div><div class="bd"><ol class="steps">${a.map(x => `<li>${esc(x)}</li>`).join('')}</ol></div></div>`).join('')}</div>
    <div class="grid g2" style="margin-bottom:12px"><div class="card"><div class="hd"><h2>Daily trend gauges</h2></div><div class="bd"><div class="kv"><span>ADX (trend strength)</span><b class="n">${dl.adx} (+DI ${dl.plus_di} / -DI ${dl.minus_di})</b><span>Efficiency ratio (10 days)</span><b class="n">${dl.er10}</b><span>EMA stack 9 / 21 / 50</span><b class="n">${dl.stack} (${fmt(dl.ema9, 0)} / ${fmt(dl.ema21, 0)} / ${fmt(dl.ema50, 0)})</b><span>ATR (14)</span><b class="n">${fmt(dl.atr, 0)} pts (${dl.atr_pct}%)</b><span>ATR percentile (1 year)</span><b class="n">${dl.atr_rank}th</b><span>20-day range</span><b class="n">${fmt(dl.range20.low, 0)} to ${fmt(dl.range20.high, 0)} (at ${Math.round(dl.range20.pos * 100)}%)</b>${dl.vix != null ? `<span>India VIX / percentile</span><b class="n">${dl.vix} / ${dl.vix_rank == null ? '-' : dl.vix_rank + 'th'}</b>` : ''}</div>
      <p class="help" style="margin-top:8px">Trend = ADX 22+ with stacked EMAs and a directional 10 days. Range = ADX under 20 and no direction. Volatile = ATR in its top quarter or VIX 18+ without a clean trend.</p></div></div>
      <div class="card"><div class="hd"><h2>Today's session</h2></div><div class="bd">${it.regime === 'unclear' ? `<p class="help">${esc(it.reading || '')}</p>` : `<div class="kv"><span>Open / High / Low / Last</span><b class="n">${fmt(it.open, 0)} / ${fmt(it.high, 0)} / ${fmt(it.low, 0)} / ${fmt(it.close, 0)}</b><span>Range so far</span><b class="n">${fmt(it.range_pts, 0)} pts${it.atr_ratio != null ? ' (' + it.atr_ratio + 'x ATR)' : ''}</b><span>Efficiency (direction)</span><b class="n">${it.er}</b><span>15m EMA crosses</span><b class="n">${it.crosses}</b><span>Gap vs previous close</span><b class="n">${it.gap_pct == null ? '-' : sg(it.gap_pct) + '%'}</b><span>Position in the range</span><b class="n">${Math.round(it.pos_in_range * 100)}%</b></div><p class="help" style="margin-top:8px">Trend day = one-directional with few EMA crosses. Range day = small and back-and-forth. Volatile = range above the daily ATR without direction.</p>`}</div></div></div>`;
  const b = m.breadth;
  if (b) h += `<div class="grid g2" style="margin-bottom:12px"><div class="card"><div class="hd"><h2>Breadth (${b.count} stocks)</h2></div><div class="bd">${[['Above 21 EMA', b.above21], ['Above 50 EMA', b.above50], ['Above 200 EMA', b.above200]].map(([k, v]) => v == null ? '' : `<div style="margin-bottom:10px"><div class="kv"><span>${k}</span><b class="n">${v}%</b></div><div class="bar"><i style="width:${v}%;background:${v >= 60 ? 'var(--good)' : v <= 40 ? 'var(--bad)' : 'var(--warn)'}"></i></div></div>`).join('')}
      <div class="kv"><span>Advancers / decliners today</span><b class="n">${b.advancers} / ${b.decliners}</b><span>20-day highs / lows</span><b class="n">${b.new_highs} / ${b.new_lows}</b><span>Average 20-day return vs Nifty</span><b class="n">${sg(b.avg_20d)}% vs ${sg(b.nifty_20d)}%</b></div></div></div>
      <div class="card"><div class="hd"><h2>Sectors vs Nifty (20 days)</h2></div><div class="bd scroll"><table class="cand" style="min-width:420px"><thead><tr><th>Sector</th><th>Stocks</th><th>Above 50 EMA</th><th>20d return</th><th>vs Nifty</th></tr></thead><tbody>${(m.sectors || []).map(s => `<tr><td>${esc(s.sector)} <span class="tag ${s.state === 'strong' ? 't-long' : s.state === 'weak' ? 't-short' : 'g-B'}">${s.state}</span></td><td class="n">${s.count}</td><td class="n">${s.above50}%</td><td class="n ${s.ret20 >= 0 ? 'good' : 'bad'}">${sg(s.ret20)}%</td><td class="n ${s.rs20 >= 0 ? 'good' : 'bad'}">${sg(s.rs20)}%</td></tr>`).join('')}</tbody></table></div></div></div>`;
  else h += '<div class="callout" style="margin-bottom:12px"><div>Breadth and sector strength come from the swing scan of the Nifty 500. They appear after the first swing run with the full list.</div></div>';
  return h;
}

/* ------------------------------------------------------------ news page */
function newsPage() {
  const nw = DS.data.news, st = store.get('ds.news', { topic: 'All' }); let h = `<div class="ph"><div><h1>News and events</h1><p>What can move the market: headlines, expiry days, holidays, policy meetings and the results dates of stocks you have setups in.</p></div><span class="sp"></span>${nw ? age(nw, true) : ''}</div>`;
  if (!nw) return h + empty('Not available yet', 'Run the workflow once (mode all) and refresh.');
  h += nw.risk_flags && nw.risk_flags.length ? nw.risk_flags.map(f => `<div class="callout warn" style="margin-bottom:8px"><span class="ic">!</span><div>${esc(f)}</div></div>`).join('') : '<div class="callout good" style="margin-bottom:8px"><div>No expiry, holiday or major event today or tomorrow.</div></div>';
  const topics = ['All', 'High impact', 'RBI', 'Fed / Global', 'Crude', 'Flows', 'Results', 'Policy', 'Rupee', 'Sector'], ok = x => st.topic === 'All' || (st.topic === 'High impact' ? x.impact === 'high' : (x.topics || []).includes(st.topic));
  const heads = (nw.headlines || []).filter(ok);
  h += `<div class="grid g2 tr2" style="grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);align-items:start;margin-top:12px"><div class="stack"><div class="card"><div class="hd"><h2>Headlines</h2></div><div class="bd"><div class="chips" style="margin-bottom:10px">${topics.map(t => `<button class="chip" type="button" data-t="${t}" aria-pressed="${st.topic === t}">${t}</button>`).join('')}</div>
    <div class="news">${heads.length ? heads.map(n => `<a class="it" href="${esc(n.link)}" target="_blank" rel="noopener">${n.impact === 'high' ? '<span class="hi">● </span>' : ''}${esc(n.title)}<small><span>${esc(n.source)}</span><span>${esc((n.published || '').slice(5, 16).replace('T', ' '))}</span>${(n.topics || []).map(t => `<span class="pill">${esc(t)}</span>`).join('')}</small></a>`).join('') : '<p class="help">No headlines for this filter in the last run.</p>'}</div></div></div>
    ${Object.keys(nw.by_symbol || {}).length ? `<div class="card"><div class="hd"><h2>News for your setups</h2></div><div class="bd news">${Object.entries(nw.by_symbol).map(([s, a]) => `<h3 style="margin:8px 0 2px">${esc(s)}</h3>${a.map(n => `<a class="it" href="${esc(n.link)}" target="_blank" rel="noopener">${esc(n.title)}<small><span>${esc(n.source)}</span></small></a>`).join('')}`).join('')}</div></div>` : ''}</div>
    <div class="card"><div class="hd"><h2>Upcoming events (24 days)</h2></div><div class="bd tl">${(nw.events || []).map(e => `<div class="ev ${esc(e.impact)}"><b>${esc(e.title)}</b><small>${esc(e.date)}${e.time ? ' · ' + esc(e.time) : ''} · ${e.days === 0 ? 'today' : e.days === 1 ? 'tomorrow' : 'in ' + e.days + ' days'} · ${esc(e.impact)} impact</small>${e.note ? `<div class="help">${esc(e.note)}</div>` : ''}</div>`).join('') || '<p class="help">Nothing scheduled.</p>'}<p class="help">Edit <b>events.json</b> in the repo to add your own events. Verify holidays on the NSE circular.</p></div></div></div>`;
  return h;
}

/* ------------------------------------------------------------ overview */
function overviewPage() {
  const m = DS.data.market, nw = DS.data.news; let h = `<div class="ph"><div><h1>Overview</h1><p>Your three scans, the state of the market and what could move it today.</p></div></div>`;
  if (nw && nw.risk_flags && nw.risk_flags.length) h += nw.risk_flags.map(f => `<div class="callout warn" style="margin-bottom:8px"><span class="ic">!</span><div>${esc(f)}</div></div>`).join('');
  if (m) h += `<div class="card" style="margin:12px 0"><div class="hd"><h2>${esc(m.playbook.headline)}</h2>${pill(esc(m.daily.label), regimeCls(m.daily.regime))}${m.intraday.regime !== 'unclear' ? pill('Today: ' + esc(m.intraday.label), regimeCls(m.intraday.regime)) : ''}<a href="market.html">Market</a></div><div class="bd"><p style="color:var(--ink2)">${esc(m.daily.reading)}</p></div></div>`;
  h += `<div class="grid g3" style="margin-bottom:12px">${['swing', 'options', 'intraday'].map(k => { const d = DS.data[k], c = SECT[k]; if (!d) return `<div class="card"><div class="hd"><h2>${c.title}</h2></div>${empty('Not run yet', '')}</div>`;
    const top = d.setups.filter(s => s.score >= 6).sort((a, b) => ({ t: 0, w: 1, a: 2 })[kind(a)] - ({ t: 0, w: 1, a: 2 })[kind(b)] || b.score - a.score).slice(0, 4), t = d.setups.filter(s => kind(s) === 't' && s.score >= 6).length;
    return `<div class="card"><div class="hd"><h2>${c.title}</h2>${t ? pill(t + ' triggered', 'ok') : pill('none triggered')}<a href="${k}.html">Open</a></div><div class="bd news">${top.length ? top.map(s => `<a class="it" href="${href(k, s)}"><b>${esc(s.options_trade ? s.options_trade.instrument : s.symbol)}</b> <span class="tag t-${s.direction}">${esc(s.label)}</span> <span class="tag ${gcls(s.grade)}">${s.grade}</span> <span class="st ${kind(s)}">${esc(s.status)}</span><small><span>Entry ${fmt(s.entry, dec(s))}</span><span>SL ${fmt(s.sl, dec(s))}</span><span>T1 ${fmt(s.t1, dec(s))}</span></small></a>`).join('') : '<p class="help">No A-grade setups right now.</p>'}</div></div>`; }).join('')}</div>`;
  const tr = ['swing', 'options', 'intraday'].map(k => { const L = LED(k), c = L.signals.filter(s => s.status === 'CLOSED'), w = c.filter(s => s.r_final > 0).length, tot = c.reduce((a, s) => a + (s.r_final || 0), 0);
    return [SECT[k].title, L.signals.filter(s => s.status === 'ACTIVE').length, c.length, c.length ? Math.round(100 * w / c.length) + '%' : '-', c.length ? sg(tot / c.length, 2) + 'R' : '-', c.length ? sg(tot, 1) + 'R' : '-', (L.dropped || []).length]; });
  h += `<div class="grid g2 tr2" style="margin-bottom:12px"><div class="card"><div class="hd"><h2>Signal track record</h2><span class="help">every triggered signal, taken or not</span></div><div class="bd scroll"><table class="cand" style="min-width:460px"><thead><tr><th>Section</th><th>Open</th><th>Closed</th><th>Win rate</th><th>Avg R</th><th>Total R</th><th>Invalidated</th></tr></thead><tbody>${tr.map(r => `<tr>${r.map((x, i) => `<td class="${i ? 'n' : ''}">${x}</td>`).join('')}</tr>`).join('')}</tbody></table><p class="help" style="margin-top:6px">Closed signals stay listed for 30 days (swing) or 5 days (options and intraday).</p></div></div>`;
  const jt = journalTrades().filter(t => (t.note || '').includes('DS:')), jc = jt.filter(t => t.exit != null && t.entry != null && t.sl != null && t.entry !== t.sl);
  const jr = jc.map(t => (t.exit - t.entry) / Math.abs(t.entry - t.sl) * (t.dir === 'Short' ? -1 : 1)), jw = jr.filter(x => x > 0).length;
  h += `<div class="card"><div class="hd"><h2>Your journal: scanner trades</h2><a href="journal.html">Open journal</a></div><div class="bd">${jt.length ? `<div class="grid g3">${tile('Logged', jt.length, (jt.length - jc.length) + ' still open')}${tile('Win rate', jc.length ? Math.round(100 * jw / jc.length) + '%' : '-', jc.length + ' closed')}${tile('Average R', jr.length ? sg(jr.reduce((a, b) => a + b, 0) / jr.length, 2) + 'R' : '-', 'from entry, stop and exit')}</div>` : '<p class="help">No scanner trades in the journal on this device yet. Use "Log in journal" on any trade page. Open the Journal once on this site and sign in, so your cloud journal syncs here.</p>'}</div></div></div>`;
  if (nw && nw.headlines && nw.headlines.length) h += `<div class="card"><div class="hd"><h2>Top headlines</h2><a href="news.html">All news</a></div><div class="bd news">${nw.headlines.slice(0, 6).map(n => `<a class="it" href="${esc(n.link)}" target="_blank" rel="noopener">${n.impact === 'high' ? '<span class="hi">● </span>' : ''}${esc(n.title)}<small><span>${esc(n.source)}</span></small></a>`).join('')}</div></div>`;
  return h;
}

/* ------------------------------------------------------------ page runner */
const SIGS = ['signals_swing', 'signals_options', 'signals_intraday'];
const PAGES = {
  overview: { need: ['swing', 'options', 'intraday', 'market', 'news', ...SIGS], html: overviewPage }, swing: { need: ['swing', 'options', 'intraday', 'market', 'signals_swing'], html: () => screener('swing'), bind: () => bindScreener('swing') },
  options: { need: ['swing', 'options', 'intraday', 'market', 'signals_options'], html: () => screener('options'), bind: () => bindScreener('options') }, intraday: { need: ['swing', 'options', 'intraday', 'market', 'signals_intraday'], html: () => screener('intraday'), bind: () => bindScreener('intraday') },
  market: { need: ['swing', 'options', 'intraday', 'market'], html: marketPage }, news: { need: ['swing', 'options', 'intraday', 'market', 'news'], html: newsPage, bind: () => document.querySelectorAll('[data-t]').forEach(b => b.onclick = () => { store.set('ds.news', { topic: b.dataset.t }); DS.draw(); }) },
  trade: { need: ['swing', 'options', 'intraday', 'market', 'news', ...SIGS], html: tradePage, bind: bindTrade } };
DS.draw = function () { const p = PAGES[DS.page]; if (DS.page === 'trade') { const R = resolveTrade(); DS.cur = R.it; DS.curSig = R.sig; } $('#page').innerHTML = p.html(); if (p.bind) p.bind(); };
DS.start = async function () {
  DS.page = document.body.dataset.page || 'overview'; const p = PAGES[DS.page]; DS.need = p.need; shell(DS.page); document.title = ({ overview: 'Overview', swing: 'Swing', options: 'Nifty options', intraday: 'Intraday', market: 'Market', news: 'News', trade: 'Trade' }[DS.page]) + ' · DownerStuffScreener';
  $('#page').innerHTML = '<div class="empty">Loading…</div>'; await DS.loadAll(p.need); paintChrome(); DS.draw();
  setInterval(() => { const a = document.activeElement && document.activeElement.tagName; if (!document.hidden && marketOpenNow() && a !== 'INPUT' && a !== 'SELECT') DS.reload(); }, 60000); document.addEventListener('visibilitychange', () => { if (!document.hidden) DS.reload(); });
  window.addEventListener('pageshow', e => { if (e.persisted) DS.reload(); });                       // iPhone: coming back to a page restored from cache
};
DS.start();
})();
