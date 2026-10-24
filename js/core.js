/* DownerStuff core: helpers, data, router, shell. Every page is a function in App.pages that returns HTML. */
'use strict';
const App = window.App = { pages: {}, binds: {}, data: {}, ui: {}, loaded: {} };
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const isNum = v => typeof v === 'number' && isFinite(v);
const fmt = (v, d = 2) => isNum(v) ? v.toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d }) : '-';
const fmt0 = v => fmt(v, 0);
const sg = (v, d = 2) => isNum(v) ? (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d }) : '-';
const inr = (v, d = 0) => isNum(v) ? (v < 0 ? '−₹' : '₹') + Math.abs(v).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d }) : '-';
const inrS = v => isNum(v) ? (v > 0 ? '+' : '') + inr(v) : '-';
const pct = (v, d = 1) => isNum(v) ? (v * 100).toFixed(d) + '%' : '-';
const rr = (v, d = 2) => isNum(v) ? sg(v, d) + 'R' : '-';
const cls = v => isNum(v) ? (v > 0 ? 'good' : v < 0 ? 'bad' : '') : '';
const istNow = () => new Date(Date.now() + 5.5 * 3600e3);
const todayIST = () => istNow().toISOString().slice(0, 10);
const hmIST = d => new Date(d).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: 'numeric', minute: '2-digit' });
const dateIST = d => new Date(d).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short' });
const ago = d => { const m = Math.round((Date.now() - new Date(d)) / 6e4); return m < 1 ? 'just now' : m < 60 ? m + ' min ago' : m < 1440 ? Math.round(m / 60) + ' h ago' : Math.round(m / 1440) + ' d ago'; };
const store = { get(k, d) { try { const r = localStorage.getItem(k); return r == null ? d : JSON.parse(r); } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { } } };
App.toast = (msg, ms = 2600) => { let t = $('#toast'); if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); } t.textContent = msg; t.hidden = false; clearTimeout(t._t); t._t = setTimeout(() => t.hidden = true, ms); };

