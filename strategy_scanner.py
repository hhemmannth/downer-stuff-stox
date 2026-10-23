#!/usr/bin/env python3
"""
DownerStuffScreener engine. Scans NSE stocks and the Nifty index with your rule book:
  structure (CHoCH, then BOS with displacement) -> FVG + order block -> pullback into the zone
  -> rejection + close back through the 9 EMA (+ volume where it applies) -> structural stop.

Sections, one engine:
  swing     Nifty 500, LONG ONLY.           1D structure -> 1H trigger
  options   Nifty 50 index, calls and puts. 15m CHoCH bias -> 5m CHoCH + BOS -> 5m trigger. No volume rule.
  intraday  most liquid Nifty 500 stocks, long and short. 15m CHoCH bias -> 5m CHoCH + BOS -> 5m trigger + volume.
Plus market (regime, breadth, sectors) and news (headlines and events).

Usage: python strategy_scanner.py --mode swing | options | intraday | market | news | live | all   [--out _site/data]
Writes swing.json, options.json, intraday.json, market.json, news.json for the web pages. Not investment advice.
"""
import argparse, io, json, math, os, pickle, sys, time, urllib.request
import datetime as dt
import numpy as np
import pandas as pd
import explain, greeks, market, newsfeed, sector_index, signals
import oi as oimod

# ------------------------------------------------------------------ settings
CFG = dict(                       # swing: structure on 1D, trigger on 1H
    pivot=3, atr_n=14, lookback=150, disp_body_atr=1.0, fvg_min_atr=0.2, stack_gap_atr=0.5, approach_atr=1.5,
    sl_buffer_atr=0.25, rvol_min=1.5, rvol_n=20, h_lookback=40, trigger_age=3,
    min_price=50.0, min_turnover_cr=20.0, min_bars=60,
    max_bos_age=60, max_zone_atr=3.5, max_zone_pct=10.0, trigger_max_atr=1.0,
    slot_rvol=True)               # India: compare 1H volume with the same time-of-day candle, not with the whole day
CFG_I = dict(CFG, lookback=240, h_lookback=48, trigger_age=6, min_bars=120, min_price=0.0, min_turnover_cr=0.0,
             max_bos_age=150, max_zone_atr=3.0, max_zone_pct=3.0, slot_rvol=False)      # options + intraday: 5m structure and trigger
CFG_B = dict(CFG_I, lookback=160, max_bos_age=120, min_bars=60)                         # 15m: CHoCH only
PAIRS = [('zone_bot', 'zone_top'), ('ob_low', 'ob_high'), ('fvg_low', 'fvg_high'), ('fib_lo', 'fib_hi'), ('leg_low', 'leg_high'), ('b15_ob_low', 'b15_ob_high')]
SINGLES = ['entry', 'sl', 't1', 't2', 't3', 'price', 'bos_level', 'choch_level', 'pullback_low', 'b15_level', 'b15_base']
COLS = ['Open', 'High', 'Low', 'Close', 'Volume']
IST = 'Asia/Kolkata'
TICK = 0.05                       # NSE tick size

