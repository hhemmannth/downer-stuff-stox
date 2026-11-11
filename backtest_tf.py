#!/usr/bin/env python3
"""Backtests for the other three playbooks: POSITIONAL, INTRADAY and NIFTY OPTIONS (swing lives in backtest.py).

Each one replays the same engine the live scanner uses, bar by bar, so a trade appears only where the live scanner would have said TRIGGERED:
  positional  weekly structure, daily trigger. Long only, held for weeks.      (10 years of free daily history)
  intraday    5m structure with the 15m CHoCH bias, long and short, stocks.     (free 5m history: about 60 days, so the page GROWS weekly)
  options     the same engine on the Nifty index, then the option premium is MODELLED with Black-Scholes (no free historical option prices).
Trades are managed by signals.walk, the live tracker: stop before targets inside a bar, half off at T1, a quarter at T2, the rest at T3 or the
stop, intraday and options squared off at 15:15. Nothing here looks at a bar that had not closed at the decision time (test_backtest_tf.py checks it).

  python backtest.py --segment positional|intraday|options --out pub/data [--top N] [--workers N] [--deep DAYS]"""
import bisect, datetime as dt, json, math, os, sys, time
import numpy as np, pandas as pd
import backtest as bt, greeks, signals, strategy_scanner as sc

IST = 'Asia/Kolkata'; LOT = greeks.LOT_SIZE
COST_INTRADAY_PCT, COST_POSITIONAL_PCT = bt.SEGMENTS['intraday']['cost_pct'], bt.SEGMENTS['positional']['cost_pct']
OPT_FIXED_INR, OPT_VAR = 40.0, 0.0015              # options: brokerage per round trip, and STT + charges as a share of premium turnover
OPT_RISK_FLOOR = 0.08                              # premium risk is never taken as less than 8% of the premium (a stop a hair away would make R explode)
CFG_P = dict(sc.CFG, pivot=2, lookback=104, h_lookback=40, trigger_age=3, rvol_min=1.5, rvol_n=20, slot_rvol=False, min_bars=50, max_bos_age=40, max_zone_atr=3.5, max_zone_pct=15.0, trigger_max_atr=1.0, min_price=50.0, min_turnover_cr=20.0)

def _utc(x): return pd.Timestamp(x).value
def _aware(df, tz=IST):
    df = df.copy(); df.index = pd.DatetimeIndex(df.index)
    df.index = df.index.tz_localize(tz) if df.index.tz is None else df.index.tz_convert(tz)
    df = df[~df.index.duplicated(keep='last')].sort_index(); return df.dropna(subset=['Open', 'High', 'Low', 'Close'])

def _stamp(ts):                                           # every time on the page is IST, whatever clock the replay used (gold runs on its own session clock)
    t = pd.Timestamp(ts); return str(t.tz_convert(IST).tz_localize(None) if t.tzinfo is not None else t)[:16]

def _regime_lookup(regimes):
    keys = sorted(regimes or {})
    def get(day):                                            # the regime on the last trading day BEFORE `day`
        i = bisect.bisect_left(keys, str(day)[:10]); return regimes[keys[i - 1]] if i > 0 else 'Unknown'
    return get

def _walk(section, item, ts, bars, now):
    sig = signals.new_signal(section, item, ts); signals.walk(sig, bars, now); return sig

def _record(sig, base, risk, entry, entry_ts, cost_pct, cost_abs=None):
    closed = sig['status'] == 'CLOSED'; t_out = pd.Timestamp(sig['closed']) if closed else None
    r = float(sig.get('r_final', sig.get('r_now', 0.0))); cost_r = (cost_abs / risk) if cost_abs else (cost_pct / 100.0) * entry / risk
    return dict(base, entry_t=_stamp(entry_ts), exit_t=_stamp(t_out) if closed else _stamp(sig['checked_to']), outcome=sig['outcome'] if closed else 'OPEN', r=round(r, 2), r_net=round(r - cost_r, 2), hits=len(sig['hits']),
                closed=closed, held=[]), t_out

# ------------------------------------------------------------------ positional (weekly structure, daily trigger)
def _weekly(daily):
    return daily.resample('W-FRI').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna(subset=['Close'])

def weekly_asof(daily, W, wk_pos, wk_first, i):
    """The weekly frame as it stood at the close of daily row i: every finished week, plus the current week built from the days so far."""
    w = wk_pos[i]; part = daily.iloc[wk_first[i]:i + 1]
    cur = pd.DataFrame([[part.Open.iloc[0], part.High.max(), part.Low.min(), part.Close.iloc[-1], part.Volume.sum()]], columns=sc.COLS, index=[daily.index[i]])
    return pd.concat([W.iloc[:w], cur])

