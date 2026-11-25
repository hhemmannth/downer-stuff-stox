/* SVG charts in the app's colours. No libraries: everything is drawn from the data files and your journal. */
'use strict';
App.charts = {};
const CV = { good: 'var(--good)', bad: 'var(--bad)', brand: 'var(--accent, var(--brand))', sun: 'var(--sun)', warn: 'var(--warn)', ink: 'var(--ink-2)', ink3: 'var(--ink-3)', c1: 'var(--c1)', c2: 'var(--c2)', c6: 'var(--c6)', c7: 'var(--c7)' };
const cv = c => CV[c] || c || 'var(--ink-2)';
const nice = p => Math.abs(p) >= 1000 ? Math.round(p).toLocaleString('en-IN') : Math.abs(p) >= 100 ? p.toFixed(1) : p.toFixed(2);

/* ---------- price chart (rebuilt 25 Nov 2026) ----------
   Clean by default: candles, the 9 EMA and the key levels only (items 7, 151); "Full" adds the minor levels, VWAP and extras (152).
   Zoom and drag (101, 155), double-tap to reset, a crosshair readout in a fixed corner (92, 117), tap a level for its meaning (31, 165),
   long-press for a note or an alert at that price (166, 167), volume with the 1.5x line and the trigger candle (105, 106, 172),
   R values on levels (112, 161), a risk-to-reward block (162), labels that never overlap with leader lines (8, 116), fading old zones (123),
   stage, news and results markers (107, 170), session shading and breaks (108, 129, 175), a "last candle" stamp and a late-data tint (9, 180),
   an overview strip (160), full screen (157, 158) and "save image" (140). One model per chart lives in App.charts._reg. */
App.charts._reg = {}; App.charts._view = {}; App.charts._seen = {};
const CPREF = () => Object.assign({ mode: store.get('tji_keylv', null) === false ? 'full' : 'clean', style: 'hollow', levels: true }, store.get('ds_chart', {}) || {});
App.charts.pref = CPREF; App.charts.setPref = (k, v) => { const p = CPREF(); p[k] = v; store.set('ds_chart', p); };
const LV_WHY = { 'Entry': 'Entry: the trade has triggered here.', 'Planned entry': 'Planned entry: a placeholder inside the zone so the stop and targets can be sized. It is not a signal; the trade starts only when the status turns TRIGGERED.',
  'SL': 'Stop-loss: beyond the zone and the swing it came from. If price closes here the idea is wrong.', 'Stop now': 'The stop as it stands now (moved to break-even or trailed after a target).',
  'T1': 'First target: take part off or trail from here.', 'T2': 'Second target.', 'T3': 'Third target: the stretch goal.', 'OB': 'Order block: the last opposite candle before the move that broke structure. Price often reacts on the way back.',
  'FVG': 'Fair value gap: a three-candle gap the move left behind. A pullback into it is part of your zone.', 'Fib': 'The .618 to .705 retracement of the last swing: the sweet spot of your pullback.',
  'CHoCH': 'Change of character: the first break against the old trend.', 'BOS': 'Break of structure: the break that confirmed the new direction.', 'Resistance': 'The nearest level above that could stop the move: it sets the room to target.',
  '1D zone': 'The daily zone (OB, FVG and fib together) where the setup is valid.', 'My entry': 'Your own entry from the journal.', 'My stop': 'Your own stop from the journal.', 'My exit': 'Where you closed the trade.', 'My target': 'Your own target from the journal.',
  '9 EMA': 'The 9-period EMA. Your trigger needs a close above it (below for shorts) on volume.', 'VWAP': 'Volume-weighted average price for the day.', 'PDH': 'Previous day high.', 'PDL': 'Previous day low.', 'Week H': 'This week high.', 'Week L': 'This week low.',
  'Day H': 'Today\'s high.', 'Day L': 'Today\'s low.', 'Alert': 'A price alert you set from the chart. It fires while the app is open.', 'Note': 'A note you pinned to this price.', 'Round': 'A round number: price often pauses at these.' };
