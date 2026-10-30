/* SVG charts in the app's colours. No libraries: everything is drawn from the data files and your journal. */
'use strict';
App.charts = {};
const CV = { good: 'var(--good)', bad: 'var(--bad)', brand: 'var(--brand)', sun: 'var(--sun)', warn: 'var(--warn)', ink: 'var(--ink-2)', ink3: 'var(--ink-3)', c1: 'var(--c1)', c2: 'var(--c2)', c6: 'var(--c6)', c7: 'var(--c7)' };
const cv = c => CV[c] || c || 'var(--ink-2)';
const nice = p => Math.abs(p) >= 1000 ? Math.round(p).toLocaleString('en-IN') : Math.abs(p) >= 100 ? p.toFixed(1) : p.toFixed(2);

/* Candles with zones, levels and markers, labels in a right-hand column (no overlaps, only the key levels). */
App.charts.candles = function (d, o = {}) {
  if (!d || !d.candles || !d.candles.length) return App.ui.empty('No candles', '');
  const W = Math.max(300, o.W || 720), narrow = W < 520, RW = narrow ? 92 : 128, PL = 4, PW = W - RW - PL - 6, PT = 10, PH = o.H || (narrow ? 230 : 300), VH = d.volume && o.volume !== false ? 40 : 0, H = PT + PH + (VH ? VH + 12 : 0) + 22;
  const C = d.candles.slice(-(o.bars || (narrow ? 60 : 90))), off = d.candles.length - C.length, n = C.length, V = d.volume ? d.volume.slice(-n) : null, E = d.ema ? d.ema.slice(-n) : null, T = d.times ? d.times.slice(-n) : [];
  const levels = (o.levels || []).filter(l => isNum(l.p)), zones = (o.zones || []).filter(z => isNum(z.lo) && isNum(z.hi));
  let lo = Math.min(...C.map(c => c[2])), hi = Math.max(...C.map(c => c[1]));
  levels.filter(l => l.scale !== false).forEach(l => { lo = Math.min(lo, l.p); hi = Math.max(hi, l.p); });
  zones.filter(z => z.scale !== false).forEach(z => { lo = Math.min(lo, z.lo); hi = Math.max(hi, z.hi); });
  const pad = (hi - lo) * .06 || 1; lo -= pad; hi += pad;
  const X = i => PL + (i + .5) * PW / n, Y = p => PT + (hi - p) / (hi - lo) * PH, bw = Math.max(1.2, PW / n * .62), g = [], labs = [];
  [0.25, .5, .75].forEach(f => g.push(`<line x1="${PL}" x2="${PL + PW}" y1="${PT + PH * f}" y2="${PT + PH * f}" stroke="var(--line-2)"/>`));
  zones.forEach(z => { const x1 = isNum(z.from) ? Math.max(PL, X(z.from - off) - bw) : PL, y1 = Y(Math.min(z.hi, hi)), y2 = Y(Math.max(z.lo, lo)); if (y2 <= y1) return;
    g.push(`<rect x="${x1}" y="${y1}" width="${PL + PW - x1}" height="${Math.max(2, y2 - y1)}" fill="${cv(z.c)}" opacity=".15"/><rect x="${x1}" y="${y1}" width="${PL + PW - x1}" height="${Math.max(2, y2 - y1)}" fill="none" stroke="${cv(z.c)}" stroke-width=".8" opacity=".5"/>`);
    if (z.label) labs.push({ y: (y1 + y2) / 2, t: z.label, c: cv(z.c), k: z.k || 1 }); });
  for (let i = 0; i < n; i++) { const [O, Hh, L, Cc] = C[i], col = Cc >= O ? 'var(--good)' : 'var(--bad)';
    g.push(`<line x1="${X(i)}" x2="${X(i)}" y1="${Y(Hh)}" y2="${Y(L)}" stroke="${col}" stroke-width="1"/><rect x="${X(i) - bw / 2}" y="${Y(Math.max(O, Cc))}" width="${bw}" height="${Math.max(1, Math.abs(Y(O) - Y(Cc)))}" fill="${col}"/>`); }
  if (E) g.push(`<polyline points="${E.map((v, i) => `${X(i)},${Y(v)}`).join(' ')}" fill="none" stroke="var(--c6)" stroke-width="1.4"/>`);
  levels.forEach(l => { if (l.p < lo || l.p > hi) return; const x1 = isNum(l.from) ? Math.max(PL, X(l.from - off)) : PL;
    g.push(`<line x1="${x1}" x2="${PL + PW}" y1="${Y(l.p)}" y2="${Y(l.p)}" stroke="${cv(l.c)}" stroke-width="${l.w || 1.2}"${l.dash ? ' stroke-dasharray="5 4"' : ''}/>`);
    if (l.label) labs.push({ y: Y(l.p), t: l.label + (narrow ? '' : ' ' + nice(l.p)), c: cv(l.c), k: l.k || 2 }); });
  (o.marks || []).forEach(m => { let i = isNum(m.i) ? m.i - off : (m.t ? T.indexOf(m.t) : -1); if (i < 0 || i >= n || !isNum(m.p)) return; const cx = X(i), cy = Y(m.p), ty = m.below ? cy + 15 : cy - 8;
    g.push(`<circle cx="${cx}" cy="${cy}" r="3.4" fill="none" stroke="${cv(m.c)}" stroke-width="1.5"/><text x="${Math.min(Math.max(cx, 26), PL + PW - 26)}" y="${ty}" font-size="11" font-weight="700" text-anchor="middle" fill="${cv(m.c)}">${esc(m.label)}</text>`); });
  if (V) { const vmax = Math.max(...V, 1), vt = PT + PH + 10; V.forEach((v, i) => { const h = v / vmax * VH; g.push(`<rect x="${X(i) - bw / 2}" y="${vt + VH - h}" width="${bw}" height="${h}" fill="var(--ink-3)" opacity=".3"/>`); }); }
  labs.sort((a, b) => b.k - a.k); labs.length = Math.min(labs.length, narrow ? 7 : 10); labs.sort((a, b) => a.y - b.y); let last = -99;
  labs.forEach(l => { l.y = Math.max(l.y, last + 13); last = l.y; });
  const lt = labs.map(l => `<text x="${PL + PW + 6}" y="${l.y + 4}" font-size="11.5" font-weight="650" fill="${l.c}">${esc(l.t)}</text>`).join('');
  const xt = [0, Math.floor(n / 2), n - 1].map(i => T[i] ? `<text x="${X(i)}" y="${H - 6}" font-size="10.5" text-anchor="${i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle'}" fill="var(--ink-3)">${esc(T[i])}</text>` : '').join('');
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.label || 'Price chart')}">${g.join('')}${lt}${xt}</svg>`;
};

