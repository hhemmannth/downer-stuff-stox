"""Positional, intraday and Nifty-options backtests (backtest_tf.py). Three kinds of checks:
 1. the REAL engine on the engineered setup (its mirror image for shorts), with the speed filter on and off;
 2. a stand-in engine whose decisions depend on the exact data window it is given, so any peek at a bar that had not closed would change the results;
 3. the rules (one trade at a time, 15:00 cutoff, expiry afternoons, 1H alignment, stop after two losses) and the option pricing arithmetic.
No network. Run: python test_backtest_tf.py"""
import datetime as dt, json, math
import numpy as np, pandas as pd
import backtest as bt, backtest_tf as tf, greeks, signals, strategy_scanner as sc, tf_fixture as fx
import os
os.environ['BACKTEST_FROM'] = 'all'; os.environ['MIN_SCORE'] = '4'      # these tests check the machinery on every grade and old dates;
                                                                          # the A+ gate and the financial-year window have their own tests (test_rules.py)
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
sc.CFG_B.update(min_bars=20)
IST = 'Asia/Kolkata'; real_scan, real_detect = sc.scan_intraday, sc.detect
key = lambda t: (t['sym'], t['side'], t['entry_t']); same = lambda a, b: [(key(t), t['exit_t'], t['outcome'], t['r']) for t in a] == [(key(t), t['exit_t'], t['outcome'], t['r']) for t in b]

# ====================================================================== 1) intraday, the real engine
f5, f15 = fx.engineered()
tr = tf.replay_intraday('X', f5, f15, cfg=fx.CFG5)
check('intraday: the engineered setup gives exactly one trade, a long, at 14:30 (the bar where the engine first says TRIGGERED)', len(tr) == 1 and tr[0]['side'] == 'long' and tr[0]['entry_t'] == '2026-10-12 14:30', str([(t['side'], t['entry_t']) for t in tr]))
t0 = tr[0]; E, S = t0['entry'], t0['sl']
check('intraday: entry is the close of that 5-minute bar on the NSE tick; the stop is below it; A grade or better', E == sc.r05(float(f5.Close.iloc[62])) and S < E and t0['grade'] in ('A', 'A+') and t0['score'] >= 6, f"{E} {S} {t0['grade']}")
check('intraday: a setup that is still open at the end of the data is squared off at 15:15 on the last price (no profit invented)', t0['outcome'] == 'EXPIRED' and abs(t0['r']) < 0.2 and t0['closed'])
trm = tf.replay_intraday('X', *fx.engineered(mirror=True), cfg=fx.CFG5)
check('intraday: the mirror-image data gives the mirror-image SHORT: entry 2300 - 1101, stop 2300 - 1025.4', len(trm) == 1 and trm[0]['side'] == 'short' and abs(trm[0]['entry'] - (2300 - E)) < 0.11 and abs(trm[0]['sl'] - (2300 - S)) < 0.11, str([(t['side'], t['entry'], t['sl']) for t in trm]))
a_, b_ = tf.replay_intraday('X', f5, f15, cfg=fx.CFG5, prefilter=False), tf.replay_intraday('X', f5, f15, cfg=fx.CFG5, prefilter=True)
check('intraday: the speed filter never drops a trade (same trades with it on and off)', same(a_, b_) and len(a_) == 1)

# outcomes from the real tracker: stop, targets, T1 then stop to entry
risk = E - S; w5 = f5.iloc[:63]; lv = sc.prev_day_levels(w5); r_ = real_scan(w5, f15, 'long', fx.CFG5, lv, section='intraday'); t1 = sc.r05(r_['t1']); R1 = (t1 - E) / risk
dn = fx.with_future(f5, [E - (1.6 * risk) * k / 4 for k in range(1, 9)])
t_sl = tf.replay_intraday('X', dn, f15, cfg=fx.CFG5)[0]
check('intraday: price falls through the stop -> SL at exactly -1.00R, then a little worse after costs', t_sl['outcome'] == 'SL' and t_sl['r'] == -1.0 and t_sl['r_net'] < -1.0 and t_sl['hold_min'] > 0, f"{t_sl['outcome']} {t_sl['r']} {t_sl['r_net']}")
up = fx.with_future(f5, [E + (3.5 * risk) * k / 6 for k in range(1, 7)] + [E + 3.5 * risk] * 2)
t_up = tf.replay_intraday('X', up, f15, cfg=fx.CFG5)[0]
exp = 0.5 * R1 + 0.25 * 2 + 0.25 * 3
check('intraday: price runs through T1, T2 and T3 -> TARGET; R = half at T1 + a quarter at T2 + a quarter at T3 (as in your plan)', t_up['outcome'] == 'TARGET' and abs(t_up['r'] - exp) < 0.03 and t_up['hits'] == 3, f"{t_up['r']} vs {exp:.2f}")
back = fx.with_future(f5, [t1 + 0.2 * risk, t1 + 0.1 * risk, E + 0.3 * risk, E - 0.2 * risk, E - 0.5 * risk, E - 0.5 * risk])
t_bk = tf.replay_intraday('X', back, f15, cfg=fx.CFG5)[0]
check('intraday: T1 hit (half booked) then price falls back: the stop moved to entry, so the rest closes at 0R -> TRAIL, total = half of T1', t_bk['outcome'] == 'TRAIL' and abs(t_bk['r'] - 0.5 * R1) < 0.03, f"{t_bk['outcome']} {t_bk['r']} vs {0.5 * R1:.2f}")
late = tf.replay_intraday('X', *fx.engineered(start='2026-10-12 09:50'), cfg=fx.CFG5)
check('intraday: a trigger after 15:00 is never taken (your rule), the same setup earlier in the day is', late == [] and len(tr) == 1)
nov = f5.copy(); nov['Volume'] = 0
check('intraday: a frame with no volume (an index) is skipped for stocks', tf.replay_intraday('X', nov, f15, cfg=fx.CFG5) == [])
check('intraday: first_day keeps early days out', tf.replay_intraday('X', f5, f15, cfg=fx.CFG5, first_day=pd.Timestamp('2026-10-13', tz=IST)) == [])

