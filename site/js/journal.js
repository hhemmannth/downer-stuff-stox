/* Journal. Same storage keys, trade format and Supabase table as your Trade Insight app, so the same account shows the same trades
   in both, and nothing is lost when you move over. */
'use strict';
(function () {
const JR = App.journal = {};
const TKEYS = ['d', 'tm', 'inst', 'cat', 'setup', 'tf', 'dir', 'grade', 'cap', 'qty', 'entry', 'sl', 'tgt', 'exit', 'chg', 'emo', 'brk', 'xt', 'note', 'ovr', 'exp', 'mae', 'mfe', 'reg', 'evt'];
const REAL_ROWS = [['2026-09-17', '12:30', 'IFCI', 'Swing', 'Pullback from OB', 'Daily', 'Long', 'B', 25000, null, 76.86, 71, null, null, null, null, null, null, null, null, null, null, null, null, null], ['2026-09-17', '12:00', 'Heromoto', 'Swing', 'Pullback from OB', 'Daily', 'Long', 'B', 25000, null, 5340, 5060, null, null, null, null, null, null, null, null, null, null, null, null, null], ['2026-09-17', '14:30', 'NIFTY 23300CE', 'Options', 'Pullback from OB', '15 MINS', 'Long', 'A', 7280, null, 112, 87, null, 112, null, 'Calm', null, null, null, null, null, null, null, null, null]];
const CATS = JR.CATS = ['Swing', 'Positional', 'Options', 'Intraday', 'Commodity'];
const SETUPS0 = ['Pullback from OB', 'Pullback from FVG', 'CHOCH + BOS', 'Liquidity Sweep', 'Trend Continuation (Experimental)', 'Premium Group Trade', 'Breakout Retest', 'News Based', 'Event/Catalyst Play', 'IPO Listing Gain', 'IPO Allotment Hold', 'Other'];
const TFS = JR.TFS = ['1 MIN', '5 MINS', '15 MINS', '1 HOUR', '4 HOUR', 'Daily', 'Weekly'];
const EMOS = JR.EMOS = ['Calm', 'Confident', 'Disciplined', 'FOMO', 'Fearful', 'Greedy', 'Impulsive', 'Revenge', 'Anxious'];
const RISKY = new Set(['FOMO', 'Fearful', 'Greedy', 'Impulsive', 'Revenge', 'Anxious']);
const GRADES = ['A+', 'A', 'B', 'C'], GRANK = { 'A+': 4, A: 3, B: 2, C: 1 };
const BREAKS = JR.BREAKS = ['None', 'FOMO entry', 'No confirmation', 'External signal', 'Moved / widened SL', 'Oversized risk', 'Ignored event risk', 'Chased entry (no retest)', 'Early breakeven', 'Overtraded (3rd+ intraday)', 'Revenge trade', 'Other'];
const REGIMES = ['Trending', 'Range', 'Volatile'], EVENTS = ['No', 'Yes'], XTYPES = ['Target Hit', 'Partial Target', 'Not Hit', 'Breakeven Exit', 'SL Hit'], DIRS = ['Long', 'Short'];
const SET0 = JR.SET0 = { capital: 200000, riskN: .005, riskA: .0075, riskC: .01, openMax: .02, dayCaution: .005, dayStop: .0075, dayLim: .01, weekAlert: .015, weekReview: .02, monthHalf: .03, monthStop: .05, maxIntra: 2, be: .1, expN: 50, minN: 5, wdTol: .1 };
JR.SETKEYS = [['capital', 'Trading capital (₹)', 'n'], ['riskN', 'Normal risk per trade', 'p'], ['riskA', 'A+ risk per trade', 'p'], ['riskC', 'Hard ceiling per trade', 'p'], ['openMax', 'Max total open risk', 'p'],
  ['dayCaution', 'Daily: caution', 'p'], ['dayStop', 'Daily: stop new trades', 'p'], ['dayLim', 'Daily: loss limit', 'p'], ['weekAlert', 'Weekly: reduce size', 'p'], ['weekReview', 'Weekly: review mode', 'p'],
  ['monthHalf', 'Monthly: half size', 'p'], ['monthStop', 'Monthly: stop', 'p'], ['maxIntra', 'Max intraday trades a day', 'i'], ['be', 'Breakeven band (± R)', 'd'], ['minN', 'Trades before a pattern counts', 'i']];
const TDEF = { d: '', tm: '', inst: '', cat: 'Intraday', setup: '', tf: '', dir: 'Long', grade: null, cap: null, qty: null, entry: null, sl: null, tgt: null, exit: null, chg: null, emo: null, brk: null, xt: null, note: '', ovr: null, exp: null, mae: null, mfe: null, reg: null, evt: null };
const NUMK = ['cap', 'qty', 'entry', 'sl', 'tgt', 'exit', 'chg', 'ovr', 'mae', 'mfe'];
const LSK = 'tji_journals_v1', LSL = 'tji_last_v1', LSU = 'tji_ui_v1', LSD = 'tji_deleted_v1';
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
const nn = v => { if (v === '' || v == null) return null; const x = typeof v === 'number' ? v : parseFloat(String(v).replace(/[,₹\s]/g, '')); return isFinite(x) ? x : null; };
const ymd = s => /^\d{4}-\d{2}-\d{2}$/.test(String(s || ''));
const utc = s => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10));
const wdOf = s => (new Date(utc(s)).getUTCDay() + 6) % 7;
const weekStart = s => new Date(utc(s) - wdOf(s) * 864e5).toISOString().slice(0, 10);
function normTrade(t) {
  const o = { ...TDEF, ...t }; NUMK.forEach(k => o[k] = nn(o[k]));
  ['tm', 'inst', 'setup', 'tf', 'note'].forEach(k => o[k] = o[k] == null ? '' : String(o[k]).trim());
  ['grade', 'emo', 'brk', 'xt', 'reg', 'evt', 'exp'].forEach(k => o[k] = (o[k] == null || o[k] === '') ? null : String(o[k]).trim());
  o.dir = o.dir === 'Short' ? 'Short' : 'Long'; o.d = String(o.d || '').slice(0, 10); if (!o.id) o.id = uid(); return o;
}
const decodeRows = (rows, pfx) => rows.map((r, n) => { const o = {}; TKEYS.forEach((k, i) => o[k] = r[i] === undefined ? null : r[i]); if (pfx) o.id = pfx + (n + 1); return normTrade(o); });
const newJournal = (name, o = {}) => ({ id: uid(), name, demo: !!o.demo, asOf: o.asOf || null, updated: Date.now(), set: { ...SET0 }, lists: { setups: [...SETUPS0] }, trades: o.trades || [] });
const fillJ = J => { J.set = { ...SET0, ...(J.set || {}) }; J.lists = { setups: [...SETUPS0], ...(J.lists || {}) }; J.trades = (J.trades || []).map(normTrade); return J; };
function mainJournal() { const j = newJournal('Hemanth’s journal', { trades: decodeRows(REAL_ROWS, 's') }); j.id = 'j_main'; j.updated = 0; return fillJ(j); }