# ------------------------------------------------------------------ indicators
def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def atr(df, n=14):
    tr = pd.concat([df.High - df.Low, (df.High - df.Close.shift()).abs(), (df.Low - df.Close.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def invert(df, K):
    """Mirror prices (p -> K - p) so the long logic can find short setups. EMA and ATR commute with this."""
    o = df.copy(); o['Open'], o['High'], o['Low'], o['Close'] = K - df.Open, K - df.Low, K - df.High, K - df.Close
    return o

def swing_points(df, n):
    h, l = df.High.values, df.Low.values; ph, pl = [], []
    for i in range(n, len(df) - n):
        if h[i] >= h[i - n:i].max() and h[i] > h[i + 1:i + n + 1].max(): ph.append(i)
        if l[i] <= l[i - n:i].min() and l[i] < l[i + 1:i + n + 1].min(): pl.append(i)
    return ph, pl

def r05(x):
    """Round a price to the NSE tick size of 5 paise."""
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(round(float(x) / TICK) * TICK, 2)

# ------------------------------------------------------------------ structure
def find_structures(df, cfg):
    """Candidate structures, newest first. Each is a CHoCH (first close above a lower high after lower highs and lower lows),
    then a BOS with a displacement candle. Later BOS legs of the same move (continuations after a pullback) are candidates too,
    each with its own order block and fair value gap, so a trend keeps producing fresh zones instead of going stale."""
    N = len(df); o, h, l, c = (df[k].values for k in ('Open', 'High', 'Low', 'Close'))
    a = atr(df, cfg['atr_n']).values; n = cfg['pivot']; ph, pl = swing_points(df, n); out = []; seen = set()
    atr_at = lambda j: a[j - 1] if j >= 1 and not math.isnan(a[j - 1]) else (h[j] - l[j])
    def next_bos(start, run):
        pulled = False
        for j in range(start, N):
            if c[j] < o[j]: pulled = True
            if pulled and c[j] > run and (c[j] - o[j]) >= cfg['disp_body_atr'] * atr_at(j): return j, run
            run = max(run, h[j])
        return None, run
    def zone_for(b, floor_i):
        a_b = atr_at(b); ob = None
        for k in range(b - 1, max(floor_i, b - 6) - 1, -1):
            if c[k] < o[k]: ob = (l[k], o[k], k); break      # order block: last down candle before the displacement
        fvg = None
        for m in range(b - 1, min(b + 2, N - 1)):
            if m >= 1 and m + 1 < N and l[m + 1] > h[m - 1] and (l[m + 1] - h[m - 1]) >= cfg['fvg_min_atr'] * a_b:
                if fvg is None or (l[m + 1] - h[m - 1]) > (fvg[1] - fvg[0]): fvg = (h[m - 1], l[m + 1], m)
        if ob is None and fvg is None: return None
        zone_top = fvg[1] if fvg else ob[1]; zone_bot = ob[0] if ob else fvg[0]
        stacked = bool(ob and fvg and (fvg[0] - ob[1]) <= cfg['stack_gap_atr'] * a_b)
        leg_low = ob[0] if ob else l[b - 1]; leg_high = h[b:].max()
        if leg_high - leg_low < 2 * a_b: return None
        rng = leg_high - leg_low
        return dict(ob_low=ob[0] if ob else np.nan, ob_high=ob[1] if ob else np.nan, fvg_low=fvg[0] if fvg else np.nan, fvg_high=fvg[1] if fvg else np.nan,
                    zone_bot=zone_bot, zone_top=zone_top, zone_q=2 if stacked else 1, leg_low=leg_low, leg_high=leg_high, fib_hi=leg_high - 0.618 * rng, fib_lo=leg_high - 0.705 * rng)
    for ci in range(N - 1, max(n * 3, N - cfg['lookback']) - 1, -1):
        phs = [i for i in ph if i + n <= ci - 1]; pls = [i for i in pl if i + n <= ci - 1]
        if len(phs) < 2 or len(pls) < 2: continue
        lh, lh2 = phs[-1], phs[-2]
        if not h[lh] < h[lh2]: continue                      # last swing high is a lower high
        if not l[pls[-1]] < l[pls[-2]]: continue             # and lows are falling: a downtrend
        lvl = h[lh]
        if not c[ci] > lvl or np.any(c[lh + 1:ci] > lvl): continue       # first close above only = CHoCH
        base_low = l[pls[-1]]
        if np.any(l[ci:] < base_low): continue               # structure failed after the CHoCH
        legs = []; j, run = next_bos(ci + 1, h[ci])
        while j is not None and len(legs) < 6:
            legs.append((j, run)); j, run = next_bos(j + 1, h[j])
        for k in range(len(legs) - 1, -1, -1):              # newest leg first
            bi, lvl_b = legs[k]
            if bi in seen: continue
            z = zone_for(bi, legs[k - 1][0] if k else ci)
            if z is None: continue
            seen.add(bi); z.update(choch_i=ci, bos_i=bi, choch_level=lvl, bos_level=lvl_b, atr=a[-1], leg=k + 1); out.append(z)
        if len(out) >= 8: break
    out.sort(key=lambda z: -z['bos_i'])
    return out

def choch_bias(df15, cfg=None):
    """15m bias for options and intraday: the latest 15m structure break (a close beyond the last swing high or low) is bullish
    and price has not traded below the swing low it started from. That break was a CHoCH, or a BOS that continued a CHoCH;
    either way the 15m has turned up and is still up. No BOS is required. Returns level, base, date and the 15m order block."""
    cfg = cfg or CFG_B
    if df15 is None or len(df15) < cfg['min_bars']: return None
    N = len(df15); o, h, l, c = (df15[k].values for k in ('Open', 'High', 'Low', 'Close')); n = cfg['pivot']; ph, pl = swing_points(df15, n)
    hi = lo = None; used_h, used_l = set(), set(); pi = qi = 0; last = None
    for t in range(N):
        while pi < len(ph) and ph[pi] + n <= t: hi = ph[pi]; pi += 1
        while qi < len(pl) and pl[qi] + n <= t: lo = pl[qi]; qi += 1
        if hi is not None and hi not in used_h and c[t] > h[hi]: used_h.add(hi); last = ('up', t, hi, lo, last[0] if last else None)
        if lo is not None and lo not in used_l and c[t] < l[lo]: used_l.add(lo); last = ('down', t, lo, hi, last[0] if last else None)
    if not last or last[0] != 'up': return None
    _, t, hi_i, lo_i, before = last
    base = float(l[lo_i]) if lo_i is not None else float(l[:t + 1].min())
    if np.any(l[t:] < base): return None
    ob = next(((l[k], o[k]) for k in range(t - 1, max(-1, t - 7), -1) if c[k] < o[k]), None)
    return dict(level=float(h[hi_i]), base_low=base, age=int(N - 1 - t), date=str(df15.index[t])[:16], kind='BOS' if before == 'up' else 'CHoCH',
                ob_low=float(ob[0]) if ob else float('nan'), ob_high=float(ob[1]) if ob else float('nan'))

def zone_state(df, s, cfg, px_ref=None):
    c, l = df.Close.values, df.Low.values; a = s['atr']; b = s['bos_i']; px_ref = px_ref if px_ref is not None else c[-1]
    if len(c) - 1 - b > cfg['max_bos_age']: return 'STALE'
    height = s['zone_top'] - s['zone_bot']
    if height > cfg['max_zone_atr'] * a or 100 * height / px_ref > cfg['max_zone_pct']: return 'WIDE'
    if np.any(c[b + 1:] < s['zone_bot'] - cfg['sl_buffer_atr'] * a): return 'BROKEN'
    touch = l[max(b + 2, len(l) - 3):]                      # bars after the displacement candle; empty if the BOS is the last bar
    if c[-1] >= s['zone_bot'] and len(touch) and touch.min() <= s['zone_top']: return 'IN_ZONE'
    if c[-1] > s['zone_top'] and c[-1] - s['zone_top'] <= cfg['approach_atr'] * a: return 'APPROACH'
    return 'FAR'

def slot_volumes(idx, v, t, days=10):
    """Volumes of the same time-of-day candle on earlier days (09:15 vs 09:15, 10:15 vs 10:15). The opening candle is always heavy,
    so comparing it with the average of the whole day makes volume look strong when it is only normal."""
    key = (idx[t].hour, idx[t].minute); d = idx[t].date()
    pos = [i for i in range(t) if (idx[i].hour, idx[i].minute) == key and idx[i].date() != d]
    return v[pos[-days:]] if len(pos) >= 3 else None

def confirm(trig, s, cfg):
    """Trigger-frame confirmation: rejection in the zone, close back above the 9 EMA, relative volume."""
    res = dict(rejection=0, reclaim=0, rvol_ok=0, rvol=np.nan, trigger_ago=None, touched=False, pullback_low=np.nan)
    if trig is None or len(trig) < cfg['rvol_n'] + 5: return res
    e = ema(trig.Close, 9).values; o, h, l, c, v = (trig[k].values for k in ('Open', 'High', 'Low', 'Close', 'Volume'))
    N = len(trig); lo_i = max(0, N - cfg['h_lookback']); zb, zt, buf = s['zone_bot'], s['zone_top'], cfg['sl_buffer_atr'] * s['atr']
    touch = [i for i in range(lo_i, N) if l[i] <= zt and l[i] >= zb - 2 * buf]
    if not touch: return res
    res['touched'] = True; t0 = touch[0]; res['pullback_low'] = l[t0:].min()
    for i in touch:
        rg = h[i] - l[i]; body = abs(c[i] - o[i]) + 1e-9; lw = min(o[i], c[i]) - l[i]
        if rg > 0 and c[i] >= l[i] + 0.6 * rg and lw >= 0.5 * body: res['rejection'] = 1
    for t in range(N - 1, max(t0 + 1, N - 1 - cfg['trigger_age']) - 1, -1):
        if c[t] > e[t] and c[t - 1] <= e[t - 1]:
            res['reclaim'] = 1; res['trigger_ago'] = N - 1 - t
            base = slot_volumes(trig.index, v, t) if cfg.get('slot_rvol') and isinstance(trig.index, pd.DatetimeIndex) else None
            if base is None: base = v[max(0, t - cfg['rvol_n']):t]
            rv = v[t] / base.mean() if len(base) and base.mean() > 0 else np.nan
            res['rvol'] = rv; res['rvol_ok'] = int(rv >= cfg['rvol_min']) if not math.isnan(rv) else 0
            break
    return res

# ------------------------------------------------------------------ scoring and plan
def grade(score): return 'A+' if score >= 8 else 'A' if score >= 6 else 'B' if score >= 4 else 'skip'

def round_in_zone(bot, top):
    step = 5 if top < 200 else 10 if top < 600 else 25 if top < 1500 else 50 if top < 4000 else 100 if top < 15000 else 500
    return math.floor(top / step) * step >= bot

def detect(struct, trig, cfg, K=None, section='swing', bias=None, levels=(), extra_ticks=(), oi=None):
    """One side (long) on one instrument. Shorts are found by passing mirrored frames and K."""
    struct = struct.dropna(subset=['Open', 'High', 'Low', 'Close']).copy()
    if len(struct) < cfg['min_bars']: return None
    px = struct.Close.iloc[-1]; px_o = px if K is None else K - px; conv = (lambda x: x) if K is None else (lambda x: K - x); side = 'long' if K is None else 'short'
    cands = find_structures(struct, cfg)
    if not cands: return None
    chosen = None
    for s in cands:
        st = zone_state(struct, s, cfg, px_o)
        if st in ('IN_ZONE', 'APPROACH'): chosen = (s, st); break
    if chosen is None: chosen = (cands[0], zone_state(struct, cands[0], cfg, px_o))
    s, state = chosen
    if state not in ('IN_ZONE', 'APPROACH'): return dict(symbol=None, state=state, score=0, grade='skip')
    b = None
    if section != 'swing':
        b = choch_bias(bias)
        if b is None: return dict(symbol=None, state='NO_BIAS', score=0, grade='skip')     # your rule: the 15m must show a CHoCH
    use_vol = section != 'options'                                                         # options: you check volume yourself
    cf = confirm(trig, s, cfg); a = s['atr']; ticks = []
    triggered = bool(cf['reclaim'] and cf['touched']); last_t = trig.Close.iloc[-1] if trig is not None and len(trig) else px
    if triggered and (last_t - s['zone_top']) > cfg['trigger_max_atr'] * a: return dict(symbol=None, state='EXTENDED', score=0, grade='skip')
    if triggered and use_vol and not cf['rvol_ok']: status = 'WATCH (trigger, low volume)'
    elif triggered: status = 'TRIGGERED'
    else: status = 'WATCH (in zone)' if state == 'IN_ZONE' else 'APPROACHING (set alert)'
    entry = last_t if status == 'TRIGGERED' else s['zone_top'] - .25 * (s['zone_top'] - s['zone_bot'])
    base = s['ob_low'] if not math.isnan(s['ob_low']) else s['zone_bot']
    sl = min(base, cf['pullback_low'] if not math.isnan(cf['pullback_low']) else base) - cfg['sl_buffer_atr'] * a; risk = entry - sl; plan = {}
    if risk > 0: plan = dict(entry=entry, sl=sl, t1=s['leg_high'], t2=entry + 2 * risk, t3=entry + 3 * risk, risk_pct=100 * risk / conv(entry), r_t1=(s['leg_high'] - entry) / risk)
    lv = [conv(x) for x in levels]; zb_o, zt_o = (s['zone_bot'], s['zone_top']) if K is None else (K - s['zone_top'], K - s['zone_bot'])      # zone in real prices, for round numbers
    if round_in_zone(zb_o, zt_o) or (s['zone_bot'] - .25 * a <= s['bos_level'] <= s['zone_top'] + .25 * a) or any(s['zone_bot'] - .25 * a <= x <= s['zone_top'] + .25 * a for x in lv): ticks.append('key level')
    if min(s['fib_hi'], s['zone_top']) >= max(s['fib_lo'], s['zone_bot']): ticks.append('fib')
    if section == 'swing':
        h_ok = trig is None or len(trig) < 15 or trig.Close.iloc[-1] > ema(trig.Close, 9).iloc[-1]
        if px >= ema(struct.Close, 21).iloc[-1] - .5 * a and h_ok: ticks.append('MTF EMA')      # daily trend intact, 1H aligned
    else:
        t_ok = trig.Close.iloc[-1] > ema(trig.Close, 9).iloc[-1]; b_ok = bias is None or bias.Close.iloc[-1] > ema(bias.Close, 9).iloc[-1]
        if t_ok and b_ok: ticks.append('MTF EMA')                                              # 5m and 15m on the same side
    if section == 'options':
        if b and not math.isnan(b['ob_low']) and min(b['ob_high'], s['zone_top'] + .25 * a) >= max(b['ob_low'], s['zone_bot'] - .25 * a): ticks.append('order block (15m)')
        aln = oimod.alignment(side, conv(entry), conv(sl), conv(plan['t1']), oi) if plan else dict(aligned=False, verdict='unknown', notes=[])
        if aln['aligned']: ticks.append('OI wall')
    else: aln = None
    ticks += [t for t in extra_ticks if t not in ticks]
    structure = 2; conf = cf['rejection'] + cf['reclaim'] + (cf['rvol_ok'] if use_vol else 0)
    ctx = min(4 if section == 'options' else 3, len(ticks)); score = structure + s['zone_q'] + conf + ctx
    notes = {'swing': ['check the results date and the sector'], 'intraday': ['check the news and results date for this stock'], 'options': ['check futures OI and the OI panel', 'expiry day: skip afternoon entries or size down']}[section]
    if plan and plan['r_t1'] < 1.5: notes.append('limited room to the prior high' if side == 'long' else 'limited room to the prior low')
    if plan and plan['risk_pct'] > 7 and section == 'swing': notes.append('wide stop: reduce size or skip')
    out = dict(state=state, status=status, structure=structure, zone_q=s['zone_q'], confirm=conf, context=ctx, score=score, grade=grade(score), ticks=', '.join(ticks) or '-', rvol=cf['rvol'] if use_vol else np.nan,
               price=px, choch_level=s['choch_level'], bos_level=s['bos_level'], zone_bot=s['zone_bot'], zone_top=s['zone_top'], ob_low=s['ob_low'], ob_high=s['ob_high'], fvg_low=s['fvg_low'], fvg_high=s['fvg_high'],
               fib_lo=s['fib_lo'], fib_hi=s['fib_hi'], leg_low=s['leg_low'], leg_high=s['leg_high'], choch_date=str(struct.index[s['choch_i']])[:16], bos_date=str(struct.index[s['bos_i']])[:16], leg=s.get('leg', 1),
               notes='; '.join(notes), atr=a, pullback_low=cf['pullback_low'], rejection=cf['rejection'], reclaim=cf['reclaim'], rvol_ok=cf['rvol_ok'], oi_verdict=aln, **plan)
    if b: out.update(b15_level=b['level'], b15_base=b['base_low'], b15_date=b['date'], b15_kind=b.get('kind', 'CHoCH'), b15_ob_low=b['ob_low'], b15_ob_high=b['ob_high'])
    return out

def unflip(r, K):
    for lo, hi in PAIRS:
        if lo in r and hi in r and r[lo] is not None and r[hi] is not None: r[lo], r[hi] = K - r[hi], K - r[lo]
    for k in SINGLES:
        if k in r and r[k] is not None and not (isinstance(r[k], float) and math.isnan(r[k])): r[k] = K - r[k]
    return r

def liquid(daily, cfg=CFG):
    return daily.Close.iloc[-1] >= cfg['min_price'] and (daily.Close * daily.Volume).tail(20).mean() / 1e7 >= cfg['min_turnover_cr']

def scan_symbol(daily, hourly=None, side='long', cfg=CFG, extra_ticks=()):
    """Swing scan. The rule book allows LONG only for swing trades, so any other side is refused.
    India: stocks with a locked (zero-range) session in the last 5 days are skipped, because you cannot exit a locked circuit."""
    if side != 'long': raise ValueError('swing trading is long only')
    daily = daily.dropna(subset=['Open', 'High', 'Low', 'Close'])
    if len(daily) < cfg['min_bars'] or not liquid(daily, cfg): return None
    if bool((daily.High.tail(5) == daily.Low.tail(5)).any()): return None
    return detect(daily, hourly, cfg, None, 'swing', extra_ticks=extra_ticks)

def scan_intraday(df5, df15, side='long', cfg=CFG_I, levels=(), extra_ticks=(), section='intraday', oi=None):
    """Options (Nifty) and intraday (stocks). long = CALL / buy, short = PUT / sell. 15m needs a CHoCH only; 5m needs CHoCH + BOS."""
    df5 = df5.dropna(subset=['Open', 'High', 'Low', 'Close'])
    if len(df5) < cfg['min_bars']: return None
    if side == 'short':
        K = float(2 * max(df5.High.max(), df15.High.max() if df15 is not None else 0))
        r = detect(invert(df5, K), invert(df5, K), cfg, K, section, bias=invert(df15, K) if df15 is not None else None, levels=levels, extra_ticks=extra_ticks, oi=oi)
        return unflip(r, K) if r and 'zone_bot' in r else r
    return detect(df5, df5, cfg, None, section, bias=df15, levels=levels, extra_ticks=extra_ticks, oi=oi)

def weekly_ok(daily):
    w = daily.Close.resample('W-FRI').last().dropna()
    if len(w) < 12: return False
    e = ema(w, 9); return bool(w.iloc[-1] >= e.iloc[-1] and e.iloc[-1] >= e.iloc[-3])

def index_ok(nifty_daily): return nifty_daily is not None and len(nifty_daily) > 30 and nifty_daily.Close.iloc[-1] >= ema(nifty_daily.Close, 21).iloc[-1]

def prev_day_levels(df5):
    d = df5.index.normalize(); days = sorted(set(d))
    if len(days) < 2: return []
    p = df5[d == days[-2]]; return [float(p.High.max()), float(p.Low.min())]

def has_volume(df): return len(df) > 0 and float((df.Volume > 0).mean()) > 0.5

# ------------------------------------------------------------------ universe
def parse_universe_csv(text, with_industry=False):
    df = pd.read_csv(io.StringIO(text)); col = next((c for c in df.columns if c.strip().lower() == 'symbol'), None)
    if col is None: raise ValueError('no Symbol column')
    syms = [str(x).strip() for x in df[col].dropna() if str(x).strip()]
    if not with_industry: return syms
    icol = next((c for c in df.columns if c.strip().lower() == 'industry'), None)
    ind = {str(r[col]).strip(): str(r[icol]).strip() for _, r in df.iterrows() if icol and pd.notna(r[col]) and pd.notna(r[icol])}
    return syms, ind

def load_nifty500(local='nifty500.csv', fallback='watchlist.txt', fetch=None):
    """Live Nifty 500 list from NSE Indices, else your uploaded nifty500.csv, else the short starter watchlist.
    Returns (symbols, note, {symbol: industry})."""
    url = 'https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv'
    try:
        syms, ind = parse_universe_csv((fetch or _http_get)(url), True)
        if len(syms) >= 450: return syms, f'Nifty 500 (live list, {len(syms)} symbols)', ind
    except Exception as ex: print(f'  live Nifty 500 list unavailable: {ex}', file=sys.stderr)
    if os.path.exists(local):
        try:
            syms, ind = parse_universe_csv(open(local, encoding='utf-8-sig').read(), True)
            if len(syms) >= 450: return syms, f'Nifty 500 (your nifty500.csv, {len(syms)} symbols)', ind
        except Exception as ex: print(f'  {local} unreadable: {ex}', file=sys.stderr)
    syms = [x.strip() for x in open(fallback) if x.strip() and not x.startswith('#')]
    return syms, f'Fallback list of {len(syms)} symbols. Upload nifty500.csv to scan all 500.', {}

def _http_get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36', 'Accept': 'text/csv,*/*'})
    return urllib.request.urlopen(req, timeout=30).read().decode('utf-8-sig')

# ------------------------------------------------------------------ data (yfinance)
def _yahoo(sym): return sym if sym.startswith('^') or sym.endswith('.NS') else sym + '.NS'

def _extract(d, t, multi):
    f = (d[t] if multi else d)[COLS].dropna()
    if f.empty: raise ValueError('no data returned')
    return f

def download_many(symbols, period, interval, chunk=50, pause=1.0):
    """Chunked yfinance download with one-by-one retries. Returns ({symbol: frame}, [failed symbols])."""
    import yfinance as yf
    out, missing = {}, []
    for i in range(0, len(symbols), chunk):
        part = symbols[i:i + chunk]; tick = [_yahoo(s) for s in part]
        kw = dict(group_by='ticker', auto_adjust=False, threads=True, progress=False)
        if len(tick) == 1: kw['multi_level_index'] = False
        try: d = yf.download(tick, period=period, interval=interval, **kw)
        except Exception as ex: print(f'  chunk failed: {ex}', file=sys.stderr); d = None
        for s, t in zip(part, tick):
            try: out[s] = _extract(d, t, len(tick) > 1)
            except Exception: missing.append((s, t))
        if i + chunk < len(symbols): time.sleep(pause)
    failed = []
    for s, t in missing:
        err = None
        for attempt in range(3):
            try:
                time.sleep(1.0 + attempt)
                out[s] = _extract(yf.download(t, period=period, interval=interval, auto_adjust=False, progress=False, threads=False, multi_level_index=False), t, False); err = None; break
            except Exception as ex: err = ex
        if err is not None: failed.append(s)
    return out, failed

def tidy_daily(df, now):
    if len(df) and df.index[-1].date() == now.date() and now.hour * 60 + now.minute < 15 * 60 + 45: df = df.iloc[:-1]
    df.index = pd.DatetimeIndex(df.index).tz_localize(None) if df.index.tz is not None else df.index
    return df

def tidy_intraday(df, now, minutes):
    if not len(df): return df
    df = df.copy(); df.index = df.index.tz_convert(IST) if df.index.tz is not None else df.index.tz_localize('UTC').tz_convert(IST)
    start = df.index[-1]; end = min(start + pd.Timedelta(minutes=minutes), start.normalize() + pd.Timedelta(hours=15, minutes=30))
    return df.iloc[:-1] if end > now else df

def market_open(now): return now.weekday() < 5 and (9 * 60 + 15) <= now.hour * 60 + now.minute <= (15 * 60 + 30)

def with_today(daily, hourly):
    """For the swing chart only: add today's candle built from the closed 1H candles, and return the latest 1H close as the LTP.
    The rules still run on closed daily candles."""
    if hourly is None or not len(hourly): return daily, None
    today = hourly[hourly.index.normalize() == hourly.index[-1].normalize()]; ltp = float(hourly.Close.iloc[-1])
    if not len(today) or today.index[-1].date() <= daily.index[-1].date(): return daily, ltp
    row = pd.DataFrame([[today.Open.iloc[0], today.High.max(), today.Low.min(), today.Close.iloc[-1], today.Volume.sum()]], columns=COLS, index=[pd.Timestamp(today.index[-1].date())])
    return pd.concat([daily, row]), ltp

def results_info(sym, now):
    """Next results date from Yahoo's calendar. Often missing for NSE stocks: then it is None and you must check the NSE notice."""
    try:
        import yfinance as yf
        cal = yf.Ticker(_yahoo(sym)).calendar
        raw = cal.get('Earnings Date') if isinstance(cal, dict) else (cal.loc['Earnings Date'].tolist() if hasattr(cal, 'loc') and 'Earnings Date' in getattr(cal, 'index', []) else None)
        if raw is None: return None
        for x in (raw if isinstance(raw, (list, tuple)) else [raw]):
            d = x.date() if hasattr(x, 'date') else dt.date.fromisoformat(str(x)[:10])
            if d >= now.date(): return dict(date=d.isoformat(), days=(d - now.date()).days, source='Yahoo')
    except Exception: return None
    return None

# ------------------------------------------------------------------ output
def _num(v):
    try: f = float(v)
    except (TypeError, ValueError): return None
    return None if math.isnan(f) or math.isinf(f) else round(f, 2)

def build_item(sym, direction, r, frame, tfs, bars, section, label=None, extra=None, ltp=None):
    """Turn an engine result into the JSON the pages read: prices on the NSE tick, candles for the chart, logic and the execution plan."""
    d = frame.tail(bars); fmt = '%Y-%m-%d' if tfs[0] == '1D' else '%d %b %H:%M'
    keys = ('price', 'zone_bot', 'zone_top', 'entry', 'sl', 't1', 't2', 't3', 'fib_lo', 'fib_hi', 'ob_low', 'ob_high', 'fvg_low', 'fvg_high')
    it = {k: r05(r.get(k)) for k in keys}; it.update({k: _num(r.get(k)) for k in ('r_t1', 'risk_pct', 'rvol')})
    it.update(symbol=sym, direction=direction, label=label or direction.upper(), section=section, grade=r['grade'], score=int(r['score']), max_score=10, status=r['status'], structure=int(r['structure']), zone_q=int(r['zone_q']),
              confirm=int(r['confirm']), context=int(r['context']), ticks=[t for t in r['ticks'].split(', ') if t and t != '-'], notes=[n for n in r['notes'].split('; ') if n],
              choch_level=r05(r.get('choch_level')), bos_level=r05(r.get('bos_level')), atr=_num(r.get('atr')),
              choch_date=r['choch_date'][:10] if tfs[0] == '1D' else r['choch_date'], bos_date=r['bos_date'][:10] if tfs[0] == '1D' else r['bos_date'], tf_structure=tfs[0], tf_trigger=tfs[1],
              times=[x.strftime(fmt) for x in d.index], candles=[[round(float(x), 2) for x in row] for row in d[['Open', 'High', 'Low', 'Close']].values], ema=[round(float(x), 2) for x in ema(frame.Close, 9).tail(bars).values])
    if ltp is not None: it['price'] = r05(ltp)
    if extra: it.update(extra)
    if r.get('oi_verdict'): it['oi'] = r['oi_verdict']
    it['logic'] = explain.build_logic(section, it, r); it['plan'] = explain.build_plan(section, it)
    return it

def write_json(out_dir, name, payload):
    os.makedirs(out_dir, exist_ok=True); path = os.path.join(out_dir, name); tmp = path + '.tmp'
    with open(tmp, 'w') as f: json.dump(payload, f, separators=(',', ':'), default=str)
    os.replace(tmp, path); print(f'saved {path}'); return path

def read_json(out_dir, name, default=None):
    try: return json.load(open(os.path.join(out_dir, name)))
    except Exception: return default

def meta(mode, now, universe, scanned, failed, note, setups, **extra):
    return dict(mode=mode, generated_at=now.isoformat(timespec='seconds'), market_open=market_open(now), universe=universe, scanned=scanned, failed=failed[:40], note=note, setups=setups, **extra)

def state_of(r, min_score):
    """What became of a symbol/side this run, for the invalidation reasons."""
    if r is None: return None
    if 'zone_bot' not in r: return r.get('state')
    return 'OK' if r['score'] >= min_score else 'SCORE'

def follow(args, section, items, states, bars, now, can_open):
    path = os.path.join(args.out, f'signals_{section}.json'); led = signals.load(path)
    events = signals.update(led, section, items, states, bars, now, can_open); signals.save(path, led, now)
    print(f'{section}: {sum(s["status"] == "ACTIVE" for s in led["signals"])} active signals, {len(events)} new events'); return led

def holidays(args):
    return [h['date'] for h in newsfeed.load_events(args.events).get('holidays', [])]

# ------------------------------------------------------------------ runs
def run_swing(args, now):
    syms, note, industries = load_nifty500(args.universe_csv or 'nifty500.csv', args.watchlist)
    print(f'swing: {note}'); daily, failed = download_many(syms, '1y', '1d'); daily = {s: tidy_daily(f, now) for s, f in daily.items()}
    if not daily: print('No data downloaded (Yahoo blocked or offline). Nothing written.', file=sys.stderr); sys.exit(2)
    nd, _ = download_many(['^NSEI'], '1y', '1d'); nifty = tidy_daily(nd['^NSEI'], now) if '^NSEI' in nd else None; n_up = index_ok(nifty)
    b_sum, b_sec, per = market.breadth(daily, industries, nifty) if nifty is not None else (None, [], {})
    write_json(args.out, 'breadth.json', dict(generated_at=now.isoformat(timespec='seconds'), summary=b_sum, sectors=b_sec))
    extra = lambda f: (['weekly trend'] if weekly_ok(f) else []) + (['Nifty trend'] if n_up else [])
    cand, turnover, states = {}, {}, {}
    for s, f in daily.items():
        if len(f) >= CFG['min_bars']: turnover[s] = float((f.Close * f.Volume).tail(20).mean() / 1e7)
        r = scan_symbol(f, None, 'long', CFG, extra(f)); states[(s, 'long')] = state_of(r, args.min_score)
        if r and 'zone_bot' in r: cand[s] = r
    liq = [s for s, _ in sorted(turnover.items(), key=lambda kv: -kv[1])[:args.intraday_top]]
    write_json(args.out, 'liquid.json', dict(generated_at=now.isoformat(timespec='seconds'), top=liq))
    active = [x['symbol'] for x in signals.load(os.path.join(args.out, 'signals_swing.json'))['signals'] if x['status'] == 'ACTIVE']
    need = list(dict.fromkeys(list(cand) + active)); hourly, _ = download_many(need, '3mo', '1h') if need else ({}, [])
    hmap, rows = {s: tidy_intraday(hourly[s], now, 60) for s in hourly}, []
    for s in cand:
        h = hmap.get(s); r = scan_symbol(daily[s], h, 'long', CFG, extra(daily[s])); states[(s, 'long')] = state_of(r, args.min_score)
        if r and 'zone_bot' in r and r['score'] >= args.min_score: rows.append((s, r))
    fd = lambda t: {k: tidy_daily(v, now) for k, v in download_many(t, '1y', '1d')[0].items()}
    fh = lambda t: {k: tidy_intraday(v, now, 60) for k, v in download_many(t, '5d', '1h')[0].items()}
    checks = sector_index.confirm([s for s, _ in rows], daily, industries, fd, fh, now) if rows else {}
    for s, r in rows:                                      # a falling sector index holds a long back: it cannot sustain
        chk = checks[s]
        if chk['state'] == 'falling':
            if r['status'] == 'TRIGGERED': r['status'] = 'WATCH (index falling)'
            r['notes'] += '; ' + f"{chk['sector_index']} is falling: wait for it to stabilise"
        elif chk['state'] == 'unknown': r['notes'] += '; sector index data unavailable: check the index yourself'
    rows.sort(key=lambda sr: (-sr[1]['score'], 0 if sr[1]['status'].startswith('TRIGGER') else 1)); rows = rows[:args.top]
    items = []
    for s, r in rows:
        ex = dict(per.get(s, {})); ex['index_check'] = checks[s]; res = results_info(s, now) if len(items) < 25 else None
        if res: ex['results'] = res
        cf, ltp = with_today(daily[s], hmap.get(s)); items.append(build_item(s, 'long', r, cf, ('1D', '1H'), 70, 'swing', extra=ex, ltp=ltp))
    for s, r in rows:                                     # a held-back trigger stays on the watch list, not as a signal
        if r['status'] == 'WATCH (index falling)': states[(s, 'long')] = 'OK'
    follow(args, 'swing', items, states, hmap, now, True)
    write_json(args.out, 'swing.json', meta('swing', now, len(syms), len(daily), failed, note, items, nifty_trend=bool(n_up)))
    return items

def snapshot(df5, df15, vix, oi_info):
    last = df5.iloc[-1]; day = df5[df5.index.normalize() == df5.index[-1].normalize()]; prev = df5[df5.index.normalize() < df5.index[-1].normalize()]
    chg = (last.Close / prev.Close.iloc[-1] - 1) * 100 if len(prev) else None
    return dict(spot=_num(last.Close), change_pct=_num(chg), day_high=_num(day.High.max()), day_low=_num(day.Low.min()), above_5m=bool(last.Close > ema(df5.Close, 9).iloc[-1]),
                above_15m=bool(df15 is not None and df15.Close.iloc[-1] > ema(df15.Close, 9).iloc[-1]), ema_5m=_num(ema(df5.Close, 9).iloc[-1]), ema_15m=_num(ema(df15.Close, 9).iloc[-1]) if df15 is not None else None,
                pdh_pdl=[_num(x) for x in prev_day_levels(df5)], bias_up=choch_bias(df15) is not None,
                bias_down=choch_bias(invert(df15, float(2 * df15.High.max()))) is not None if df15 is not None else False, vix=_num(vix), oi=oi_info)

REASON = {'FAR': 'Price is far from the zone: wait for a pullback.', 'STALE': 'The structure is old.', 'WIDE': 'The zone is too tall for a sensible stop.', 'BROKEN': 'The zone was broken.',
          'EXTENDED': 'The trigger fired but price has already run away from the zone.', 'NO_BIAS': 'The 15m has no intact CHoCH in this direction.', None: 'No CHoCH + BOS found on the 5m.'}

def run_options(args, now):
    d5, _ = download_many(['^NSEI'], '5d', '5m'); d15, _ = download_many(['^NSEI'], '10d', '15m'); dv, _ = download_many(['^INDIAVIX'], '1mo', '1d')
    if '^NSEI' not in d5 or '^NSEI' not in d15: print('No Nifty data downloaded. Nothing written.', file=sys.stderr); sys.exit(2)
    df5 = tidy_intraday(d5['^NSEI'], now, 5); df15 = tidy_intraday(d15['^NSEI'], now, 15); lv = prev_day_levels(df5)
    vix = float(dv['^INDIAVIX'].Close.iloc[-1]) if '^INDIAVIX' in dv else None
    try: oi_info = oimod.analyse_chain(oimod.fetch_nse_chain('NIFTY'))
    except Exception as ex: print(f'  OI unavailable: {ex}', file=sys.stderr); oi_info = None
    hol = holidays(args); rows, why, states = [], {}, {}
    for side, label in (('long', 'CALL'), ('short', 'PUT')):
        r = scan_intraday(df5, df15, side, CFG_I, lv, section='options', oi=oi_info); states[('NIFTY 50', side)] = state_of(r, args.min_score)
        if r and 'zone_bot' in r and r['score'] >= args.min_score:
            ex = {}
            try: ex['options_trade'] = greeks.pick_strike(side, float(df5.Close.iloc[-1]), r['entry'], r['sl'], [r['t1'], r['t2'], r['t3']], vix, now, hol)
            except Exception as e: print(f'  strike selection failed: {e}', file=sys.stderr)
            rows.append(build_item('NIFTY 50', side, r, df5, ('5m', '5m'), 90, 'options', label, ex))
        else: why[label] = REASON.get((r or {}).get('state'), 'No setup.')
    follow(args, 'options', rows, states, {'NIFTY 50': df5}, now, market_open(now))
    snap = snapshot(df5, df15, vix, oi_info); snap['why_none'] = why
    write_json(args.out, 'options.json', meta('options', now, 1, 1, [], 'Nifty 50 index only', rows, snapshot=snap, session_date=str(df5.index[-1].date()), lot_size=greeks.LOT_SIZE))
    return rows

def quarter_index(ts): return (ts.hour * 60 + ts.minute - 555) // 15          # which 15-minute candle of the session we are in

def cached_15m(syms, now, state_dir):
    """15m candles only change when a new 15-minute candle closes, so reuse them for the other two 5-minute runs of the quarter."""
    try:
        obj = pickle.load(open(os.path.join(state_dir, 'm15.pkl'), 'rb'))
        if obj['day'] == str(now.date()) and quarter_index(obj['at']) == quarter_index(now) and set(syms) <= set(obj['frames']): return {s: obj['frames'][s] for s in syms}
    except Exception: pass
    return None

def save_15m(frames, now, state_dir):
    try: os.makedirs(state_dir, exist_ok=True); pickle.dump(dict(day=str(now.date()), at=now, frames=frames), open(os.path.join(state_dir, 'm15.pkl'), 'wb'))
    except Exception as ex: print(f'  could not cache 15m data: {ex}', file=sys.stderr)

def run_intraday(args, now):
    liq = read_json(args.out, 'liquid.json')
    if liq: syms = liq['top'][:args.intraday_top]; note = f'Most liquid {len(syms)} of the Nifty 500 (from the last swing scan)'
    else: syms = [x.strip() for x in open(args.watchlist) if x.strip() and not x.startswith('#')][:args.intraday_top]; note = f'Starter list of {len(syms)} (run the swing scan once to rank the Nifty 500 by liquidity)'
    d5, failed = download_many(syms, '5d', '5m'); d15 = cached_15m(list(d5), now, args.state_dir)
    if d15 is None and d5: d15, _ = download_many(list(d5), '10d', '15m'); save_15m(d15, now, args.state_dir)
    if not d5: print('No data downloaded. Nothing written.', file=sys.stderr); sys.exit(2)
    rows, states, frames = [], {}, {}
    for s, f in d5.items():
        f5 = tidy_intraday(f, now, 5); frames[s] = f5; f15 = tidy_intraday(d15[s], now, 15) if s in d15 else None
        if f15 is None or len(f5) < CFG_I['min_bars'] or not has_volume(f5): continue
        for side in ('long', 'short'):
            try: r = scan_intraday(f5, f15, side, CFG_I, prev_day_levels(f5), section='intraday')
            except Exception as ex: print(f'  error {s}: {ex}', file=sys.stderr); continue
            states[(s, side)] = state_of(r, args.min_score)
            if r and 'zone_bot' in r and r['score'] >= args.min_score: rows.append((s, side, r, f5))
    rows.sort(key=lambda x: (-x[2]['score'], 0 if x[2]['status'].startswith('TRIGGER') else 1)); rows = rows[:args.top]
    items = [build_item(s, side, r, f5, ('5m', '5m'), 90, 'intraday') for s, side, r, f5 in rows]
    follow(args, 'intraday', items, states, frames, now, market_open(now))
    write_json(args.out, 'intraday.json', meta('intraday', now, len(syms), len(d5), failed, note, items))
    return items

def run_market(args, now):
    dn, _ = download_many(['^NSEI', '^NSEBANK'], '2y', '1d'); dv, _ = download_many(['^INDIAVIX'], '1y', '1d'); d5, _ = download_many(['^NSEI'], '5d', '5m')
    if '^NSEI' not in dn: print('No Nifty data downloaded. Nothing written.', file=sys.stderr); sys.exit(2)
    nifty = tidy_daily(dn['^NSEI'], now); vix_hist = dv['^INDIAVIX'].Close if '^INDIAVIX' in dv else None
    tile = lambda f: dict(price=_num(f.Close.iloc[-1]), change_pct=_num(100 * (f.Close.iloc[-1] / f.Close.iloc[-2] - 1)), prev_close=_num(f.Close.iloc[-2]))
    f5 = tidy_intraday(d5['^NSEI'], now, 5) if '^NSEI' in d5 else None; prev_close = None
    if f5 is not None and len(f5):
        day0 = f5.index[-1].normalize(); before = f5[f5.index < day0]
        prev_close = float(before.Close.iloc[-1]) if len(before) else float(nifty.Close.iloc[-1])
    idx = dict(nifty=tile(nifty))
    if f5 is not None and len(f5) and prev_close: idx['nifty'] = dict(price=_num(f5.Close.iloc[-1]), change_pct=_num(100 * (f5.Close.iloc[-1] / prev_close - 1)), prev_close=_num(prev_close))
    if '^NSEBANK' in dn: idx['banknifty'] = tile(tidy_daily(dn['^NSEBANK'], now))
    if vix_hist is not None: idx['vix'] = dict(price=_num(vix_hist.iloc[-1]), change_pct=_num(100 * (vix_hist.iloc[-1] / vix_hist.iloc[-2] - 1)))
    daily = market.classify_daily(nifty, vix_hist); atr_d = daily['atr']
    intra = market.classify_intraday(f5, atr_d, prev_close) if f5 is not None and len(f5) else dict(regime='unclear', label=market.LABELS['unclear'], reading='No 5-minute data.')
    vix = float(vix_hist.iloc[-1]) if vix_hist is not None else None
    br = read_json(args.out, 'breadth.json') or {}
    payload = meta('market', now, 0, 0, [], 'Nifty 50, Bank Nifty, India VIX', [], indices=idx, daily=daily, intraday=intra, expected_move=market.expected_move(float(nifty.Close.iloc[-1]), vix),
                   playbook=market.playbook(daily, intra, vix), breadth=br.get('summary'), sectors=br.get('sectors') or [], breadth_time=br.get('generated_at'))
    write_json(args.out, 'market.json', payload); return payload

def run_news(args, now):
    syms = []
    for name in ('swing', 'intraday', 'options'):
        js = read_json(args.out, name + '.json') or {}
        for s in js.get('setups', []):
            if s['symbol'] not in syms and s['symbol'] != 'NIFTY 50': syms.append(s['symbol'])
    news = newsfeed.build_news(now, syms[:15]); cfg = newsfeed.load_events(args.events)
    results = {}
    for name in ('swing', 'intraday'):
        for s in (read_json(args.out, name + '.json') or {}).get('setups', []):
            if (s.get('results') or {}).get('date'): results[s['symbol']] = s['results']['date']
    ev = newsfeed.upcoming(now, cfg, results); news.update(events=ev, risk_flags=newsfeed.risk_flags(ev))
    write_json(args.out, 'news.json', news); return news

def minutes_since(path, now):
    """Age of a results file in minutes (infinite if it is missing). Keeps the 30-minute intraday rhythm even when GitHub starts runs late."""
    try: return (now - pd.Timestamp(json.load(open(path))['generated_at'])).total_seconds() / 60
    except Exception: return float('inf')

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--mode', choices=['swing', 'options', 'intraday', 'market', 'news', 'live', 'all'], default='swing')
    p.add_argument('--out', default='_site/data'); p.add_argument('--watchlist', default='watchlist.txt'); p.add_argument('--universe-csv', default=None); p.add_argument('--events', default='events.json'); p.add_argument('--state-dir', default='.state')
    p.add_argument('--min-score', type=int, default=4); p.add_argument('--top', type=int, default=60); p.add_argument('--intraday-top', type=int, default=100)
    args = p.parse_args(); now = pd.Timestamp.now(tz=IST)
    news_due = minutes_since(os.path.join(args.out, 'news.json'), now) >= 25
    modes = {'swing': ['swing'] + ([] if market_open(now) else ['market', 'news']), 'options': ['options'], 'intraday': ['intraday'], 'market': ['market'], 'news': ['news'], 'all': ['swing', 'options', 'intraday', 'market', 'news']}.get(args.mode)
    if args.mode == 'live': modes = ['options', 'intraday', 'market'] + (['news'] if news_due else [])         # Nifty and intraday stocks every 5 minutes, news about every 30
    runs = dict(swing=run_swing, options=run_options, intraday=run_intraday, market=run_market, news=run_news)
    for m in modes:
        try: runs[m](args, now)
        except SystemExit: raise
        except Exception as ex: print(f'{m} failed: {ex}', file=sys.stderr)         # one section failing must not stop the others

if __name__ == '__main__':
    main()