const whyOf = l => l.why || LV_WHY[String(l.label || '').replace(/^✓ /, '').replace(/ \d.*$/, '')] || LV_WHY[String(l.label || '').split(' ')[0]] || '';
const isIntra = T => T.some(t => /\d{1,2}:\d{2}/.test(String(t)));
const dayOf = t => String(t).replace(/\s*\d{1,2}:\d{2}.*$/, '');
App.charts.candles = function (d, o = {}) {
  if (!d || !d.candles || !d.candles.length) return App.ui.empty('No candles', '');
  const id = o.id || ('c' + String(o.label || '').replace(/\W+/g, '_')), P = CPREF(), clean = P.mode !== 'full' && !o.forceFull, showLv = P.levels !== false;
  App.charts._reg[id] = { d, o };
  const W = Math.max(300, o.W || 720), narrow = W < 520, land = innerWidth > innerHeight && matchMedia('(pointer:coarse)').matches;
  const RW = narrow ? 96 : (P.mode === 'full' && !o.forceFull ? 196 : 150), PL = 4, MAXC = Math.floor((RW - 8) / 6.3), PW = W - RW - PL - 6, PT = 22;
  const PH = o.H || (land ? Math.max(170, Math.min(260, innerHeight * .52)) : narrow ? 240 : 310);
  App.charts._grp = App.charts._grp || {}; const N = d.candles.length, v0 = App.charts._view[id] || (o.zoomGroup && App.charts._grp[o.zoomGroup] ? { bars: App.charts._grp[o.zoomGroup] } : {}), defBars = o.bars || (narrow ? 60 : 90);
  const bars = Math.max(Math.min(20, N), Math.min(N, v0.bars || defBars)), end = Math.max(bars, Math.min(N, v0.end == null ? N : v0.end)), start = end - bars;
  const C = d.candles.slice(start, end), off = start, n = C.length, Vall = d.volume || null, V = Vall ? Vall.slice(start, end) : null, E = d.ema ? d.ema.slice(start, end) : null, T = (d.times || []).slice(start, end);
  const VH = (V || o.noVolNote) && o.volume !== false ? 44 : 0, OVH = N > bars ? 18 : 0, H = PT + PH + (VH ? VH + 12 : 0) + 22 + OVH;
  let levels = showLv ? (o.levels || []).filter(l => isNum(l.p)) : [], zones = showLv ? (o.zones || []).filter(z => isNum(z.lo) && isNum(z.hi)) : [];
  if (clean) { levels = levels.filter(l => (l.k || 2) >= 2 || /^(✓ )?(SL|Stop now|My )/.test(l.label || '')); zones = zones.filter(z => (z.k || 2) >= 2); }
  let lo = Math.min(...C.map(c => c[2])), hi = Math.max(...C.map(c => c[1])); const plo = lo, phi = hi;
  levels.filter(l => l.scale !== false).forEach(l => { lo = Math.min(lo, l.p); hi = Math.max(hi, l.p); });
  zones.filter(z => z.scale !== false).forEach(z => { lo = Math.min(lo, z.lo); hi = Math.max(hi, z.hi); });
  const pad = (hi - lo) * .06 || 1; lo -= pad; hi += pad;
  const X = i => PL + (i + .5) * PW / n, Y = p => PT + (hi - p) / (hi - lo) * PH, bw = Math.max(narrow ? 2 : 1.4, PW / n * .62), g = [], labs = [], last = C[n - 1][3];
  const intra = isIntra(T);
  /* sessions (gold Asia / London / New York) and market hours (129, 175), session breaks (108) */
  if (o.sessions) { let run = null; const SC = { asia: 'var(--c6)', london: 'var(--sun)', ny: 'var(--good)', off: 'var(--ink-3)' };
    for (let i = 0; i <= n; i++) { const s = i < n ? o.sessions(T[i]) : null; if (run && s !== run.s) { g.push(`<rect x="${X(run.i) - PW / n / 2}" y="${PT}" width="${(i - run.i) * PW / n}" height="${PH}" fill="${SC[run.s] || 'var(--ink-3)'}" opacity="${run.s === 'off' ? .05 : .045}"/>`); if (run.s !== 'off' && i - run.i > 4) g.push(`<text x="${X(run.i) - PW / n / 2 + 3}" y="${PT + 10}" font-size="9" fill="var(--ink-3)" opacity=".8">${run.s === 'ny' ? 'NEW YORK' : run.s.toUpperCase()}</text>`); run = null; } if (s && !run) run = { s, i }; } }
  if (intra) for (let i = 1; i < n; i++) if (dayOf(T[i]) !== dayOf(T[i - 1])) g.push(`<line x1="${X(i) - PW / n / 2}" x2="${X(i) - PW / n / 2}" y1="${PT}" y2="${PT + PH}" stroke="var(--line)" stroke-dasharray="2 4"/>`);
  /* grid: two light lines (91) */
  [1 / 3, 2 / 3].forEach(f => g.push(`<line x1="${PL}" x2="${PL + PW}" y1="${PT + PH * f}" y2="${PT + PH * f}" stroke="var(--line-2)" opacity=".7"/>`));
  if (o.stale) g.push(`<rect x="${PL}" y="${PT}" width="${PW}" height="${PH}" fill="var(--warn)" opacity=".06"/>`);
  /* zones: soft bands, dashed edge, older ones fade (90, 111, 123) */
  zones.forEach(z => { const fi = isNum(z.from) ? z.from - off : 0, x1 = isNum(z.from) ? Math.max(PL, X(fi) - bw) : PL, y1 = Y(Math.min(z.hi, hi)), y2 = Y(Math.max(z.lo, lo)); if (y2 <= y1) return;
    const age = isNum(z.from) ? Math.max(0, Math.min(1, (n - fi) / Math.max(n, 1))) : 0, op = .16 * (1 - .55 * age);
    g.push(`<rect x="${x1}" y="${y1}" width="${PL + PW - x1}" height="${Math.max(2, y2 - y1)}" fill="${cv(z.c)}" opacity="${op.toFixed(3)}"/><line x1="${x1}" x2="${PL + PW}" y1="${y1}" y2="${y1}" stroke="${cv(z.c)}" stroke-dasharray="4 3" opacity=".55"/><line x1="${x1}" x2="${PL + PW}" y1="${y2}" y2="${y2}" stroke="${cv(z.c)}" stroke-dasharray="4 3" opacity=".55"/>`);
    if (z.label) labs.push({ y: (y1 + y2) / 2, y0: (y1 + y2) / 2, t: z.label + (narrow || clean ? '' : ` ${nice(z.lo)}–${nice(z.hi)}`), c: cv(z.c), k: z.k || 1, why: whyOf(z) }); });
  /* risk-to-reward block (162) */
  const ref = o.entryRef; if (ref && isNum(ref.entry) && isNum(ref.sl) && showLv) { const x0 = PL + PW * .84, ww = PW * .16, ye = Y(ref.entry), ys = Y(Math.max(lo, Math.min(hi, ref.sl)));
    g.push(`<rect x="${x0}" y="${Math.min(ye, ys)}" width="${ww}" height="${Math.abs(ys - ye)}" fill="var(--bad)" opacity=".09"/>`);
    if (isNum(ref.t1)) { const yt = Y(Math.max(lo, Math.min(hi, ref.t1))); g.push(`<rect x="${x0}" y="${Math.min(ye, yt)}" width="${ww}" height="${Math.abs(yt - ye)}" fill="var(--good)" opacity=".09"/>`); } }
  /* trigger candle (106) */
  const tIdx = o.trigger ? (isNum(o.trigger.i) ? o.trigger.i - off : T.indexOf(o.trigger.t)) : -1;
  if (tIdx >= 0 && tIdx < n) g.push(`<rect x="${X(tIdx) - PW / n * .55}" y="${PT}" width="${PW / n * 1.1}" height="${PH + (VH ? VH + 12 : 0)}" fill="var(--accent, var(--brand))" opacity=".09"/>`);
  /* candles: hollow, filled or bars (153), thicker on phones (154) */
  const wk = narrow ? 1.2 : 1;
  for (let i = 0; i < n; i++) { const [O, Hh, L, Cc] = C[i], up = Cc >= O, x = X(i);
    if (P.style === 'bars') g.push(`<path d="M${x} ${Y(Hh)}V${Y(L)}M${x - bw / 2} ${Y(O)}H${x}M${x} ${Y(Cc)}H${x + bw / 2}" stroke="${up ? 'var(--ink)' : 'var(--ink-3)'}" stroke-width="${wk + .2}"/>`);
    else g.push(`<line x1="${x}" x2="${x}" y1="${Y(Hh)}" y2="${Y(L)}" stroke="var(--ink)" stroke-width="${wk}"/><rect x="${x - bw / 2}" y="${Y(Math.max(O, Cc))}" width="${bw}" height="${Math.max(1, Math.abs(Y(O) - Y(Cc)))}" fill="${up ? (P.style === 'filled' ? 'var(--good)' : 'var(--bg)') : (P.style === 'filled' ? 'var(--bad)' : 'var(--ink)')}" stroke="${P.style === 'filled' ? (up ? 'var(--good)' : 'var(--bad)') : 'var(--ink)'}" stroke-width="1"/>`); }
  /* 9 EMA: changes tone when price closes below it (173), value and slope in the label column (121, 171) */
  if (E) { let seg = [], below = null; const flush = () => { if (seg.length > 1) g.push(`<polyline points="${seg.join(' ')}" fill="none" stroke="${below ? 'var(--warn)' : 'var(--c6)'}" stroke-width="1.5" opacity="${below ? .75 : 1}"/>`); };
    E.forEach((v, i) => { if (!isNum(v)) return; const b = C[i][3] < v; if (below !== null && b !== below) { seg.push(`${X(i)},${Y(v)}`); flush(); seg = []; } below = b; seg.push(`${X(i)},${Y(v)}`); }); flush();
    const e1 = E[n - 1], e3 = E[Math.max(0, n - 4)]; if (isNum(e1) && e1 > lo && e1 < hi) labs.push({ y: Y(e1), y0: Y(e1), t: '9 EMA ' + (narrow ? '' : nice(e1) + ' ') + (e1 > e3 ? '↗' : e1 < e3 ? '↘' : '→'), c: 'var(--c6)', k: 1.5, why: LV_WHY['9 EMA'] }); }
  /* VWAP for intraday charts in Full view (174) */
  if (!clean && intra && V && o.vwap !== false) { let pv = 0, vv = 0, pts = []; for (let i = 0; i < n; i++) { if (i && dayOf(T[i]) !== dayOf(T[i - 1])) { if (pts.length > 1) g.push(`<polyline points="${pts.join(' ')}" fill="none" stroke="var(--sun)" stroke-width="1.1" stroke-dasharray="1 3"/>`); pts = []; pv = vv = 0; } const tp = (C[i][1] + C[i][2] + C[i][3]) / 3; pv += tp * (V[i] || 0); vv += V[i] || 0; if (vv) pts.push(`${X(i)},${Y(pv / vv)}`); }
    if (pts.length > 1) { g.push(`<polyline points="${pts.join(' ')}" fill="none" stroke="var(--sun)" stroke-width="1.1" stroke-dasharray="1 3"/>`); labs.push({ y: +pts[pts.length - 1].split(',')[1], y0: +pts[pts.length - 1].split(',')[1], t: 'VWAP', c: 'var(--sun)', k: 1, why: LV_WHY.VWAP }); } }
  /* comparison line (109), normalised to the first visible close */
  if (o.compare && o.compare.pts && !clean) { const cp = o.compare.pts.slice(-N).slice(start, end), b0 = cp.find(isNum), c0 = C[0][3]; if (b0) { const pts = cp.map((v, i) => isNum(v) ? `${X(i)},${Y(c0 * v / b0)}` : null).filter(Boolean); g.push(`<polyline points="${pts.join(' ')}" fill="none" stroke="var(--ink-3)" stroke-width="1" opacity=".55" stroke-dasharray="6 3"/>`); } }
  /* levels: R values (112, 161), distance (115), far ones faded (164) */
  levels.forEach(l => { if (l.p < lo || l.p > hi) return; const x1 = isNum(l.from) ? Math.max(PL, X(l.from - off)) : PL, far = l.p < plo - (phi - plo) * .25 || l.p > phi + (phi - plo) * .25;
    g.push(`<line x1="${x1}" x2="${PL + PW}" y1="${Y(l.p)}" y2="${Y(l.p)}" stroke="${cv(l.c)}" stroke-width="${l.w || 1.2}"${l.dash ? ' stroke-dasharray="5 4"' : ''} opacity="${far ? .45 : 1}"/>`);
    if (!l.label) return; const base = String(l.label).replace(/^✓ /, ''), R = ref && isNum(ref.entry) && isNum(ref.sl) && ref.entry !== ref.sl && /^(Entry|Planned entry|SL|Stop now|T\d)/.test(base) && !/^(Entry|Planned entry)$/.test(base) ? (l.p - ref.entry) / (ref.entry - ref.sl) : null;
    const dist = !narrow && !clean && last ? ` ${l.p >= last ? '+' : '−'}${Math.abs((l.p - last) / last * 100).toFixed(1)}%` : '';
    labs.push({ y: Y(l.p), y0: Y(l.p), t: l.label + (narrow ? '' : ' ' + nice(l.p)) + (R != null ? ` · ${R >= 0 ? '+' : '−'}${Math.abs(R).toFixed(1)}R` : '') + dist, c: cv(l.c), k: l.k || 2, why: whyOf(l), far, p: l.p }); });
  /* markers (pullback, sweep, entry...) and stage changes (107) */
  (o.marks || []).forEach(m => { let i = isNum(m.i) ? m.i - off : (m.t ? T.indexOf(m.t) : -1); if (i < 0 || i >= n || !isNum(m.p)) return; const cx = X(i), cy = Y(m.p), ty = m.below ? cy + 15 : cy - 8;
    g.push(`<circle cx="${cx}" cy="${cy}" r="3.4" fill="none" stroke="${cv(m.c)}" stroke-width="1.5"/><text x="${Math.min(Math.max(cx, 26), PL + PW - 26)}" y="${ty}" font-size="11" font-weight="700" text-anchor="middle" fill="${cv(m.c)}">${esc(m.label)}</text>`); });
  (o.stageMarks || []).forEach(m => { const i = T.indexOf(m.t); if (i < 0) return; const x = X(i); g.push(`<path d="M${x} ${PT}V${PT - 10}h7l-2 3 2 3h-7" fill="var(--accent, var(--brand))" opacity=".8"/><title>${esc(m.label)}</title>`); });
  /* volume with the 1.5x line (105) and the ratio on the trigger candle (172); or a note when there is no volume (130) */
  const vt = PT + PH + 10;
  if (V && VH) { const avg = i => { const a = Vall.slice(Math.max(0, i + off - 20), i + off).filter(isNum); return a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0; };
    const vmax = Math.max(...V, 1), A = V.map((_, i) => avg(i)), rule = o.volRule || 1.5;
    V.forEach((v, i) => { const h = v / vmax * VH, big = A[i] && v >= rule * A[i]; g.push(`<rect x="${X(i) - bw / 2}" y="${vt + VH - h}" width="${bw}" height="${h}" fill="var(--ink-2)" opacity="${big ? .6 : .22}"/>`); });
    const aL = A[n - 1] * rule; if (aL && aL < vmax) { const y = vt + VH - aL / vmax * VH; g.push(`<line x1="${PL}" x2="${PL + PW}" y1="${y}" y2="${y}" stroke="var(--ink-3)" stroke-dasharray="3 3"/><text x="${PL + PW + 6}" y="${y + 4}" font-size="10" fill="var(--ink-3)">${rule}× avg vol</text>`); }
    if (tIdx >= 0 && tIdx < n && A[tIdx]) { const r = V[tIdx] / A[tIdx]; g.push(`<text x="${X(tIdx)}" y="${vt - 2}" font-size="10.5" font-weight="700" text-anchor="middle" fill="${r >= rule ? 'var(--good)' : 'var(--warn)'}">${r.toFixed(1)}×</text>`); } }
  else if (VH && o.noVolNote) g.push(`<text x="${PL + 4}" y="${vt + VH / 2 + 4}" font-size="11" fill="var(--ink-3)">${esc(o.noVolNote)}</text>`);
  /* news and results dates on the time axis (170) */
  (o.events || []).forEach(ev => { let i = T.findIndex(t => String(t).startsWith(ev.t)); if (i < 0) return; const x = X(i), y = PT + PH + (VH ? VH + 12 : 0) + 2; g.push(`<path d="M${x - 4} ${y + 7}L${x} ${y}L${x + 4} ${y + 7}Z" fill="${ev.c ? cv(ev.c) : 'var(--sun)'}"><title>${esc(ev.label)}</title></path>`); });
  /* labels: never overlap; a leader line shows where a moved label belongs (8, 116) */
  labs.sort((a, b) => b.k - a.k); labs.length = Math.min(labs.length, narrow ? 7 : 11); labs.sort((a, b) => a.y - b.y); let lastY = PT - 6;
  labs.forEach(l => { l.y = Math.max(l.y, lastY + 13); lastY = l.y; }); const over = lastY - (PT + PH + 4); if (over > 0) labs.forEach(l => { l.y -= over; });
  const lt = labs.map((l, i) => `${Math.abs(l.y - l.y0) > 3 ? `<path d="M${PL + PW} ${l.y0}L${PL + PW + 4} ${l.y}" stroke="${l.c}" stroke-width=".8" opacity=".6" fill="none"/>` : ''}<g class="lvl" tabindex="0" role="button" data-why="${esc(l.why || '')}" data-lt="${esc(l.t)}"><text x="${PL + PW + 6}" y="${l.y + 4}" font-size="11.5" font-weight="650" fill="${l.c}" opacity="${l.far ? .55 : 1}">${esc(l.t.length > MAXC ? l.t.slice(0, MAXC - 1) + '…' : l.t)}</text></g>`).join('');
  const xt = [0, Math.floor(n / 2), n - 1].map(i => T[i] ? `<text x="${X(i)}" y="${PT + PH + (VH ? VH + 12 : 0) + 18}" font-size="10.5" text-anchor="${i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle'}" fill="var(--ink-3)">${esc(T[i])}</text>` : '').join('');
  /* last candle stamp (9), late tint text (180), corner note such as the Nifty trend (176), daily-limit note (169), ribbons (126, 127) */
  const top = [`<text x="${PL + 2}" y="12" font-size="10.5" fill="var(--ink-3)">${esc((d.times || [])[N - 1] ? (narrow ? 'Last ' : 'Last candle ') + (d.times || [])[N - 1] : '')}${o.stale ? ' · data late' : ''}</text>`];
  if (o.corner && !narrow) top.push(`<text x="${PL + PW}" y="12" font-size="10.5" text-anchor="end" fill="var(--ink-3)">${esc(o.corner)}</text>`);
  (o.ribbons || []).forEach((r, k) => top.push(`<rect x="${PL}" y="${PT + k * 4}" width="${PW}" height="3" fill="${cv(r.c)}" opacity=".5"><title>${esc(r.t)}</title></rect>`));
  if (o.block) top.push(`<text x="${PL + 4}" y="${PT + PH - 6}" font-size="10.5" font-weight="650" fill="var(--warn)">${esc(o.block)}</text>`);
  /* overview strip (160) */
  let ov = ''; if (OVH) { const all = d.candles.map(c => c[3]), alo = Math.min(...all), ahi = Math.max(...all), oy = H - OVH + 2, oh = OVH - 4, ox = i => PL + i / (N - 1) * PW, oyv = v => oy + (ahi - v) / ((ahi - alo) || 1) * oh;
    ov = `<g class="ovw"><polyline points="${all.map((v, i) => `${ox(i)},${oyv(v)}`).join(' ')}" fill="none" stroke="var(--ink-3)" stroke-width=".8" opacity=".7"/><rect x="${ox(start)}" y="${oy - 1}" width="${Math.max(4, ox(end - 1) - ox(start))}" height="${oh + 2}" fill="var(--accent, var(--brand))" opacity=".12" stroke="var(--accent, var(--brand))" stroke-opacity=".4" rx="2"/></g>`; }
  App.charts._reg[id].geo = { PL, PW, PT, PH, n, off, lo, hi, W, H, N, bars, end, start, T, C, V, E };
  const fresh = !App.charts._seen[id]; App.charts._seen[id] = 1;
  setTimeout(() => App.charts.bind(id), 0);
  const tb = o.toolbar === false ? '' : `<div class="ch-tb" role="toolbar" aria-label="Chart options">
    <button type="button" data-ch="mode" aria-pressed="${!clean}" title="Clean shows only the key levels">${clean ? 'Clean' : 'Full'}</button>
    <button type="button" data-ch="levels" aria-pressed="${!showLv}">${showLv ? 'Hide levels' : 'Show levels'}</button>
    <button type="button" data-ch="style">${P.style === 'hollow' ? 'Hollow' : P.style === 'filled' ? 'Filled' : 'Bars'}</button>
    ${end < N || bars < N ? `<button type="button" data-ch="fit">Fit</button>` : ''}${end < N ? `<button type="button" data-ch="now">Jump to now</button>` : ''}
    <span class="sp"></span><button type="button" data-ch="zout" aria-label="Zoom out" title="Zoom out (or Ctrl + scroll, or pinch)">−</button><button type="button" data-ch="zin" aria-label="Zoom in" title="Zoom in">+</button><button type="button" data-ch="fs" aria-label="Full screen" title="Full screen">⤢</button><button type="button" data-ch="png" aria-label="Save image" title="Save image">⤓</button></div>`;
  return `<div class="chw" data-chw="${esc(id)}">${tb}<div class="ch-box"><svg class="chart${fresh && !(App.ux && App.ux.reduced && App.ux.reduced()) ? ' draw-in' : ''}" data-chart="${esc(id)}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.label || 'Price chart')}">${top.join('')}${g.join('')}${lt}${xt}${ov}<g class="xh"></g></svg><div class="ch-read" aria-live="polite"></div><div class="ch-pop" hidden></div></div></div>`;
};

