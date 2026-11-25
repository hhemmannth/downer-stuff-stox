/* DownerStuff journal additions (25 Nov 2026, batch 6). Loaded after journal.js, vault.js and fills.js; it extends the trade form and the
   Journal page without changing how trades are stored or how P&L is worked out. New fields are additive (bin, hist, notes3, att, templates,
   goals, reviews), so an older copy of the app simply ignores them. */
(() => {
'use strict';
const JR = App.journal;
const J = () => JR.J();

/* ---------- 30-day recycle bin (item 208) and edit history with undo (item 207) ---------- */
JR.bin = () => { const j = J(); j.bin = (j.bin || []).filter(b => Date.now() - new Date(b.at).getTime() < 30 * 864e5); return j.bin; };
JR.restoreBin = id => { const j = J(), b = JR.bin().find(x => x.t.id === id); if (!b) return; j.trades.push(b.t); j.bin = j.bin.filter(x => x !== b); JR.touch(); JR.persist(); App.toast('Trade restored'); App.render(); };
JR.purgeBin = id => { const j = J(); j.bin = JR.bin().filter(x => x.t.id !== id); JR.touch(); JR.persist(); App.render(); };
const HKEYS = ['d', 'tm', 'inst', 'cat', 'setup', 'tf', 'dir', 'grade', 'qty', 'entry', 'sl', 'tgt', 'exit', 'xd', 'xtm', 'chg', 'xt', 'emo', 'brk', 'note', 'ovr', 'mae', 'mfe'];
JR.undo = (id, k) => { const j = J(), t = j.trades.find(x => x.id === id); if (!t || !t.hist || !t.hist[k]) return; const h = t.hist[k];
  Object.entries(h.before).forEach(([key, v]) => { t[key] = v; }); t.hist = t.hist.slice(0, k); JR.touch(); JR.persist(); App.toast('Change undone'); App.render(); };

/* ---------- a minimal .xlsx writer (item 47): real Excel files without a library (stored zip, inline strings) ---------- */
const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return b => { let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = t[(c ^ b[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }; })();
function zip(files) { const enc = new TextEncoder(), parts = [], cd = []; let off = 0;
  files.forEach(([name, text]) => { const nb = enc.encode(name), db = enc.encode(text), crc = CRC(db), h = new DataView(new ArrayBuffer(30));
    h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(8, 0, true); h.setUint32(14, crc, true); h.setUint32(18, db.length, true); h.setUint32(22, db.length, true); h.setUint16(26, nb.length, true);
    parts.push(new Uint8Array(h.buffer), nb, db); const c = new DataView(new ArrayBuffer(46)); c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint32(16, crc, true); c.setUint32(20, db.length, true); c.setUint32(24, db.length, true); c.setUint16(28, nb.length, true); c.setUint32(42, off, true);
    cd.push(new Uint8Array(c.buffer), nb); off += 30 + nb.length + db.length; });
  const cdLen = cd.reduce((a, b) => a + b.length, 0), e = new DataView(new ArrayBuffer(22)); e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.length, true); e.setUint16(10, files.length, true); e.setUint32(12, cdLen, true); e.setUint32(16, off, true);
  return new Blob([...parts, ...cd, new Uint8Array(e.buffer)], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }); }
JR.xlsx = (sheets, name) => { const x = s => String(s == null ? '' : s).replace(/[<>&"]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c])), col = i => { let s = ''; i++; while (i) { const m = (i - 1) % 26; s = String.fromCharCode(65 + m) + s; i = Math.floor((i - 1) / 26); } return s; };
  const ws = rows => `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetData>${rows.map((r, ri) => `<row r="${ri + 1}">${r.map((v, ci) => { const ref = col(ci) + (ri + 1); return typeof v === 'number' && isFinite(v) ? `<c r="${ref}"><v>${v}</v></c>` : v == null || v === '' ? '' : `<c r="${ref}" t="inlineStr"${ri === 0 ? ' s="1"' : ''}><is><t xml:space="preserve">${x(v)}</t></is></c>`; }).join('')}</row>`).join('')}</sheetData></worksheet>`;
  const files = [['[Content_Types].xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>${sheets.map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('')}</Types>`],
    ['_rels/.rels', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`],
    ['xl/workbook.xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${sheets.map(([n], i) => `<sheet name="${x(n).slice(0, 31)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join('')}</sheets></workbook>`],
    ['xl/_rels/workbook.xml.rels', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${sheets.map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join('')}<Relationship Id="rId${sheets.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`],
    ['xl/styles.xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>`],
    ...sheets.map(([, rows], i) => [`xl/worksheets/sheet${i + 1}.xml`, ws(rows)])];
  const a = document.createElement('a'); a.href = URL.createObjectURL(zip(files)); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500); };
JR.exportXlsx = () => { const T = JR.enrich(), j = J();
  const head = ['Date', 'Time', 'Instrument', 'Category', 'Setup', 'Timeframe', 'Direction', 'Grade', 'Qty', 'Entry', 'Stop', 'Target', 'Exit', 'Exit date', 'Charges', 'Net P&L', 'R', 'Result', 'Rule break', 'Rules ticked', 'Emotion', 'Notes'];
  const rows = T.map(t => [t.d, t.tm, t.inst, t.cat, t.setup, t.tf, t.dir, t.grade, t.q, t.entry, t.sl, t.tgt, t.exit, t.xd || (t.xdUnknown ? 'unknown' : ''), t.chg, t.net != null ? Math.round(t.net * 100) / 100 : null, t.r != null ? Math.round(t.r * 100) / 100 : null, t.open ? 'Open' : t.res, t.brk, t.chk && t.chk.n ? `${t.chk.ok}/${t.chk.n}` : '', t.emo, t.note]);
  const set = Object.entries(j.set || {}).map(([k, v]) => [k, v]);
  JR.xlsx([['Trades', [head, ...rows]], ['Settings', [['Setting', 'Value'], ...set]]], (j.name || 'journal').replace(/[^\w]+/g, '-') + '.xlsx'); App.toast('Excel file saved'); };

/* ---------- broker CSV import with column matching and a duplicate check (item 243) ---------- */
const csvRows = text => { const out = []; let row = [], cur = '', q = false; for (let i = 0; i < text.length; i++) { const c = text[i];
  if (q) { if (c === '"' && text[i + 1] === '"') { cur += '"'; i++; } else if (c === '"') q = false; else cur += c; } else if (c === '"') q = true; else if (c === ',') { row.push(cur); cur = ''; } else if (c === '\n' || c === '\r') { if (c === '\r' && text[i + 1] === '\n') i++; row.push(cur); cur = ''; if (row.some(x => x.trim())) out.push(row); row = []; } else cur += c; }
  row.push(cur); if (row.some(x => x.trim())) out.push(row); return out; };
const COLMAP = { symbol: /^(symbol|tradingsymbol|trading symbol|scrip|instrument|stock|script name)$/i, side: /^(trade_type|trade type|buy\/sell|side|transaction type|type|action)$/i, qty: /^(quantity|qty|traded qty|filled qty)$/i, price: /^(price|trade price|avg price|average price|rate|traded price)$/i,
  date: /^(trade_date|trade date|date|order date)$/i, time: /^(order_execution_time|execution time|trade time|time|order time)$/i, id: /^(trade_id|trade id|order_id|order id|fill id)$/i, product: /^(product|product type|segment)$/i };
JR.parseBrokerCsv = text => { const R = csvRows(text); if (R.length < 2) throw new Error('No rows found'); const H = R[0].map(h => h.trim()), idx = {};
  Object.entries(COLMAP).forEach(([k, re]) => { idx[k] = H.findIndex(h => re.test(h)); });
  const miss = ['symbol', 'side', 'qty', 'price', 'date'].filter(k => idx[k] < 0); if (miss.length) throw new Error('Could not find these columns: ' + miss.join(', ') + '. Found: ' + H.join(', '));
  return R.slice(1).map((r, n) => { const g = k => idx[k] >= 0 ? String(r[idx[k]] || '').trim() : ''; let d = g('date'); const m = d.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})/); if (m) d = `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`; d = d.slice(0, 10);
    let tm = g('time'); const tmm = tm.match(/(\d{1,2}):(\d{2})/); tm = tmm ? tmm[1].padStart(2, '0') + ':' + tmm[2] : '09:15';
    const side = /^s/i.test(g('side')) ? 'SELL' : 'BUY', prod = /mis|intraday/i.test(g('product')) ? 'INTRADAY' : /nrml|fo|opt|fut/i.test(g('product')) ? 'CARRYFORWARD' : 'DELIVERY';
    return { fill_id: g('id') || `csv${n}`, symbol: g('symbol').toUpperCase(), side, qty: +g('qty').replace(/,/g, ''), price: +g('price').replace(/,/g, ''), product: prod, filled_at: new Date(`${d}T${tm}:00+05:30`).toISOString() }; }).filter(f => f.symbol && f.qty > 0 && f.price > 0 && !isNaN(new Date(f.filled_at))); };
JR.importBroker = file => new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => { try {
  const fills = JR.parseBrokerCsv(String(r.result)), props = window.Fills.propose(fills, JR.enrich().filter(t => t.open)).filter(p => p.kind === 'trade'), j = J(); let added = 0, dup = 0;
  props.forEach(p => { const same = j.trades.some(t => String(t.inst).toUpperCase() === String(p.inst).toUpperCase() && t.d === p.d && Math.abs((+t.entry || 0) - p.entry) < 0.011 && Math.abs((+t.qty || 0) - p.qty) < 1e-6) || j.trades.some(t => String(t.note || '').includes('BR:' + p.key));
    if (same) { dup++; return; } const o = window.Fills.prefill(p); o.id = 't' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); o.note = (o.note || '').replace('from Angel One fills', 'from your broker CSV'); j.trades.push(o); added++; });
  JR.touch(); JR.persist(); ok({ added, dup, fills: fills.length }); } catch (e) { bad(e); } }; r.onerror = () => bad(new Error('Could not read the file')); r.readAsText(file); });