/* ---------- icons ---------- */
const ICONS = {
  home: '<path d="M4 11l8-7 8 7v9a1 1 0 0 1-1 1h-5v-6h-4v6H5a1 1 0 0 1-1-1z"/>',
  swing: '<path d="M3 17l5-5 4 3 8-9"/><path d="M15 6h5v5"/>',
  options: '<path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/>',
  intraday: '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>',
  journal: '<path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"/><path d="M9 8h6M9 12h6"/>',
  analytics: '<path d="M4 20V4M4 20h16"/><path d="M8 16l3-4 3 2 5-7"/>',
  market: '<path d="M12 3a9 9 0 1 0 9 9"/><path d="M12 12l7-7"/><path d="M15 3h6v6"/>',
  news: '<rect x="3" y="5" width="18" height="15" rx="2"/><path d="M7 9h10M7 13h10M7 17h6"/>',
  playbook: '<path d="M4 5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2z"/><path d="M8 7h6M8 11h6"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  more: '<circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>', back: '<path d="M15 5l-7 7 7 7"/>', ext: '<path d="M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>',
  cloud: '<path d="M7 18h10a4 4 0 0 0 .5-8 6 6 0 0 0-11.6 1.5A3.3 3.3 0 0 0 7 18z"/>', download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>', upload: '<path d="M12 20V9M7 14l5-5 5 5M5 4h14"/>'
};
const ic = k => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[k] || ''}</svg>`;

/* ---------- navigation ---------- */
const NAV = [
  ['Today', [['dashboard', 'Dashboard', 'home']]],
  ['Scanner', [['swing', 'Swing', 'swing', 'primary'], ['options', 'Nifty options', 'options'], ['intraday', 'Intraday', 'intraday']]],
  ['Journal', [['journal', 'Trades', 'journal'], ['analytics', 'Analytics', 'analytics']]],
  ['Context', [['market', 'Market', 'market'], ['news', 'News & events', 'news']]],
  ['You', [['playbook', 'Playbook & rules', 'playbook'], ['settings', 'Settings', 'settings']]]];
const TABS = [['dashboard', 'Today', 'home'], ['swing', 'Swing', 'swing'], ['journal', 'Journal', 'journal'], ['analytics', 'Stats', 'analytics']];
const TITLES = { dashboard: 'Today', swing: 'Swing scanner', options: 'Nifty options', intraday: 'Intraday', journal: 'Journal', analytics: 'Analytics', market: 'Market', news: 'News & events', playbook: 'Playbook & rules', settings: 'Settings', trade: 'Trade' };

App.route = () => { const h = location.hash.replace(/^#\/?/, ''); const [p, q] = h.split('?'); return { page: p || 'dashboard', q: new URLSearchParams(q || '') }; };
App.go = (page, q) => { location.hash = '#/' + page + (q ? '?' + new URLSearchParams(q).toString() : ''); };

function shell() {
  const nav = NAV.map(([h, items]) => `<div class="nav-h">${h}</div><nav class="nav">${items.map(([k, t, i, star]) => `<a href="#/${k}" data-nav="${k}">${ic(i)}<span>${t}</span>${star ? '<span class="star">primary</span>' : `<span class="cnt" data-cnt="${k}" hidden></span>`}</a>`).join('')}</nav>`).join('');
  document.body.insertAdjacentHTML('afterbegin', `<div class="app"><aside class="side"><a class="brandmark" href="#/dashboard"><span class="logo">DS</span><span><b>DownerStuff</b><small>scanner · journal · analytics</small></span></a>${nav}
    <div class="side-foot">Rules-based candidates from your playbook, not advice. Check the chart, results date and news before every trade.</div></aside>
    <div class="main"><header class="top"><a class="brandmark mob-brand" href="#/dashboard" style="padding:0" aria-label="DownerStuff home"><span class="logo" style="width:30px;height:30px;font-size:13px">DS</span></a><span class="ttl" id="ttl">Today</span>
      <span class="pill hide-m" id="upd" hidden></span><span class="pill" id="mkt"><i></i><span>…</span></span><button class="pill" id="syncp" type="button" title="Journal sync">…</button>
      <button class="btn primary sm" id="addTrade" type="button">${ic('plus')}<span class="hide-m">Trade</span></button><button class="btn icon ghost" id="themeB" type="button" aria-label="Switch theme">${ic('moon')}</button><button class="btn icon ghost hide-m" id="refreshB" type="button" aria-label="Refresh data">${ic('refresh')}</button></header>
      <main class="page" id="page" tabindex="-1"></main></div></div>
    <nav class="tabbar" aria-label="Main">${TABS.map(([k, t, i]) => `<a href="#/${k}" data-tab="${k}">${ic(i)}<span>${t}</span></a>`).join('')}<button type="button" id="moreB">${ic('more')}<span>More</span></button></nav>`);
  $('#themeB').onclick = () => { const cur = App.theme(); App.setTheme(cur === 'dark' ? 'light' : 'dark'); };
  $('#refreshB').onclick = () => App.reload(true);
  $('#addTrade').onclick = () => App.journal && App.journal.openForm(null);
  $('#syncp').onclick = () => App.go('settings');
  $('#moreB').onclick = () => {
    const bg = document.createElement('div'); bg.className = 'modal-bg'; bg.style.alignItems = 'flex-end'; bg.style.padding = '0';
    bg.innerHTML = `<div class="sheet" role="dialog" aria-label="More pages"><nav class="nav">${NAV.flatMap(n => n[1]).map(([k, t, i]) => `<a href="#/${k}">${ic(i)}<span>${t}</span></a>`).join('')}</nav></div>`;
    bg.onclick = e => { if (e.target === bg || e.target.closest('a')) bg.remove(); }; document.body.appendChild(bg);
  };
}

/* ---------- theme ---------- */
App.theme = () => { const t = (store.get('tji_ui_v1', {}) || {}).theme || 'auto'; return t === 'auto' ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : t; };
App.setTheme = t => { const ui = store.get('tji_ui_v1', {}) || {}; ui.theme = t; store.set('tji_ui_v1', ui); applyTheme(); App.render(); };
function applyTheme() { const t = (store.get('tji_ui_v1', {}) || {}).theme || 'auto'; if (t === 'auto') document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme', t); const b = $('#themeB'); if (b) b.innerHTML = ic(App.theme() === 'dark' ? 'sun' : 'moon'); }

/* ---------- scanner data ---------- */
const FILES = ['swing', 'options', 'intraday', 'market', 'news', 'signals_swing', 'signals_options', 'signals_intraday'];
App.reload = async (manual) => {
  await Promise.all(FILES.map(async f => {
    try { const r = await fetch(`data/${f}.json?t=${Date.now()}`, { cache: 'no-store' }); if (r.ok) App.data[f] = await r.json(); } catch (e) { }
  }));
  App.loaded.at = Date.now(); paintChrome(); if (manual !== 'silent') App.render(); if (manual === true) App.toast('Data refreshed');
};
App.marketOpen = () => { const t = istNow(), d = t.getUTCDay(), m = t.getUTCHours() * 60 + t.getUTCMinutes(); return d > 0 && d < 6 && m >= 555 && m <= 930; };
App.LED = k => App.data['signals_' + k] || { signals: [], dropped: [], watch: {} };
function actionsUrl() { const m = location.hostname.match(/^([^.]+)\.github\.io$/), repo = location.pathname.split('/').filter(Boolean)[0]; return m && repo ? `https://github.com/${m[1]}/${repo}/actions` : 'https://github.com'; }
function paintChrome() {
  const o = App.marketOpen(), mk = $('#mkt'); if (mk) { mk.className = 'pill ' + (o ? 'ok' : ''); mk.querySelector('span').textContent = o ? 'Market open' : 'Market closed'; }
  const r = App.route().page, src = r === 'swing' ? App.data.swing : (App.data.options || App.data.swing), up = $('#upd');
  if (up && src && src.generated_at) {
    const age = (Date.now() - new Date(src.generated_at)) / 6e4, every = r === 'swing' ? 60 : 5, late = o && age > (r === 'swing' ? 100 : 12), nxt = new Date(new Date(src.generated_at).getTime() + every * 6e4);
    up.hidden = false; up.className = 'pill hide-m ' + (late ? 'bad' : 'info');
    up.innerHTML = late ? `<i></i><a href="${actionsUrl()}" target="_blank" rel="noopener">Delayed: last ${hmIST(src.generated_at)}</a>` : `<i></i>Updated ${hmIST(src.generated_at)}${o ? ' · next ~' + hmIST(nxt) : ''}`;
  }
  ['options', 'intraday'].forEach(k => { const d = App.data[k], c = $(`[data-cnt="${k}"]`); if (c && d) { const n = d.setups.length; c.hidden = !n; c.textContent = n; } });
  const jc = $('[data-cnt="journal"]'); if (jc && App.journal) { const n = App.journal.openCount(); jc.hidden = !n; jc.textContent = n + ' open'; }
  if (App.journal) App.journal.paintSync();
}
App.paintChrome = paintChrome;