def replay_positional(sym, daily, sector='', regimes=None, nifty_up=None, cfg=None, min_score=4, prefilter=True, start_at=None, stock=True, cost_abs=None):
    """All the positional trades the playbook would have opened on one stock. daily: OHLCV with a daily index."""
    cfg = cfg or CFG_P; d = daily.dropna(subset=['Open', 'High', 'Low', 'Close']).copy(); d.index = pd.DatetimeIndex(d.index).tz_localize(None) if d.index.tz is not None else pd.DatetimeIndex(d.index)
    d = d[~d.index.duplicated(keep='last')].sort_index(); trades = []
    if len(d) < cfg['min_bars'] * 5 + 30: return trades
    W = _weekly(d); wmap = {k: n for n, k in enumerate(W.index.to_period('W-FRI'))}
    wk_pos = np.array([wmap.get(p, len(W) - 1) for p in d.index.to_period('W-FRI')]); wk_first = np.array([int(np.searchsorted(d.index.values, W.index[w].to_period('W-FRI').start_time.to_datetime64())) for w in wk_pos])
    c, v = d.Close.values, d.Volume.values; e9 = sc.ema(d.Close, 9).values; get_regime = _regime_lookup(regimes); seen = set(); busy_until = None; life = signals.POSITIONAL_EXPIRY_DAYS
    n = len(d); ok = np.zeros(n, dtype=bool)                         # a bar where the close crossed above the 9 EMA on 1.5x volume
    for t in range(cfg['rvol_n'] + 1, n):
        if c[t] > e9[t] and c[t - 1] <= e9[t - 1]:
            base = v[max(0, t - cfg['rvol_n']):t].mean(); ok[t] = bool(base > 0 and v[t] / base >= cfg['rvol_min'])
    last_ts = pd.Timestamp(d.index[-1]).tz_localize(IST)
    for i in range(cfg['min_bars'] * 5, n - 1):
        day = d.index[i]
        if start_at is not None and day < start_at: continue
        if busy_until is not None and day <= busy_until: continue
        if prefilter and not ok[max(0, i - cfg['trigger_age']):i + 1].any(): continue
        win = d.iloc[max(0, i + 1 - 240):i + 1]
        if not sc.liquid(win, cfg) or (stock and bool((win.High.tail(5) == win.Low.tail(5)).any())): continue
        struct = weekly_asof(d, W, wk_pos, wk_first, i)
        if len(struct) < cfg['min_bars']: continue
        ex = ['Nifty trend'] if nifty_up is not None and nifty_up.get(str(day)[:10]) else []
        try: r = sc.detect(struct.iloc[-cfg['lookback']:], win, cfg, None, 'swing', None, (), ex)
        except Exception: continue
        if not r or 'zone_bot' not in r or r.get('status') != 'TRIGGERED' or r['score'] < min_score or 'entry' not in r: continue
        key = (sym, r['bos_date'])
        if key in seen: continue
        entry, sl = float(r['entry']), float(r['sl']); risk = entry - sl
        if risk <= 0: continue
        seen.add(key); t_in = pd.Timestamp(day).tz_localize(IST)
        item = dict(symbol=sym, direction='long', label='LONG', grade=r['grade'], score=int(r['score']), entry=round(entry, 2), sl=round(sl, 2), t1=round(entry + risk, 2), t2=round(entry + 2 * risk, 2), t3=round(entry + 3 * risk, 2), bos_date=r['bos_date'], stage=None, status='TRIGGERED')
        fut = d.iloc[i + 1:]; fut = fut[fut.index <= day + pd.Timedelta(days=life + 2)].copy(); fut.index = fut.index.tz_localize(IST)
        end = min(last_ts, t_in + pd.Timedelta(days=life + 1)); sig = _walk('positional', item, t_in, fut, end + pd.Timedelta(days=1))
        base = dict(sym=sym, sector=sector or 'Other', side='long', grade=r['grade'], score=int(r['score']), structure=int(r['structure']), zone_q=int(r['zone_q']), confirm=int(r['confirm']), context=int(r['context']), entry=round(entry, 2), sl=round(sl, 2),
                    risk_pct=round(100 * risk / entry, 2), rvol=None if r.get('rvol') is None or (isinstance(r['rvol'], float) and math.isnan(r['rvol'])) else round(float(r['rvol']), 2), regime=get_regime(day), weekday=pd.Timestamp(day).strftime('%a'))
        if not stock: base['risk_usd'] = round(risk, 2)
        rec, t_out = _record(sig, base, risk, entry, t_in + pd.Timedelta(hours=15, minutes=30), COST_POSITIONAL_PCT, cost_abs)
        rec['hold_days'] = int((pd.Timestamp(rec['exit_t']).normalize() - pd.Timestamp(day).normalize()).days); trades.append(rec)
        busy_until = pd.Timestamp(rec['exit_t']).normalize() if rec['closed'] else pd.Timestamp(d.index[-1]) + pd.Timedelta(days=1)
    return trades

# ------------------------------------------------------------------ intraday (5m structure, 15m bias, stocks)
def _qualifiers(f5, cfg, need_volume):
    """Bars where the 5m close crossed the 9 EMA (up for longs, down for shorts), with volume at least rvol_min times the 20 before it when volume matters.
    A trigger needs one of these within the last trigger_age bars, so the engine only has to be asked at bars that follow one."""
    c, v = f5.Close.values, f5.Volume.values.astype(float); e = sc.ema(f5.Close, 9).values; n = len(c); up = np.zeros(n, bool); dn = np.zeros(n, bool); k = cfg['rvol_n']
    for t in range(1, n):
        vol_ok = True
        if need_volume:
            base = v[max(0, t - k):t]; vol_ok = len(base) > 0 and base.mean() > 0 and v[t] / base.mean() >= cfg['rvol_min']
        up[t] = vol_ok and c[t] > e[t] and c[t - 1] <= e[t - 1]; dn[t] = vol_ok and c[t] < e[t] and c[t - 1] >= e[t - 1]
    near = lambda a: np.convolve(a.astype(int), np.ones(cfg['trigger_age'] + 1, dtype=int))[:n] > 0         # a qualifier at this bar or in the trigger_age bars before it
    return near(up), near(dn)