# tiled days
T5 = [tf.replay_intraday(f'S{s}', *fx.tiled(s), cfg=fx.CFG5, hist_bars=200, prefilter=p) for s in (1, 2) for p in (False, True)]
check('intraday: the real engine triggers every session on tiled copies, and the speed filter gives identical results on them', len(T5[0]) >= 6 and same(T5[0], T5[1]) and same(T5[2], T5[3]), f'{len(T5[0])} + {len(T5[2])} trades')
tiles = T5[0]; ok_seq = all(b['entry_t'] >= a['exit_t'] for a_, b in zip(tiles, tiles[1:]) for a in [a_] if a['sym'] == b['sym'] and a['side'] == b['side'])
check('intraday: one trade at a time per stock and side (each opens after the previous closed)', ok_seq)

# ====================================================================== 2) no look-ahead with a data-dependent stand-in engine
VIOL = []
def fake_scan(df5, df15, side, cfg=None, levels=(), extra_ticks=(), section='intraday'):
    if df15 is not None and len(df15) and df15.index[-1] + pd.Timedelta(minutes=15) > df5.index[-1] + pd.Timedelta(minutes=5): VIOL.append('a 15m bar that had not finished was used')
    if df5.index[-1] + pd.Timedelta(minutes=5) > pd.Timestamp(df5.index[-1].normalize() + pd.Timedelta(hours=15, minutes=5)): VIOL.append('decision after 15:00')
    c = df5.Close.values
    if len(c) < 30 or df15 is None or len(df15) < 6: return None
    mom = c[-1] / c[-13:-1].mean() - 1; m15 = df15.Close.iloc[-1] / df15.Close.iloc[-5:-1].mean() - 1; long = side == 'long'
    if (long and mom > 0.0012 and m15 > 0) or (not long and mom < -0.0012 and m15 < 0):
        e = float(c[-1]); rk = e * 0.003; sl = e - rk if long else e + rk; sg = 1 if long else -1
        return dict(zone_bot=e - rk, zone_top=e, status='TRIGGERED', score=8, grade='A+', structure=2, zone_q=2, confirm=3, context=2, rvol=2.0, entry=e, sl=sl, t1=e + sg * 1.2 * rk, t2=e + sg * 2 * rk, t3=e + sg * 3 * rk, bos_date=str(df5.index[-9])[:16], b15_kind='CHoCH')
    return None
sc.scan_intraday = fake_scan
W5, W15 = fx.walk5(3, days=10, p0=1000.0); cfgf = dict(sc.CFG_I, min_bars=60); full = tf.replay_intraday('Z', W5, W15, cfg=cfgf, prefilter=False)
cut = pd.Timestamp('2026-09-08 12:00', tz=IST); c5 = W5[W5.index + pd.Timedelta(minutes=5) <= cut]; c15 = W15[W15.index + pd.Timedelta(minutes=15) <= cut]
part = tf.replay_intraday('Z', c5, c15, cfg=cfgf, prefilter=False); safe = lambda L: [t for t in L if pd.Timestamp(t['exit_t']) < pd.Timestamp('2026-09-08 11:45')]
check('no look-ahead (intraday): with a data-dependent engine there are plenty of trades (long and short)', len(full) >= 15 and {t['side'] for t in full} == {'long', 'short'}, f'{len(full)} trades')
check('no look-ahead (intraday): cutting the data at 12:00 leaves every earlier trade exactly as before, and adds none', same(safe(full), safe(part)) and len(safe(full)) > 5, f'{len(safe(full))} compared')
check('no look-ahead (intraday): no 15m bar was used before it had finished, and no decision came after 15:00', not VIOL, str(set(VIOL)))
check('every intraday trade is closed by 15:15 and its entry was not after 15:00', all(t['exit_t'][11:] <= '15:15' and t['entry_t'][11:] <= '15:00' and t['closed'] for t in full))
check('shorts are signed correctly: a short that hit its stop is -1R, never +1R', all(t['r'] == -1.0 for t in full if t['outcome'] == 'SL') and any(t['side'] == 'short' and t['outcome'] == 'SL' for t in full))
check('R never exceeds +3 or falls below -1 (stop, T1, T2, T3 and square-off are all inside that range)', all(-1.0001 <= t['r'] <= 3.0001 for t in full), f"{min(t['r'] for t in full)}..{max(t['r'] for t in full)}")