/* ---------- journal data-health check (items 204, 248) ---------- */
JR.health = () => { const T = JR.enrich(), out = [], seen = {};
  T.forEach(t => { const k = [String(t.inst).toUpperCase(), t.d, t.entry, t.qty, t.dir].join('|');
    if (seen[k]) out.push({ kind: 'dup', t, other: seen[k], txt: `Looks like a duplicate of the ${seen[k].d} ${seen[k].inst} trade (same day, entry, quantity)` }); else seen[k] = t;
    if (t.closed && t.xdUnknown) out.push({ kind: 'xd', t, txt: 'Exit date missing: the P&L counts in no day, week or month' });
    if (!isNum(t.sl)) out.push({ kind: 'sl', t, txt: 'No stop-loss: R and risk cannot be worked out' });
    if (isNum(t.exit) && isNum(t.entry) && t.entry > 0 && Math.abs(t.exit / t.entry - 1) > .5 && t.cat !== 'Options') out.push({ kind: 'odd', t, txt: `Exit ${fmt(t.exit)} is more than 50% away from entry ${fmt(t.entry)}: a typo?` });
    if (isNum(t.sl) && isNum(t.entry) && ((t.dir !== 'Short' && t.sl >= t.entry) || (t.dir === 'Short' && t.sl <= t.entry)) && t.xt !== 'Trail') out.push({ kind: 'side', t, txt: 'Stop is on the wrong side of the entry' }); });
  return out; };

/* ---------- small helpers ---------- */
const ruleScore = t => t.chk && t.chk.n ? t.chk.ok / t.chk.n : null;
JR.ruleScore = ruleScore;
const dot = s => s == null ? '' : `<span class="rdot ${s >= .9 ? 'ok' : s >= .6 ? 'warn' : 'bad'}" title="Rules ticked: ${Math.round(s * 100)}%"></span>`;
const pastedTrade = txt => { const s = String(txt || ''), o = {}, up = s.toUpperCase();
  const side = up.match(/\b(BUY|BOUGHT|LONG|SELL|SOLD|SHORT)\b/); if (side) o.dir = /SELL|SOLD|SHORT/.test(side[1]) ? 'Short' : 'Long';
  const qty = s.match(/(?:qty|quantity|shares|lots?)\s*[:=]?\s*([\d,]+)/i) || s.match(/\b([\d,]+)\s*(?:shares|qty|nos)\b/i) || s.match(/\b([\d,]+)\s*(?:@|at\s)/i); if (qty) o.qty = +qty[1].replace(/,/g, '');
  const px = s.match(/(?:@|at|price|rate|avg)\s*[:=]?\s*₹?\s*([\d,]+(?:\.\d+)?)/i); if (px) o.entry = +px[1].replace(/,/g, '');
  const sl = s.match(/(?:sl|stop(?:-loss)?)\s*[:=]?\s*₹?\s*([\d,]+(?:\.\d+)?)/i); if (sl) o.sl = +sl[1].replace(/,/g, '');
  const tg = s.match(/(?:tgt|target|t1)\s*[:=]?\s*₹?\s*([\d,]+(?:\.\d+)?)/i); if (tg) o.tgt = +tg[1].replace(/,/g, '');
  const d = s.match(/(\d{4})-(\d{2})-(\d{2})/) || s.match(/(\d{1,2})[-/](\d{1,2})[-/](\d{4})/); if (d) o.d = d[1].length === 4 ? `${d[1]}-${d[2]}-${d[3]}` : `${d[3]}-${d[2].padStart(2, '0')}-${d[1].padStart(2, '0')}`;
  const skip = new Set(['BUY', 'SELL', 'BOUGHT', 'SOLD', 'LONG', 'SHORT', 'QTY', 'NSE', 'BSE', 'EQ', 'CNC', 'MIS', 'NRML', 'AT', 'SL', 'TGT', 'LIMIT', 'MARKET', 'PRICE', 'INR', 'RS', 'TARGET', 'STOP', 'ORDER', 'TRADE']);
  const sym = (up.match(/\b[A-Z][A-Z0-9&-]{1,19}\b/g) || []).find(w => !skip.has(w) && !/^\d/.test(w)); if (sym) o.inst = sym;
  if (/\d{3,5}\s*(CE|PE)\b/.test(up)) { o.cat = 'Options'; const m = up.match(/([A-Z]+)\s*(\d{3,6})\s*(CE|PE)/); if (m) o.inst = `${m[1]} ${m[2]} ${m[3]}`; }
  return o; };
