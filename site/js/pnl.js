/* Realized P&L: the ONE place where a trade's profit or loss is worked out and given a date (18 Nov 2026).
   Used by the journal, the risk banner, the dashboard and analytics, and written to be dropped into Trade Insight unchanged
   (no dependencies, works in the browser as window.PnL and in Node for the tests), so the two apps cannot disagree.

   The rule: realized P&L belongs to the day it was REALIZED (the exit date), never to the entry date.
   A trade has legs: each partial exit {d, tm, qty, px, chg} is a leg on its own date, and the final exit (xd, xtm, exit price) carries
   the remaining quantity. A manual net override is one leg on the exit date. A leg without a valid exit date is UNKNOWN: it is counted in
   the trade's total but in no day, week or month, and the app asks for the date. No exit date is ever guessed from the entry date or today.

   Unrealized P&L (open quantity at a live price) is separate and never part of daily or weekly realized P&L. */
(function (root) {
  'use strict';
  const ymd = s => /^\d{4}-\d{2}-\d{2}$/.test(String(s || ''));
  const num = v => (v === '' || v == null || !isFinite(+v)) ? null : +v;
  const utc = s => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10));
  /* NSE weeks run Monday to Friday on the IST calendar; dates in the journal are IST dates. */
  const weekStart = s => { const d = new Date(utc(s)); const wd = (d.getUTCDay() + 6) % 7; return new Date(utc(s) - wd * 864e5).toISOString().slice(0, 10); };
  const sgn = t => t.dir === 'Short' ? -1 : 1;

  /* Normalized partial exits: only rows with a positive quantity and a price. */
  function parts(t) {
    return (Array.isArray(t.parts) ? t.parts : []).map(p => ({ d: ymd(p.d) ? p.d : '', tm: String(p.tm || ''), qty: num(p.qty), px: num(p.px), chg: num(p.chg) || 0 })).filter(p => p.qty > 0 && p.px != null);
  }

  /* All realized legs of one trade. q = position quantity (qty, or worked out from capital by the caller). */
  function legs(t, q) {
    const out = [], e = num(t.entry), s = sgn(t), P = parts(t), ovr = num(t.ovr);
    if (ovr != null) { out.push({ kind: 'override', d: ymd(t.xd) ? t.xd : '', tm: t.xtm || '', qty: q, gross: null, chg: 0, net: ovr, known: ymd(t.xd) }); return out; }
    let used = 0;
    P.forEach(p => { const g = e != null ? (p.px - e) * p.qty * s : null; used += p.qty; out.push({ kind: 'partial', d: p.d, tm: p.tm, qty: p.qty, px: p.px, gross: g, chg: p.chg, net: g != null ? g - p.chg : null, known: ymd(p.d) }); });
    const x = num(t.exit);
    if (x != null && q != null) {
      const rest = Math.max(0, q - used), g = e != null ? (x - e) * rest * s : null, c = num(t.chg) || 0;
      out.push({ kind: 'final', d: ymd(t.xd) ? t.xd : '', tm: t.xtm || '', qty: rest, px: x, gross: g, chg: c, net: g != null ? g - c : null, known: ymd(t.xd) });
    }
    return out;
  }

  /* Totals for one trade: closed, gross, net, open quantity. */
  function totals(t, q) {
    const L = legs(t, q), closed = num(t.exit) != null || num(t.ovr) != null;
    const realized = L.reduce((a, l) => a + (l.net || 0), 0), gross = L.some(l => l.gross == null) ? null : L.reduce((a, l) => a + l.gross, 0);
    const openQty = closed ? 0 : Math.max(0, (q || 0) - L.reduce((a, l) => a + (l.qty || 0), 0));
    return { legs: L, closed, realized: L.length ? realized : null, gross: L.length ? gross : null, net: closed ? (L.length && L.every(l => l.net != null) ? realized : null) : null, openQty, unknown: L.filter(l => !l.known && l.net != null) };
  }

  /* Realized P&L of a set of enriched trades (each with ._legs) over the days `inPeriod(dateString)` accepts. */
  function realized(T, inPeriod) {
    let net = 0, n = 0, unknown = 0, unknownNet = 0;
    T.forEach(t => (t._legs || []).forEach(l => {
      if (l.net == null) return;
      if (!l.known) { unknown++; unknownNet += l.net; return; }
      if (inPeriod(l.d)) { net += l.net; n++; }
    }));
    return { net, legs: n, unknown, unknownNet };
  }

  /* The banner numbers for one period: realized P&L, the limit, how much of it is used and what is left (all as fractions of capital). */
  function limitUse(netRs, cap, limitFrac) {
    const pnl = cap ? netRs / cap : 0, loss = Math.max(0, -pnl), use = limitFrac ? loss / limitFrac : 0;
    return { pnl, pnlRs: netRs, limit: limitFrac, limitRs: limitFrac * cap, use, remaining: Math.max(0, limitFrac - loss), remainingRs: Math.max(0, limitFrac - loss) * cap, status: use >= 1 ? 'bad' : use >= 0.6 ? 'warn' : 'ok' };
  }

  /* Unrealized P&L of the open quantity at a live price (null when there is no price). Never part of realized day/week P&L. */
  function unrealized(t, q, live) {
    const e = num(t.entry), L = totals(t, q);
    if (L.closed || live == null || e == null || !L.openQty) return null;
    return (live - e) * L.openQty * sgn(t);
  }

  const api = { legs, totals, realized, limitUse, unrealized, weekStart, parts, ymd };
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.PnL = api;
})(typeof window !== 'undefined' ? window : globalThis);