let E = { list: [], cur: null, deleted: [] }; JR.E = E;
JR.J = () => E.list.find(x => x.id === E.cur) || E.list[0];
function load() {
  const saved = store.get(LSK, null); E.deleted = store.get(LSD, []) || [];
  E.list = Array.isArray(saved) && saved.length ? saved.filter(j => j && Array.isArray(j.trades)).map(fillJ) : [mainJournal()];
  E.cur = store.get(LSL, null); if (!E.list.some(x => x.id === E.cur)) E.cur = (E.list.find(j => !j.demo) || E.list[0]).id;
}
let _pt; JR.persist = () => { clearTimeout(_pt); _pt = setTimeout(persistNow, 250); };
function persistNow() { store.set(LSK, E.list); store.set(LSL, E.cur); store.set(LSD, E.deleted); cloudSchedule(); }
JR.touch = () => { const J = JR.J(); J.updated = Date.now(); };
JR.setCurrent = id => { if (E.list.some(x => x.id === id)) { E.cur = id; JR.persist(); App.render(); } };

/* ---------- per-trade working (same maths as Trade Insight) ---------- */
JR.enrich = function (J) {
  J = J || JR.J(); const S = J.set, cap = S.capital || 1;
  const T = J.trades.map((t, i) => Object.assign({}, t, { _i: i })).filter(t => ymd(t.d));
  T.sort((a, b) => (a.d < b.d ? -1 : a.d > b.d ? 1 : 0) || ((a.tm || '') < (b.tm || '') ? -1 : (a.tm || '') > (b.tm || '') ? 1 : 0) || a._i - b._i);
  const dayIntra = {};
  T.forEach(t => {
    const sgn = t.dir === 'Short' ? -1 : 1;
    t.q = t.qty > 0 ? t.qty : (t.cap > 0 && t.entry > 0 ? Math.floor(t.cap / t.entry + 1e-6) : null);
    t.risk = (t.q != null && t.sl != null && t.entry != null) ? Math.abs(t.entry - t.sl) * t.q : null;
    t.riskP = t.risk != null ? t.risk / cap : null;
    t.closed = t.exit != null || t.ovr != null;
    t.gross = (t.q != null && t.exit != null && t.entry != null) ? (t.exit - t.entry) * t.q * sgn : null;
    t.net = !t.closed ? null : (t.ovr != null ? t.ovr : (t.gross != null ? t.gross - (t.chg || 0) : null));
    t.r = (t.net != null && t.risk > 0) ? t.net / t.risk : null;
    t.res = t.net == null ? null : (t.r != null ? (t.r > S.be ? 'Win' : t.r < -S.be ? 'Loss' : 'BE') : (t.net > 0 ? 'Win' : t.net < 0 ? 'Loss' : 'BE'));
    t.mkey = t.d.slice(0, 7); t.wd = wdOf(t.d); t.hr = t.tm ? +t.tm.slice(0, 2) : null; t.wk = weekStart(t.d);
    const sd = (t.entry != null && t.sl != null && t.entry !== t.sl) ? Math.abs(t.entry - t.sl) : null;
    t.prr = (t.tgt != null && sd) ? Math.abs(t.tgt - t.entry) / sd : null;
    t.maer = (t.mae != null && sd) ? Math.max(0, (t.entry - t.mae) * sgn) / sd : null;
    t.mfer = (t.mfe != null && sd) ? Math.max(0, (t.mfe - t.entry) * sgn) / sd : null;
    t.brkd = !!(t.brk && t.brk !== 'None');
    t.lt = t.res !== 'Loss' ? null : ((t.brkd || (t.riskP != null && t.riskP > S.riskC + 1e-5)) ? 'Bad loss' : 'Good loss');
    t.ec = t.emo ? (RISKY.has(t.emo) ? 'Risky' : 'Calm') : null; t.gr = GRANK[t.grade] || 0;
    t.src = /DS:/.test(t.note || '') ? 'Scanner' : 'Own idea';
    if (t.cat === 'Intraday') { dayIntra[t.d] = (dayIntra[t.d] || 0) + 1; t.idx = dayIntra[t.d]; }
    t.open = !t.closed;
  });
  return T;
};
JR.period = (T, mode, from, to) => {
  const td = todayIST(), y = td.slice(0, 4), m = td.slice(0, 7), lm = (() => { const d = new Date(Date.UTC(+y, +td.slice(5, 7) - 2, 1)); return d.toISOString().slice(0, 7); })(), back = n => new Date(Date.now() - n * 864e5).toISOString().slice(0, 10);
  if (mode === 'year') return T.filter(t => t.d.slice(0, 4) === y); if (mode === 'month') return T.filter(t => t.mkey === m); if (mode === 'lastm') return T.filter(t => t.mkey === lm);
  if (mode === 'd30') return T.filter(t => t.d >= back(30)); if (mode === 'd90') return T.filter(t => t.d >= back(90)); if (mode === 'custom' && from && to) return T.filter(t => t.d >= from && t.d <= to); return T;
};
JR.PERIODS = [['all', 'All time'], ['year', 'This year'], ['month', 'This month'], ['lastm', 'Last month'], ['d30', '30 days'], ['d90', '90 days']];
JR.openCount = () => JR.enrich().filter(t => t.open).length;