JR.pastedTrade = pastedTrade;
const shrink = file => new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => { const im = new Image(); im.onload = () => { const k = Math.min(1, 900 / Math.max(im.width, im.height)), c = document.createElement('canvas'); c.width = Math.round(im.width * k); c.height = Math.round(im.height * k); c.getContext('2d').drawImage(im, 0, 0, c.width, c.height); ok(c.toDataURL('image/jpeg', .72)); }; im.onerror = () => bad(new Error('Not an image')); im.src = r.result; }; r.readAsDataURL(file); });

/* ---------- the trade form: quick add, paste, templates, duplicate, size helper, notes at three moments, screenshots, limits, history ---------- */
const base = JR.openForm;
JR.openForm = function (id, prefill) {
  const before = id ? JSON.parse(JSON.stringify(J().trades.find(x => x.id === id) || null)) : null;
  base.call(JR, id, prefill);
  const bg = [...document.querySelectorAll('.modal-bg')].pop(); if (!bg || !bg.querySelector('#f-entry')) return;
  const mb = bg.querySelector('.mb'), mh = bg.querySelector('.mh'), t = before || {}, ds = JR.dayStatus(), j = J();
  const set = (k, v) => { const el = bg.querySelector(`[data-k="${k}"]`); if (el && v != null && v !== '') { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); } };
  /* daily limit (215) and cooling-off after two losses (217): a reminder you can override; it is recorded */
  if (!id && ds.blocked) mb.insertAdjacentHTML('afterbegin', `<div class="callout ${ds.losses >= 2 ? 'bad' : 'warn'}" style="margin:10px 0"><span class="ic">!</span><div><b>${ds.losses >= 2 ? 'Two losses today: cool off.' : 'Daily limit reached: two trades today.'}</b> Your rule is at most two trades a day, A+ only. You can still save it, and it is logged as a rule break so the review shows it.</div></div>`);
  /* quick add (201): only the essentials first */
  const quick = !id && !prefill && store.get('ds_quickform', true);
  const tools = document.createElement('div'); tools.className = 'jf-tools';
  tools.innerHTML = `${!id ? `<button class="btn sm ghost" type="button" data-jf="quick" aria-pressed="${quick}">${quick ? 'Show all fields' : 'Quick add'}</button><button class="btn sm ghost" type="button" data-jf="paste">Paste a trade</button>` : `<button class="btn sm ghost" type="button" data-jf="dup">Duplicate</button><button class="btn sm ghost" type="button" data-jf="card" title="An image of the trade review with R, not rupees">Share card</button>`}
    <select class="inp sm" data-jf="tpl" aria-label="Template"><option value="">Template…</option>${(j.templates || []).map((x, i) => `<option value="${i}">${esc(x.name)}</option>`).join('')}<option value="save">Save these fields as a template</option></select>
    <button class="btn sm ghost" type="button" data-jf="size" title="Quantity from your risk per trade and the stop distance">Size from risk</button>`;
  mh.insertAdjacentElement('afterend', tools);
  const applyQuick = on => { bg.classList.toggle('jf-quick', on); let after = false; [...mb.children].forEach(el => { if (el.id === 'fcalc') { after = true; return; } if (after) el.classList.toggle('jf-hide', on); });
    ['reg', 'evt', 'exp', 'tm', 'cap', 'chg', 'tf'].forEach(kk => { const f = bg.querySelector(`[data-k="${kk}"]`); if (f && f.closest('.field')) f.closest('.field').classList.toggle('jf-hide', on); }); const b = tools.querySelector('[data-jf="quick"]'); if (b) { b.textContent = on ? 'Show all fields' : 'Quick add'; b.setAttribute('aria-pressed', on); } };
  applyQuick(quick);
  /* notes at entry, at exit and a week later (210), screenshots (209), history (207) */
  const n3 = t.notes3 || {}, att = (t.att || []).slice();
  mb.insertAdjacentHTML('beforeend', `<div class="fsec jf-more">Notes at three moments</div><div class="fgrid jf-more"><div class="field w4"><label for="f-n3e">At entry: why this trade?</label><textarea id="f-n3e" data-n3="entry">${esc(n3.entry || '')}</textarea></div><div class="field w4"><label for="f-n3x">At exit: what happened?</label><textarea id="f-n3x" data-n3="exit">${esc(n3.exit || '')}</textarea></div><div class="field w4"><label for="f-n3w">A week later: how do you see it now?</label><textarea id="f-n3w" data-n3="week">${esc(n3.week || '')}</textarea></div></div>
    <div class="fsec jf-more">Screenshots <small class="muted">(up to 3, shrunk to save space)</small></div><div class="jf-att jf-more" id="jfAtt"></div><label class="btn sm ghost jf-more">+ Add a screenshot<input type="file" accept="image/*" id="jfAttIn" hidden></label>
    ${before && (before.hist || []).length ? `<div class="fsec jf-more">Edit history</div><ul class="ins jf-more">${before.hist.map((h, k) => `<li><i></i><span><b>${esc(String(h.at).replace('T', ' ').slice(0, 16))}</b> changed ${esc(Object.keys(h.before).join(', '))} <button class="btn sm ghost" type="button" data-undo="${k}">Undo this and later</button></span></li>`).reverse().join('')}</ul>` : ''}`);
  const drawAtt = () => { const box = bg.querySelector('#jfAtt'); box.innerHTML = att.map((src, k) => `<span class="jf-thumb"><img src="${src}" alt="Screenshot ${k + 1}"><button type="button" data-attdel="${k}" aria-label="Remove">✕</button></span>`).join('') || '<small class="muted">None yet.</small>'; };
  drawAtt();
  bg.querySelector('#jfAttIn').onchange = async e => { const f = e.target.files[0]; if (!f) return; if (att.length >= 3) { App.toast('Up to 3 screenshots per trade'); return; } try { att.push(await shrink(f)); drawAtt(); } catch (er) { App.toast(er.message); } e.target.value = ''; };
  bg.addEventListener('click', e => {
    const jf = e.target.closest('[data-jf]'), k = jf && jf.dataset.jf;
    if (k === 'quick') { const on = !bg.classList.contains('jf-quick'); store.set('ds_quickform', on); applyQuick(on); }
    if (k === 'paste') { const txt = prompt('Paste a line from your contract note or broker app, for example:\nBUY GABRIEL 40 @ 1505.45 SL 1386.95 TGT 1624'); if (txt) { const o = pastedTrade(txt); Object.entries(o).forEach(([kk, v]) => set(kk, v)); App.toast(Object.keys(o).length ? 'Filled ' + Object.keys(o).join(', ') + ': check before saving' : 'Nothing recognised in that text'); } }
    if (k === 'dup') { const src = J().trades.find(x => x.id === id); if (src) { bg.remove(); const c = { ...src }; ['id', 'exit', 'xd', 'xtm', 'parts', 'ovr', 'hist', 'chk', 'notes3', 'att', 'mae', 'mfe', 'xt', 'res'].forEach(x => delete c[x]); c.d = todayIST(); c.tm = istNow().toISOString().slice(11, 16); JR.openForm(null, c); } }
    if (k === 'card') { const tr = J().trades.find(x => x.id === id); if (tr) JR.shareTrade(tr); }
    if (k === 'size') { const v = kk => +((bg.querySelector(`[data-k="${kk}"]`) || {}).value || 0), g = (bg.querySelector('[data-k="grade"]') || {}).value; const sz = JR.sizeFor(v('entry'), v('sl'), g); if (sz && sz.qty) { set('qty', sz.qty); App.toast(`Quantity ${sz.qty}: risk ${inr(sz.risk)} at ${g === 'A+' ? 'your A+' : 'your normal'} risk`); } else App.toast('Enter the entry and the stop first'); }
    const ad = e.target.closest('[data-attdel]'); if (ad) { att.splice(+ad.dataset.attdel, 1); drawAtt(); }
    const ud = e.target.closest('[data-undo]'); if (ud) { bg.remove(); JR.undo(id, +ud.dataset.undo); }
  });
  const tpl = tools.querySelector('[data-jf="tpl"]'); tpl.onchange = () => { const v = tpl.value; tpl.value = '';
    if (v === 'save') { const name = prompt('Template name (for example "Swing A+ pullback")'); if (!name) return; const keep = ['cat', 'setup', 'tf', 'dir', 'grade', 'reg', 'evt'], f = {}; keep.forEach(kk => { const el = bg.querySelector(`[data-k="${kk}"]`); if (el && el.value) f[kk] = el.value; }); const jj = J(); jj.templates = (jj.templates || []).concat({ name, fields: f }); JR.touch(); JR.persist(); App.toast('Template saved'); return; }
    const T = (J().templates || [])[+v]; if (T) { Object.entries(T.fields).forEach(([kk, val]) => set(kk, val)); App.toast('Template applied: ' + T.name); } };
  /* saving: keep notes, screenshots, history; a save over the daily limit is recorded as a rule break */
  bg.addEventListener('click', e => { if (!e.target.closest('[data-save]')) return;
    const n3n = {}; bg.querySelectorAll('[data-n3]').forEach(el => { if (el.value.trim()) n3n[el.dataset.n3] = el.value.trim(); });
    const brkEl = bg.querySelector('[data-k="brk"]'); if (!id && ds.blocked && brkEl && (!brkEl.value || brkEl.value === 'None')) { if (!bg._limitNote) { const noteEl = bg.querySelector('[data-k="note"]'); if (noteEl) noteEl.value = (noteEl.value ? noteEl.value + ' | ' : '') + 'over the daily limit (' + ds.why + ')'; bg._limitNote = true; } }
    const stamp = () => { const jj = J(); let tr = id ? jj.trades.find(x => x.id === id) : jj.trades[jj.trades.length - 1]; if (!tr) return;
      if (Object.keys(n3n).length || tr.notes3) tr.notes3 = n3n; if (att.length || tr.att) tr.att = att.slice();
      if (before) { const ch = {}; HKEYS.forEach(kk => { const a = before[kk] == null ? null : before[kk], b = tr[kk] == null ? null : tr[kk]; if (String(a) !== String(b)) ch[kk] = a; }); if (Object.keys(ch).length) tr.hist = (before.hist || []).concat({ at: new Date().toISOString(), before: ch }).slice(-20); else if (before.hist) tr.hist = before.hist; }
      JR.touch(); JR.persist(); };
    setTimeout(stamp, 0); }, true);
  /* deleting moves the trade to the recycle bin first (208) */
  bg.addEventListener('click', e => { if (!e.target.closest('[data-del]') || !id) return; const tr = J().trades.find(x => x.id === id); if (tr) { const jj = J(); jj.bin = JR.bin().concat({ at: new Date().toISOString(), t: JSON.parse(JSON.stringify(tr)) }); } }, true);
};
/* delete confirmation says where the trade goes */
const conf0 = window.confirm; window.confirm = msg => conf0(msg === 'Delete this trade?' ? 'Delete this trade? It goes to the recycle bin for 30 days (Journal → Recycle bin), where you can restore it.' : msg);