/* ---------- render ---------- */
App.render = () => {
  const { page } = App.route(), fn = App.pages[page] || App.pages.dashboard, el = $('#page');
  $$('[data-nav]').forEach(a => a.classList.toggle('on', a.dataset.nav === page || (page === 'trade' && a.dataset.nav === App.route().q.get('s'))));
  $$('[data-tab]').forEach(a => a.classList.toggle('on', a.dataset.tab === page));
  $('#ttl').textContent = TITLES[page] || 'DownerStuff';
  const keep = App._lastPage === page ? window.scrollY : 0;
  try { el.innerHTML = fn(App.route().q); } catch (e) { console.error(e); el.innerHTML = `<div class="callout bad"><span class="ic">!</span><div><b>This page hit an error.</b> ${esc(e.message)}</div></div>`; }
  if (App.binds[page]) try { App.binds[page](App.route().q); } catch (e) { console.error(e); }
  if (App._lastPage !== page) window.scrollTo(0, 0); else window.scrollTo(0, keep);
  App._lastPage = page; paintChrome();
};

/* ---------- small shared widgets ---------- */
App.ui.empty = (t, s) => `<div class="empty"><b>${t}</b>${s || ''}</div>`;
App.ui.kpi = (l, v, s = '', c = '') => `<div class="kpi"><div class="l">${l}</div><div class="v ${c}">${v}</div>${s ? `<div class="s">${s}</div>` : ''}</div>`;
App.ui.grade = g => `<span class="grade ${g === 'A+' ? 'ap' : (g || 'skip').toLowerCase()}">${esc(g || '-')}</span>`;
App.ui.ring = (score, max = 10) => { const r = 19, c = 2 * Math.PI * r, f = Math.max(0, Math.min(1, score / max)), col = score >= 8 ? 'var(--good)' : score >= 6 ? 'var(--brand)' : score >= 4 ? 'var(--sun)' : 'var(--ink-3)';
  return `<svg class="ring" viewBox="0 0 46 46" role="img" aria-label="Score ${score} of ${max}"><circle cx="23" cy="23" r="${r}" fill="none" stroke="var(--line-2)" stroke-width="5"/><circle cx="23" cy="23" r="${r}" fill="none" stroke="${col}" stroke-width="5" stroke-linecap="round" stroke-dasharray="${c * f} ${c}" transform="rotate(-90 23 23)"/><text x="23" y="27.5" text-anchor="middle" class="ring-txt" fill="var(--ink)">${score}</text></svg>`; };