/* ---------- risk status from your rules (daily / weekly / monthly limits, open risk, intraday count) ---------- */
JR.riskStatus = () => {
  const J = JR.J(), S = J.set, cap = S.capital || 1, T = JR.enrich(J), td = todayIST(), wk = weekStart(td), mo = td.slice(0, 7);
  const sum = a => a.reduce((x, t) => x + (t.net || 0), 0), closed = T.filter(t => t.closed && t.net != null);
  const day = sum(closed.filter(t => t.d === td)) / cap, week = sum(closed.filter(t => t.wk === wk)) / cap, month = sum(closed.filter(t => t.mkey === mo)) / cap;
  const openRisk = T.filter(t => t.open && t.risk).reduce((x, t) => x + t.risk, 0) / cap, intra = T.filter(t => t.d === td && t.cat === 'Intraday').length;
  const fullLoss = closed.filter(t => t.d === td && t.r != null && t.r <= -0.9).length; const msgs = []; let level = 'ok';
  const bump = (l, m) => { msgs.push([l, m]); if (l === 'bad' || (l === 'warn' && level === 'ok')) level = l; };
  if (day <= -S.dayLim) bump('bad', `Day is over: down ${pct(-day)} (limit ${pct(S.dayLim)}). No recovery trade.`); else if (day <= -S.dayStop) bump('bad', `Stop new trades today: down ${pct(-day)}.`); else if (day <= -S.dayCaution) bump('warn', `Caution: down ${pct(-day)} today.`);
  if (week <= -S.weekReview) bump('bad', `Weekly review mode: down ${pct(-week)} this week. Never increase risk to recover.`); else if (week <= -S.weekAlert) bump('warn', `Reduce size: down ${pct(-week)} this week.`);
  if (month <= -S.monthStop) bump('bad', `Monthly stop: down ${pct(-month)}. Review the last 30 to 50 trades.`); else if (month <= -S.monthHalf) bump('warn', `Half size: down ${pct(-month)} this month.`);
  if (openRisk > S.openMax) bump('warn', `Open risk ${pct(openRisk)} is above your ${pct(S.openMax)} cap.`);
  if (intra >= S.maxIntra) bump('warn', `${intra} intraday trades today: that is your maximum.`);
  if (fullLoss >= 2) bump('bad', 'Two full-risk losses today: trading stops for the day.'); else if (fullLoss === 1) bump('warn', 'One full-risk loss today: take a 20 to 30 minute reset before the next idea.');
  return { level, msgs, day, week, month, openRisk, intra, fullLoss, cap, S };
};
JR.sizeFor = (entry, sl, grade) => { const S = JR.J().set, rp = grade === 'A+' ? S.riskA : S.riskN, risk = S.capital * rp, per = Math.abs(entry - sl); return { rp, risk, qty: per > 0 ? Math.floor(risk / per) : 0, ceiling: S.capital * S.riskC, capital: S.capital }; };
JR.findByTag = tag => JR.enrich().find(t => (t.note || '').includes('DS:' + tag));