/* keep the scanner's planned entry with the trade so slippage can be measured once you edit the entry to your fill (item 229) */
const fs0 = JR.fromScanner; JR.fromScanner = function (it, sig) { const o = fs0.call(JR, it, sig); if (!it.options_trade && isNum(it.entry)) o.plan_entry = sig && isNum(sig.entry) ? sig.entry : it.entry; return o; };
/* ---------- auto-fill from the scanner (item 45): grade, timeframe and the rules the scanner already ticked ---------- */
const gate0 = JR.gate; JR.gate = function (o, done) { gate0.call(JR, o, done); const bg = [...document.querySelectorAll('.gate-bg')].pop(); if (!bg) return;
  const rules = JR.RULES[o.cat] || JR.RULES.Swing, ds = JR.dayStatus(), from = String(o.note || '').includes('DS:');
  rules.forEach((r, i) => { const cb = bg.querySelector(`[data-g="${i}"]`); if (!cb) return; if (r === JR.DAYRULE) cb.checked = ds.n < 2 && ds.losses < 2; else if (from && /Risk is within/.test(r)) cb.checked = true; });
  if (from) bg.querySelector('.mb .help').insertAdjacentHTML('beforeend', ' <b>From the scanner:</b> grade and timeframe are filled in; tick what you checked yourself.'); bg.dispatchEvent(new Event('change')); };