/* Line chart (equity, R curve, rolling stats). series: [{pts:[y...], c, area}], labels: x labels. */
App.charts.line = function (series, o = {}) {
  const W = Math.max(280, o.W || 640), H = o.H || 200, PL = 52, PR = 10, PT = 10, PB = 24, PW = W - PL - PR, PH = H - PT - PB;
  const all = series.flatMap(s => s.pts).filter(isNum); if (all.length < 2) return App.ui.empty('Not enough data yet', 'This chart fills in as trades are closed.');
  let lo = Math.min(...all, o.zero ? 0 : Infinity), hi = Math.max(...all, o.zero ? 0 : -Infinity); if (hi === lo) { hi += 1; lo -= 1; } const pad = (hi - lo) * .08; lo -= pad; hi += pad;
  const n = Math.max(...series.map(s => s.pts.length)), X = i => PL + (n <= 1 ? PW / 2 : i * PW / (n - 1)), Y = v => PT + (hi - v) / (hi - lo) * PH, fy = o.fmt || (v => nice(v)), g = [];
  [0, .5, 1].forEach(f => { const v = hi - f * (hi - lo); g.push(`<line x1="${PL}" x2="${W - PR}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line-2)"/><text x="${PL - 6}" y="${Y(v) + 4}" font-size="10.5" text-anchor="end" fill="var(--ink-3)">${esc(fy(v))}</text>`); });
  if (o.zero && lo < 0 && hi > 0) g.push(`<line x1="${PL}" x2="${W - PR}" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--ink-3)" stroke-dasharray="3 3"/>`);
  series.forEach(s => { const pts = s.pts.map((v, i) => isNum(v) ? `${X(i)},${Y(v)}` : null).filter(Boolean);
    if (s.area) g.push(`<polygon points="${X(0)},${Y(Math.max(lo, Math.min(hi, 0)))} ${pts.join(' ')} ${X(s.pts.length - 1)},${Y(Math.max(lo, Math.min(hi, 0)))}" fill="${cv(s.c)}" opacity=".13"/>`);
    g.push(`<polyline points="${pts.join(' ')}" fill="none" stroke="${cv(s.c)}" stroke-width="${s.w || 2}" stroke-linejoin="round"/>`); });
  const L = o.labels || []; if (L.length) [0, Math.floor((L.length - 1) / 2), L.length - 1].forEach((i, k) => g.push(`<text x="${X(i)}" y="${H - 6}" font-size="10.5" text-anchor="${k === 0 ? 'start' : k === 2 ? 'end' : 'middle'}" fill="var(--ink-3)">${esc(L[i] || '')}</text>`));
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.label || 'Line chart')}">${g.join('')}</svg>`;
};