/* ---------- trade form ---------- */
const opt = (list, v, blank = true) => (blank ? '<option value=""></option>' : '') + list.map(x => `<option${x === v ? ' selected' : ''}>${esc(x)}</option>`).join('');
JR.openForm = function (id, prefill) {
  const J = JR.J(); if (J.demo) { const real = E.list.find(x => !x.demo); if (real) { E.cur = real.id; } }
  const ex = id ? JR.J().trades.find(t => t.id === id) : null, last = JR.J().trades[JR.J().trades.length - 1];
  const t = ex ? { ...ex } : { ...TDEF, d: todayIST(), tm: istNow().toISOString().slice(11, 16), cat: last ? last.cat : 'Swing', ...(prefill || {}) };
  const setups = [...new Set([...(JR.J().lists.setups || SETUPS0), t.setup].filter(Boolean))];
  const f = (k, l, type = 'text', cls = '', extra = '') => `<div class="field ${cls}"><label for="f-${k}">${l}</label><input id="f-${k}" data-k="${k}" type="${type}" ${type === 'number' ? 'step="any" inputmode="decimal"' : ''} value="${t[k] == null ? '' : esc(t[k])}" ${extra}></div>`;
  const s = (k, l, list, cls = '') => `<div class="field ${cls}"><label for="f-${k}">${l}</label><select id="f-${k}" data-k="${k}">${opt(list, t[k])}</select></div>`;
  const bg = document.createElement('div'); bg.className = 'modal-bg';
  bg.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-label="${ex ? 'Edit trade' : 'Add a trade'}"><div class="mh"><h2>${ex ? 'Edit trade' : 'Add a trade'}</h2>${prefill ? '<span class="pill info">from the scanner</span>' : ''}<button class="btn sm ghost" data-x>Close</button></div><div class="mb">
    <div class="fsec">The trade</div><div class="fgrid">${f('d', 'Date', 'date')}${f('tm', 'Time', 'time')}${f('inst', 'Instrument', 'text', 'w2', 'list="instList" autocomplete="off"')}
    ${s('cat', 'Category', CATS)}${s('dir', 'Direction', DIRS)}${s('setup', 'Setup', setups, 'w2')}${s('tf', 'Timeframe', TFS)}${s('grade', 'Grade', GRADES)}${s('reg', 'Market regime', REGIMES)}${s('evt', 'Event risk', EVENTS)}${f('exp', 'Expiry (options)', 'date')}</div>
    <div class="fsec">Size and risk</div><div class="fgrid">${f('entry', 'Entry', 'number')}${f('sl', 'Stop-loss', 'number')}${f('tgt', 'Target', 'number')}${f('qty', 'Quantity', 'number')}${f('cap', 'Capital used (₹)', 'number')}${f('chg', 'Charges (₹)', 'number')}</div>
    <div class="calc" id="fcalc"></div>
    <div class="fsec">Exit and review</div><div class="fgrid">${f('exit', 'Exit price', 'number')}${s('xt', 'Exit type', XTYPES)}${f('mae', 'Worst price (MAE)', 'number')}${f('mfe', 'Best price (MFE)', 'number')}${f('ovr', 'P/L override (₹)', 'number')}${s('emo', 'Emotion', EMOS)}${s('brk', 'Rule break', BREAKS, 'w2')}
    <div class="field w4"><label for="f-note">Notes / lesson</label><textarea id="f-note" data-k="note">${esc(t.note || '')}</textarea></div></div>
    <datalist id="instList">${[...new Set(JR.J().trades.map(x => x.inst).filter(Boolean))].slice(-60).map(x => `<option value="${esc(x)}">`).join('')}</datalist></div>
    <div class="mf">${ex ? '<button class="btn danger" data-del>Delete</button><span style="flex:1"></span>' : ''}<button class="btn" data-x>Cancel</button><button class="btn primary" data-save>${ex ? 'Save changes' : 'Save trade'}</button></div></div>`;
  document.body.appendChild(bg);
  const read = () => { const o = { ...t }; $$('[data-k]', bg).forEach(el => o[el.dataset.k] = el.value); return normTrade(o); };
  const calc = () => { const o = read(), J2 = { ...JR.J(), trades: [o] }, e = JR.enrich(J2)[0] || {}, S = JR.J().set;
    $('#fcalc', bg).innerHTML = `<div><small>Quantity used</small><b>${e.q != null ? fmt0(e.q) : '-'}</b></div><div><small>Risk</small><b class="${e.riskP > S.riskC ? 'bad' : ''}">${e.risk != null ? inr(e.risk) : '-'}</b><small>${e.riskP != null ? pct(e.riskP, 2) + ' of capital' : ''}</small></div>
      <div><small>Planned R:R</small><b>${e.prr != null ? e.prr.toFixed(1) : '-'}</b>${e.prr != null && e.prr < 2 ? '<small class="warn">under 2R</small>' : ''}</div><div><small>Result</small><b class="${cls(e.net)}">${e.closed ? (e.net != null ? inrS(e.net) : '?') : 'Open'}</b><small>${e.r != null ? rr(e.r) : ''}</small></div>`; };
  bg.addEventListener('input', calc); calc();
  const close = () => bg.remove();
  bg.addEventListener('click', e => {
    if (e.target === bg || e.target.closest('[data-x]')) close();
    if (e.target.closest('[data-del]') && confirm('Delete this trade?')) { const J = JR.J(); J.trades = J.trades.filter(x => x.id !== id); JR.touch(); JR.persist(); close(); App.render(); App.toast('Trade deleted'); }
    if (e.target.closest('[data-save]')) {
      const o = read(); if (!o.d || !o.inst) { App.toast('Add at least a date and an instrument'); return; }
      const J = JR.J(); if (ex) J.trades[J.trades.findIndex(x => x.id === id)] = o; else J.trades.push(o);
      if (o.setup && !J.lists.setups.includes(o.setup)) J.lists.setups.push(o.setup);
      JR.touch(); JR.persist(); close(); App.render(); App.toast(ex ? 'Trade updated' : 'Trade saved to your journal');
    }
  });
  setTimeout(() => $(ex && !ex.exit ? '#f-exit' : '#f-entry', bg)?.focus(), 30);
};

/* Scanner -> journal: build a pre-filled trade from a setup or a tracked signal. */
JR.fromScanner = function (it, sig) {
  const ot = it.options_trade, m = App.data.market, sec = it.section, key = sig ? sig.id : `${sec}|${it.symbol}|${it.direction}|${it.bos_date}`;
  const reg = m && m.daily ? ({ trending_up: 'Trending', trending_down: 'Trending', range: 'Range', volatile: 'Volatile' }[m.daily.regime] || null) : null;
  const sz = JR.sizeFor(ot ? ot.premium : it.entry, ot ? ot.premium_sl : it.sl, it.grade); let qty = sz.qty;
  if (ot) { const lot = ot.lot_size || 65, per = Math.max(ot.premium - ot.premium_sl, .01); qty = Math.max(1, Math.floor(sz.risk / (per * lot))) * lot; }
  return { inst: ot ? ot.instrument : it.symbol, cat: { swing: 'Swing', options: 'Options', intraday: 'Intraday' }[sec], setup: isNum(it.ob_low) ? 'Pullback from OB' : 'Pullback from FVG',
    tf: sec === 'swing' ? 'Daily' : '5 MINS', dir: it.direction === 'long' ? 'Long' : 'Short', grade: GRADES.includes(it.grade) ? it.grade : null, qty,
    entry: ot ? +ot.premium.toFixed(2) : it.entry, sl: ot ? +ot.premium_sl.toFixed(2) : it.sl, tgt: ot ? +ot.premium_targets[1].toFixed(2) : it.t2, reg, evt: it.results && it.results.days != null && it.results.days <= 14 ? 'Yes' : 'No', exp: ot ? ot.expiry : null,
    note: `DS:${key} | ${it.score}/10 ${it.grade} | ${(it.ticks || []).join(', ')}` + (ot ? ` | model premium, index entry ${it.entry} SL ${it.sl}: edit to your fill` : '') };
};

/* ---------- cloud sync (Supabase, same project and table as Trade Insight) ---------- */
const SUPABASE_URL = 'https://gdecjijdudotkfikfona.supabase.co', SUPABASE_KEY = 'sb_publishable_xBuw3PmoTgq-gNz3_YY7Kg_1p_adtBI';
let sb = null; const Cloud = JR.Cloud = { userId: null, email: null, mode: 'pending', busy: false, timer: null, off: false, last: 0, err: '' };
const latestLocal = () => E.list.filter(j => !j.demo).reduce((m, j) => Math.max(m, Number(j.updated) || 0), 0);
const payload = () => ({ v: 1, updated_at: Date.now(), journals: E.list.filter(j => !j.demo), cur: (JR.J() && !JR.J().demo ? JR.J().id : (E.list.find(j => !j.demo) || {}).id) || null, deleted: E.deleted || [], ui: { period: (store.get(LSU, {}) || {}).period || { mode: 'all' }, theme: (store.get(LSU, {}) || {}).theme || 'auto' } });
async function push() {
  if (!sb || !Cloud.userId || Cloud.off || Cloud.busy) return; Cloud.busy = true;
  try { const p = payload(); const { error } = await sb.from('journal_state').upsert({ user_id: Cloud.userId, payload: p, updated_at: new Date(p.updated_at).toISOString() }, { onConflict: 'user_id' }); if (error) throw error; Cloud.mode = 'cloud'; Cloud.last = Date.now(); }
  catch (e) { fail(e); } finally { Cloud.busy = false; JR.paintSync(); }
}
function cloudSchedule() { if (!sb || !Cloud.userId || Cloud.off) return; clearTimeout(Cloud.timer); Cloud.timer = setTimeout(push, 900); }
function fail(e) { Cloud.off = true; Cloud.mode = 'error'; Cloud.err = (e && (e.message || e.code)) || 'unavailable'; JR.paintSync(); App.toast('Cloud sync paused: your journal is still saved on this device'); }
async function pull(initial) {
  if (!sb || !Cloud.userId || Cloud.off) return;
  const { data, error } = await sb.from('journal_state').select('payload,updated_at').eq('user_id', Cloud.userId).maybeSingle(); if (error) throw error;
  if (!data || !data.payload) { await push(); return; }
  const p = data.payload, cu = Number(p.updated_at || new Date(data.updated_at || 0).getTime()) || 0, lu = latestLocal();
  if (cu > lu || (initial && lu === 0)) {
    const journals = Array.isArray(p.journals) ? p.journals.map(fillJ) : []; E.list = [...journals, ...E.list.filter(j => j.demo)]; if (!E.list.length) E.list = [mainJournal()];
    E.deleted = Array.isArray(p.deleted) ? p.deleted : []; E.cur = E.list.some(j => j.id === p.cur) ? p.cur : (E.list.find(j => !j.demo) || E.list[0]).id;
    store.set(LSK, E.list); store.set(LSL, E.cur); store.set(LSD, E.deleted); App.render(); if (!initial) App.toast('Journal updated from your cloud');
  } else if (lu > cu) await push();
  Cloud.mode = 'cloud'; Cloud.last = Date.now(); JR.paintSync();
}
JR.signIn = async (email, password) => {
  if (!sb) throw new Error('Cloud library did not load (check your connection).');
  const { data, error } = await sb.auth.signInWithPassword({ email, password }); if (error) throw error;
  Cloud.userId = data.user.id; Cloud.email = data.user.email; Cloud.off = false; await pull(true); Cloud.mode = 'cloud'; JR.paintSync(); App.render();
};
JR.signOut = async () => { if (sb) await sb.auth.signOut(); Cloud.userId = null; Cloud.email = null; Cloud.mode = 'signin'; JR.paintSync(); App.render(); };
JR.syncNow = async () => { Cloud.off = false; try { await pull(false); App.toast('Synced'); } catch (e) { fail(e); } };
async function cloudInit() {
  if (!window.supabase) { Cloud.mode = 'local'; JR.paintSync(); return; }
  sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } });
  try { const { data } = await sb.auth.getSession(); const u = data && data.session && data.session.user;
    if (u) { Cloud.userId = u.id; Cloud.email = u.email; await pull(true); } else Cloud.mode = 'signin'; } catch (e) { fail(e); }
  JR.paintSync();
  document.addEventListener('visibilitychange', () => { if (!document.hidden && Cloud.userId && !Cloud.off && Date.now() - Cloud.last > 60000) pull(false).catch(fail); });
}
JR.paintSync = () => { const p = $('#syncp'); if (!p) return; const m = Cloud.mode;
  p.className = 'pill ' + (m === 'cloud' ? 'ok' : m === 'error' ? 'bad' : m === 'signin' ? 'warn' : '');
  p.innerHTML = `<i></i>${m === 'cloud' ? 'Synced' : m === 'signin' ? 'Sign in' : m === 'error' ? 'Sync paused' : m === 'local' ? 'This device' : '…'}`;
  p.title = m === 'cloud' ? `Journal saved here and in your cloud (${Cloud.email || ''})` : m === 'signin' ? 'Sign in to sync your journal' : 'Saved in this browser'; };
JR.init = () => { load(); cloudInit(); };

/* ---------- import / export ---------- */
JR.exportJSON = () => { const J = JR.J(); dl((J.name || 'journal').replace(/[^\w]+/g, '-') + '-backup.json', JSON.stringify({ format: 'trade-insight', version: 1, exported: new Date().toISOString(), journal: { name: J.name, set: J.set, lists: J.lists, trades: J.trades } }, null, 1), 'application/json'); };
JR.exportCSV = () => { const T = JR.enrich(); const head = ['Date', 'Time', 'Instrument', 'Category', 'Setup', 'Timeframe', 'Direction', 'Grade', 'Qty', 'Entry', 'SL', 'Target', 'Exit', 'Charges', 'Net P/L', 'R', 'Result', 'Emotion', 'Rule break', 'Exit type', 'Notes'];
  const q = v => v == null ? '' : /[",\n]/.test(String(v)) ? '"' + String(v).replace(/"/g, '""') + '"' : String(v);
  dl('journal.csv', [head.join(','), ...T.map(t => [t.d, t.tm, t.inst, t.cat, t.setup, t.tf, t.dir, t.grade, t.q, t.entry, t.sl, t.tgt, t.exit, t.chg, t.net != null ? t.net.toFixed(2) : '', t.r != null ? t.r.toFixed(2) : '', t.res, t.emo, t.brk, t.xt, t.note].map(q).join(','))].join('\n'), 'text/csv'); };
function dl(name, text, type) { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500); }
JR.importFile = file => new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => { try {
  const o = JSON.parse(r.result), src = o.journal || o, trades = Array.isArray(src) ? src : src.trades; if (!Array.isArray(trades)) throw new Error('No trades in this file');
  const j = newJournal(src.name ? src.name + ' (imported)' : 'Imported journal', { trades: trades.map(normTrade) }); if (src.set) j.set = { ...SET0, ...src.set }; if (src.lists) j.lists = { setups: [...SETUPS0], ...src.lists };
  E.list.push(j); E.cur = j.id; JR.persist(); ok(j); } catch (e) { bad(e); } }; r.onerror = bad; r.readAsText(file); });
JR.newJournal = name => { const j = newJournal(name); E.list.push(j); E.cur = j.id; JR.persist(); };
JR.deleteJournal = id => { if (E.list.filter(j => !j.demo).length <= 1 && !E.list.find(j => j.id === id).demo) { App.toast('Keep at least one journal'); return; } E.deleted.push(id); E.list = E.list.filter(j => j.id !== id); E.cur = E.list[0].id; JR.persist(); App.render(); };

/* ---------- journal page ---------- */
const U = () => App.ui.j || (App.ui.j = { period: 'all', cat: 'all', res: 'all', q: '', n: 60 });
App.pages.journal = () => {
  const u = U(), J = JR.J(), all = JR.enrich(J), P = JR.period(all, u.period), S = J.set;
  let T = P.filter(t => (u.cat === 'all' || t.cat === u.cat) && (u.res === 'all' || (u.res === 'open' ? t.open : u.res === 'brk' ? t.brkd : t.res === u.res)) && (!u.q || (t.inst + ' ' + t.setup + ' ' + t.note).toLowerCase().includes(u.q.toLowerCase())));
  const C = T.filter(t => t.closed && t.net != null), net = C.reduce((a, t) => a + t.net, 0), wins = C.filter(t => t.res === 'Win'), losses = C.filter(t => t.res === 'Loss'), gw = wins.reduce((a, t) => a + t.net, 0), gl = -losses.reduce((a, t) => a + t.net, 0), Rs = C.filter(t => t.r != null);
  const open = all.filter(t => t.open);
  const jsel = `<select class="inp" style="width:auto" id="jSel" aria-label="Journal">${E.list.map(j => `<option value="${j.id}"${j.id === J.id ? ' selected' : ''}>${esc(j.name)}${j.demo ? ' (sample)' : ''}</option>`).join('')}</select>`;
  let h = `<div class="ph"><div><h1>Journal</h1><p>Every trade with its plan, result in rupees and in R, and the review. Scanner trades are tagged so you can compare them with your own ideas.</p></div><span class="sp"></span>${jsel}
    <button class="btn" id="jCsv">${ic('download')} CSV</button><button class="btn" id="jJson">${ic('download')} Backup</button><label class="btn">${ic('upload')} Import<input type="file" accept=".json,application/json" id="jImp" hidden></label><button class="btn primary" id="jAdd">${ic('plus')} Add trade</button></div>`;
  h += `<div class="kpis" style="margin-bottom:14px">${App.ui.kpi('Trades', T.length, `${C.length} closed · ${T.length - C.length} open`)}${App.ui.kpi('Net P&L', inrS(net), pct(net / (S.capital || 1), 2) + ' of capital', cls(net))}
    ${App.ui.kpi('Win rate', C.length ? Math.round(100 * wins.length / C.length) + '%' : '-', `${wins.length} W · ${losses.length} L · ${C.length - wins.length - losses.length} BE`)}${App.ui.kpi('Average R', Rs.length ? rr(Rs.reduce((a, t) => a + t.r, 0) / Rs.length) : '-', 'per closed trade', cls(Rs.length ? Rs.reduce((a, t) => a + t.r, 0) : 0))}
    ${App.ui.kpi('Profit factor', gl > 0 ? (gw / gl).toFixed(2) : gw > 0 ? '∞' : '-', 'gross win / gross loss')}${App.ui.kpi('Rule breaks', T.filter(t => t.brkd).length, `${C.length ? Math.round(100 * (1 - C.filter(t => t.brkd).length / C.length)) : 100}% compliant`, T.some(t => t.brkd) ? 'warn' : '')}</div>`;
  if (open.length) h += `<div class="card" style="margin-bottom:14px"><div class="hd"><h2>Open positions</h2><span class="cap">${open.length} open · total risk ${inr(open.reduce((a, t) => a + (t.risk || 0), 0))}</span></div><div class="bd tbl-wrap"><table class="tbl"><thead><tr><th>Since</th><th>Instrument</th><th>Setup</th><th class="n">Entry</th><th class="n">Stop</th><th class="n">Qty</th><th class="n">Risk</th><th class="n">Now</th><th></th></tr></thead><tbody>${open.slice().reverse().map(t => { const live = livePrice(t);
    return `<tr class="click open" data-id="${t.id}"><td>${esc(t.d.slice(5))}</td><td><b>${esc(t.inst)}</b> <span class="tag ${t.dir === 'Short' ? 'short' : 'long'}">${t.dir === 'Short' ? 'SHORT' : 'LONG'}</span>${t.src === 'Scanner' ? ' <span class="pill info" style="padding:0 7px">scanner</span>' : ''}</td><td>${esc(t.setup || '-')}</td><td class="n">${fmt(t.entry)}</td><td class="n">${fmt(t.sl)}</td><td class="n">${t.q != null ? fmt0(t.q) : '-'}</td><td class="n">${inr(t.risk)}</td><td class="n ${cls(live.r)}">${live.txt}</td><td class="n"><button class="btn sm" data-close="${t.id}">Close</button></td></tr>`; }).join('')}</tbody></table></div></div>`;
  h += `<div class="card"><div class="hd">${App.ui.seg('jper', JR.PERIODS, u.period)}<span class="sp"></span><input class="inp" style="width:200px" id="jQ" placeholder="Search instrument, setup, notes" value="${esc(u.q)}" aria-label="Search"></div>
    <div class="hd" style="padding-top:10px"><div class="chips">${[['all', 'All'], ...CATS.map(c => [c, c])].map(([v, t]) => `<button class="chip" data-jcat="${v}" aria-pressed="${u.cat === v}">${t}</button>`).join('')}</div><span class="sp"></span>${App.ui.seg('jres', [['all', 'All'], ['Win', 'Wins'], ['Loss', 'Losses'], ['open', 'Open'], ['brk', 'Rule breaks']], u.res)}</div>
    <div class="bd tbl-wrap">${T.length ? `<table class="tbl"><thead><tr><th>Date</th><th>Instrument</th><th>Cat</th><th>Setup</th><th>Grade</th><th class="n">Entry</th><th class="n">SL</th><th class="n">Exit</th><th class="n">Qty</th><th class="n">Net P&L</th><th class="n">R</th><th>Result</th><th>Notes</th></tr></thead><tbody>
    ${T.slice().reverse().slice(0, u.n).map(t => `<tr class="click${t.open ? ' open' : ''}" data-id="${t.id}"><td class="n">${esc(t.d.slice(2))}</td><td><b>${esc(t.inst)}</b> <span class="tag ${t.dir === 'Short' ? 'short' : 'long'}">${t.dir === 'Short' ? 'S' : 'L'}</span>${t.src === 'Scanner' ? ' <span class="pill info" style="padding:0 6px;font-size:11px">DS</span>' : ''}</td><td>${esc(t.cat || '')}</td><td>${esc(t.setup || '-')}</td><td>${t.grade ? App.ui.grade(t.grade) : '-'}</td>
      <td class="n">${fmt(t.entry)}</td><td class="n">${fmt(t.sl)}</td><td class="n">${fmt(t.exit)}</td><td class="n">${t.q != null ? fmt0(t.q) : '-'}</td><td class="n ${cls(t.net)}">${t.net != null ? inrS(t.net) : t.open ? '<span class="muted">open</span>' : '?'}</td><td class="n ${cls(t.r)}">${t.r != null ? rr(t.r) : '-'}</td>
      <td>${t.res ? `<span class="pill ${t.res === 'Win' ? 'ok' : t.res === 'Loss' ? (t.lt === 'Bad loss' ? 'bad' : 'warn') : ''}">${t.res === 'Loss' ? t.lt : t.res}</span>` : ''}${t.brkd ? ` <span class="pill bad" title="${esc(t.brk)}">rule</span>` : ''}</td><td class="muted" style="max-width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc((t.note || '').replace(/DS:\S+\s*\|?\s*/, ''))}</td></tr>`).join('')}</tbody></table>
    ${T.length > u.n ? `<div style="text-align:center;padding:10px"><button class="btn" id="jMore">Show more (${T.length - u.n})</button></div>` : ''}` : App.ui.empty('No trades here yet', 'Add one, or use "Log trade" on any scanner setup.')}</div></div>`;
  return h;
};
function livePrice(t) {
  const sym = (t.inst || '').toUpperCase(); let px = null;
  ['swing', 'intraday'].forEach(k => { const d = App.data[k]; const s = d && d.setups.find(x => x.symbol === sym); if (s && isNum(s.price)) px = s.price; });
  ['swing', 'intraday'].forEach(k => App.LED(k).signals.forEach(x => { if (x.symbol === sym && isNum(x.last)) px = x.last; }));
  if (px == null || t.entry == null || t.sl == null || t.entry === t.sl) return { txt: '-', r: null };
  const r = (px - t.entry) / Math.abs(t.entry - t.sl) * (t.dir === 'Short' ? -1 : 1); return { txt: `${fmt(px)} <small>${rr(r, 1)}</small>`, r };
}
App.binds.journal = () => {
  const u = U(), rr_ = () => App.render();
  $('#jAdd').onclick = () => JR.openForm(null); $('#jCsv').onclick = JR.exportCSV; $('#jJson').onclick = JR.exportJSON;
  $('#jSel').onchange = e => JR.setCurrent(e.target.value);
  $('#jImp').onchange = e => { const f = e.target.files[0]; if (f) JR.importFile(f).then(j => { App.toast(`Imported ${j.trades.length} trades`); App.render(); }).catch(er => App.toast('Import failed: ' + er.message)); };
  $$('[data-seg="jper"]').forEach(b => b.onclick = () => { u.period = b.dataset.v; rr_(); });
  $$('[data-seg="jres"]').forEach(b => b.onclick = () => { u.res = b.dataset.v; rr_(); });
  $$('[data-jcat]').forEach(b => b.onclick = () => { u.cat = b.dataset.jcat; rr_(); });
  let tq; $('#jQ').oninput = e => { clearTimeout(tq); tq = setTimeout(() => { u.q = e.target.value; rr_(); setTimeout(() => { const q = $('#jQ'); if (q) { q.focus(); q.setSelectionRange(q.value.length, q.value.length); } }, 0); }, 250); };
  $$('tr[data-id]').forEach(tr => tr.onclick = e => { if (e.target.closest('[data-close]')) return; JR.openForm(tr.dataset.id); });
  $$('[data-close]').forEach(b => b.onclick = () => JR.openForm(b.dataset.close));
  const m = $('#jMore'); if (m) m.onclick = () => { u.n += 100; rr_(); };
};
})();
