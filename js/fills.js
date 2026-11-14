/* Broker fills -> proposed journal trades (item 21). Pure functions with no page access, so they are tested on their own (test_fills.py).
   A "round trip" is everything from a flat position back to flat for one symbol and product: the first side decides Long or Short,
   the average of the opening fills is the entry, the average of the closing fills is the exit. */
(function (root) {
  const IST = 330 * 60000;
  const ist = iso => { const d = new Date(new Date(iso).getTime() + IST).toISOString(); return { d: d.slice(0, 10), tm: d.slice(11, 16) }; };
  const clean = s => String(s || '').replace(/-EQ$/, '');
  const isOpt = f => !!(f.option_type || /^OPT/.test(f.instrument || '') || /\d(CE|PE)$/.test(f.symbol || ''));
  const catOf = f => isOpt(f) ? 'Options' : f.product === 'DELIVERY' ? 'Swing' : 'Intraday';
  const r2 = x => x == null ? null : Math.round(x * 100) / 100;
  const wavg = a => { const q = a.reduce((s, x) => s + x.qty, 0); return q ? a.reduce((s, x) => s + x.qty * x.price, 0) / q : null; };
  const num = x => +x;

  function propose(fills, openTrades) {
    openTrades = openTrades || []; const groups = {}, out = [];
    (fills || []).forEach(f => { const k = f.symbol + '|' + (f.product || ''); (groups[k] = groups[k] || []).push(Object.assign({}, f, { qty: num(f.qty), price: num(f.price) })); });
    Object.values(groups).forEach(g => {
      g.sort((a, b) => (a.filled_at < b.filled_at ? -1 : a.filled_at > b.filled_at ? 1 : 0) || (a.fill_id < b.fill_id ? -1 : 1));
      let pos = 0, rt = null;
      const start = (f, qty) => ({ first: f, side: f.side, opens: [Object.assign({}, f, { qty })], closes: [], ids: [f.fill_id], last: f });
      const finish = (partial) => {
        if (!rt) return; const f0 = rt.first, t0 = ist(f0.filled_at), tl = ist(rt.last.filled_at), qty = rt.opens.reduce((s, x) => s + x.qty, 0), closed = !partial && rt.closes.length > 0;
        out.push({ kind: 'trade', key: rt.ids[0], ids: rt.ids.slice(), symbol: f0.symbol, inst: isOpt(f0) ? f0.symbol : clean(f0.symbol), cat: catOf(f0), dir: rt.side === 'BUY' ? 'Long' : 'Short', qty, entry: r2(wavg(rt.opens)),
          exit: closed ? r2(wavg(rt.closes)) : null, d: t0.d, tm: t0.tm, xd: closed ? tl.d : null, xtm: closed ? tl.tm : null, closed, partial: !!partial && rt.closes.length > 0, lot: f0.lot || null, at: f0.filled_at });
        rt = null;
      };
      g.forEach(f => {
        const sgn = f.side === 'BUY' ? 1 : -1;
        if (pos === 0) { rt = start(f, f.qty); pos = sgn * f.qty; return; }
        if (Math.sign(pos) === sgn) { rt.opens.push(Object.assign({}, f)); rt.ids.push(f.fill_id); rt.last = f; pos += sgn * f.qty; return; }
        const reduce = Math.min(Math.abs(pos), f.qty); rt.closes.push(Object.assign({}, f, { qty: reduce })); rt.ids.push(f.fill_id); rt.last = f; pos += sgn * reduce;
        const rest = f.qty - reduce;
        if (pos === 0) { finish(false); if (rest > 0) { rt = start(f, rest); rt.ids = [f.fill_id]; pos = sgn * rest; } }
      });
      if (rt) finish(pos !== 0);
    });
    // a delivery SELL with no earlier buy in these fills is you selling something you already hold
    const res = [];
    out.forEach(t => {
      if (t.cat === 'Swing' && t.dir === 'Short') {
        const m = openTrades.find(x => !x.closed && x.exit == null && String(x.inst || '').toUpperCase() === t.inst.toUpperCase() && x.dir !== 'Short');
        res.push(m ? { kind: 'close', key: t.key, ids: t.ids, inst: t.inst, tradeId: m.id, exit: t.entry, qty: t.qty, d: t.d, tm: t.tm, at: t.at, entry: m.entry } : Object.assign({}, t, { kind: 'orphan' }));
      } else res.push(t);
    });
    return res.sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0));
  }

  /* split proposals into still-to-do and already-in-the-journal (a trade whose note carries BR:<key>) */
  function split(props, trades) {
    const notes = (trades || []).map(t => String(t.note || '')).join('\n'), pending = [], done = [];
    props.forEach(p => (notes.indexOf('BR:' + p.key) >= 0 ? done : pending).push(p));
    return { pending, done };
  }
  function prefill(p) {
    return { d: p.d, tm: p.tm, inst: p.inst, cat: p.cat, dir: p.dir, qty: p.qty, entry: p.entry, exit: p.exit, tf: p.cat === 'Swing' ? 'Daily' : '5 MINS', note: 'BR:' + p.key + ' | from Angel One fills: add your stop-loss, grade and charges' };
  }
  const api = { propose, split, prefill, ist, clean, catOf };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.Fills = api;
})(typeof window !== 'undefined' ? window : globalThis);