/* ---------- Journal page additions ---------- */
const page0 = App.pages.journal, bind0 = App.binds.journal;
App.pages.journal = q => {
  let h = page0(q); const j = J(), T = JR.enrich(), ds = JR.dayStatus(), today = todayIST(), mon = today.slice(0, 7), u = App.ui.jx || (App.ui.jx = { view: 'list', month: mon });
  /* daily limit meter (214) */
  const meter = `<div class="daymeter ${ds.blocked ? 'blocked' : ''}"><span><b>Today</b> ${ds.n} of 2 trades · ${ds.losses} loss${ds.losses === 1 ? '' : 'es'}</span><span class="dm-bar">${[0, 1].map(i => `<i class="${i < ds.n ? 'on' : ''}"></i>`).join('')}</span><span class="muted">${ds.blocked ? 'limit reached: ' + esc(ds.why) : `A+ only · ${ds.left} left`}</span></div>`;
  const tools = `<div class="jx-bar"><div class="seg" role="group">${[['list', 'List'], ['cal', 'Calendar']].map(([v, l]) => `<button type="button" data-jxv="${v}" aria-pressed="${u.view === v}">${l}</button>`).join('')}</div><span class="sp"></span>
    <button class="btn sm" type="button" id="jxXlsx">${ic('download')} Excel</button><button class="btn sm" type="button" id="jxPdf">${ic('download')} PDF</button><label class="btn sm">${ic('upload')} Broker CSV<input type="file" accept=".csv,text/csv" id="jxCsv" hidden></label></div>`;
  /* prompts: end-of-day review (218), a-week-later notes (210) */
  const pr = []; const tod = T.filter(t => t.d === today); const rv = (j.reviews || {})[today];
  if (tod.length && istNow().getUTCHours() * 60 + istNow().getUTCMinutes() >= 930 && !rv) pr.push(`<b>End of day:</b> ${tod.length} trade${tod.length > 1 ? 's' : ''} today. What went to plan, and what didn't? <button class="btn sm" type="button" id="jxDay">Write today's review</button>`);
  const wk = T.filter(t => t.closed && t.xd && (Date.now() - new Date(t.xd + 'T15:30:00+05:30')) > 7 * 864e5 && (Date.now() - new Date(t.xd + 'T15:30:00+05:30')) < 30 * 864e5 && !(t.notes3 && t.notes3.week)).slice(-3);
  if (wk.length) pr.push(`<b>A week later:</b> how do you see ${wk.map(t => `<a href="#" data-jopen="${esc(t.id)}">${esc(t.inst)} (${esc(t.xd.slice(5))})</a>`).join(', ')} now? A line each is enough.`);
  /* monthly goals (220) */
  const goals = ((j.goals || {})[mon] || []);
  const goalsCard = `<div class="card jx-goals"><div class="hd"><h2>Goals for ${esc(new Date(mon + '-01').toLocaleString('en-IN', { month: 'long' }))}</h2><span class="sp"></span><button class="btn sm ghost" type="button" id="jxGoal">+ Goal</button></div><div class="bd">${(() => { const M = T.filter(t => (t.xd || t.d || '').startsWith(mon)), C = M.filter(t => t.closed && isNum(t.net)), net = C.reduce((a, t) => a + t.net, 0), br = M.filter(t => t.brkd).length, sc = M.map(ruleScore).filter(x => x != null);
    return `<p class="help" style="margin:0 0 10px"><b>This month so far:</b> ${M.length} trades · ${inrS(net)} closed · ${br} rule break${br === 1 ? '' : 's'}${sc.length ? ` · rules ticked ${Math.round(100 * sc.reduce((a, b) => a + b, 0) / sc.length)}% on average` : ''}${goals.length ? ` · goals ${goals.filter(g => g.done).length} of ${goals.length} done` : ''}</p>`; })()}${goals.length ? `<ul class="goal-list">${goals.map((g, i) => `<li><label><input type="checkbox" data-goal="${i}" ${g.done ? 'checked' : ''}> <span>${esc(g.text)}</span></label></li>`).join('')}</ul>` : '<p class="help">Set one or two, for example "no trade without the 1H confirmation".</p>'}</div></div>`;
  /* data health (204, 248) */
  const H = JR.health(), hc = H.length ? `<details class="card jx-health"><summary class="hd"><h2>Journal check</h2><span class="cap">${H.length} to look at</span></summary><div class="bd"><ul class="ins">${H.slice(0, 30).map(x => `<li class="warn"><i></i><span><b>${esc(x.t.d)} ${esc(x.t.inst)}</b>: ${esc(x.txt)} <button class="btn sm ghost" type="button" data-jopen="${esc(x.t.id)}">Fix</button>${x.kind === 'dup' ? ` <button class="btn sm ghost" type="button" data-jdel="${esc(x.t.id)}">Delete this copy</button>` : ''}</span></li>`).join('')}</ul>
      ${H.filter(x => x.kind === 'xd').length > 1 ? `<button class="btn sm" type="button" id="jxFixXd">Add the missing exit dates one by one (${H.filter(x => x.kind === 'xd').length})</button>` : ''}</div></details>` : '';
  /* recycle bin (208) */
  const B = JR.bin(), bin = B.length ? `<details class="card jx-bin"><summary class="hd"><h2>Recycle bin</h2><span class="cap">${B.length} · kept 30 days</span></summary><div class="bd"><ul class="ins">${B.map(b => `<li><i></i><span><b>${esc(b.t.d)} ${esc(b.t.inst)}</b> deleted ${esc(ago(b.at))} <button class="btn sm" type="button" data-jrest="${esc(b.t.id)}">Restore</button> <button class="btn sm ghost" type="button" data-jpurge="${esc(b.t.id)}">Delete for good</button></span></li>`).join('')}</ul></div></details>` : '';
  /* calendar view (284) */
  let cal = ''; if (u.view === 'cal') { const [y, m] = u.month.split('-').map(Number), first = new Date(Date.UTC(y, m - 1, 1)), days = new Date(Date.UTC(y, m, 0)).getUTCDate(), lead = (first.getUTCDay() + 6) % 7, by = {};
    T.forEach(t => (t._legs || []).forEach(l => { if (l.d && String(l.d).startsWith(u.month) && isNum(l.net)) by[l.d] = (by[l.d] || 0) + l.net; }));
    const opened = {}; T.forEach(t => { if (t.d.startsWith(u.month)) opened[t.d] = (opened[t.d] || 0) + 1; });
    cal = `<div class="card jx-cal"><div class="hd"><button class="btn sm ghost" type="button" data-jxm="-1">←</button><h2 style="margin:0 10px">${esc(first.toLocaleString('en-IN', { month: 'long', year: 'numeric', timeZone: 'UTC' }))}</h2><button class="btn sm ghost" type="button" data-jxm="1">→</button><span class="sp"></span><span class="cap">P&L by exit day · trades opened</span></div><div class="bd"><div class="calg">${['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(d => `<b>${d}</b>`).join('')}${'<span></span>'.repeat(lead)}${Array.from({ length: days }, (_, i) => { const d = `${u.month}-${String(i + 1).padStart(2, '0')}`, v = by[d], n = opened[d]; return `<button type="button" class="cd ${v > 0 ? 'pos' : v < 0 ? 'neg' : ''} ${d === today ? 'today' : ''}" data-jday="${d}"><small>${i + 1}</small>${v != null ? `<em>${inrS(v)}</em>` : ''}${n ? `<i>${n} opened</i>` : ''}</button>`; }).join('')}</div></div></div>`; }
  const add = meter + tools + (pr.length ? `<div class="callout info jx-prompts"><span class="ic">i</span><div>${pr.join('<br>')}</div></div>` : '') + cal;
  const i = h.indexOf('<div class="kpis"'); h = i >= 0 ? h.slice(0, i) + add + h.slice(i) : h + add;
  h += `<div class="grid g2" style="margin-top:14px">${goalsCard}<div class="stack">${hc}${bin}</div></div><button class="fab" type="button" id="jxFab" aria-label="Add a trade">+</button>`;
  return h;
};
App.binds.journal = q => {
  bind0(q); const u = App.ui.jx, j = J();
  $$('[data-jxv]').forEach(b => b.onclick = () => { u.view = b.dataset.jxv; App.render(); });
  $$('[data-jxm]').forEach(b => b.onclick = () => { const [y, m] = u.month.split('-').map(Number), d = new Date(Date.UTC(y, m - 1 + +b.dataset.jxm, 1)); u.month = d.toISOString().slice(0, 7); App.render(); });
  $$('[data-jday]').forEach(b => b.onclick = () => { const jq = $('#jQ'); App.ui.jr = App.ui.jr || {}; const U0 = (App.ui.jrn = App.ui.jrn || null); const T = JR.enrich().filter(t => t.d === b.dataset.jday || t.xd === b.dataset.jday); if (T.length === 1) JR.openForm(T[0].id); else if (T.length) { if (jq) { jq.value = ''; } App.toast(`${T.length} trades on ${b.dataset.jday}: shown in the list below`); u.view = 'list'; App.render(); } });
  const x = $('#jxXlsx'); if (x) x.onclick = JR.exportXlsx; const pdf = $('#jxPdf'); if (pdf) pdf.onclick = () => { document.documentElement.classList.add('print-journal'); window.print(); setTimeout(() => document.documentElement.classList.remove('print-journal'), 500); };
  const c = $('#jxCsv'); if (c) c.onchange = e => { const f = e.target.files[0]; if (!f) return; JR.importBroker(f).then(r => { App.toast(`${r.added} trade${r.added === 1 ? '' : 's'} added from ${r.fills} fills${r.dup ? `, ${r.dup} already in the journal (skipped)` : ''}. Add your stops.`, 6000); App.render(); }).catch(er => App.toast('Import failed: ' + er.message, 7000)); };
  const dy = $('#jxDay'); if (dy) dy.onclick = () => { const t = prompt("Today's review: what went to plan, and what didn't?"); if (t) { j.reviews = j.reviews || {}; j.reviews[todayIST()] = { text: t, at: new Date().toISOString() }; JR.touch(); JR.persist(); App.render(); } };
  const g = $('#jxGoal'); if (g) g.onclick = () => { const t = prompt('A goal for this month'); if (t) { const mon = todayIST().slice(0, 7); j.goals = j.goals || {}; j.goals[mon] = (j.goals[mon] || []).concat({ text: t, done: false }); JR.touch(); JR.persist(); App.render(); } };
  $$('[data-goal]').forEach(cb => cb.onchange = () => { const mon = todayIST().slice(0, 7); j.goals[mon][+cb.dataset.goal].done = cb.checked; JR.touch(); JR.persist(); });
  $$('[data-jopen]').forEach(a => a.onclick = e => { e.preventDefault(); e.stopPropagation(); JR.openForm(a.dataset.jopen); });
  $$('[data-jdel]').forEach(b => b.onclick = () => { if (!confirm('Delete this trade?')) return; const tr = j.trades.find(t => t.id === b.dataset.jdel); if (tr) { j.bin = JR.bin().concat({ at: new Date().toISOString(), t: JSON.parse(JSON.stringify(tr)) }); j.trades = j.trades.filter(t => t !== tr); JR.touch(); JR.persist(); App.render(); } });
  $$('[data-jrest]').forEach(b => b.onclick = () => JR.restoreBin(b.dataset.jrest)); $$('[data-jpurge]').forEach(b => b.onclick = () => { if (confirm('Delete for good? This cannot be undone.')) JR.purgeBin(b.dataset.jpurge); });
  const fx = $('#jxFixXd'); if (fx) fx.onclick = () => { const ids = JR.health().filter(h => h.kind === 'xd').map(h => h.t.id); const next = () => { const id = ids.shift(); if (!id) { App.toast('All done'); return; } JR.openForm(id); const bg = [...document.querySelectorAll('.modal-bg')].pop(); if (bg) { const el = bg.querySelector('#f-xd'); if (el) el.focus(); const ob = new MutationObserver(() => { if (!document.body.contains(bg)) { ob.disconnect(); setTimeout(next, 200); } }); ob.observe(document.body, { childList: true }); } }; next(); };
  const fab = $('#jxFab'); if (fab) fab.onclick = () => JR.openForm(null);
  /* rows: rule-score dot (212, 281) and quiet badges for missing information (283) */
  const by = Object.fromEntries(JR.enrich().map(t => [t.id, t]));
  $$('tr[data-id]').forEach(tr => { const t = by[tr.dataset.id]; if (!t) return; const cell = tr.querySelector('td:nth-child(2)'); if (!cell) return; const b = [];
    if (!isNum(t.sl)) b.push('no stop'); if (!t.grade) b.push('no grade'); if (t.closed && t.xdUnknown) b.push('exit date?'); if (t.att && t.att.length) b.push('📷 ' + t.att.length);
    cell.insertAdjacentHTML('beforeend', dot(ruleScore(t)) + b.map(x => ` <span class="qbadge">${esc(x)}</span>`).join('')); });
};