/* interaction layer: zoom, drag, pinch, double-tap reset, crosshair readout, level meaning, long-press note or alert, toolbar */
App.charts.redraw = id => { const box = document.querySelector(`[data-chw="${CSS.escape(id)}"]`), r = App.charts._reg[id]; if (!box || !r) return; const w = document.createElement('div'); w.innerHTML = App.charts.candles(r.d, r.o); box.replaceWith(w.firstElementChild); };
App.charts.bind = id => {
  const svg = document.querySelector(`svg[data-chart="${CSS.escape(id)}"]`); if (!svg || svg.dataset.bound) return; svg.dataset.bound = '1';
  const wrap = svg.closest('.chw'), R = App.charts._reg[id]; if (!R) return; const G = R.geo, read = wrap.querySelector('.ch-read'), pop = wrap.querySelector('.ch-pop'), xh = svg.querySelector('.xh');
  const V = () => App.charts._view[id] || (App.charts._view[id] = {}), sx = e => { const b = svg.getBoundingClientRect(); return (e.clientX - b.left) * G.W / b.width; }, sy = e => { const b = svg.getBoundingClientRect(); return (e.clientY - b.top) * G.H / b.height; };
  let raf = 0; const later = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; App.charts.redraw(id); }); };
  const setView = (bars, end) => { const v = V(); v.bars = Math.max(Math.min(20, G.N), Math.min(G.N, Math.round(bars))); if (R.o.zoomGroup) App.charts._grp[R.o.zoomGroup] = v.bars; v.end = Math.max(v.bars, Math.min(G.N, Math.round(end))); later(); };
  const idx = x => Math.max(0, Math.min(G.n - 1, Math.floor((x - G.PL) / (G.PW / G.n))));
  const price = y => G.hi - (y - G.PT) / G.PH * (G.hi - G.lo);
  const showX = e => { const x = sx(e), y = sy(e); if (x < G.PL || x > G.PL + G.PW || y < G.PT || y > G.PT + G.PH) { xh.innerHTML = ''; read.textContent = ''; return; }
    const i = idx(x), c = G.C[i], cx = G.PL + (i + .5) * G.PW / G.n; xh.innerHTML = `<line x1="${cx}" x2="${cx}" y1="${G.PT}" y2="${G.PT + G.PH}" stroke="var(--ink-3)" stroke-dasharray="2 3"/><line x1="${G.PL}" x2="${G.PL + G.PW}" y1="${y}" y2="${y}" stroke="var(--ink-3)" stroke-dasharray="2 3" opacity=".6"/>`;
    read.innerHTML = `<b>${esc(G.T[i] || '')}</b> O ${nice(c[0])} H ${nice(c[1])} L ${nice(c[2])} C <b>${nice(c[3])}</b>${G.V && isNum(G.V[i]) ? ' · Vol ' + Math.round(G.V[i]).toLocaleString('en-IN') : ''}${G.E && isNum(G.E[i]) ? ' · 9 EMA ' + nice(G.E[i]) : ''} · <span class="muted">cursor ${nice(price(y))}</span>`; };
  svg.addEventListener('wheel', e => { if (!e.ctrlKey && !e.metaKey) return; e.preventDefault(); const f = e.deltaY > 0 ? 1.15 : 1 / 1.15, x = sx(e), anchor = (x - G.PL) / G.PW, nb = G.bars * f; setView(nb, G.start + anchor * G.bars + (1 - anchor) * Math.max(Math.min(20, G.N), Math.min(G.N, nb))); }, { passive: false });
  const pts = new Map(); let drag = null, pinch = null, lp = null, lastTap = 0;
  svg.addEventListener('pointerdown', e => { svg.setPointerCapture(e.pointerId); pts.set(e.pointerId, e);
    if (pts.size === 1) { drag = { x: e.clientX, end: G.end, moved: false }; clearTimeout(lp); const ex = e; lp = setTimeout(() => { if (drag && !drag.moved) { drag = null; menu(ex); } }, 550); }
    if (pts.size === 2) { const [a, b] = [...pts.values()]; pinch = { d: Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY), bars: G.bars, end: G.end }; drag = null; clearTimeout(lp); } });
  svg.addEventListener('pointermove', e => { if (pts.has(e.pointerId)) pts.set(e.pointerId, e);
    if (pinch && pts.size === 2) { const [a, b] = [...pts.values()], d = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY); if (d > 10) setView(pinch.bars * pinch.d / d, pinch.end); return; }
    if (drag && pts.size === 1) { const dx = e.clientX - drag.x, per = svg.getBoundingClientRect().width * (G.PW / G.W) / G.n; if (Math.abs(dx) > 6) { drag.moved = true; clearTimeout(lp); } if (drag.moved) { setView(G.bars, drag.end - dx / per); return; } }
    showX(e); });
  const up = e => { pts.delete(e.pointerId); clearTimeout(lp); if (!pts.size) { if (drag && !drag.moved && e.type === 'pointerup') { const now = Date.now(); if (now - lastTap < 320) { delete App.charts._view[id]; later(); } lastTap = now; showX(e); } drag = null; pinch = null; } };
  svg.addEventListener('pointerup', up); svg.addEventListener('pointercancel', up); svg.addEventListener('pointerleave', e => { if (!pts.size) { xh.innerHTML = ''; read.textContent = ''; } });
  svg.addEventListener('dblclick', () => { delete App.charts._view[id]; later(); });
  svg.style.touchAction = 'pan-y';
  /* level meaning: tap to pin, tap again to close (31, 165) */
  svg.querySelectorAll('g.lvl').forEach(gl => { const open = () => { if (!gl.dataset.why) return; const same = pop.dataset.for === gl.dataset.lt && !pop.hidden; pop.hidden = same; pop.dataset.for = gl.dataset.lt; pop.innerHTML = `<b>${esc(gl.dataset.lt)}</b><span>${esc(gl.dataset.why)}</span>`; };
    gl.addEventListener('click', e => { e.stopPropagation(); open(); }); gl.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } }); gl.addEventListener('pointerdown', e => e.stopPropagation()); });
  pop.onclick = () => { pop.hidden = true; };
  /* long-press: a note or an alert at that price (166, 167) */
  function menu(e) { const y = sy(e); if (y < G.PT || y > G.PT + G.PH) return; const p = price(y); if (!R.o.onNote && !R.o.onAlert) return;
    pop.hidden = false; pop.dataset.for = ''; pop.innerHTML = `<b>At ${nice(p)}</b><span>${R.o.onAlert ? `<button type="button" class="btn sm" data-pa="alert">Alert me at this price</button> ` : ''}${R.o.onNote ? `<button type="button" class="btn sm" data-pa="note">Pin a note here</button>` : ''}</span>`;
    pop.querySelectorAll('[data-pa]').forEach(b => b.onclick = ev => { ev.stopPropagation(); pop.hidden = true; (b.dataset.pa === 'alert' ? R.o.onAlert : R.o.onNote)(+p.toFixed(2)); }); }
  /* toolbar */
  wrap.querySelectorAll('[data-ch]').forEach(b => b.onclick = () => { const k = b.dataset.ch, P = CPREF();
    if (k === 'mode') { App.charts.setPref('mode', P.mode === 'full' ? 'clean' : 'full'); store.set('tji_keylv', P.mode === 'full'); later(); }
    if (k === 'levels') { App.charts.setPref('levels', P.levels === false); later(); }
    if (k === 'style') { App.charts.setPref('style', { hollow: 'filled', filled: 'bars', bars: 'hollow' }[P.style] || 'hollow'); later(); }
    if (k === 'fit') { delete App.charts._view[id]; const v = V(); v.bars = G.N; v.end = G.N; later(); }
    if (k === 'now') { setView(G.bars, G.N); }
    if (k === 'zin' || k === 'zout') { const nb = G.bars * (k === 'zin' ? .75 : 1.33); setView(nb, G.end); }
    if (k === 'fs') App.charts.full(id);
    if (k === 'png') App.charts.savePng(svg, (R.o.label || 'chart').replace(/\W+/g, '-'), R.o.frame); });
  /* the overview strip jumps to where you tap (160) */
  const ovw = svg.querySelector('.ovw'); if (ovw) ovw.addEventListener('pointerdown', e => { e.stopPropagation(); const f = (sx(e) - G.PL) / G.PW; setView(G.bars, f * G.N + G.bars / 2); });
};
/* full screen with the key numbers on top (157), and a hint to turn the phone sideways (158) */
App.charts.full = id => { const r = App.charts._reg[id]; if (!r) return; const bg = document.createElement('div'); bg.className = 'modal-bg chfs';
  const portrait = innerHeight > innerWidth && matchMedia('(pointer:coarse)').matches;
  const drawIt = () => { const w = Math.min(1600, innerWidth - 24), h = Math.max(220, innerHeight - 190); bg.querySelector('.chfs-b').innerHTML = App.charts.candles(r.d, Object.assign({}, r.o, { id: id + ':fs', W: w, H: h })); };
  bg.innerHTML = `<div class="modal chfs-m" role="dialog" aria-label="Full-screen chart"><div class="mh"><h2>${esc(r.o.head || r.o.label || 'Chart')}</h2><button class="btn icon ghost" type="button" data-x aria-label="Close">✕</button></div>${portrait ? '<p class="help" style="padding:0 18px">Turn your phone sideways for a wider chart.</p>' : ''}<div class="chfs-b"></div></div>`;
  document.body.appendChild(bg); drawIt(); const onR = () => drawIt(); addEventListener('resize', onR);
  const close = () => { removeEventListener('resize', onR); bg.remove(); }; bg.onclick = e => { if (e.target === bg || e.target.closest('[data-x]')) close(); };
  addEventListener('keydown', function k(e) { if (e.key === 'Escape') { close(); removeEventListener('keydown', k); } }); };
