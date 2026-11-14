/* 3D models: small monochrome scenes drawn on <canvas data-m3d="name">, each one chosen for what its section is about
   (a coin for money, a ring that fills for a win rate, candles for intraday, a helix for the backtest lab, a globe for the market).
   One animation loop draws every model that is on screen; models scrolled out of view, or on a hidden tab, cost nothing.
   They use the theme's ink (white on black, black on white). Colour appears only where it means something: green or red for
   profit or loss, gold on the gold page. With "reduce motion" switched on, each model is drawn once and stays still.
   Options on the canvas: data-m3d (model), data-tone (good, bad, gold), data-fill (0 to 1, for "ring"), data-txt (coin face),
   data-speed (1 = normal), data-tilt (radians). */
(() => {
  const TAU = Math.PI * 2, still = () => !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);

  /* ---------- geometry: points p [x,y,z], edges e [i,j], faces f [i,j,k,(l)]; hot = indexes drawn in the tone colour ---------- */
  const G = {};
  const box = (o, x0, y0, z0, x1, y1, z1) => {
    const b = o.p.length;
    [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]].forEach(v => o.p.push(v));
    [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]].forEach(([i, j]) => o.e.push([b + i, b + j]));
    [[0, 1, 2, 3], [5, 4, 7, 6], [4, 0, 3, 7], [1, 5, 6, 2], [3, 2, 6, 7], [4, 5, 1, 0]].forEach(f => o.f.push(f.map(i => b + i)));
    return b;
  };
  const ring = (o, n, fn, close = true) => { const b = o.p.length; for (let i = 0; i < n; i++) o.p.push(fn(i / n * TAU, i)); for (let i = 0; i < n - (close ? 0 : 1); i++) o.e.push([b + i, b + (i + 1) % n]); return b; };
  const mk = () => ({ p: [], e: [], f: [], d: [], hot: new Set() });

  G.orb = (n = 260) => { const o = mk(), ga = Math.PI * (3 - Math.sqrt(5)); for (let i = 0; i < n; i++) { const y = 1 - (i + 0.5) / n * 2, r = Math.sqrt(1 - y * y), t = ga * i; o.p.push([Math.cos(t) * r * .9, y * .9, Math.sin(t) * r * .9]); o.d.push(o.p.length - 1); } return o; };
  G.ring = (fill) => {                                                        // a torus; with data-fill the filled share glows (a win rate, progress)
    const o = mk(), nu = 44, nv = 9, R = .78, r = .2;
    for (let u = 0; u < nu; u++) for (let v = 0; v < nv; v++) { const a = u / nu * TAU, b = v / nv * TAU; o.p.push([(R + r * Math.cos(b)) * Math.cos(a), r * Math.sin(b), (R + r * Math.cos(b)) * Math.sin(a)]); }
    for (let u = 0; u < nu; u++) for (let v = 0; v < nv; v++) { const i = u * nv + v; o.e.push([i, u * nv + (v + 1) % nv]); if (v % 3 === 0) o.e.push([i, ((u + 1) % nu) * nv + v]); if (fill != null && u / nu < fill) o.hot.add(i); }
    return o;
  };
  G.cube = () => { const o = mk(); box(o, -.62, -.62, -.62, .62, .62, .62); const b = box(o, -.26, -.26, -.26, .26, .26, .26); for (let i = 0; i < 8; i++) { o.e.push([i, b + i]); o.d.push(i); } o.f.length = 6; return o; };
  G.coin = () => {
    const o = mk(), n = 56, R = .86, T = .11;
    ring(o, n, a => [Math.cos(a) * R, Math.sin(a) * R, T]); ring(o, n, a => [Math.cos(a) * R, Math.sin(a) * R, -T]);
    for (let i = 0; i < n; i += 4) o.e.push([i, n + i]);
    ring(o, 40, a => [Math.cos(a) * R * .76, Math.sin(a) * R * .76, T]); ring(o, 40, a => [Math.cos(a) * R * .76, Math.sin(a) * R * .76, -T]);
    o.face = { c: [0, 0, T], ux: [-1, 0, 0], uy: [0, 1, 0], r: R }; o.back = { c: [0, 0, -T], ux: [1, 0, 0], uy: [0, 1, 0], r: R };   // each face reads the right way round when it faces you
    o.f.push([...Array(n).keys()].filter(i => i % 2 === 0));
    return o;
  };
  G.helix = () => {
    const o = mk(), n = 54;
    for (let s = 0; s < 2; s++) { const b = o.p.length; for (let i = 0; i < n; i++) { const t = i / (n - 1) * TAU * 1.6 + s * Math.PI; o.p.push([Math.cos(t) * .45, i / (n - 1) * 1.8 - .9, Math.sin(t) * .45]); o.d.push(b + i); if (i) o.e.push([b + i - 1, b + i]); } }
    for (let i = 0; i < n; i += 4) o.e.push([i, n + i]);
    return o;
  };
  G.candles = () => {                                                         // hollow = up candle, filled = down candle
    const o = mk(), H = [[.10, .55, -.05, .70], [.30, .75, .20, .85], [.55, .25, .15, .65], [.20, .80, .10, .95], [.65, 1.05, .55, 1.15], [.95, .70, .60, 1.05]];
    H.forEach(([op, cl, lo, hi], i) => { const x = -.8 + i * .32, w = .085, y0 = Math.min(op, cl) - .5, y1 = Math.max(op, cl) - .5, f0 = o.f.length;
      box(o, x - w, -y1, -w, x + w, -y0, w); if (cl < op) o.solid = (o.solid || []).concat([f0, f0 + 1, f0 + 2, f0 + 3, f0 + 4, f0 + 5]);
      const b = o.p.length; o.p.push([x, -(hi - .5), 0], [x, -y1, 0], [x, -y0, 0], [x, -(lo - .5), 0]); o.e.push([b, b + 1], [b + 2, b + 3]); });
    return o;
  };
  G.bars = t => { const o = mk(); for (let i = 0; i < 4; i++) for (let j = 0; j < 3; j++) { const h = .25 + .55 * (.5 + .5 * Math.sin(t * .9 + i * 1.3 + j * 2.1)), x = -.72 + i * .4, z = -.4 + j * .4; box(o, x, .55 - h * 1.25, z, x + .26, .55, z + .26); } return o; };
  G.wave = t => {
    const o = mk(), n = 12;
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { const x = i / (n - 1) * 1.7 - .85, z = j / (n - 1) * 1.7 - .85; o.p.push([x, .24 * Math.sin(x * 3 + t * 1.4) * Math.cos(z * 2.6 + t), z]); }
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { const k = i * n + j; if (j < n - 1) o.e.push([k, k + 1]); if (i < n - 1 && j % 2 === 0) o.e.push([k, k + n]); }
    return o;
  };
  G.globe = () => {
    const o = mk();
    [-60, -30, 0, 30, 60].forEach(lat => { const y = Math.sin(lat * Math.PI / 180) * .78, r = Math.cos(lat * Math.PI / 180) * .78; ring(o, 40, a => [Math.cos(a) * r, y, Math.sin(a) * r]); });
    for (let m = 0; m < 8; m++) { const a0 = m / 8 * Math.PI; ring(o, 32, b => [Math.cos(b) * .78 * Math.cos(a0), Math.sin(b) * .78, Math.cos(b) * .78 * Math.sin(a0)]); }
    const b = ring(o, 60, a => [Math.cos(a) * 1.08, Math.sin(a) * .2, Math.sin(a) * 1.08]); for (let i = 0; i < 60; i += 6) o.d.push(b + i);
    [[.3, .5], [-.4, .2], [.6, -.3], [-.1, -.6], [.1, .1]].forEach(([u, v]) => { const y = Math.sin(v) * .78, r = Math.cos(v) * .78; o.p.push([Math.cos(u * 4) * r, y, Math.sin(u * 4) * r]); o.d.push(o.p.length - 1); o.hot.add(o.p.length - 1); });
    return o;
  };
  G.gem = () => {
    const o = mk(), n = 8, t = ring(o, n, a => [Math.cos(a) * .4, .52, Math.sin(a) * .4]), g = ring(o, n, a => [Math.cos(a + Math.PI / n) * .78, .22, Math.sin(a + Math.PI / n) * .78]);
    o.p.push([0, -.92, 0]); const tip = o.p.length - 1;
    for (let i = 0; i < n; i++) { o.e.push([t + i, g + i], [t + (i + 1) % n, g + i], [g + i, tip]); o.f.push([t + i, t + (i + 1) % n, g + i], [g + i, g + (i + 1) % n, tip]); o.d.push(g + i); }
    o.f.push([...Array(n).keys()].map(i => t + i));
    return o;
  };
  G.pyramid = () => { const o = mk(); o.p.push([-.65, .55, -.65], [.65, .55, -.65], [.65, .55, .65], [-.65, .55, .65], [0, -.85, 0]); o.e.push([0, 1], [1, 2], [2, 3], [3, 0], [0, 4], [1, 4], [2, 4], [3, 4]); o.f.push([0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4], [3, 2, 1, 0]); o.d.push(4); o.hot.add(4); return o; };
  G.stairs = () => { const o = mk(); for (let i = 0; i < 5; i++) { const x = -.9 + i * .36; box(o, x, .7 - (.22 + i * .3), -.36, x + .36, .7, .36); } return o; };
  G.stack = t => { const o = mk(); for (let i = 0; i < 4; i++) { const y = .5 - i * .3, s = Math.sin(t * .8 + i) * .06; box(o, -.75 + s, y - .07, -.5, .75 + s, y + .07, .5); } return o; };
  G.radar = t => {
    const o = mk();
    for (let k = 0; k < 3; k++) { const r = ((t * .35 + k / 3) % 1) * 1.05; const b = ring(o, 48, a => [Math.cos(a) * r, .35, Math.sin(a) * r]); o.fade = (o.fade || []).concat([[b, b + 48, 1 - r / 1.05]]); }
    ring(o, 48, a => [Math.cos(a) * 1.05, .35, Math.sin(a) * 1.05]);
    o.p.push([0, .35, 0], [0, -.55, 0]); const c = o.p.length - 2; o.e.push([c, c + 1]); o.d.push(c + 1); o.hot.add(c + 1);
    return o;
  };
  G.knot = () => { const o = mk(), n = 150; for (let i = 0; i < n; i++) { const t = i / n * TAU, r = .5 + .22 * Math.cos(3 * t); o.p.push([r * Math.cos(2 * t), .22 * Math.sin(3 * t) * 1.6, r * Math.sin(2 * t)]); o.e.push([i, (i + 1) % n]); if (i % 3 === 0) o.d.push(i); } return o; };
  G.shield = () => {
    const o = mk(), out = [[0, -.9], [.62, -.66], [.62, .05], [.42, .5], [0, .9], [-.42, .5], [-.62, .05], [-.62, -.66]], n = out.length, T = .12;
    out.forEach(([x, y]) => o.p.push([x, y, T])); out.forEach(([x, y]) => o.p.push([x, y, -T])); out.forEach(([x, y]) => o.p.push([x * .62, y * .62 - .02, T + .001]));
    for (let i = 0; i < n; i++) o.e.push([i, (i + 1) % n], [n + i, n + (i + 1) % n], [i, n + i], [2 * n + i, 2 * n + (i + 1) % n]);
    o.f.push([...Array(n).keys()]);
    return o;
  };
  G.portal = t => {                                                           // the login pedestal: rings of light the avatar stands on
    const o = mk();
    [[1, 90], [.78, 70], [.56, 52]].forEach(([r, n], k) => { const b = ring(o, n, a => [Math.cos(a + t * (k % 2 ? -.25 : .18)) * r, 0, Math.sin(a + t * (k % 2 ? -.25 : .18)) * r]); for (let i = 0; i < n; i += k ? 5 : 3) o.d.push(b + i); });
    for (let i = 0; i < 26; i++) { const a = i / 26 * TAU + t * .12, h = ((t * .22 + i * .37) % 1); o.p.push([Math.cos(a) * .95, -h * .42, Math.sin(a) * .95]); o.d.push(o.p.length - 1); o.fadeP = (o.fadeP || {}); o.fadeP[o.p.length - 1] = 1 - h; }
    return o;
  };
  const ANIM = new Set(['bars', 'wave', 'stack', 'radar', 'portal']);

  /* ---------- colour ---------- */
  const rgbOf = v => { v = String(v || '').trim(); let m = v.match(/^#([0-9a-f]{3})$/i); if (m) return m[1].split('').map(c => parseInt(c + c, 16)).join(',');
    m = v.match(/^#([0-9a-f]{6})/i); if (m) return [0, 2, 4].map(i => parseInt(m[1].slice(i, i + 2), 16)).join(','); m = v.match(/rgba?\(([^)]+)\)/); if (m) return m[1].split(',').slice(0, 3).map(s => +s).join(','); return null; };
  const css = k => getComputedStyle(document.documentElement).getPropertyValue(k);
  const inkRGB = () => rgbOf(css('--ink')) || '255,255,255';
  const toneRGB = t => t ? rgbOf(css(t === 'gold' ? '--gold' : t === 'bad' ? '--bad' : t === 'good' ? '--good' : '--ink')) : null;

  /* ---------- drawing ---------- */
  const L = { list: [], raf: 0, n: 0, io: null, ro: null };
  function size(o) {
    const box0 = o.cv.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2), W = Math.max(8, box0.width), H = Math.max(8, box0.height);
    if (o.W === W && o.H === H) return; o.W = W; o.H = H; o.cv.width = Math.round(W * dpr); o.cv.height = Math.round(H * dpr); o.ctx.setTransform(dpr, 0, 0, dpr, 0, 0); o.dirty = true;
  }
  function draw(o, t) {
    const { ctx, W, H } = o, ink = o.ink, tone = o.tone || ink;
    const geo = ANIM.has(o.kind) ? G[o.kind](t) : o.geo;
    ctx.clearRect(0, 0, W, H);
    const S = Math.min(W, H) * (o.zoom || .4), cx = W / 2, cy = H / 2;
    const a = o.kind === 'coin' ? o.yaw0 + Math.sin(t * .8 * o.speed) * 1.05 : o.yaw0 + (o.spin ? t * .45 * o.speed : 0), ca = Math.cos(a), sa = Math.sin(a), tl = o.tilt + (o.spin ? Math.sin(t * .5) * .06 : 0), ct = Math.cos(tl), st = Math.sin(tl);
    const P = geo.p.map(([x0, y0, z0]) => { const x = x0 * ca + z0 * sa, z1 = -x0 * sa + z0 * ca, y = y0 * ct - z1 * st, z = y0 * st + z1 * ct, k = 3 / (3 + z); return [cx + x * S * k, cy + y * S * k, z, k]; });
    const dep = z => Math.max(0, Math.min(1, (1 - z) / 2));
    if (o.halo) { const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.min(W, H) * .5); g.addColorStop(0, `rgba(${tone},${o.halo})`); g.addColorStop(1, `rgba(${tone},0)`); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); }
    if (geo.f.length) {                                                       // glass faces, back to front
      const F = geo.f.map((f, i) => [f, f.reduce((s, j) => s + P[j][2], 0) / f.length, i]).sort((A, B) => B[1] - A[1]);
      for (const [f, z, i] of F) {
        const p0 = P[f[0]], p1 = P[f[1]], p2 = P[f[2]], front = ((p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0])) < 0, solid = geo.solid && geo.solid.includes(i);
        ctx.beginPath(); f.forEach((j, n) => n ? ctx.lineTo(P[j][0], P[j][1]) : ctx.moveTo(P[j][0], P[j][1])); ctx.closePath();
        ctx.fillStyle = `rgba(${ink},${solid ? .55 + .3 * dep(z) : (front ? .07 : .025) + .05 * dep(z)})`; ctx.fill();
      }
    }
    const lw = W < 40 ? .7 : W < 90 ? .9 : 1.1, boost = W >= 60 ? 1.18 : 1;
    ctx.lineWidth = lw; const fadeE = new Map(); (geo.fade || []).forEach(([b, e, v]) => { for (let i = b; i < e; i++) fadeE.set(i, v); });
    for (const [i, j] of geo.e) {
      const z = (P[i][2] + P[j][2]) / 2, d = dep(z), hot = geo.hot.has(i) && geo.hot.has(j), f = fadeE.has(i) ? fadeE.get(i) : 1;
      ctx.strokeStyle = `rgba(${hot ? tone : ink},${Math.min(1, ((hot ? .45 : .12) + (hot ? .5 : .62) * d * d) * f * boost)})`;
      ctx.beginPath(); ctx.moveTo(P[i][0], P[i][1]); ctx.lineTo(P[j][0], P[j][1]); ctx.stroke();
    }
    for (const i of geo.d) { const [x, y, z, k] = P[i], d = dep(z), hot = geo.hot.has(i), f = geo.fadeP && geo.fadeP[i] != null ? geo.fadeP[i] : 1, s = (W < 60 ? .8 : 1.1) + (hot ? 1.3 : 1.1) * d * k;
      ctx.fillStyle = `rgba(${hot ? tone : ink},${(.25 + .75 * d) * f})`; ctx.fillRect(x - s / 2, y - s / 2, s, s); }
    for (const fc of [geo.face, geo.back]) {                                  // the coin's face: its symbol, drawn on the face plane
      if (!fc || !o.txt) continue;
      const pr = v => { const [x0, y0, z0] = v, x = x0 * ca + z0 * sa, z1 = -x0 * sa + z0 * ca, y = y0 * ct - z1 * st, z = y0 * st + z1 * ct, k = 3 / (3 + z); return [cx + x * S * k, cy + y * S * k, z]; };
      const c = pr(fc.c), ux = pr(fc.c.map((v, n) => v + fc.ux[n] * .01)), uy = pr(fc.c.map((v, n) => v + fc.uy[n] * .01)), nz = pr(fc.c.map((v, n) => v + (fc === geo.face ? [0, 0, .01] : [0, 0, -.01])[n]));
      if (nz[2] > c[2]) continue;                                             // facing away
      const ax = (ux[0] - c[0]) / .01, ay = (ux[1] - c[1]) / .01, bx = (uy[0] - c[0]) / .01, by = (uy[1] - c[1]) / .01;
      ctx.save(); ctx.transform(ax / 100, ay / 100, bx / 100, by / 100, c[0], c[1]);
      ctx.fillStyle = `rgba(${tone},${.92})`; ctx.font = `600 ${o.txt.length > 1 ? 70 : 96}px Archivo, system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(o.txt, 0, 4);
      ctx.restore();
    }
  }
  function frame(now) {
    L.raf = 0; L.n++;
    const t = now / 1000, moving = !still();
    L.list = L.list.filter(o => o.cv.isConnected);
    for (const o of L.list) {
      if (!o.vis) continue;
      if (o.W == null || L.n % 30 === 0) size(o);
      if (!moving) { if (o.dirty) { draw(o, 1.2); o.dirty = false; } continue; }
      if (o.W < 60 && L.n % 2) continue;                                     // tiny models: 30 frames a second is plenty
      draw(o, t + o.phase);
    }
    if (L.list.length && moving && !document.hidden) L.raf = requestAnimationFrame(frame);
  }
  const kick = () => { if (!L.raf && L.list.length) L.raf = requestAnimationFrame(frame); };
  document.addEventListener('visibilitychange', () => { if (!document.hidden) kick(); });
  addEventListener('resize', () => { L.list.forEach(o => { o.W = null; o.dirty = true; }); kick(); });

  App.m3dScan = (root = document) => {
    if (!L.io && 'IntersectionObserver' in window) L.io = new IntersectionObserver(es => { es.forEach(e => { const o = e.target._m3d; if (o) { o.vis = e.isIntersecting; o.dirty = true; } }); kick(); }, { rootMargin: '80px' });
    root.querySelectorAll('canvas[data-m3d]').forEach(cv => {
      if (cv._m3d) return; const ctx = cv.getContext && cv.getContext('2d'); if (!ctx) return;
      const ds = cv.dataset, kind = G[ds.m3d] ? ds.m3d : 'orb', fill = ds.fill != null && ds.fill !== '' ? Math.max(0, Math.min(1, +ds.fill)) : null;
      const w0 = cv.getBoundingClientRect().width || 80, arg = kind === 'orb' ? Math.round(Math.max(70, Math.min(260, w0 * 1.5))) : fill;   // fewer points on a small orb, so it stays airy
      const o = { cv, ctx, kind, geo: ANIM.has(kind) ? null : G[kind](arg), ink: ds.ink ? toneRGB(ds.ink) : inkRGB(), tone: toneRGB(ds.tone), txt: ds.txt || (kind === 'coin' ? '₹' : ''), speed: +ds.speed || 1,
        tilt: ds.tilt != null ? +ds.tilt : (kind === 'portal' ? .3 : kind === 'wave' || kind === 'bars' || kind === 'radar' ? .5 : kind === 'coin' ? .08 : .38),
        yaw0: Math.random() * TAU, phase: Math.random() * 20, spin: kind !== 'portal', zoom: +ds.zoom || (kind === 'portal' ? 1.1 : kind === 'ring' ? .44 : kind === 'candles' ? .47 : .4), halo: ds.halo != null ? +ds.halo : 0, vis: !L.io, dirty: true };
      if (kind === 'coin') o.yaw0 = 0;                                       // a coin rocks rather than spins, so its face stays readable
      cv._m3d = o; L.list.push(o); if (L.io) L.io.observe(cv);
    });
    kick();
  };
  App.m3dRetheme = () => { const ink = inkRGB(); L.list.forEach(o => { o.ink = o.cv.dataset.ink ? toneRGB(o.cv.dataset.ink) : ink; o.tone = toneRGB(o.cv.dataset.tone); o.dirty = true; }); kick(); };
  new MutationObserver(() => App.m3dRetheme()).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  /* ---------- placing models by what each section is about ---------- */
  const m = (kind, cls, extra = '') => `<canvas class="m3d ${cls}" data-m3d="${kind}" ${extra} aria-hidden="true"></canvas>`;
  const PAGE = { swing: 'stairs', options: 'wave', intraday: 'candles', journal: 'stack', analytics: 'bars', review: 'ring', backtest: 'helix', market: 'globe', news: 'radar', health: 'knot', playbook: 'gem', settings: 'cube' };
  const BY = [                                                                // first match wins: what the words say → which model
    [/a\+|rules|playbook|why this|insight|edge|scorecard|setup/i, 'gem'],
    [/win rate|progress|discipline|checklist|readiness|hold|weekly|calendar|events/i, 'ring'],
    [/heat|risk|loss|caution|break|two-factor|invalidated|skipped|no data|stop/i, 'shield'],
    [/p&l|profit|net|today|this month|money|average r|total r|expectancy|position size|best since/i, 'coin'],
    [/drawdown|vix|curve|distribution|expected move|atr|execution|mae/i, 'wave'],
    [/monthly|sector|breadth|analytics|backtests?\b/i, 'bars'],
    [/nifty|bank|market|regime|news|headline|from angel|sources/i, 'globe'],
    [/intraday|timeframe|ema|bias|alignment|5m|15m|1h|prev day/i, 'candles'],
    [/swing|shortlist|pipeline|stage/i, 'stairs'],
    [/backtest|data|freshness|loop|running|scan|journal backup|cloud/i, 'helix'],
    [/trades?|position|open|order|ticket|journal|closed|signal|live/i, 'cube'],
  ];
  const pick = s => { for (const [re, k] of BY) if (re.test(s)) return k; return 'orb'; };
  const STAGE = { 1: 'orb', 2: 'radar', 3: 'cube', 4: 'gem', 5: 'pyramid' };
  const GZ = el => el.closest('.gold-zone,.gold-card') ? ' data-ink="gold" data-tone="gold"' : '';     // on the gold page the models are gold

  App.deco3d = (root = document) => {
    const page = (App.route && App.route().page) || '';
    root.querySelectorAll('.ph').forEach(ph => {                              // the page title gets its emblem
      if (ph.querySelector('.ph-orb,.ph-3d')) return;
      const gold = ph.classList.contains('gold-head'), k = gold ? 'coin' : PAGE[page]; if (!k) return;
      const ctl = [...ph.children].slice(1).some(c => c.matches('.seg,.btn,select') || c.querySelector('.btn,select,.seg')), html = `<div class="ph-3d${gold ? ' gold' : ''}">${m(k, '', `${gold ? 'data-ink="gold" data-tone="gold" data-txt="Au"' : ''} data-halo="${gold ? .16 : .07}"`)}</div>`;
      if (ctl && ph.firstElementChild) ph.firstElementChild.insertAdjacentHTML('afterend', html.replace('class="ph-3d', 'class="ph-3d inl')); else ph.insertAdjacentHTML('beforeend', html);   // with buttons in the header, it sits beside the title instead of wrapping onto a row of its own
    });
    root.querySelectorAll('.kpi').forEach(el => {                             // each figure gets a small model for what it measures
      if (el.querySelector('.m3d')) return; const l = el.querySelector('.l'), v = el.querySelector('.v'); if (!l) return;
      const k = pick(l.textContent), vt = v ? v.textContent : '', pc = vt.match(/(-?\d+(?:\.\d+)?)\s*%/), neg = v && (/\b(neg|bad)\b/.test(v.className) || /^\s*[-−]/.test(vt)), pos = v && /\b(pos|good)\b/.test(v.className);
      const tone = k === 'coin' || k === 'ring' ? (neg ? 'bad' : pos ? 'good' : '') : '';
      el.classList.add('has-3d'); el.insertAdjacentHTML('afterbegin', m(k, 'kpi-3d', `${GZ(el)} ${tone ? `data-tone="${tone}"` : ''} ${k === 'ring' && pc ? `data-fill="${Math.max(0, Math.min(1, +pc[1] / 100))}" data-tone="${tone || 'good'}"` : ''} ${k === 'coin' && /\br\b|expectancy/i.test(l.textContent) ? 'data-txt="R"' : ''}`));
    });
    root.querySelectorAll('.card>.hd h2').forEach(h => {                      // each card title gets one too
      if (h.querySelector('.m3d') || !h.textContent.trim()) return; const gold = !!h.closest('.gold-zone,.gold-card');
      const card = !!h.closest('.gold-card'), k = card ? 'coin' : pick(h.textContent);       // the gold card's flat coin becomes a 3D one
      h.insertAdjacentHTML('afterbegin', m(k, 'h2-3d', (gold ? GZ(h) : '') + (gold && k === 'coin' ? ' data-txt="Au"' : '')));
    });
    root.querySelectorAll('.pipe').forEach(p => { if (p.querySelector('.m3d')) return; const k = (p.className.match(/\bp([1-5])\b/) || [])[1]; if (k) p.insertAdjacentHTML('beforeend', m(STAGE[k], 'pipe-3d', k === '5' || k === '4' ? 'data-tone="good"' : '')); });
    root.querySelectorAll('.live-row').forEach(r => { if (r.querySelector('.m3d')) return; const t = (r.querySelector('b') || r).textContent; r.insertAdjacentHTML('afterbegin', m(/option/i.test(t) ? 'wave' : /intraday/i.test(t) ? 'candles' : 'stairs', 'row-3d')); });
    root.querySelectorAll('.sc').forEach(c => {                               // setup cards: the model shows how far along the playbook it is
      if (c.querySelector('.m3d')) return; const sc = c.querySelector('.sc-score'); if (!sc) return; const st = c.querySelector('.sc-st'), s = st && (st.className.match(/\bs([1-5])\b/) || [])[1], held = st && st.classList.contains('hold');
      sc.insertAdjacentHTML('afterbegin', m(held ? 'shield' : STAGE[s] || 'gem', 'sc-3d', held ? 'data-tone="bad"' : s === '5' || s === '4' ? 'data-tone="good"' : ''));
    });
    root.querySelectorAll('.empty').forEach(e => { if (e.querySelector('.m3d') || e.offsetHeight < 40) return; e.insertAdjacentHTML('afterbegin', m('orb', 'empty-3d', 'data-halo=".06"' + GZ(e))); });
    App.m3dScan(root);
  };

  /* ---------- the sign-in stage: your avatar on a pedestal of light, with the desk's models floating round him ---------- */
  App.gateMount = (g, formHtml) => {
    if (!g.querySelector('.gs')) {
      const hr = new Date().getHours(), hello = (hr < 12 ? 'Good morning.' : hr < 17 ? 'Good afternoon.' : 'Good evening.') + ' Ready for the A+ setups?';
      g.classList.add('gate-3d');
      g.innerHTML = `<div class="gs" aria-hidden="true">
        <div class="gs-spot"></div>
        <div class="gs-orb"><canvas data-orb data-energy=".55"></canvas></div>
        ${m('portal', 'gs-portal', 'data-halo=".10"')}
        ${m('coin', 'gs-f f1', 'data-halo=".05"')}${m('cube', 'gs-f f2')}${m('gem', 'gs-f f3')}${m('helix', 'gs-f f4')}${m('candles', 'gs-f f5')}${m('ring', 'gs-f f6', 'data-fill=".72"')}${m('globe', 'gs-f f7')}${m('coin', 'gs-f f8', 'data-tone="gold" data-txt="Au"')}
        <div class="gs-av"><div class="gs-in">
          <img class="gs-body" src="avatar.png?v=19" alt="" draggable="false">
          <div class="gs-head"><img src="avatar.png?v=19" alt="" draggable="false"><i class="gl l"></i><i class="gl r"></i></div>
        </div><div class="gs-shadow"></div></div>
        <div class="gs-say" id="gSay">${hello}</div>
        <div class="gs-cap"><small>Private trading desk</small><b>DownerStuff</b></div>
        <div class="gs-tick"><span>NIFTY 50 · BANK NIFTY · XAUUSD · SWING · NIFTY OPTIONS · INTRADAY · A+ ONLY · NIFTY 50 · BANK NIFTY · XAUUSD · SWING · NIFTY OPTIONS · INTRADAY · A+ ONLY · </span></div>
      </div><div class="gside">${m('ring', 'gside-ring', 'data-zoom=".47" data-tilt="1.42" data-speed=".3"')}${m('orb', 'gside-dust', 'data-zoom=".5" data-speed=".2"')}<div class="gform"></div></div>`;
      gateLife(g, hello);
    }
    g.querySelector('.gform').innerHTML = formHtml;
    try { App.orbsInit(); } catch (e) { }
    App.m3dScan(g);
    return g;
  };
  function gateLife(g, hello) {                                                // what makes the avatar "live": he breathes, looks at you, reacts
    const av = g.querySelector('.gs-av'), say = t => { const s = g.querySelector('#gSay'); if (s && s.textContent !== t) { s.textContent = t; s.classList.remove('pop'); void s.offsetWidth; s.classList.add('pop'); } };
    let away = false, ready = false; setTimeout(() => { ready = true; }, 600);           // the email box focuses itself on load: no comment for that one
    g.addEventListener('pointermove', e => {
      if (away || still()) return; const r = av.getBoundingClientRect(), hx = r.left + r.width * .45, hy = r.top + r.height * .14;
      const dx = Math.max(-1, Math.min(1, (e.clientX - hx) / 500)), dy = Math.max(-1, Math.min(1, (e.clientY - hy) / 500));
      av.style.setProperty('--hr', (dx * 5).toFixed(2) + 'deg'); av.style.setProperty('--hx', (dx * 3).toFixed(1) + 'px'); av.style.setProperty('--hy', (dy * 2).toFixed(1) + 'px');
      g.style.setProperty('--px', dx.toFixed(3)); g.style.setProperty('--py', dy.toFixed(3));
    });
    g.addEventListener('focusin', e => {
      const id = e.target.id; away = id === 'gPw'; av.classList.toggle('away', away); av.classList.toggle('look', id === 'gEm' || id === 'gCode');
      if (away) { av.style.removeProperty('--hr'); say('Not looking. Promise.'); } else if (id === 'gEm' && ready) say('That is me. Your email, please.'); else if (id === 'gCode') say('One more step: the 6-digit code.');
    });
    g.addEventListener('focusout', () => setTimeout(() => { const a = document.activeElement; if (!a || !g.contains(a) || !/INPUT/.test(a.tagName)) { away = false; av.classList.remove('away', 'look'); } }, 0));
    g.addEventListener('input', () => { av.classList.remove('nod'); void av.offsetWidth; av.classList.add('nod'); });
    g.addEventListener('submit', () => { say('Opening your desk…'); }, true);
    new MutationObserver(() => {                                              // a message under the form means something went wrong: he shakes his head
      const msg = g.querySelector('#gMsg'), t = msg ? msg.textContent.trim() : '';
      if (t && t !== g._lastMsg) { av.classList.remove('shake'); void av.offsetWidth; av.classList.add('shake'); say(/code/i.test(t) ? 'That code did not work.' : /wrong/i.test(t) ? 'Hmm, not quite. Try again.' : 'Something is off.'); }
      g._lastMsg = t;
      if (g.querySelector('#gateM') && !g._mfa) { g._mfa = true; say('One more step: the 6-digit code.'); }
    }).observe(g, { subtree: true, childList: true, characterData: true });
  }
})();
