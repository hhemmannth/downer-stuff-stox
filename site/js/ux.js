/* DownerStuff look-and-feel layer (25 Nov 2026). Loaded after every page module, it adds the things that cut across pages:
   appearance preferences, private mode, calm/reduced motion, the refresh progress bar, number flash, collapsible cards, scroll-fade tables,
   pull-to-refresh, the offline banner, the favicon dot, global search, the first-run tour and "What's new".
   Nothing here touches the strategy, the scanner logic or the 3D model look. */
(() => {
'use strict';
const UX_KEY = 'ds_ux_v1';
const DEF = { preset: 'midnight', accent: 'mono', cb: false, calm: false, density: 'comfortable', text: 'm', priv: false, softRed: true, dimOff: true, collapse: {} };
const U = App.ux = { get: () => Object.assign({}, DEF, store.get(UX_KEY, {}) || {}) };
U.set = (k, v) => { const p = U.get(); p[k] = v; store.set(UX_KEY, p); U.apply(); };
U.VERSION = 35;

/* ---------- appearance (items 2, 26, 28, 51-56, 60, 79, 246) ---------- */
U.lowPower = () => { const p = U.get(); return p.calm || (matchMedia('(pointer:coarse)').matches && (navigator.connection && navigator.connection.saveData)); };
U.apply = () => {
  const p = U.get(), r = document.documentElement, set = (k, v) => v ? r.setAttribute(k, v === true ? '' : v) : r.removeAttribute(k);
  set('data-preset', p.preset !== 'midnight' && p.preset); set('data-accent', p.accent !== 'mono' && p.accent); set('data-cb', p.cb);
  set('data-calm', p.calm); set('data-density', p.density === 'compact' && 'compact'); set('data-text', p.text !== 'm' && p.text);
  set('data-private', p.priv); set('data-softred', p.softRed); set('data-offhours', p.dimOff && !App.marketOpen());
  set('data-coarse', matchMedia('(pointer:coarse)').matches); set('data-lowpower', U.lowPower());
  App.priv = !!p.priv; App._calmForever = !!p.calm;
  const m = $('meta[name="theme-color"]'); if (m) m.content = App.theme() === 'dark' ? '#020202' : '#F3F3F1';
};
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches || U.get().calm;
U.reduced = reduced;

/* ---------- haptics with every toast (item 29) ---------- */
const toast0 = App.toast; App.toast = (msg, ms) => { try { if (navigator.vibrate && !reduced()) navigator.vibrate(8); } catch (e) { } return toast0(msg, ms); };

/* ---------- top progress bar while data refreshes (item 195) ---------- */
const bar = () => { let b = $('#dsProg'); if (!b) { b = document.createElement('div'); b.id = 'dsProg'; b.setAttribute('aria-hidden', 'true'); document.body.appendChild(b); } return b; };
U.busy = on => { const b = bar(); b.classList.toggle('on', !!on); if (!on) { b.classList.add('done'); setTimeout(() => b.classList.remove('done'), 400); } };
const reload0 = App.reload; App.reload = async (...a) => { U.busy(true); try { return await reload0(...a); } finally { U.busy(false); } };

/* ---------- number flash (item 77) and smooth card reorder (item 193) ---------- */
let snap = { page: '', nums: {}, pos: {} };
const numKey = (el, i) => (el.closest('[data-k],[href]') ? (el.closest('[data-k]') || el.closest('[href]')).getAttribute('data-k') || el.closest('[href]').getAttribute('href') : '') + '|' + i;
function takeSnap() {
  const page = location.hash, nums = {}, pos = {};
  $$('.kpi .v, .sc-lv b, [data-live]').forEach((el, i) => { nums[numKey(el, i)] = el.textContent; });
  if (!reduced()) $$('.cards > a[href], .cards > [data-k]').forEach(el => { const k = el.getAttribute('data-k') || el.getAttribute('href'); pos[k] = el.getBoundingClientRect().top + scrollY; });
  snap = { page, nums, pos };
}
function afterSnap() {
  if (snap.page !== location.hash) return;
  $$('.kpi .v, .sc-lv b, [data-live]').forEach((el, i) => { const o = snap.nums[numKey(el, i)]; if (o != null && o !== el.textContent && !reduced()) { el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash'); } });
  if (!reduced()) $$('.cards > a[href], .cards > [data-k]').forEach(el => {
    const k = el.getAttribute('data-k') || el.getAttribute('href'), y0 = snap.pos[k]; if (y0 == null) return;
    const dy = y0 - (el.getBoundingClientRect().top + scrollY); if (Math.abs(dy) < 4) return;
    try { el.animate([{ transform: `translateY(${dy}px)` }, { transform: 'none' }], { duration: 220, easing: 'cubic-bezier(.2,.7,.2,1)' }); } catch (e) { }
  });
}

/* ---------- collapsible cards that remember their state (item 68) ---------- */
function collapsibles(page) {
  const st = U.get().collapse || {};
  $$('#page .card > .hd').forEach(hd => {
    const h2 = hd.querySelector('h2'); if (!h2 || hd.querySelector('.cl-b') || hd.closest('.no-collapse')) return;
    const k = page + ':' + h2.textContent.trim().slice(0, 40), card = hd.parentElement;
    const b = document.createElement('button'); b.type = 'button'; b.className = 'cl-b'; b.setAttribute('aria-label', 'Show or hide ' + h2.textContent.trim());
    const paint = () => { const c = !!(U.get().collapse || {})[k]; card.classList.toggle('collapsed', c); b.setAttribute('aria-expanded', String(!c)); };
    b.onclick = e => { e.stopPropagation(); const p = U.get(); p.collapse = p.collapse || {}; if (p.collapse[k]) delete p.collapse[k]; else p.collapse[k] = 1; store.set(UX_KEY, p); paint(); };
    hd.appendChild(b); if (st[k]) paint();
  });
}
/* ---------- wide tables show a soft fade where they continue (item 72) ---------- */
function tableFades() {
  $$('#page .tbl-wrap').forEach(w => { const f = () => { const more = w.scrollWidth - w.clientWidth - w.scrollLeft > 4; w.classList.toggle('fade-r', more); w.classList.toggle('fade-l', w.scrollLeft > 4); }; f(); w.onscroll = f; });
}
/* ---------- long names: shortened, tap to expand (item 63) ---------- */
function longNames() { $$('#page .sc-h .nm b, #page .tbl td b').forEach(b => { if (b.scrollWidth > b.clientWidth + 2 && !b.title) { b.title = b.textContent; b.classList.add('trunc'); } }); }
/* ---------- icon-only buttons always have a label (item 86) ---------- */
function iconLabels() { $$('button.icon:not([aria-label]), a.icon:not([aria-label])').forEach(b => b.setAttribute('aria-label', b.title || 'Button')); }

/* ---------- scroll position kept when you go back (item 299) ---------- */
const scrolls = {}; let linkNav = false, lastHash = location.hash;
document.addEventListener('click', e => { const a = e.target.closest && e.target.closest('a[href^="#/"]'); if (a) linkNav = true; }, true);
window.addEventListener('hashchange', () => { scrolls[lastHash] = U._lastY || 0; lastHash = location.hash; });
addEventListener('scroll', () => { U._lastY = scrollY; }, { passive: true });

/* ---------- render hook ---------- */
const render0 = App.render;
App.render = () => {
  takeSnap(); U.apply();
  render0();
  if (!U._booted && $('header.top')) { U._booted = true; U.boot(); }
  const page = App.route().page;
  try { collapsibles(page); tableFades(); longNames(); iconLabels(); backArrow(page); afterSnap(); favDot(); } catch (e) { console.error(e); }
  if (!linkNav && scrolls[location.hash] != null && App._lastPageHash !== location.hash) requestAnimationFrame(() => scrollTo(0, scrolls[location.hash]));
  linkNav = false; App._lastPageHash = location.hash;
};

/* ---------- back arrow on inner pages (item 299) ---------- */
const INNER = { trade: 1, design: 1, stock: 1, yearly: 1, glossary: 1, privacy: 1, review: 0 };
function backArrow(page) {
  const t = $('#ttl'); if (!t) return; let b = $('#backB');
  if (INNER[page]) { if (!b) { b = document.createElement('button'); b.id = 'backB'; b.type = 'button'; b.className = 'btn icon ghost'; b.setAttribute('aria-label', 'Back'); b.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'; b.onclick = () => history.length > 1 ? history.back() : App.go('dashboard'); t.parentElement.insertBefore(b, t); } }
  else if (b) b.remove();
}

/* ---------- favicon dot and title mark when an A+ setup is live (item 96) ---------- */
let favState = null;
function favDot() {
  const live = ['options', 'intraday'].some(k => ((App.data[k] || {}).setups || []).some(s => s.grade === 'A+' && /TRIGGER|ENTRY/i.test(s.status || ''))) ||
    (((App.data.swing || {}).setups) || []).some(s => s.grade === 'A+' && s.stage >= 5 && !(s.holds || []).length);
  if (live === favState) return; favState = live;
  const base = document.title.replace(/^● /, ''); document.title = (live ? '● ' : '') + base;
  const link = $('link[rel="icon"]'); if (!link) return;
  if (!live) { link.href = 'icon-192.png'; return; }
  const img = new Image(); img.onload = () => { try { const c = document.createElement('canvas'); c.width = c.height = 64; const x = c.getContext('2d'); x.drawImage(img, 0, 0, 64, 64); x.fillStyle = '#5BC28A'; x.strokeStyle = '#000'; x.lineWidth = 4; x.beginPath(); x.arc(50, 14, 11, 0, 7); x.fill(); x.stroke(); link.href = c.toDataURL('image/png'); } catch (e) { } }; img.src = 'icon-192.png';
}

/* ---------- pull to refresh on phones (item 30) ---------- */
(function pull() {
  let y0 = null, d = 0; const ind = () => { let i = $('#ptr'); if (!i) { i = document.createElement('div'); i.id = 'ptr'; i.innerHTML = '<span></span>'; document.body.appendChild(i); } return i; };
  addEventListener('touchstart', e => { if (scrollY <= 0 && !document.querySelector('.modal-bg') && e.touches.length === 1) { y0 = e.touches[0].clientY; d = 0; } else y0 = null; }, { passive: true });
  addEventListener('touchmove', e => { if (y0 == null) return; d = Math.max(0, Math.min(110, e.touches[0].clientY - y0)); const i = ind(); i.style.transform = `translate(-50%,${d - 50}px)`; i.classList.toggle('ready', d > 72); i.querySelector('span').textContent = d > 72 ? 'Release to refresh' : 'Pull to refresh'; }, { passive: true });
  addEventListener('touchend', () => { if (y0 == null) return; const i = ind(); if (d > 72) { i.querySelector('span').textContent = 'Refreshing…'; App.reload(true).finally(() => { i.style.transform = ''; i.classList.remove('ready'); App.toast('Updated ' + hmIST(new Date())); }); } else i.style.transform = ''; y0 = null; d = 0; });
})();

/* ---------- offline banner with the last good data (item 48) ---------- */
function offline() {
  let b = $('#offB'); const off = !navigator.onLine;
  if (off && !b) { b = document.createElement('div'); b.id = 'offB'; b.setAttribute('role', 'status'); document.body.appendChild(b); }
  if (b) { b.hidden = !off; if (off) { const at = (App.data.swing || App.data.options || {}).generated_at; b.textContent = 'Offline: showing the last data saved on this device' + (at ? ' (' + hmIST(at) + ', ' + dateIST(at) + ')' : '') + '. Journal changes are kept and sync when you are back online.'; } }
}
addEventListener('online', () => { offline(); App.toast('Back online'); App.reload(); }); addEventListener('offline', offline);

/* ---------- global search: symbols, trades and pages (item 298) ---------- */
const PAGES = [['dashboard', 'Dashboard'], ['swing', 'Swing scanner'], ['options', 'Nifty options'], ['intraday', 'Intraday'], ['gold', 'XAUUSD Gold'], ['journal', 'Journal trades'], ['analytics', 'Analytics'], ['review', 'Weekly review'], ['backtest', 'Backtest lab'], ['market', 'Market'], ['news', 'News & events'], ['playbook', 'Playbook & rules'], ['health', 'System health'], ['settings', 'Settings'], ['design', 'Design check']];
U.search = q => {
  q = String(q || '').trim().toLowerCase(); if (!q) return [];
  const out = [], seen = new Set(), add = (k, r) => { if (!seen.has(k)) { seen.add(k); out.push(r); } };
  PAGES.forEach(([k, t]) => { if (t.toLowerCase().includes(q)) add('p' + k, { kind: 'Page', t, href: '#/' + k }); });
  ['swing', 'options', 'intraday'].forEach(sec => ((App.data[sec] || {}).setups || []).forEach(s => { if (String(s.symbol).toLowerCase().includes(q)) add(sec + s.symbol + s.direction, { kind: sec === 'swing' ? 'Swing setup' : sec === 'options' ? 'Options setup' : 'Intraday setup', t: s.symbol + (sec !== 'swing' ? ' ' + (s.label || s.direction) : ''), s: (s.status || '') + (s.grade ? ' · ' + s.grade : ''), href: `#/trade?s=${sec}&id=${encodeURIComponent(s.symbol + '|' + s.direction)}` }); }));
  ['swing', 'options', 'intraday'].forEach(sec => (App.LED(sec).dropped || []).forEach(w => { if (String(w.symbol).toLowerCase().includes(q)) add(sec + w.symbol + w.direction, { kind: 'Past setup', t: w.symbol, s: (w.reason || '').slice(0, 70), href: `#/trade?s=${sec}&id=${encodeURIComponent(w.symbol + '|' + w.direction)}` }); }));
  if (App.journal) App.journal.enrich().filter(t => String(t.inst || '').toLowerCase().includes(q)).slice(0, 12).forEach(t => add('j' + t.id, { kind: t.open ? 'Open trade' : 'Journal trade', t: t.inst, s: t.d + (t.cat ? ' · ' + t.cat : ''), jid: t.id }));
  const sym = q.toUpperCase().replace(/[^A-Z0-9&-]/g, ''); if (sym.length >= 2 && !out.some(r => r.t === sym)) add('stock' + sym, { kind: 'Stock page', t: sym, s: 'everything for this symbol', href: '#/stock?sym=' + encodeURIComponent(sym) });
  return out.slice(0, 30);
};
U.openSearch = () => {
  if ($('#gsBg')) return; const bg = document.createElement('div'); bg.className = 'modal-bg'; bg.id = 'gsBg';
  bg.innerHTML = `<div class="modal gs-modal" role="dialog" aria-label="Search"><div class="mh"><input id="gsQ" type="search" placeholder="Symbol, trade or page" autocomplete="off" aria-label="Search"><button class="btn icon ghost" id="gsX" type="button" aria-label="Close"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/></svg></button></div><div class="mb"><ul class="gs-list" id="gsL"><li class="muted">Type a symbol like GABRIEL, a trade or a page name.</li></ul></div></div>`;
  document.body.appendChild(bg); const close = () => bg.remove(); bg.onclick = e => { if (e.target === bg) close(); }; $('#gsX').onclick = close;
  const q = $('#gsQ'), L = $('#gsL'); let sel = 0, rows = [];
  const draw = () => { rows = U.search(q.value); L.innerHTML = rows.length ? rows.map((r, i) => `<li><a href="${r.href || '#'}" data-i="${i}" class="${i === sel ? 'on' : ''}"><small>${esc(r.kind)}</small><b>${esc(r.t)}</b>${r.s ? `<span class="muted">${esc(r.s)}</span>` : ''}</a></li>`).join('') : `<li class="muted">${q.value ? 'Nothing found.' : 'Type a symbol like GABRIEL, a trade or a page name.'}</li>`;
    $$('a[data-i]', L).forEach(a => a.onclick = e => { const r = rows[+a.dataset.i]; if (r.jid) { e.preventDefault(); close(); App.journal.openForm(r.jid); } else close(); }); };
  q.oninput = () => { sel = 0; draw(); }; draw();
  q.onkeydown = e => { if (e.key === 'Escape') close(); if (e.key === 'ArrowDown') { sel = Math.min(rows.length - 1, sel + 1); draw(); e.preventDefault(); } if (e.key === 'ArrowUp') { sel = Math.max(0, sel - 1); draw(); e.preventDefault(); } if (e.key === 'Enter' && rows[sel]) { const a = $(`a[data-i="${sel}"]`, L); if (a) a.click(); if (rows[sel] && rows[sel].href) location.hash = rows[sel].href.slice(1); } };
  setTimeout(() => q.focus(), 30);
};
addEventListener('keydown', e => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); U.openSearch(); } if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || '')) { e.preventDefault(); U.openSearch(); } });

/* ---------- "What's new" after each update (item 300) ---------- */
U.CHANGES = [
  [35, '25 Nov 2026', [
    'Works offline with the last data, tells you when a new version is ready, and remembers your filters, recent symbols and pinned watchlist.',
    'Charts: measure tool, draw lines and boxes (saved with your journal), candle-by-candle replay, Heikin-Ashi and line styles, export the candles as CSV.',
    'Journal: five review questions, tags you can search with #, mood and energy before trading, a no-rule-break streak, trade of the week, the scanner plan next to your own trade.',
    'Monthly report page, goal progress bars, a capital tracker for deposits and withdrawals, and a drawdown and risk-of-ruin card from your own results (Analytics).',
    'Screen lock with a PIN or Face ID, start in private mode, a change log across your devices, settings export to a new phone, and a feedback note for the next update (Settings).',
    'System health: run all checks now, journal checks with a link to each trade, errors history, phone alerts sent, and a push when a system check fails.',
    'Help, Glossary, Privacy and Launch checklist pages; keyboard shortcuts (press ?).']],
  [34, '25 Nov 2026', [
    'Appearance: theme presets, accent colour, colour-blind-safe mode, calm mode, text size, compact cards and a private mode that hides rupee amounts (Settings → Appearance).',
    'Search anything with the search button, Ctrl/Cmd+K or "/": symbols, past setups, your trades and pages.',
    'Charts: clean view by default, zoom and drag, volume with the 1.5x line, the trigger candle, tap a level for its meaning, your own trade drawn on the chart.',
    'Swing: clickable stage ladder, three-line cards with "why not entry yet", distance to zone and stop, sector heat, setup history and a per-stock page.',
    'Options and intraday: the five steps fill as they pass; near-miss triggers are logged; "replay this day" from saved 5-minute candles.',
    'Gold: session band, withheld triggers kept apart, and a decision screen for the volume rule (nothing changes without your approval).',
    'Journal: quick add, paste a contract note, partial exits, templates, edit history with undo, a 30-day recycle bin, rule checklist and score, reviews, import, private mode and a data-health check.',
    'Analytics: tabs (Performance, Discipline, Timing, Setups), plain takeaways, sample-size notes, rule-break cost, mistakes ranked, the tax view and a yearly report.',
    'Dashboard: choose and reorder blocks, a Today card and one "needs me now" list. System health opens with one plain status.',
    'Pull down to refresh on the phone, an offline banner, a dot on the tab icon when an A+ setup is live, and a short tour (Settings → Show the tour).']]];
U.whatsNew = force => {
  const seen = store.get('ds_seen_ver', 0); if (!force && seen >= U.VERSION) return; store.set('ds_seen_ver', U.VERSION);
  if (!force && !seen && !store.get('ds_tour_done', false)) return;          // a first visit gets the tour instead
  const bg = document.createElement('div'); bg.className = 'modal-bg';
  bg.innerHTML = `<div class="modal" role="dialog" aria-label="What's new"><div class="mh"><h2>What's new</h2><button class="btn icon ghost" type="button" data-x aria-label="Close"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/></svg></button></div><div class="mb">${U.CHANGES.map(([v, d, items]) => `<p class="help" style="margin:12px 0 6px"><b>Version ${v}</b> · ${d}</p><ul class="ins">${items.map(t => `<li><i></i><span>${esc(t)}</span></li>`).join('')}</ul>`).join('')}</div><div class="mf"><button class="btn primary" type="button" data-x>Got it</button></div></div>`;
  bg.onclick = e => { if (e.target === bg || e.target.closest('[data-x]')) bg.remove(); }; document.body.appendChild(bg);
};

/* ---------- first-run tour (item 97) ---------- */
const TOUR = [
  ['The stage ladder', 'Every swing setup moves through five stages: Developing, Set alert, In zone, 1H confirmed and Entry. Tap a stage to see only those setups.'],
  ['Planned entry is not a signal', 'A dashed entry is where the plan sits inside the zone. A trade starts only when the status turns TRIGGERED, after the 1H close above the 9 EMA on volume.'],
  ['Chips on each card', 'Grade and score, why a setup is held back, and "↓ was …" when it moved back a stage. Tap a card for the chart, the checklist and its history.'],
  ['Your journal', 'Tap "Trade" (or "I took this") to log a trade. Your own trades show on the scanner pages too, even when the scanner is not following them.'],
  ['Find anything', 'Use search (Ctrl/Cmd+K or the search button) for a symbol, a past setup, a trade or a page.']];
U.tour = () => {
  let i = 0; const bg = document.createElement('div'); bg.className = 'modal-bg tour-bg';
  const draw = () => { const [t, s] = TOUR[i]; bg.innerHTML = `<div class="modal tour" role="dialog" aria-label="Tour"><div class="mb" style="padding-top:18px"><small class="muted">${i + 1} of ${TOUR.length}</small><h2 style="margin:6px 0 8px">${esc(t)}</h2><p>${esc(s)}</p></div><div class="mf"><button class="btn ghost" type="button" data-skip>Skip</button>${i ? '<button class="btn" type="button" data-prev>Back</button>' : ''}<button class="btn primary" type="button" data-next>${i < TOUR.length - 1 ? 'Next' : 'Done'}</button></div></div>`; };
  bg.onclick = e => { const end = () => { bg.remove(); store.set('ds_tour_done', true); store.set('ds_seen_ver', U.VERSION); };
    if (e.target.closest('[data-skip]')) end(); else if (e.target.closest('[data-prev]')) { i--; draw(); } else if (e.target.closest('[data-next]')) { if (i < TOUR.length - 1) { i++; draw(); } else end(); } };
  draw(); document.body.appendChild(bg);
};

/* ---------- appearance card for Settings ---------- */
U.settingsCard = () => {
  const p = U.get(), seg = (k, opts) => App.ui.seg('ux-' + k, opts, String(p[k]));
  const tog = (k, l, s) => `<label class="ux-tog"><input type="checkbox" data-uxt="${k}" ${p[k] ? 'checked' : ''}><span><b>${l}</b>${s ? `<small class="muted">${s}</small>` : ''}</span></label>`;
  return `<div class="card"><div class="hd"><h2>Appearance</h2><span class="cap">this device</span></div><div class="bd ux-set">
    <div class="ux-row"><span>Theme</span>${App.ui.seg('theme', [['auto', 'Match device'], ['light', 'Light'], ['dark', 'Dark']], (store.get('tji_ui_v1', {}) || {}).theme || 'auto')}</div>
    <div class="ux-row"><span>Dark style</span>${seg('preset', [['midnight', 'Midnight'], ['graphite', 'Graphite'], ['warm', 'Warm']])}</div>
    <div class="ux-row"><span>Accent</span><div class="ux-acc">${[['mono', 'Mono'], ['blue', 'Blue'], ['gold', 'Gold'], ['teal', 'Teal'], ['violet', 'Violet']].map(([v, t]) => `<button type="button" data-acc="${v}" aria-pressed="${p.accent === v}" aria-label="${t}" title="${t}" class="acc-${v}"></button>`).join('')}</div></div>
    <div class="ux-row"><span>Cards</span>${seg('density', [['comfortable', 'Comfortable'], ['compact', 'Compact']])}</div>
    <div class="ux-row"><span>Text size</span>${seg('text', [['m', 'Normal'], ['l', 'Large'], ['xl', 'Larger']])}</div>
    ${tog('calm', 'Calm mode', 'no animation or glow; the 3D models stand still')}
    ${tog('cb', 'Colour-blind-safe colours', 'blue and orange instead of green and red, with ▲ ▼ marks')}
    ${tog('softRed', 'Softer red for losses', 'so a red day does not shout')}
    ${tog('dimOff', 'Dim extras outside market hours')}
    ${tog('priv', 'Private mode', 'hides rupee amounts on screen (for screenshots)')}
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px"><button class="btn sm" type="button" id="uxTour">Show the tour</button><button class="btn sm" type="button" id="uxNew">What's new</button><a class="btn sm" href="#/design">Design check</a></div></div></div>`;
};
U.bindSettings = () => {
  ['preset', 'density', 'text'].forEach(k => $$(`[data-seg="ux-${k}"]`).forEach(b => b.onclick = () => { U.set(k, b.dataset.v); App.render(); }));
  $$('[data-acc]').forEach(b => b.onclick = () => { U.set('accent', b.dataset.acc); App.render(); });
  $$('[data-uxt]').forEach(c => c.onchange = () => { U.set(c.dataset.uxt, c.checked); App.render(); });
  const t = $('#uxTour'); if (t) t.onclick = U.tour; const n = $('#uxNew'); if (n) n.onclick = () => U.whatsNew(true);
};

/* ---------- pause decorative work when the tab is hidden (item 80) ---------- */
document.addEventListener('visibilitychange', () => document.documentElement.toggleAttribute('data-hidden', document.hidden));

/* ---------- start ---------- */
U.apply(); setInterval(() => { const o = document.documentElement.hasAttribute('data-offhours'); U.apply(); if (o !== document.documentElement.hasAttribute('data-offhours')) paintLive(); }, 60000);
function paintLive() { const m = $('#mkt'); if (m) m.classList.toggle('pulse', App.marketOpen() && !reduced()); }
U.boot = () => {
  const top = $('header.top'); if (top && !$('#searchB')) { const b = document.createElement('button'); b.id = 'searchB'; b.type = 'button'; b.className = 'btn icon ghost'; b.setAttribute('aria-label', 'Search'); b.title = 'Search (Ctrl/Cmd+K)'; b.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M20 20l-4.2-4.2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'; b.onclick = U.openSearch; const th = $('#themeB'); top.insertBefore(b, th); }
  paintLive(); offline();
  setTimeout(() => { if (!store.get('ds_tour_done', false) && !store.get('ds_seen_ver', 0)) U.tour(); else U.whatsNew(); }, 1200);
};
})();