/* save as an image with the theme colours resolved; an optional frame adds a title line (140, 200) */
/* share: the same framed image, through the phone's share sheet when it has one, otherwise saved (items 100, 200) */
App.charts.share = (svg, name, frame) => App.charts.savePng(svg, name, frame, true);
App.charts.savePng = (svg, name, frame, share) => {
  const cs = getComputedStyle(document.documentElement), probe = document.createElement('i'); document.body.appendChild(probe);
  const res = v => v.replace(/var\(([^)]+)\)/g, (m, inner) => { const parts = inner.split(','); const nm = parts[0].trim(); let val = cs.getPropertyValue(nm).trim(); if (!val && parts[1]) val = res(parts.slice(1).join(',').trim()); if (/^var\(/.test(val)) val = res(val); return val || '#888'; });
  const c = svg.cloneNode(true); c.querySelectorAll('.xh').forEach(x => x.remove()); c.removeAttribute('class');
  c.querySelectorAll('*').forEach(el => ['fill', 'stroke'].forEach(a => { const v = el.getAttribute(a); if (v && v.includes('var(')) el.setAttribute(a, res(v)); }));
  probe.remove(); const vb = svg.viewBox.baseVal, top = frame ? 46 : 0, W = vb.width, H = vb.height + top, sc = 2;
  c.setAttribute('width', W); c.setAttribute('height', vb.height); c.setAttribute('font-family', 'IBM Plex Sans, Arial, sans-serif');
  const xml = new XMLSerializer().serializeToString(c), img = new Image();
  img.onload = () => { const cv = document.createElement('canvas'); cv.width = W * sc; cv.height = H * sc; const x = cv.getContext('2d'); x.scale(sc, sc); x.fillStyle = res('var(--bg)') || '#000'; x.fillRect(0, 0, W, H);
    if (frame) { x.fillStyle = res('var(--ink)'); x.font = '700 16px Arial'; x.fillText(frame.title || '', 8, 20); x.fillStyle = res('var(--ink-3)'); x.font = '12px Arial'; x.fillText(frame.sub || '', 8, 38); x.textAlign = 'right'; x.fillText('DownerStuff · not advice', W - 8, 20); x.textAlign = 'left'; }
    x.drawImage(img, 0, top, W, vb.height); cv.toBlob(b => { if (share && navigator.canShare) { try { const f = new File([b], name + '.png', { type: 'image/png' }); if (navigator.canShare({ files: [f] })) { navigator.share({ files: [f], title: frame && frame.title || name }).catch(() => { }); return; } } catch (e) { } } const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = name + '.png'; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000); App.toast('Image saved'); }, 'image/png'); };
  img.onerror = () => App.toast('Could not make the image on this browser'); img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml);
};