/* ---------- dated backups on this device, with a preview before restoring (item 242) ----------
   One snapshot per day of every journal, kept 14 days in IndexedDB (room for screenshots, unlike localStorage). The nightly encrypted
   backup to your private repository still runs; this is the quick "undo a bad day" copy. */
const IDB = () => new Promise((ok, bad) => { try { const r = indexedDB.open('ds_backups', 1); r.onupgradeneeded = () => r.result.createObjectStore('snaps', { keyPath: 'day' }); r.onsuccess = () => ok(r.result); r.onerror = () => bad(r.error); } catch (e) { bad(e); } });
const tx = async (mode, fn) => { const db = await IDB(); return new Promise((ok, bad) => { const t = db.transaction('snaps', mode), st = t.objectStore('snaps'), res = fn(st); t.oncomplete = () => ok(res && res.result !== undefined ? res.result : res); t.onerror = () => bad(t.error); }); };
JR.snapToday = async () => { try { const day = todayIST(), have = await tx('readonly', st => st.get(day)); const list = JSON.parse(localStorage.getItem('tji_journals_v1') || '[]');
  if (!list.length) return; await tx('readwrite', st => st.put({ day, at: new Date().toISOString(), journals: list }));
  const keys = await tx('readonly', st => st.getAllKeys()); const old = (keys || []).sort().slice(0, Math.max(0, keys.length - 14)); if (old.length) await tx('readwrite', st => old.forEach(k => st.delete(k))); } catch (e) { } };