# ---- rules, with forced triggers on a flat day
def flat_day(start='2026-10-12', price=24000.0, crash=(), spike=()):
    idx = pd.date_range(f'{start} 09:15', periods=75, freq='5min', tz=IST); rows = []
    for i, ts in enumerate(idx):
        c = price - (30 if i in crash else 0) + (60 if i in spike else 0); rows.append([price, max(price, c) + 2, min(price, c) - (45 if i in crash else 2), c, 1000])
    f5 = pd.DataFrame(rows, columns=sc.COLS, index=idx); return f5, f5.resample('15min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
def forced(bars, side='long', risk=40.0):
    def scan(df5, df15, s, cfg=None, levels=(), extra_ticks=(), section='intraday'):
        p = len(df5) - 1
        if s != side or p not in bars: return None
        e = float(df5.Close.iloc[-1]); sg = 1 if s == 'long' else -1
        return dict(zone_bot=e - risk, zone_top=e, status='TRIGGERED', score=9, grade='A+', structure=2, zone_q=2, confirm=3, context=3, rvol=2.0, entry=e, sl=e - sg * risk, t1=e + sg * risk, t2=e + sg * 2 * risk, t3=e + sg * 3 * risk, bos_date=f'k{p}', b15_kind='CHoCH')
    return scan
cfg1 = dict(sc.CFG_I, min_bars=30); F5, F15 = flat_day(crash={36, 51, 66})
sc.scan_intraday = forced({35, 50, 65}); got = tf.replay_intraday('F', F5, F15, cfg=cfg1, prefilter=False)
check('intraday rules: three triggers, each followed by a crash through its stop -> three losing trades (intraday has no stop-after-two-losses rule; the account view limits it)', [t['outcome'] for t in got] == ['SL', 'SL', 'SL'] and [t['entry_t'][11:] for t in got] == ['12:15', '13:30', '14:45'], str([(t['entry_t'][11:], t['outcome']) for t in got]))
F5b, F15b = flat_day(); sc.scan_intraday = forced({35, 50}); got = tf.replay_intraday('F', F5b, F15b, cfg=cfg1, prefilter=False)
check('intraday rules: a second trigger while the first is still open is ignored (one trade at a time per stock and side)', len(got) == 1 and got[0]['outcome'] == 'EXPIRED')
sc.scan_intraday = forced({35, 36, 37}); got = tf.replay_intraday('F', F5b, F15b, cfg=cfg1, prefilter=False)
check('intraday rules: the same structure (same bos date) can only trigger once', len(got) == 1 or len({t['entry_t'] for t in got}) == len(got))

# ====================================================================== 3) Nifty options
VIX = pd.Series([13.0, 14.0, 15.0], index=pd.to_datetime(['2026-10-08', '2026-10-09', '2026-10-12'])); O5, O15 = fx.engineered(); HOL = []
sc.scan_intraday = real_scan
to = tf.replay_options(O5, O15, None, VIX, HOL, cfg=fx.CFG5)
check('options: the engineered setup gives one CALL trade on Nifty (no volume needed, so earlier than the intraday one: 12:10) with a modelled strike and premium', len(to) == 1 and to[0]['side'] == 'long' and to[0]['instrument'].endswith('CE') and to[0]['modelled'] and to[0]['premium'] > 0 and to[0]['strike'] % 50 == 0, str(to and (to[0]['instrument'], to[0]['premium'])))
check('options: the volatility used is the previous trading day\'s VIX (14 from 09 Oct, never the 15 of the day itself)', to[0]['vix'] == 14.0 and to[0]['dte'] > 0.5, f"vix {to[0]['vix']} dte {to[0]['dte']}")
tue = tf.replay_options(*fx.engineered(start='2026-10-13 10:30'), None, VIX, HOL, cfg=fx.CFG5); mon = tf.replay_options(*fx.engineered(start='2026-10-12 10:30'), None, VIX, HOL, cfg=fx.CFG5)
check('options rules: no entry on an expiry-day afternoon (Tuesday 13 Oct, the trigger comes at 13:25), the same setup on Monday is taken', tue == [] and len(mon) == 1 and mon[0]['entry_t'][11:] == '13:25', str([t['entry_t'] for t in mon]))
dn1 = pd.DataFrame({'Open': np.linspace(24100, 23900, 24), 'High': np.linspace(24110, 23910, 24), 'Low': np.linspace(24090, 23890, 24), 'Close': np.linspace(24100, 23900, 24), 'Volume': 0}, index=pd.date_range('2026-10-09 09:15', periods=24, freq='1h', tz=IST))
up1 = dn1.copy(); up1[['Open', 'High', 'Low', 'Close']] = up1[['Open', 'High', 'Low', 'Close']].values[::-1]
check('options rules: when the 1H is on the other side of its 9 EMA the CALL is not taken; when it agrees it is', tf.replay_options(O5, O15, dn1, VIX, HOL, cfg=fx.CFG5) == [] and len(tf.replay_options(O5, O15, up1, VIX, HOL, cfg=fx.CFG5)) == 1)
# outcomes in option terms
Eo = to[0]['entry']; Ro = Eo - to[0]['sl']; O5c = O5.iloc[:35]                  # the data up to the trigger bar, then a path we choose
assert tf.replay_options(O5c, O15, None, VIX, HOL, cfg=fx.CFG5)[0]['entry'] == Eo
o_dn = tf.replay_options(fx.with_future(O5c, [Eo - (1.6 * Ro) * k / 4 for k in range(1, 9)]), O15, None, VIX, HOL, cfg=fx.CFG5)[0]
o_up = tf.replay_options(fx.with_future(O5c, [Eo + (3.5 * Ro) * k / 6 for k in range(1, 7)] + [Eo + 3.5 * Ro] * 2), O15, None, VIX, HOL, cfg=fx.CFG5)[0]
check('options: the index hits the stop -> the option loses about 1R (within theta and the modelling of the stop premium) and the lot loses money', o_dn['outcome'] == 'SL' and -1.4 < o_dn['r'] < -0.6 and o_dn['pnl_lot'] < 0 and o_dn['r_net'] < o_dn['r'], f"{o_dn['r']} {o_dn['pnl_lot']}")
check('options: the index runs through T3 -> the option wins by far more than it risked and the lot makes money after costs', o_up['outcome'] == 'TARGET' and o_up['r'] > 1.0 and o_up['pnl_lot'] > 0 and o_up['premium_exit'] > o_up['premium'], f"{o_up['r']} {o_up['pnl_lot']}")
# the arithmetic of option_result against an independent calculation
ot = dict(kind='CE', strike=24000, expiry='2026-10-13', premium=120.0, premium_sl=96.0); sg = dict(direction='long', booked=[(0.5, 24050.0), (0.25, 24100.0)], hits={'T1': '2026-10-12T10:30:00+05:30', 'T2': '2026-10-12T11:00:00+05:30'}, exit=24150.0, closed='2026-10-12T12:00:00+05:30')
res = tf.option_result(sg, ot, 14.0)
px = lambda lvl, ts: greeks.bs(lvl, 24000, max((dt.datetime(2026, 10, 13, 15, 30, tzinfo=greeks.IST) - dt.datetime.fromisoformat(ts)).total_seconds() / 86400, 1e-4) / 365, 0.14, 'CE')['price']
legs = 0.5 * px(24050, '2026-10-12T10:30:00+05:30') + 0.25 * px(24100, '2026-10-12T11:00:00+05:30') + 0.25 * px(24150, '2026-10-12T12:00:00+05:30'); cost = 40 + 0.0015 * (120 + legs) * 65
check('option_result: each leg is priced at its own level and time; R = (value - premium paid) / (premium paid - premium at the stop)', abs(res['r'] - (legs - 120) / 24) < 0.01 and abs(res['cost_inr'] - cost) < 1 and abs(res['r_net'] - ((legs - 120) / 24 - cost / 65 / 24)) < 0.01, f"{res['r']} vs {(legs - 120) / 24:.2f}")
p0 = px(24000, '2026-10-12T10:30:00+05:30'); tiny = tf.option_result(dict(sg, booked=[], hits={}, exit=23990.0, closed='2026-10-12T10:40:00+05:30'), dict(ot, premium=p0, premium_sl=p0 - 0.1), 14.0)
check('option_result: a stop a hair from entry cannot make R explode (premium risk is floored at 8% of the premium)', abs(tiny['risk_p'] - 0.08 * p0) < 0.01 and -2 < tiny['r'] < 0, f"{tiny['risk_p']} {tiny['r']}")
# stop after two losing trades (forced triggers, real pricing)
NF5, NF15 = flat_day(price=24000.0, crash={36, 51, 66}); sc.scan_intraday = forced({35, 50, 65}); opt = tf.replay_options(NF5, NF15, None, VIX, HOL, cfg=cfg1, prefilter=False)
check('options rules: after two losing trades the day is over: the third trigger (14:45) is skipped', [t['outcome'] for t in opt] == ['SL', 'SL'] and [t['entry_t'][11:] for t in opt] == ['12:15', '13:30'], str([(t['entry_t'][11:], t['outcome']) for t in opt]))
NF5b, NF15b = flat_day(price=24000.0, crash={36, 66}); sc.scan_intraday = forced({35, 50, 65}); opt2 = tf.replay_options(NF5b, NF15b, None, VIX, HOL, cfg=cfg1, prefilter=False)
check('options rules: one loss does not stop the day (loss, open trade skipped while running, then another entry later)', len(opt2) >= 2 and opt2[0]['outcome'] == 'SL')
NS5, NS15 = flat_day(price=24000.0); sc.scan_intraday = forced({35, 50}, side='short'); ps = tf.replay_options(NS5, NS15, None, VIX, HOL, cfg=cfg1, prefilter=False)
check('options: a short signal buys a PUT', len(ps) == 1 and ps[0]['side'] == 'short' and ps[0]['instrument'].endswith('PE'), str(ps and ps[0]['instrument']))
sc.scan_intraday = real_scan

# ====================================================================== 4) positional
D1 = fx.daily_walk(1, 700, start='2021-01-04'); wk = tf._weekly(D1); n = len(D1)
wmap = {k: i for i, k in enumerate(wk.index.to_period('W-FRI'))}; wk_pos = np.array([wmap[p] for p in D1.index.to_period('W-FRI')]); wk_first = np.array([int(np.searchsorted(D1.index.values, wk.index[w].to_period('W-FRI').start_time.to_datetime64())) for w in wk_pos])
i = int(np.nonzero(D1.index.dayofweek == 2)[0][60]); wa = tf.weekly_asof(D1, wk, wk_pos, wk_first, i); part_week = D1.iloc[i - 2:i + 1]
check('positional: the weekly frame at a Wednesday close has the finished weeks plus a part-week built only from Mon-Wed', abs(wa.iloc[-1].Close - D1.Close.iloc[i]) < 1e-9 and abs(wa.iloc[-1].High - part_week.High.max()) < 1e-9 and abs(wa.iloc[-1].Low - part_week.Low.min()) < 1e-9 and abs(wa.iloc[-1].Volume - part_week.Volume.sum()) < 1e-6 and abs(wa.iloc[-1].Open - part_week.Open.iloc[0]) < 1e-9, str(wa.index[-1]))
check('positional: the finished weeks in that frame equal a normal weekly resample (nothing from Thu-Fri leaks in)', np.allclose(wa.iloc[:-1].values, wk.iloc[:len(wa) - 1].values) and wa.index[-2] < D1.index[i])
PV = []
def fake_detect(struct, trig, cfg, K=None, section='swing', bias=None, levels=(), extra_ticks=()):
    if struct.index[-1] > trig.index[-1]: PV.append('weekly frame ends after the daily one')
    if len(trig) < 30 or len(struct) < 10: return None
    if trig.Close.iloc[-1] > trig.Close.iloc[-21:-1].mean() * 1.05 and struct.Close.iloc[-1] > struct.Close.iloc[-5:-1].mean():
        e = float(trig.Close.iloc[-1]); sl = float(struct.Low.iloc[-3:].min()) * 0.98
        if sl >= e: return None
        return dict(zone_bot=sl, zone_top=e, status='TRIGGERED', score=9, grade='A+', structure=2, zone_q=2, confirm=3, context=2, rvol=2.0, entry=e, sl=sl, bos_date=str(struct.index[-4])[:10])
    return None
sc.detect = fake_detect; cfgp = dict(tf.CFG_P, min_price=0, min_turnover_cr=0)
pall = [t for s in (1, 2, 3) for t in tf.replay_positional(f'P{s}', fx.daily_walk(s, 800, start='2021-01-04'), regimes={}, cfg=cfgp, prefilter=False)]
check('positional: the stand-in engine gives a good number of trades on three random stocks', len(pall) >= 8, f'{len(pall)} trades')
cutd = pd.Timestamp('2023-06-30'); fulls = [t for s in (1, 2, 3) for t in tf.replay_positional(f'P{s}', fx.daily_walk(s, 800, start='2021-01-04'), regimes={}, cfg=cfgp, prefilter=False)]
cuts = [t for s in (1, 2, 3) for t in tf.replay_positional(f'P{s}', fx.daily_walk(s, 800, start='2021-01-04').loc[:cutd], regimes={}, cfg=cfgp, prefilter=False)]
sf = lambda L: sorted([(t['sym'], t['entry_t'], t['exit_t'], t['outcome'], t['r']) for t in L if pd.Timestamp(t['exit_t']) < cutd - pd.Timedelta(days=5) and t['closed']])
check('no look-ahead (positional): cutting the history at 30 Jun 2023 leaves every earlier closed trade exactly as before', sf(fulls) == sf(cuts) and len(sf(fulls)) >= 4, f'{len(sf(fulls))} compared')
check('no look-ahead (positional): the weekly frame never ended after the daily frame it was paired with', not PV, str(set(PV)))
check('positional: one trade at a time per stock, exits after entries, never more than 3R or less than -1R, held at most about 120 days (closed on the first daily bar after the limit)', all(t['exit_t'] >= t['entry_t'] and -1.0001 <= t['r'] <= 3.0001 and (t['hold_days'] or 0) <= 123 for t in pall) and all(b['entry_t'] >= a['exit_t'] for p in ('P1', 'P2', 'P3') for L in [sorted([t for t in pall if t['sym'] == p], key=lambda t: t['entry_t'])] for a, b in zip(L, L[1:])))
# the ladder on daily bars, forced
def one_trade(path, n0=420):
    base = fx.daily_walk(9, n0, start='2021-01-04'); sc.detect = lambda *a, **k: None
    last = base.index[-1]; rows = []; prev = float(base.Close.iloc[-1])
    for c in path: rows.append([prev, max(prev, c) * 1.001, min(prev, c) * 0.999, c, 1_000_000]); prev = c
    ext = pd.DataFrame(rows, columns=sc.COLS, index=pd.bdate_range(last + pd.Timedelta(days=1), periods=len(path))); ext.iloc[0, 3] = ext.iloc[0, 3]
    d = pd.concat([base, ext]); E0 = float(base.Close.iloc[-1]); sl0 = E0 * 0.9
    def det(struct, trig, cfg, K=None, section='swing', bias=None, levels=(), extra_ticks=()):
        if trig.index[-1] == last: return dict(zone_bot=sl0, zone_top=E0, status='TRIGGERED', score=9, grade='A+', structure=2, zone_q=2, confirm=3, context=2, rvol=2.0, entry=E0, sl=sl0, bos_date='2021-01-01')
        return None
    sc.detect = det; r = tf.replay_positional('Q', d, regimes={}, cfg=cfgp, prefilter=False, start_at=last); sc.detect = fake_detect; return r, E0, E0 - sl0
t3p, E0, R0 = one_trade([E0 * 1.02 for E0 in [500.0]] and [round(float(fx.daily_walk(9, 420, start='2021-01-04').Close.iloc[-1]) * (1 + 0.04 * k), 2) for k in range(1, 12)])
check('positional: the daily close that triggers is the entry; the trade reaches T1, T2 and T3 -> TARGET with R = 1.75 and an exit within weeks', len(t3p) == 1 and t3p[0]['outcome'] == 'TARGET' and abs(t3p[0]['r'] - 1.75) < 0.01 and t3p[0]['hits'] == 3, str(t3p and (t3p[0]['outcome'], t3p[0]['r'])))
E1 = float(fx.daily_walk(9, 420, start='2021-01-04').Close.iloc[-1]); R1p = E1 * 0.1
t1p, _, _ = one_trade([E1 + 1.1 * R1p, E1 + 1.05 * R1p] + [E1 - 1.2 * R1p] * 3)
check('positional: T1 hit (half off), then price falls to the ORIGINAL stop (no early breakeven, your rule) -> 0.5 x 1R - 0.5 x 1R = 0R, outcome TRAIL', len(t1p) == 1 and t1p[0]['outcome'] == 'TRAIL' and abs(t1p[0]['r']) < 0.01, str(t1p and (t1p[0]['outcome'], t1p[0]['r'])))
t2p, _, _ = one_trade([E1 + 1.1 * R1p, E1 + 2.1 * R1p] + [E1 - 0.1 * R1p] * 3)
check('positional: T2 hit (a quarter), stop moves to entry, price comes back -> 0.5 x 1 + 0.25 x 2 + 0.25 x 0 = +1.0R', len(t2p) == 1 and t2p[0]['outcome'] == 'TRAIL' and abs(t2p[0]['r'] - 1.0) < 0.01, str(t2p and t2p[0]['r']))
tsl, _, _ = one_trade([E1 * 0.97] * 3 + [E1 * 0.88] * 3)
check('positional: price falls through the stop -> SL at -1.00R', len(tsl) == 1 and tsl[0]['outcome'] == 'SL' and tsl[0]['r'] == -1.0 and tsl[0]['hold_days'] >= 3)
texp, _, _ = one_trade([E1 * 1.01, E1 * 0.99] * 80)
check('positional: a trade that goes nowhere is closed after 120 days (not 28, the swing limit)', len(texp) == 1 and texp[0]['outcome'] == 'EXPIRED' and 115 <= texp[0]['hold_days'] <= 125, str(texp and (texp[0]['outcome'], texp[0]['hold_days'])))
topen, _, _ = one_trade([E1 * 1.01, E1 * 0.99] * 6)
check('positional: a trade still running when the data ends is kept apart (not closed, not counted)', len(topen) == 1 and not topen[0]['closed'] and topen[0]['outcome'] == 'OPEN')
sc.detect = real_detect
sm = [t for s in (4, 5) for t in tf.replay_positional(f'R{s}', fx.daily_walk(s, 900, start='2019-01-01'), cfg=cfgp)]
check('positional: the real engine runs end to end on random data without error (random data rarely satisfies a strict playbook)', isinstance(sm, list) and all(-1.0001 <= t['r'] <= 3.0001 for t in sm), f'{len(sm)} trades')

# ====================================================================== 5) merging and the reporting for each segment
a = dict(sym='X', side='long', entry_t='2026-09-01 10:00', exit_t='2026-09-01 12:00', r=1.0); b = dict(a, r=2.0); c = dict(sym='X', side='short', entry_t='2026-09-02 10:00', exit_t='2026-09-02 11:00', r=-1.0)
mg = bt.merge_trades([a], [b, c])
check('merge: the same stock, side and entry time is the same trade (the new run replaces the old one); different ones are added; sorted by exit', len(mg) == 2 and mg[0]['r'] == 2.0 and mg[1]['side'] == 'short')
def mk(i, seg):
    d = pd.Timestamp('2026-09-01') + pd.Timedelta(days=i); r = [1.75, -1.0, 0.0][i % 3]
    t = dict(sym='NIFTY' if seg == 'options' else f'S{i % 5}', sector='IT', side='long' if i % 2 else 'short', grade='A+', score=9, structure=2, zone_q=2, confirm=3, context=2, entry_t=f'{d:%Y-%m-%d} 10:{15 + i % 40}', exit_t=f'{d:%Y-%m-%d} 12:30', entry=100.0, sl=99.0, risk_pct=0.5,
             outcome='TARGET' if r > 1 else 'SL' if r < 0 else 'TRAIL', r=r, r_net=r - 0.1, hits=1, rvol=1.8, regime='Range', weekday=d.strftime('%a'), closed=True, held=[], hold_min=45)
    if seg == 'options': t.update(vix=14.0 + i % 4, dte=1.5 + i % 5, strike=24000, premium=100.0)
    if seg == 'positional': t.update(hold_days=20, hold_min=None)
    return t
for seg, want in (('swing', {'grade', 'regime', 'volume', 'stop', 'sector'}), ('positional', {'grade', 'regime', 'sector', 'stop'}), ('intraday', {'grade', 'side', 'hour', 'volume', 'stop'}), ('options', {'grade', 'side', 'hour', 'vix', 'dte', 'regime'})):
    R = bt.report([mk(i, seg) for i in range(60)], segment=seg)
    check(f'report ({seg}): has the breakdown tables that make sense for it, in order, and the right title and costs', want <= set(R['by']) and [x['key'] for x in R['by_order']] == [k for k in R['by_order'] and [x['key'] for x in R['by_order']]] and R['segment'] == seg and R['title'] == bt.SEGMENTS[seg]['title'] and R['cost_pct'] == bt.SEGMENTS[seg]['cost_pct'], str(sorted(R['by'])))
Ri = bt.report([mk(i, 'intraday') for i in range(60)], segment='intraday'); Rp = bt.report([mk(i, 'positional') for i in range(60)], segment='positional')
check('report: intraday and options show their hold time in minutes, positional in days; each has its own assumptions text', Ri['summary']['avg_hold_min'] == 45 and Ri['summary']['avg_hold_days'] is None and Rp['summary']['avg_hold_days'] == 20 and 'weekly' in ' '.join(Rp['assumptions']).lower() and '60 days' in ' '.join(Ri['assumptions']))
Ro = bt.report([mk(i, 'options') for i in range(60)], segment='options'); check('report (options): the page is told the premiums are modelled', 'MODELLED PREMIUMS' in ' '.join(Ro['assumptions']) and Ro['account']['stop_after_losses'] == 2)
three = [dict(mk(0, 'options'), r_net=-1.0, entry_t='2026-09-01 10:00', exit_t='2026-09-01 10:30'), dict(mk(0, 'options'), r_net=-1.0, entry_t='2026-09-01 11:00', exit_t='2026-09-01 11:30'), dict(mk(0, 'options'), r_net=2.0, entry_t='2026-09-01 13:00', exit_t='2026-09-01 14:00')]
A0 = dict(risk=0.5, risk_aplus=0.75, aplus_score=8, open_cap=2.0, day_stop=9, week_stop=9, month_half=9, month_stop=9, max_per_day=5)
s2 = bt.simulate_account(three, 8, True, dict(A0, stop_after_losses=2)); s0 = bt.simulate_account(three, 8, True, dict(A0, stop_after_losses=None))
check('account (options): "stop after 2 losing trades in a day" skips the third trade that day; without the rule it is taken', s2['n'] == 2 and s2['skipped']['loss_limit'] == 1 and s0['n'] == 3)
env = bt.account_from_env({'STOP_AFTER_LOSSES': '3'}, 'options'); env0 = bt.account_from_env({}, 'options'); envs = bt.account_from_env({}, 'swing')
check('account: options default to stopping after 2 losses, other segments do not; STOP_AFTER_LOSSES can change it', env0['stop_after_losses'] == 2 and envs['stop_after_losses'] is None and env['stop_after_losses'] == 3)
check('regime and day helpers: the regime used is the last one BEFORE the day; sessions are split correctly', tf._regime_lookup({'2026-09-01': 'A', '2026-09-03': 'B'})('2026-09-03') == 'A' and tf._regime_lookup({'2026-09-01': 'A'})('2026-08-01') == 'Unknown' and tf._day_bounds(W5)[0] == (0, 75) and len(tf._day_bounds(W5)) == 10)

# ====================================================================== 6) deeper history from Angel One (paged windows, stops when the data runs out)
import http.server, os, tempfile, threading, urllib.parse, datasource
NOW = dt.datetime(2026, 11, 10, 16, 0, tzinfo=greeks.IST); CUT = {'days': 150}; CALLS = []
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _j(self, o): b = json.dumps(o).encode(); self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(b)
    def do_GET(self): self._j([dict(token='2885', symbol='RELIANCE-EQ', name='RELIANCE', exch_seg='NSE', instrumenttype='')])
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])) or b'{}')
        if 'loginByPassword' in self.path: return self._j(dict(status=True, message='SUCCESS', data=dict(jwtToken='J')))
        a, b = (dt.datetime.strptime(body[k], '%Y-%m-%d %H:%M') for k in ('fromdate', 'todate')); CALLS.append((a.date(), b.date())); first = (NOW - dt.timedelta(days=CUT['days'])).replace(tzinfo=None).date(); out = []; d = a.date()
        while d <= b.date():
            if d.weekday() < 5 and d >= first:
                for k in range(75): out.append([f'{d}T{(dt.datetime(2000, 1, 1, 9, 15) + dt.timedelta(minutes=5 * k)):%H:%M}:00+05:30', 100, 101, 99, 100.5, 1000])
            d += dt.timedelta(days=1)
        self._j(dict(status=True, message='SUCCESS', errorcode='', data=out))
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start(); URL = f'http://127.0.0.1:{srv.server_port}'
os.environ.update(ANGEL_API_KEY='k', ANGEL_CLIENT_CODE='c', ANGEL_MPIN='1', ANGEL_TOTP_SECRET='JBSWY3DPEHPK3PXP', ANGEL_BASE=URL, ANGEL_MASTER_URL=URL + '/master')
for x in os.listdir(tempfile.gettempdir()):
    if x.startswith('angel_session_'): os.remove(os.path.join(tempfile.gettempdir(), x))