/* Line chart (equity, R curve, rolling stats). series: [{pts:[y...], c, area}], labels: x labels. */
App.charts.line = function (series, o = {}) {
  const W = Math.max(280, o.W || 640), H = o.H || 200, PL = 52, PR = 10, PT = 10, PB = 24, PW = W - PL - PR, PH = H - PT - PB;
  const all = series.flatMap(s => s.pts).filter(isNum); if (all.length < 2) return App.ui.empty('Not enough data yet', 'This chart fills in as trades are closed.');
  let lo = Math.min(...all, o.zero ? 0 : Infinity), hi = Math.max(...all, o.zero ? 0 : -Infinity); if (hi === lo) { hi += 1; lo -= 1; } const pad = (hi - lo) * .08; lo -= pad; hi += pad;
  const n = Math.max(...series.map(s => s.pts.length)), X = i => PL + (n <= 1 ? PW / 2 : i * PW / (n - 1)), Y = v => PT + (hi - v) / (hi - lo) * PH, fy = o.fmt || (v => nice(v)), g = [];
  [0, .5, 1].forEach(f => { const v = hi - f * (hi - lo); g.push(`<line x1="${PL}" x2="${W - PR}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line-2)" opacity=".7"/><text x="${PL - 6}" y="${Y(v) + 4}" font-size="10.5" text-anchor="end" fill="var(--ink-3)">${esc(fy(v))}</text>`); });
  if (o.zero && lo < 0 && hi > 0) g.push(`<line x1="${PL}" x2="${W - PR}" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--ink-3)" stroke-dasharray="3 3"/>`);
  series.forEach(s => { const pts = s.pts.map((v, i) => isNum(v) ? `${X(i)},${Y(v)}` : null).filter(Boolean); const li = s.pts.map(isNum).lastIndexOf(true);
    if (li >= 0 && o.endLabel !== false && (s.name || series.length === 1)) g.push(`<text x="${Math.min(X(li) + 4, W - PR)}" y="${Y(s.pts[li]) - 6}" font-size="10.5" font-weight="700" text-anchor="end" fill="${cv(s.c)}">${esc((s.name ? s.name + ' ' : '') + fy(s.pts[li]))}</text>`);
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
  if (o.line) { const pts = o.line.map((v, i) => isNum(v) ? `${PL + i * bw + bw / 2},${Y(v)}` : null).filter(Boolean); if (pts.length > 1) g.push(`<polyline points="${pts.join(' ')}" fill="none" stroke="var(--ink-2)" stroke-width="1.6" stroke-dasharray="4 3"/><text x="${pts[pts.length - 1].split(',')[0]}" y="${+pts[pts.length - 1].split(',')[1] - 6}" font-size="10" text-anchor="end" fill="var(--ink-2)">3-mo avg</text>`); }
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