JR.snaps = async () => { try { return (await tx('readonly', st => st.getAll())).sort((a, b) => b.day.localeCompare(a.day)); } catch (e) { return []; } };
const statsOf = journals => { const T = (journals || []).filter(j => !j.demo).flatMap(j => j.trades || []), d = T.map(t => t.d).filter(Boolean).sort(); return { n: T.length, open: T.filter(t => t.exit == null || t.exit === '').length, from: d[0], to: d[d.length - 1], names: (journals || []).filter(j => !j.demo).map(j => j.name).join(', ') }; };
JR.previewRestore = (journals, label, apply) => { const a = statsOf(journals), b = statsOf(JSON.parse(localStorage.getItem('tji_journals_v1') || '[]')), bg = document.createElement('div'); bg.className = 'modal-bg';
  bg.innerHTML = `<div class="modal" role="dialog" aria-label="Restore preview" style="max-width:560px"><div class="mh"><h2>Restore ${esc(label)}?</h2></div><div class="mb"><div class="grid g2" style="margin-top:10px"><div class="opt"><b>Now on this device</b><p class="help">${b.n} trades (${b.open} open)<br>${esc(b.from || '-')} to ${esc(b.to || '-')}<br>${esc(b.names)}</p></div><div class="opt on"><b>The backup</b><p class="help">${a.n} trades (${a.open} open)<br>${esc(a.from || '-')} to ${esc(a.to || '-')}<br>${esc(a.names)}</p></div></div>
    <p class="help" style="margin-top:10px">Restoring replaces the journals on this device and then syncs them to your cloud. Today's copy is kept as a backup first, so you can undo it.</p></div><div class="mf"><button class="btn" type="button" data-x>Cancel</button><button class="btn primary" type="button" data-go>Restore</button></div></div>`;
  document.body.appendChild(bg); bg.addEventListener('click', async e => { if (e.target === bg || e.target.closest('[data-x]')) bg.remove(); if (e.target.closest('[data-go]')) { bg.remove(); await JR.snapToday(); apply(); } }); };
JR.restoreSnap = async day => { const sn = (await JR.snaps()).find(x => x.day === day); if (!sn) return; JR.previewRestore(sn.journals, 'the ' + day + ' copy', () => { localStorage.setItem('tji_journals_v1', JSON.stringify(sn.journals)); JR.loadLocal(); (sn.journals || []).forEach(j => { j.updated = Date.now(); }); JR.J().updated = Date.now(); JR.persist(); App.toast('Restored the ' + day + ' copy'); App.render(); }); };
setTimeout(() => JR.snapToday(), 4000);
/* JSON import shows the same preview first */
const imp0 = JR.importFile; JR.importFile = file => new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => { let data; try { data = JSON.parse(r.result); } catch (e) { bad(new Error('Not a journal backup file')); return; }
  const js = data.journals || (data.journal ? [data.journal] : data.trades ? [{ name: 'Imported', trades: data.trades }] : null); if (!js) { imp0(file).then(ok, bad); return; }
  const st = statsOf(js); if (!confirm(`Import ${st.n} trades (${st.from || '-'} to ${st.to || '-'}) from ${file.name}? They are added as a journal, nothing is overwritten.`)) { bad(new Error('cancelled')); return; } imp0(file).then(ok, bad); }; r.readAsText(file); });
/* Settings: backups card */
const set0 = App.pages.settings, setb0 = App.binds.settings;
App.pages.settings = q => set0(q) + `<div class="card" style="margin-top:14px"><div class="hd"><h2>Backups on this device</h2><span class="cap">one a day, kept 14 days</span></div><div class="bd" id="snapBox"><p class="help">Loading…</p></div></div>
  <div class="card" style="margin-top:14px"><div class="hd"><h2>Sync</h2></div><div class="bd"><p>${esc(JR.syncText ? JR.syncText() : '')}</p>${store.get('ds_conflict_backup', null) ? `<p class="help">A copy from the last sync conflict (${esc(String(store.get('ds_conflict_backup').at).slice(0, 16).replace('T', ' '))}) is kept on this device.</p>` : ''}</div></div>`;
App.binds.settings = q => { setb0(q); JR.snaps().then(L => { const b = $('#snapBox'); if (!b) return; b.innerHTML = L.length ? `<div class="tbl-wrap"><table class="tbl"><tbody>${L.map(x => { const st = statsOf(x.journals); return `<tr><td><b>${esc(x.day)}</b></td><td>${st.n} trades</td><td class="n"><button class="btn sm" type="button" data-snap="${esc(x.day)}">Preview and restore</button></td></tr>`; }).join('')}</tbody></table></div>` : '<p class="help">The first copy is made a few seconds after the app opens.</p>'; $$('[data-snap]').forEach(btn => btn.onclick = () => JR.restoreSnap(btn.dataset.snap)); }); };