/* Vertical bars with signed values (monthly P&L, R histogram). items: [{l, v, c?}] */
App.charts.bars = function (items, o = {}) {
  if (!items.length) return App.ui.empty('Nothing to show yet', '');
  const W = Math.max(280, o.W || 640), H = o.H || 190, PL = o.noAxis ? 6 : 52, PR = 8, PT = 14, PB = 24, PW = W - PL - PR, PH = H - PT - PB;
  const vs = items.map(x => x.v), lo = Math.min(0, ...vs), hi = Math.max(0, ...vs) || 1, Y = v => PT + (hi - v) / ((hi - lo) || 1) * PH, bw = PW / items.length, g = [], fy = o.fmt || nice;
  if (!o.noAxis) [hi, lo].forEach(v => g.push(`<text x="${PL - 6}" y="${Y(v) + 4}" font-size="10.5" text-anchor="end" fill="var(--ink-3)">${esc(fy(v))}</text>`));
  g.push(`<line x1="${PL}" x2="${W - PR}" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--line)"/>`);
  const every = Math.ceil(items.length / (W < 480 ? 6 : 12));
  items.forEach((x, i) => { const y = Math.min(Y(0), Y(x.v)), h = Math.max(1, Math.abs(Y(x.v) - Y(0))), c = x.c || (x.v >= 0 ? 'var(--good)' : 'var(--bad)');
    g.push(`<rect x="${PL + i * bw + bw * .15}" y="${y}" width="${bw * .7}" height="${h}" rx="3" fill="${cv(c)}"><title>${esc(x.l)}: ${esc(fy(x.v))}</title></rect>`);
    if (i % every === 0 || i === items.length - 1) g.push(`<text x="${PL + i * bw + bw / 2}" y="${H - 6}" font-size="10.5" text-anchor="middle" fill="var(--ink-3)">${esc(x.l)}</text>`); });
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.label || 'Bar chart')}">${g.join('')}</svg>`;
};

/* Tiny sparkline for setup cards: daily closes with the entry zone shaded. */
App.charts.spark = function (cl, z = {}) {
  if (!cl || cl.length < 5) return ''; const W = 300, H = 54; let lo = Math.min(...cl), hi = Math.max(...cl);
  [z.lo, z.hi, z.sl].forEach(v => { if (isNum(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }); const p = (hi - lo) * .08 || 1; lo -= p; hi += p;
  const X = i => i * W / (cl.length - 1), Y = v => (hi - v) / (hi - lo) * H, up = cl[cl.length - 1] >= cl[0];
  const zone = isNum(z.lo) && isNum(z.hi) ? `<rect x="0" y="${Y(z.hi)}" width="${W}" height="${Math.max(2, Y(z.lo) - Y(z.hi))}" fill="var(--brand)" opacity=".13"/>` : '';
  const sl = isNum(z.sl) ? `<line x1="0" x2="${W}" y1="${Y(z.sl)}" y2="${Y(z.sl)}" stroke="var(--bad)" stroke-dasharray="4 3" stroke-width="1"/>` : '';
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="width:100%;height:46px;display:block" aria-hidden="true">${zone}${sl}<polyline points="${cl.map((v, i) => `${X(i)},${Y(v)}`).join(' ')}" fill="none" stroke="${up ? 'var(--good)' : 'var(--brand)'}" stroke-width="1.8" vector-effect="non-scaling-stroke"/></svg>`;
};

/* Horizontal bar inside a table cell. */
App.charts.hbar = (v, max, c) => { if (!isNum(v) || !max) return ''; const w = Math.min(100, Math.abs(v) / max * 50); return `<i style="left:${v >= 0 ? 50 : 50 - w}%;width:${w}%;background:${c || (v >= 0 ? 'var(--good)' : 'var(--bad)')}"></i><i style="left:50%;width:1px;background:var(--line);opacity:1"></i>`; };