def _day_bounds(f5):
    d = f5.index.normalize(); out, a = [], 0
    for b in range(1, len(f5) + 1):
        if b == len(f5) or d[b] != d[a]: out.append((a, b)); a = b
    return out

# Trading sessions, in minutes after midnight on the session's own clock. NSE stocks run on IST; gold runs on a UTC+2 clock, so its trading
# day (COMEX: 23:00 UTC to 22:00 UTC, an hour later in US summer) never splits across two dates and the daily candle ends at midnight.
NSE_SESSION = dict(tz=IST, first=9 * 60 + 30, last=15 * 60, square=15 * 60 + 15)
GOLD_TZ = 'Etc/GMT-2'                                                 # = UTC+2 (the sign is reversed in these zone names)
GOLD_ALL = dict(tz=GOLD_TZ, first=30, last=21 * 60, square=22 * 60 + 30)              # every session: entries 22:30-19:00 UTC (04:00-00:30 IST), all closed 20:30 UTC (02:00 IST)
GOLD_LNY = dict(tz=GOLD_TZ, first=9 * 60, last=21 * 60, square=22 * 60 + 30)            # London and New York only: entries 07:00-19:00 UTC (12:30-00:30 IST)
GOLD_SESSION = GOLD_ALL                                                                 # your choice: scan and trade through every session

def gold_session(env=None):
    """GOLD_SESSIONS=london_ny limits gold intraday entries to London and New York; anything else (the default) is every session."""
    v = str((env if env is not None else os.environ).get('GOLD_SESSIONS', '') or '').strip().lower()
    return GOLD_LNY if v in ('london_ny', 'london-ny', 'lny') else GOLD_ALL