/* ---------- a trade review card as an image: R and prices only, never rupee amounts or account size (item 100) ---------- */
JR.shareTrade = t0 => { const t = JR.enrich().find(x => x.id === t0.id) || t0, cs = getComputedStyle(document.documentElement), v = n => cs.getPropertyValue(n).trim() || '#888', W = 720, H = 380, sc = 2, c = document.createElement('canvas'); c.width = W * sc; c.height = H * sc; const x = c.getContext('2d'); x.scale(sc, sc);
  const bg = v('--bg') || '#000', ink = v('--ink') || '#fff', ink3 = v('--ink-3'), good = v('--good'), bad = v('--bad'); x.fillStyle = bg; x.fillRect(0, 0, W, H); x.strokeStyle = v('--line'); x.strokeRect(10.5, 10.5, W - 21, H - 21);
  x.fillStyle = ink3; x.font = '600 12px Arial'; x.fillText('TRADE REVIEW · DownerStuff', 32, 44); x.textAlign = 'right'; x.fillText(String(t.d || '') + (t.xd ? ' → ' + t.xd : ''), W - 32, 44); x.textAlign = 'left';
  x.fillStyle = ink; x.font = '700 40px Arial'; x.fillText(String(t.inst || ''), 32, 100); x.font = '600 16px Arial'; x.fillStyle = t.dir === 'Short' ? bad : good; x.fillText((t.dir || '').toUpperCase() + (t.grade ? ' · ' + t.grade : '') + (t.setup ? ' · ' + t.setup : ''), 32, 128);
  const big = t.r != null ? (t.r >= 0 ? '+' : '−') + Math.abs(t.r).toFixed(2) + 'R' : t.open ? 'Open' : '-'; x.font = '800 64px Arial'; x.fillStyle = t.r == null ? ink : t.r >= 0 ? good : bad; x.fillText(big, 32, 220);
  const rows = [['Entry', fmt(t.entry)], ['Stop', fmt(t.sl)], ['Target', fmt(t.tgt)], ['Exit', t.exit != null ? fmt(t.exit) : '-'], ['Rules ticked', t.chk && t.chk.n ? `${t.chk.ok}/${t.chk.n}` : '-'], ['Result', t.open ? 'Open' : (t.res || '-')]];
  x.font = '12px Arial'; rows.forEach(([l, val], i) => { const cx = 32 + (i % 3) * 220, cy = 268 + Math.floor(i / 3) * 52; x.fillStyle = ink3; x.fillText(l.toUpperCase(), cx, cy); x.fillStyle = ink; x.font = '600 20px Arial'; x.fillText(String(val), cx, cy + 24); x.font = '12px Arial'; });
  const note = (t.notes3 && (t.notes3.week || t.notes3.exit)) || ''; if (note) { x.fillStyle = ink3; x.font = 'italic 13px Arial'; x.fillText('“' + note.slice(0, 90) + (note.length > 90 ? '…' : '') + '”', 32, H - 28); }
  c.toBlob(b => { const name = `${t.inst}-${t.d}-review.png`.replace(/\s+/g, '-'); try { const f = new File([b], name, { type: 'image/png' }); if (navigator.canShare && navigator.canShare({ files: [f] })) { navigator.share({ files: [f], title: t.inst + ' review' }).catch(() => { }); return; } } catch (e) { }
    const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000); App.toast('Review card saved (R and prices only, no rupee amounts)'); }, 'image/png'); };
/* ---------- yearly report: one printable page with results, rules followed, lessons and goals (item 250) ---------- */
App.pages.yearly = q => { const j = J(), all = JR.enrich(j), fy = +(q.get('fy') || 0) || (() => { const d = todayIST(); return +d.slice(5, 7) >= 4 ? +d.slice(0, 4) : +d.slice(0, 4) - 1; })();
  const inFy = d => d && d >= `${fy}-04-01` && d <= `${fy + 1}-03-31`, C = all.filter(t => t.closed && isNum(t.net) && inFy(t.xd)), T = all.filter(t => inFy(t.d)), st = App.analytics.stats(C, j.set);
  const months = {}; C.forEach(t => { const k = t.xd.slice(0, 7); months[k] = (months[k] || 0) + t.net; }); const goals = Object.entries(j.goals || {}).filter(([m]) => inFy(m + '-15')).flatMap(([m, g]) => g.map(x => ({ m, ...x })));
  const lessons = []; all.forEach(t => { if (!inFy(t.xd || t.d)) return; const n = t.notes3 || {}; if (n.week) lessons.push(`${t.inst}: ${n.week}`); else if (n.exit) lessons.push(`${t.inst}: ${n.exit}`); });
  const sc = T.map(JR.ruleScore).filter(x => x != null), bySetup = App.analytics.group(C, t => t.setup || 'No setup', 1);
  return `<div class="ph yearly"><div><h1>Year in review · FY ${fy}–${String(fy + 1).slice(2)}</h1><p>${esc(j.name)} · 1 April ${fy} to 31 March ${fy + 1}</p></div><span class="sp"></span><button class="btn" type="button" onclick="window.print()">${ic('download')} Save as PDF</button></div>
    <div class="kpis" style="margin-bottom:14px">${[['Net P&L', inrS(st.net), pct(st.net / (j.set.capital || 1), 1) + ' of capital', cls(st.net)], ['Trades', T.length, `${C.length} closed`], ['Win rate', pct(st.winRate, 0), `${st.wins} W · ${st.losses} L`], ['Expectancy', rr(st.expR), 'per trade', cls(st.expR)], ['Rule compliance', pct(st.comply, 0), sc.length ? `checklist ${Math.round(100 * sc.reduce((a, b) => a + b, 0) / sc.length)}% ticked` : ''], ['Max drawdown', inr(st.dd), pct(st.ddP, 1) + ' of capital', st.dd < 0 ? 'bad' : '']].map(k => App.ui.kpi(...k)).join('')}</div>
    <div class="grid g2"><div class="card"><div class="hd"><h2>Month by month</h2></div><div class="bd">${App.charts.bars(Object.keys(months).sort().map(k => ({ l: k.slice(5), v: months[k] })), { W: 520, H: 180, fmt: v => inr(v), label: 'Monthly P&L' })}</div></div>
      <div class="card"><div class="hd"><h2>Setups</h2></div><div class="bd"><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Setup</th><th class="n">Trades</th><th class="n">Win</th><th class="n">Avg R</th><th class="n">Net</th></tr></thead><tbody>${bySetup.map(g => `<tr><td>${esc(g.k)}</td><td class="n">${g.n}</td><td class="n">${pct(g.win, 0)}</td><td class="n ${cls(g.avgR)}">${rr(g.avgR)}</td><td class="n ${cls(g.net)}">${inrS(g.net)}</td></tr>`).join('')}</tbody></table></div></div></div></div>
    <div class="grid g2" style="margin-top:14px"><div class="card"><div class="hd"><h2>Lessons</h2></div><div class="bd">${lessons.length ? `<ul class="ins">${lessons.slice(0, 20).map(l => `<li><i></i><span>${esc(l)}</span></li>`).join('')}</ul>` : '<p class="help">No exit or week-later notes this year.</p>'}</div></div>
      <div class="card"><div class="hd"><h2>Goals</h2></div><div class="bd">${goals.length ? `<ul class="ins">${goals.map(g => `<li class="${g.done ? 'good' : ''}"><i></i><span>${g.done ? '✓' : '·'} ${esc(g.text)} <small class="muted">${esc(g.m)}</small></span></li>`).join('')}</ul>` : '<p class="help">Set monthly goals on the Journal page.</p>'}
      <p class="help" style="margin-top:10px"><b>Goals for next year:</b> write two or three here before you print.</p><textarea class="inp" style="width:100%;min-height:80px"></textarea></div></div></div>`; };
})();