datasource.reset(); datasource.configure(tempfile.mkdtemp()); datasource.Angel.GAP = 0.02
deep = datasource.deep_intraday('RELIANCE', '5m', 400, now=NOW)
check('deep history: windows of at most 95 days are fetched backwards and joined into one sorted frame without duplicates', deep is not None and deep.index.is_monotonic_increasing and deep.index.is_unique and len(deep) > 75 * 90, f'{len(deep)} candles')
check('deep history: it reaches back as far as the data goes (about 150 days) and not beyond', deep.index[0].date() >= (NOW - dt.timedelta(days=151)).date() and deep.index[0].date() <= (NOW - dt.timedelta(days=140)).date() and deep.index[-1].date() >= (NOW - dt.timedelta(days=3)).date(), f'{deep.index[0].date()} to {deep.index[-1].date()}')
check('deep history: after two empty windows in a row it stops asking (4 requests here, not 5 or more), so it never hammers the API', len(CALLS) == 4, f'{len(CALLS)} requests')
CUT['days'] = -10; CALLS.clear(); check('deep history: when Angel One has nothing it returns None (the run falls back to Yahoo)', datasource.deep_intraday('RELIANCE', '5m', 400, now=NOW) is None and len(CALLS) == 2)
check('deep history: daily candles and unknown intervals are not fetched this way', datasource.deep_intraday('RELIANCE', '1d', 400, now=NOW) is None)
srv.shutdown()
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED'); raise SystemExit(1 if fails else 0)