App.ui.callout = (kind, html) => `<div class="callout ${kind}"><span class="ic">${kind === 'good' ? '✓' : kind === 'info' || !kind ? 'i' : '!'}</span><div>${html}</div></div>`;
App.ui.seg = (key, opts, cur) => `<div class="seg" role="group">${opts.map(([v, t]) => `<button type="button" data-seg="${key}" data-v="${v}" aria-pressed="${String(cur) === String(v)}">${t}</button>`).join('')}</div>`;
App.tv = sym => `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(sym === 'NIFTY 50' ? 'NSE:NIFTY' : 'NSE:' + sym.replace(/&/g, '_').replace(/-/g, '_'))}`;

/* ---------- private access: sign-in gate ----------
   Nothing in the app is built and no data is loaded until an allowed account is signed in.
   The session is remembered on each device (Supabase keeps it in this browser), so you sign in once per device. */
App.SUPA = { url: 'https://gdecjijdudotkfikfona.supabase.co', key: 'sb_publishable_xBuw3PmoTgq-gNz3_YY7Kg_1p_adtBI' };
App.ALLOWED = [];  // optional extra lock: put your email(s) here, e.g. ['you@example.com']. Empty = any account in your Supabase project.
const allowedUser = u => !!u && (!App.ALLOWED.length || App.ALLOWED.map(e => e.toLowerCase()).includes(String(u.email || '').toLowerCase()));
function gateView(msg, fatal) {
  let g = $('#gate'); if (!g) { g = document.createElement('div'); g.id = 'gate'; document.body.appendChild(g); }
  g.innerHTML = `<form class="gate-card" id="gateF" novalidate>
    <div class="gate-mark"><span class="logo">DS</span><div><b>DownerStuff</b><small>Private trading desk</small></div></div>
    <h1>Sign in</h1><p class="gate-sub">Use your Trade Insight account.</p>
    ${fatal ? `<div class="callout bad"><span class="ic">!</span><div>${esc(msg)}</div></div>` : `
    <div class="field"><label for="gEm">Email</label><input id="gEm" type="email" autocomplete="username" inputmode="email" autocapitalize="off" spellcheck="false" required></div>
    <div class="field"><label for="gPw">Password</label><input id="gPw" type="password" autocomplete="current-password" required></div>
    <p class="gate-msg" id="gMsg" role="alert">${msg ? esc(msg) : ''}</p>
    <button class="btn primary gate-btn" id="gBtn" type="submit">Sign in</button>`}
  </form>`;
  return g;
}
async function gate() {
  if (!window.supabase) { gateView('The sign-in service did not load. Check your connection and reload the page.', true); return null; }
  App.sb = window.supabase.createClient(App.SUPA.url, App.SUPA.key, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } });
  try { const { data } = await App.sb.auth.getSession(); const u = data && data.session && data.session.user;
    if (allowedUser(u)) return u; if (u) await App.sb.auth.signOut(); } catch (e) { console.error(e); }
  return new Promise(done => {
    const g = gateView(''); const f = $('#gateF', g); setTimeout(() => { const e = $('#gEm', g); if (e) e.focus(); }, 50);
    f.onsubmit = async ev => { ev.preventDefault(); const m = $('#gMsg', g), b = $('#gBtn', g), em = $('#gEm', g).value.trim(), pw = $('#gPw', g).value;
      if (!em || !pw) { m.textContent = 'Enter your email and password.'; return; }
      b.disabled = true; b.textContent = 'Signing in…'; m.textContent = '';
      try { const { data, error } = await App.sb.auth.signInWithPassword({ email: em, password: pw }); if (error) throw error;
        if (!allowedUser(data.user)) { await App.sb.auth.signOut(); throw new Error('This account does not have access.'); }
        g.remove(); done(data.user); }
      catch (e) { m.textContent = /invalid/i.test(e.message || '') ? 'Wrong email or password.' : (e.message || 'Sign-in failed.'); b.disabled = false; b.textContent = 'Sign in'; $('#gPw', g).select(); } };
  });
}

/* ---------- start ---------- */
App.start = async () => {
  applyTheme();
  const user = await gate(); if (!user) return;
  App.user = user;
  App.sb.auth.onAuthStateChange(ev => { if (ev === 'SIGNED_OUT') location.reload(); });
  shell(); applyTheme();
  if (App.journal) App.journal.init();
  App.render();
  await App.reload('silent'); App.render();
  window.addEventListener('hashchange', App.render);
  setInterval(() => { if (App.marketOpen() && !document.hidden && !$('.modal-bg')) App.reload('silent').then(() => { if (!document.activeElement || !/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) App.render(); }); }, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden && !$('.modal-bg')) App.reload('silent').then(App.render); });
  window.addEventListener('pageshow', e => { if (e.persisted) App.reload('silent').then(App.render); });
  matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', () => { applyTheme(); App.render(); });
};