def replay_intraday(sym, f5, f15, cfg=None, min_score=4, hist_bars=375, bias_bars=250, regimes=None, prefilter=True, cost_pct=None, first_day=None,
                    session=None, bar_min=5, bias_min=15, cost_abs=None, stock=True):
    """All the intraday trades (long and short) the live engine would have opened on one instrument. f5: 5m OHLCV (the trigger frame),
    f15: 15m OHLCV (the bias frame); any timezone. session: the entry window and square-off (NSE by default, GOLD_SESSION for gold)."""
    cfg = cfg or sc.CFG_I; cost_pct = COST_INTRADAY_PCT if cost_pct is None else cost_pct; trades = []; S = session or NSE_SESSION
    if f15 is None or len(f5) < cfg['min_bars']: return trades
    f5, f15 = _aware(f5, S['tz']), _aware(f15, S['tz'])
    if not sc.has_volume(f5): return trades
    q_long, q_short = _qualifiers(f5, cfg, True) if prefilter else (np.ones(len(f5), bool), np.ones(len(f5), bool)); get_regime = _regime_lookup(regimes)
    e15 = f15.index + pd.Timedelta(minutes=bias_min); ts5 = f5.index; seen = set(); busy = {'long': None, 'short': None}      # when each bias bar ENDS (compared as timestamps, never as raw integers: pandas 3 stores microseconds)
    if first_day is not None: first_day = pd.Timestamp(first_day).tz_localize(S['tz']) if pd.Timestamp(first_day).tzinfo is None else pd.Timestamp(first_day).tz_convert(S['tz'])
    for a, b in _day_bounds(f5):
        day = ts5[a].normalize()
        if first_day is not None and day < first_day.normalize(): continue
        sq = day + pd.Timedelta(minutes=S['square']); stop_at = day + pd.Timedelta(minutes=S['last']); open_at = day + pd.Timedelta(minutes=S['first'])
        for p in range(a, b):
            T = ts5[p] + pd.Timedelta(minutes=bar_min)
            if T < open_at or T > stop_at: continue
            lo = max(0, p + 1 - hist_bars)
            if p + 1 - lo < cfg['min_bars']: continue
            sides = [s for s, q in (('long', q_long[p]), ('short', q_short[p])) if q and (busy[s] is None or busy[s] <= T)]
            if not sides: continue
            w5 = f5.iloc[lo:p + 1]; k = int(e15.searchsorted(T, side='right')); w15 = f15.iloc[max(0, k - bias_bars):k]
            if len(w15) < 3: continue
            lv = sc.prev_day_levels(w5)
            for side in sides:
                try: r = sc.scan_intraday(w5, w15, side, cfg, lv, section='intraday')
                except Exception: continue
                if not r or 'zone_bot' not in r or r.get('status') != 'TRIGGERED' or r['score'] < min_score or 'entry' not in r: continue
                key = (side, r['bos_date'])
                if key in seen: continue
                long = side == 'long'; entry, sl = sc.r05(r['entry']), sc.r05(r['sl']); risk = (entry - sl) if long else (sl - entry)
                if risk <= 0: continue
                t1, t2, t3 = sc.r05(r['t1']), sc.r05(r['t2']), sc.r05(r['t3'])
                if (long and t1 <= entry) or (not long and t1 >= entry): t1 = sc.r05(entry + risk if long else entry - risk)
                seen.add(key); item = dict(symbol=sym, direction=side, label=side.upper(), grade=r['grade'], score=int(r['score']), entry=entry, sl=sl, t1=t1, t2=t2, t3=t3, bos_date=r['bos_date'], stage=None, status='TRIGGERED')
                end = sq
                fut = f5.iloc[p + 1:b]; fut = fut[fut.index + pd.Timedelta(minutes=bar_min) <= end]; sig = _walk('intraday', item, ts5[p], fut, end)
                if sig['status'] != 'CLOSED':                                      # still open at the square-off: out at the last close
                    signals._close(sig, end, sig['last'], 'EXPIRED', 'Squared off.')
                base = dict(sym=sym, sector='', side=side, grade=r['grade'], score=int(r['score']), structure=int(r['structure']), zone_q=int(r['zone_q']), confirm=int(r['confirm']), context=int(r['context']), entry=entry, sl=sl,
                            risk_pct=round(100 * risk / entry, 3), rvol=None if r.get('rvol') is None or (isinstance(r['rvol'], float) and math.isnan(r['rvol'])) else round(float(r['rvol']), 2), regime=get_regime(day), weekday=day.strftime('%a'), bias=r.get('b15_kind'))
                if not stock: base['risk_usd'] = round(risk, 2)
                rec, t_out = _record(sig, base, risk, entry, T, cost_pct, cost_abs)
                rec['hold_min'] = int((t_out - T).total_seconds() // 60) if t_out is not None else None; trades.append(rec); busy[side] = t_out if t_out is not None else sq
    return trades

# ------------------------------------------------------------------ Nifty options (index signals, modelled premiums)
def _bs_at(level, ts, K, expiry, sigma, kind):
    left = (dt.datetime.combine(expiry, dt.time(15, 30), tzinfo=greeks.IST) - pd.Timestamp(ts).to_pydatetime()).total_seconds() / 86400.0
    return greeks.bs(float(level), float(K), max(left, 1e-4) / 365.0, sigma, kind)['price']

def option_result(sig, ot, vix):
    """Turn a finished index trade into the option's result: each leg (T1, T2, the rest) is priced with Black-Scholes at the index level and the time it happened."""
    kind, K, sigma, expiry = ot['kind'], ot['strike'], vix / 100.0, dt.date.fromisoformat(ot['expiry']); p0 = float(ot['premium']); long = sig['direction'] == 'long'
    legs = [(f, lvl) for f, lvl in sig.get('booked', [])]; out = []
    for (f, lvl), tm in zip(legs, list(sig['hits'].values())): out.append((f, _bs_at(lvl, tm, K, expiry, sigma, kind)))           # booked legs are in the order the targets were hit
    rest = 1.0 - sum(f for f, _ in legs)
    if rest > 1e-9: out.append((rest, _bs_at(sig['exit'], sig['closed'], K, expiry, sigma, kind)))
    risk_p = max(p0 - float(ot['premium_sl']), OPT_RISK_FLOOR * p0)
    r_gross = sum(f * (p - p0) for f, p in out) / risk_p; p_exit = sum(f * p for f, p in out)
    cost_inr = OPT_FIXED_INR + OPT_VAR * (p0 + p_exit) * LOT; cost_r = cost_inr / LOT / risk_p
    return dict(r=round(r_gross, 2), r_net=round(r_gross - cost_r, 2), premium=round(p0, 2), premium_exit=round(p_exit, 2), risk_p=round(risk_p, 2), pnl_lot=round((p_exit - p0) * LOT - cost_inr, 0), cost_inr=round(cost_inr, 0))

def replay_options(f5, f15, h1, vix_daily, holidays=(), cfg=None, min_score=4, hist_bars=375, bias_bars=250, regimes=None, prefilter=True, first_day=None):
    """The Nifty options playbook on the index: CALLs on long signals and PUTs on short ones, with your rules (1H must agree, no expiry-day afternoons, stop for the day after two losing trades, nothing after 15:00, one trade at a time)."""
    cfg = cfg or sc.CFG_I; trades = []; f5, f15 = _aware(f5), _aware(f15); h1 = _aware(h1) if h1 is not None and len(h1) else None; get_regime = _regime_lookup(regimes)
    if len(f5) < cfg['min_bars']: return trades
    q_long, q_short = _qualifiers(f5, cfg, False) if prefilter else (np.ones(len(f5), bool), np.ones(len(f5), bool))
    e15 = f15.index + pd.Timedelta(minutes=15); ts5 = f5.index; seen = set(); busy = None; vix_s = vix_daily.dropna() if vix_daily is not None else None; closed_today = []
    if h1 is not None:
        e1h = pd.DatetimeIndex([min(t + pd.Timedelta(hours=1), t.normalize() + pd.Timedelta(hours=15, minutes=30)) for t in h1.index])      # a 1H bar ends at its hour, or at the 15:30 close
    for a, b in _day_bounds(f5):
        day = ts5[a].normalize(); closed_today = []
        if first_day is not None and day < first_day: continue
        sq = day + pd.Timedelta(hours=15, minutes=15); stop_at = day + pd.Timedelta(hours=15, minutes=0)
        vix = 14.0
        if vix_s is not None and len(vix_s):
            vi = vix_s[vix_s.index.tz_localize(None) < day.tz_localize(None)] if vix_s.index.tz is not None else vix_s[vix_s.index < day.tz_localize(None)]
            if len(vi): vix = float(vi.iloc[-1])
        for p in range(a, b):
            T = ts5[p] + pd.Timedelta(minutes=5)
            if T < day + pd.Timedelta(hours=9, minutes=30) or T > stop_at or (busy is not None and busy > T): continue
            lo = max(0, p + 1 - hist_bars)
            if p + 1 - lo < cfg['min_bars']: continue
            sides = [s for s, q in (('long', q_long[p]), ('short', q_short[p])) if q]
            if not sides: continue
            lost = sum(1 for tc, rn in closed_today if tc <= T and rn < 0)
            if lost >= 2: continue
            try: expiry_pm = greeks.weekly_expiry(T.to_pydatetime(), holidays) == T.date() and T.hour >= 13
            except Exception: expiry_pm = False
            if expiry_pm: continue
            w5 = f5.iloc[lo:p + 1]; k = int(e15.searchsorted(T, side='right')); w15 = f15.iloc[max(0, k - bias_bars):k]
            if len(w15) < 3: continue
            lv = sc.prev_day_levels(w5)
            if h1 is not None:
                kk = int(e1h.searchsorted(T, side='right')); w1 = h1.iloc[max(0, kk - 60):kk]
                if len(w1) >= 10: up = w1.Close.iloc[-1] > sc.ema(w1.Close, 9).iloc[-1]
            for side in sides:
                if h1 is not None and len(w1) >= 10 and up != (side == 'long'): continue                      # the 1H must agree with the direction
                ex_t = ['PDH/PDL sweep'] if sc.pdl_sweep(w15, w5, side) else []
                try: r = sc.scan_intraday(w5, w15, side, cfg, lv, extra_ticks=ex_t, section='options')
                except Exception: continue
                if not r or 'zone_bot' not in r or r.get('status') != 'TRIGGERED' or r['score'] < min_score or 'entry' not in r: continue
                key = (side, r['bos_date'])
                if key in seen: continue
                long = side == 'long'; entry, sl = sc.r05(r['entry']), sc.r05(r['sl']); risk = (entry - sl) if long else (sl - entry)
                if risk <= 0: continue
                t1, t2, t3 = sc.r05(r['t1']), sc.r05(r['t2']), sc.r05(r['t3'])
                if (long and t1 <= entry) or (not long and t1 >= entry): t1 = sc.r05(entry + risk if long else entry - risk)
                try: ot = greeks.pick_strike(side, float(w5.Close.iloc[-1]), entry, sl, [t1, t2, t3], vix, T.to_pydatetime(), holidays)
                except Exception: continue
                seen.add(key); item = dict(symbol='NIFTY 50', direction=side, label='CALL' if long else 'PUT', grade=r['grade'], score=int(r['score']), entry=entry, sl=sl, t1=t1, t2=t2, t3=t3, bos_date=r['bos_date'], stage=None, status='TRIGGERED')
                fut = f5.iloc[p + 1:b]; fut = fut[fut.index < sq]; sig = _walk('options', item, ts5[p], fut, sq)
                if sig['status'] != 'CLOSED': continue
                o = option_result(sig, ot, vix); t_out = pd.Timestamp(sig['closed'])
                base = dict(sym='NIFTY', sector='', side=side, instrument=ot['instrument'], strike=ot['strike'], dte=round(ot['dte_days'], 2), vix=round(vix, 2), grade=r['grade'], score=int(r['score']), structure=int(r['structure']), zone_q=int(r['zone_q']),
                            confirm=int(r['confirm']), context=int(r['context']), entry=entry, sl=sl, risk_pct=round(100 * risk / entry, 3), rvol=None, regime=get_regime(day), weekday=day.strftime('%a'), idx_r=round(float(sig['r_final']), 2),
                            premium=o['premium'], premium_exit=o['premium_exit'], pnl_lot=o['pnl_lot'], modelled=True)
                rec = dict(base, entry_t=_stamp(T), exit_t=_stamp(t_out), outcome=sig['outcome'], r=o['r'], r_net=o['r_net'], hits=len(sig['hits']), closed=True, held=[], hold_min=int((t_out - T).total_seconds() // 60))
                trades.append(rec); busy = t_out; closed_today.append((t_out, o['r_net']))
    return trades


# ------------------------------------------------------------------ running them: data, workers, merging, files
def _liquid_top(syms, daily_frames, n):
    turn = {s: float((f.Close * f.Volume).tail(60).mean()) for s, f in daily_frames.items() if len(f) > 60}
    return sorted(turn, key=lambda x: -turn[x])[:n] if n else sorted(turn, key=lambda x: -turn[x])

def _nifty_context(now, years='2y'):
    raw, _ = sc.yahoo_many(['^NSEI'], years, '1d'); nd = sc.tidy_daily(raw['^NSEI'], now) if '^NSEI' in raw else None
    if nd is None: return None, {}, {}
    up = (nd.Close >= sc.ema(nd.Close, 21)); return nd, bt.regime_map(nd), {str(k)[:10]: bool(v) for k, v in up.items()}

def _job_pos(job): sym, d, sector, regimes, up, ms, st = job; return replay_positional(sym, d, sector, regimes, up, min_score=ms, start_at=st)
def _job_intra(job): sym, f5, f15, regimes, fd, ms = job; return replay_intraday(sym, f5, f15, regimes=regimes, first_day=fd, min_score=ms)

# ------------------------------------------------------------------ gold (XAUUSD) data
CFG_GP = dict(CFG_P, min_price=0.0, min_turnover_cr=0.0)              # gold positional: no NSE liquidity floor
GOLD_LABEL = 'XAUUSD'
def gold_symbol(env=None): return str((env if env is not None else os.environ).get('GOLD_SYMBOL', '') or 'GC=F').strip()
def gold_cost(env=None):
    try: return max(0.0, float((env if env is not None else os.environ).get('GOLD_COST', '') or 0.35))
    except ValueError: return 0.35

def _bar_open(df, minutes, now):
    """Drop the last candle when it has not finished yet (gold trades almost round the clock, so the NSE close cannot be used for this)."""
    if len(df) and df.index[-1] + pd.Timedelta(minutes=minutes) > now: return df.iloc[:-1]
    return df

def gold_intraday(sym, period, interval, now, fetch=None):
    """Gold candles (5m, 15m or 1h), tz-aware IST, the unfinished last candle removed."""
    raw, _ = (fetch or sc.yahoo_many)([sym], period, interval); f = raw.get(sym)
    if f is None or not len(f): return None
    f = f.dropna(subset=['Open', 'High', 'Low', 'Close']).copy(); idx = pd.DatetimeIndex(f.index)
    f.index = (idx.tz_localize('UTC') if idx.tz is None else idx).tz_convert(IST); f = f[~f.index.duplicated(keep='last')].sort_index()
    return _bar_open(f, {'1m': 1, '5m': 5, '15m': 15, '1h': 60}[interval], now)

def gold_daily(sym, period, now, fetch=None):
    """Daily gold candles, one per session (dated by the day the session ends), without today's unfinished session."""
    raw, _ = (fetch or sc.yahoo_many)([sym], period, '1d'); f = raw.get(sym)
    if f is None or not len(f): return None
    f = f.dropna(subset=['Open', 'High', 'Low', 'Close']).copy(); idx = pd.DatetimeIndex(f.index)
    f.index = (idx.tz_convert(None) if idx.tz is not None else idx).normalize(); f = f[~f.index.duplicated(keep='last')].sort_index()
    today = pd.Timestamp(now).tz_convert(GOLD_TZ).tz_localize(None).normalize()           # the session still trading now
    return f[f.index < today]

def mirror_k(*frames):
    """The mirror constant for shorts: prices become K - p, so a falling market looks like a rising one to the long-only swing engines."""
    return float(2 * max(float(f.High.max()) for f in frames if f is not None and len(f)))

def both_sides(longs, shorts_mirrored, K):
    """Gold swing and positional trade both ways: the short trades were found on the mirrored chart, so their prices are mirrored back.
    R, the outcome and the dollar stop distance are the same in both pictures (the mirror keeps every distance)."""
    for t in longs: t['side'] = 'long'
    for t in shorts_mirrored:
        t['side'] = 'short'; t['entry'], t['sl'] = round(K - t['entry'], 2), round(K - t['sl'], 2); t['risk_pct'] = round(100 * abs(t['entry'] - t['sl']) / t['entry'], 2)
    return sorted(longs + shorts_mirrored, key=lambda t: (t['exit_t'], t['entry_t']))

def _from(fd, rules):
    """The first day a replay may open a trade: after the warm-up AND inside the window (1 April 2026 by default)."""
    st = bt.start_stamp(rules)
    if st is None: return fd
    st = st.tz_localize(fd.tzinfo) if fd.tzinfo is not None else st
    return max(fd, st)

def _pool(fn, jobs, workers, label, every=25):
    out, t0 = [], time.time()
    if workers > 1 and len(jobs) > 6:
        import multiprocessing as mp
        with mp.get_context('fork').Pool(workers) as pool:
            for n, res in enumerate(pool.imap_unordered(fn, jobs, chunksize=2), 1):
                out += res
                if n % every == 0: print(f'  {label}: {n}/{len(jobs)} stocks, {len(out)} trades, {time.time() - t0:.0f}s', flush=True)
    else:
        for n, j in enumerate(jobs, 1):
            out += fn(j)
            if n % every == 0: print(f'  {label}: {n}/{len(jobs)}, {len(out)} trades, {time.time() - t0:.0f}s', flush=True)
    return sorted(out, key=lambda t: (t['exit_t'], t['entry_t']))

def _load_prev(out_dir, seg):
    try: return json.load(open(os.path.join(out_dir, bt.SEGMENTS[seg]['files'][1])))
    except Exception: return {}

def _save(out_dir, seg, rep, trades, window, universe, params):
    rf, tf = bt.SEGMENTS[seg]['files']
    with open(os.path.join(out_dir, rf), 'w') as f: json.dump(rep, f, separators=(',', ':'), default=str)
    with open(os.path.join(out_dir, tf), 'w') as f: json.dump(dict(window=window, universe=universe, params=params, trades=trades), f, separators=(',', ':'), default=str)

def _intraday_frames(syms, now, deep, minutes_budget):
    """5m and 15m candles: Yahoo's last 60 days, or (with --deep DAYS and Angel One set up) as far back as Angel One answers."""
    d5, _ = sc.yahoo_many(syms, '60d', '5m'); d15, _ = sc.yahoo_many(syms, '60d', '15m')
    f5 = {s: sc.tidy_intraday(f, now, 5) for s, f in d5.items() if len(f)}; f15 = {s: sc.tidy_intraday(f, now, 15) for s, f in d15.items() if len(f)}
    if deep:
        import datasource; t0 = time.time(); got = 0
        if datasource.angel() is None: print('  --deep: Angel One is not available, using Yahoo\'s 60 days', flush=True)
        else:
            for s in list(f5):
                if time.time() - t0 > minutes_budget * 60: print('  --deep: time budget used, the rest keep Yahoo\'s 60 days', flush=True); break
                try:
                    a5, a15 = datasource.deep_intraday(s, '5m', deep), datasource.deep_intraday(s, '15m', deep)
                    if a5 is not None and a15 is not None and len(a5) > len(f5[s]): f5[s], f15[s] = a5, a15; got += 1
                except Exception as ex: print(f'  --deep {s}: {ex}', file=sys.stderr)
            print(f'  --deep: {got} stocks got longer history from Angel One', flush=True)
    return f5, f15

def _liquid_list(a, now):
    try:
        liq = json.load(open(os.path.join(a.out, 'liquid.json')))['top']
        if liq: return liq
    except Exception: pass
    syms, _, _ = sc.load_nifty500('nifty500.csv', 'watchlist.txt'); raw, _ = sc.yahoo_many(syms, '3mo', '1d')
    return _liquid_top(syms, {s: sc.tidy_daily(f, now) for s, f in raw.items() if len(f)}, 0)

def _warm(frames, now, days):
    day0 = min((f.index[0] for f in frames if f is not None and len(f)), default=now)
    return (pd.Timestamp(day0).tz_convert(IST) if pd.Timestamp(day0).tzinfo else pd.Timestamp(day0).tz_localize(IST)).normalize() + pd.Timedelta(days=days)

def main_segment(a):
    seg = a.segment; t0 = time.time(); now = pd.Timestamp.now(tz=IST); os.makedirs(a.out, exist_ok=True); acct = bt.account_from_env(segment=seg); workers = a.workers
    rules = bt.rules_from_env(); ms = rules['min_score']; start = bt.start_stamp(rules)
    print(f'backtest {seg}: starting, {bt.rules_text(rules)}', flush=True)
    if seg == 'positional':
        syms, note, industries = sc.load_nifty500('nifty500.csv', 'watchlist.txt'); print(f'backtest: {note}', flush=True)
        raw, _ = sc.yahoo_many(syms, '10y', '1d'); daily = {s: sc.tidy_daily(f, now) for s, f in raw.items() if len(f) > 300}; pick = _liquid_top(syms, daily, a.top)
        nd, regimes, up = _nifty_context(now, '10y'); print(f'backtest: {len(pick)} stocks, replaying on {workers} cores', flush=True)
        trades = _pool(_job_pos, [(s, daily[s], industries.get(s, ''), regimes, up, ms, start) for s in pick], workers, 'positional')
        first = min((str(daily[s].index[0])[:10] for s in pick), default=''); window = dict(**{'from': first, 'to': str(max(daily[s].index[-1] for s in pick))[:10]}); params = dict(top=a.top, seconds=round(time.time() - t0)); universe = len(pick)
    elif seg == 'intraday':
        prev = _load_prev(a.out, seg); liq = _liquid_list(a, now)
        pick = liq[:a.top or 100]; print(f'backtest: {len(pick)} most liquid stocks, downloading 5m and 15m candles', flush=True)
        fa, fb = _intraday_frames(pick, now, a.deep, a.deep_minutes)
        nd, regimes, up = _nifty_context(now); fd = _from(_warm(fa.values(), now, 3), rules)
        print(f'backtest: replaying {len(fa)} stocks on {workers} cores from {str(fd)[:10]}', flush=True)
        new = _pool(_job_intra, [(s, fa[s], fb[s], regimes, fd, ms) for s in fa if s in fb], workers, seg, every=10)
        trades = bt.merge_trades(prev.get('trades', []), new); first = min([str(fd)[:10]] + ([prev['window']['from']] if prev.get('window', {}).get('from') else []))
        window = {'from': first, 'to': str(max((f.index[-1] for f in fa.values()), default=now))[:10], 'note': 'grows every week'}; params = dict(top=len(pick), days=a.deep or 60, seconds=round(time.time() - t0)); universe = len(fa)
    elif seg.startswith('gold_'):
        sym = gold_symbol(); cost = gold_cost(); style = seg[5:]; prev = _load_prev(a.out, seg) if style == 'intraday' else {}
        gd = gold_daily(sym, '10y' if style == 'positional' else '3y', now)
        if gd is None or len(gd) < 300: print(f'No gold daily data downloaded for {sym}.', file=sys.stderr); return 2
        regimes = bt.regime_map(gd); print(f'backtest: gold from {sym}, {len(gd)} daily candles, cost {cost} dollars per ounce', flush=True)
        if style == 'intraday':
            fa = gold_intraday(sym, '60d', '5m', now); fb = gold_intraday(sym, '60d', '15m', now)
            if fa is None or fb is None or not len(fa): print('No gold intraday data downloaded.', file=sys.stderr); return 2
            fd = _from(_warm([fa], now, 3), rules); print(f'backtest: replaying gold intraday from {str(fd)[:10]}', flush=True)
            new = replay_intraday(GOLD_LABEL, fa, fb, regimes=regimes, first_day=fd, min_score=ms, cost_abs=cost, stock=False, session=gold_session())
            trades = bt.merge_trades(prev.get('trades', []), new); first = min([str(fd)[:10]] + ([prev['window']['from']] if prev.get('window', {}).get('from') else []))
            window = {'from': first, 'to': str(fa.index[-1])[:10], 'note': 'grows every week'}
        elif style == 'swing':
            h1 = gold_intraday(sym, '730d', '1h', now)
            if h1 is None or len(h1) < 100: print('No gold hourly data downloaded.', file=sys.stderr); return 2
            run = lambda dd, hh: bt.replay_symbol(GOLD_LABEL, dd, hh, 'Gold', regimes, min_score=ms, start_at=start, day_tz=GOLD_TZ, stock=False, cost_abs=cost)
            K = mirror_k(gd, h1); trades = both_sides(run(gd, h1), run(sc.invert(gd, K), sc.invert(h1, K)), K)
            window = {'from': str(h1.index[0])[:10], 'to': str(gd.index[-1])[:10]}
        else:
            run = lambda dd: replay_positional(GOLD_LABEL, dd, 'Gold', regimes, None, CFG_GP, min_score=ms, start_at=start, stock=False, cost_abs=cost)
            K = mirror_k(gd); trades = both_sides(run(gd), run(sc.invert(gd, K)), K)
            window = {'from': str(gd.index[0])[:10], 'to': str(gd.index[-1])[:10]}
        params = dict(source=sym, cost_usd=cost, seconds=round(time.time() - t0)); universe = 1
    else:                                                                           # options
        prev = _load_prev(a.out, seg); raw5, _ = sc.yahoo_many(['^NSEI'], '60d', '5m'); raw15, _ = sc.yahoo_many(['^NSEI'], '60d', '15m'); raw1h, _ = sc.yahoo_many(['^NSEI'], '730d', '1h'); rawv, _ = sc.yahoo_many(['^INDIAVIX'], '2y', '1d')
        if '^NSEI' not in raw5 or '^NSEI' not in raw15: print('No Nifty data downloaded.', file=sys.stderr); return 2
        f5, f15 = sc.tidy_intraday(raw5['^NSEI'], now, 5), sc.tidy_intraday(raw15['^NSEI'], now, 15); h1 = sc.tidy_intraday(raw1h['^NSEI'], now, 60) if '^NSEI' in raw1h else None
        if a.deep:
            import datasource
            if datasource.angel() is not None:
                try:
                    d5, d15 = datasource.deep_intraday('^NSEI', '5m', a.deep), datasource.deep_intraday('^NSEI', '15m', a.deep)
                    if d5 is not None and d15 is not None and len(d5) > len(f5): f5, f15 = d5, d15; print(f'  --deep: Angel One gave {len(d5)} five-minute Nifty candles', flush=True)
                except Exception as ex: print(f'  --deep: {ex}', file=sys.stderr)
        vix = sc.tidy_daily(rawv['^INDIAVIX'], now).Close if '^INDIAVIX' in rawv else None; nd, regimes, up = _nifty_context(now)
        import argparse; hol = sc.holidays(argparse.Namespace(events='events.json'))
        fd = _from(_aware(f5).index[0].normalize() + pd.Timedelta(days=3), rules); print(f'backtest: replaying Nifty options from {str(fd)[:10]}', flush=True)
        new = replay_options(f5, f15, h1, vix, hol, regimes=regimes, first_day=fd, min_score=ms)
        trades = bt.merge_trades(prev.get('trades', []), new); first = min([str(fd)[:10]] + ([prev['window']['from']] if prev.get('window', {}).get('from') else []))
        window = {'from': first, 'to': str(_aware(f5).index[-1])[:10], 'note': 'modelled premiums; grows every week'}; params = dict(days=a.deep or 60, seconds=round(time.time() - t0)); universe = 1
    rep = bt.report(trades, (), window=window, universe=universe, params=params, acct=acct, segment=seg, rules=rules); _save(a.out, seg, rep, trades, window, universe, params)
    s = rep['summary']['net']; print(f"backtest {seg}: {s['n']} trades, win {s['win']}%, expectancy {s['avg']}R net, profit factor {s['pf']}, max drawdown {s['max_dd']}R, {time.time() - t0:.0f}s"); return 0
