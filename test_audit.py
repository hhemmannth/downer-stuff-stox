"""Audit tests (18 Nov 2026): independent checks of the data hygiene, the stale-data fail-safe, the trade tracker's arithmetic (long, short,
partial exits, gaps, same-candle stop and target), the backtest statistics, option costs, Black-Scholes, the swing replay's use of time,
API failures and the System health validation. Expected values are worked out here by hand, never taken from the code under test.
No network, no orders. Run: python test_audit.py"""
import json, math, os, sys, tempfile, time
import numpy as np, pandas as pd
os.environ.pop('STALE_CHECK', None)
import dataquality as dq, datasource as ds, signals as sg, backtest as bt, backtest_tf as tf, greeks, validation
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
TZ = 'Asia/Kolkata'; T = lambda s: pd.Timestamp(s, tz=TZ)
COLS = ['Open', 'High', 'Low', 'Close', 'Volume']
def frame(rows, start='2026-11-17 10:00', freq='5min'):
    return pd.DataFrame(rows, columns=COLS[:len(rows[0])], index=pd.date_range(start, periods=len(rows), freq=freq, tz=TZ))

# ====================================================================== 1) candle hygiene (Section 3)
idx = pd.DatetimeIndex([T('2026-11-17 10:00'), T('2026-11-17 10:10'), T('2026-11-17 10:05'), T('2026-11-17 10:10'), T('2026-11-17 10:15'), T('2026-11-17 10:20'), T('2026-11-17 10:25')])
dirty = pd.DataFrame([[100, 101, 99, 100.5, 10], [101, 102, 100, 101.5, 10], [100.5, 101, 100, 100.8, 10], [101, 103, 100.5, 102, 12],
                      [102, 101, 103, 102, 10],                 # high below low: not a candle
                      [102, 102.5, 101.5, 102.9, -5],          # close above high (rounding): repaired; negative volume
                      [0, 103, 102, 102.5, 0]], columns=COLS, index=idx)   # no open (index feeds), zero volume (legitimate)
clean, n = dq.sanitize(dirty)
check('hygiene: the repeated 10:10 candle is kept once (the later print)', clean.index.is_unique and float(clean.loc[T('2026-11-17 10:10'), 'High']) == 103, str(n))
check('hygiene: rows come out in time order', clean.index.is_monotonic_increasing)
check('hygiene: a candle with high below low is removed', T('2026-11-17 10:15') not in clean.index and n['dropped'] == 1)
check('hygiene: a close above the high widens the high (row kept) and negative volume becomes 0', float(clean.loc[T('2026-11-17 10:20'), 'High']) == 102.9 and float(clean.loc[T('2026-11-17 10:20'), 'Volume']) == 0 and n['neg_volume'] == 1)
check('hygiene: a missing open becomes the close (a doji, never a down candle); zero volume is left alone', float(clean.loc[T('2026-11-17 10:25'), 'Open']) == 102.5 and float(clean.loc[T('2026-11-17 10:25'), 'Volume']) == 0)
check('hygiene: nothing impossible is left (independent invariant check)', dq.ohlc_problems(clean) == [], str(dq.ohlc_problems(clean)))
check('hygiene: the dirty frame really was dirty (the invariant check sees it)', set(dq.ohlc_problems(dirty)) >= {'duplicate timestamps', 'timestamps out of order', 'high below low', 'negative volume'}, str(dq.ohlc_problems(dirty)))
rng = np.random.default_rng(3); bad_left = 0
for k in range(200):                                                          # property test: random corruption, always clean afterwards
    m = 60; c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, m))); o = np.r_[c[0], c[:-1]]; h = np.maximum(o, c) * 1.002; l = np.minimum(o, c) * 0.998
    f = pd.DataFrame({'Open': o, 'High': h, 'Low': l, 'Close': c, 'Volume': rng.integers(0, 1000, m).astype(float)}, index=pd.date_range('2026-11-17 09:15', periods=m, freq='5min', tz=TZ))
    j = rng.integers(0, m, 6); f.iloc[j[0], 1] = f.iloc[j[0], 2] * 0.99; f.iloc[j[1], 3] = f.iloc[j[1], 1] * 1.01; f.iloc[j[2], 4] = -1
    f = pd.concat([f, f.iloc[[j[3]]]]).iloc[rng.permutation(m + 1)]; f.iloc[0, 0] = np.nan
    g, _ = dq.sanitize(f); bad_left += bool(dq.ohlc_problems(g))
check('hygiene: 200 randomly corrupted frames all come out with no impossible candle, duplicate or disorder', bad_left == 0, f'{bad_left} left dirty')

# every download passes through it, whichever source served it
ds.reset(); ds.angel = (lambda: None)
got, failed = ds.fetch(['AAA', 'BBB'], '5d', '5m', yahoo=lambda sy, pe, iv: ({'AAA': dirty.copy(), 'BBB': dirty.iloc[[4]].copy()}, []))
check('fetch: the frame Yahoo returned is cleaned before any rule sees it', 'AAA' in got and dq.ohlc_problems(got['AAA']) == [])
check('fetch: a frame with no real candle left is not returned (callers treat it as no data)', 'BBB' not in got)
check('fetch: the repairs are counted for System health', ds.report()['quality'].get('5m', {}).get('AAA', {}).get('dropped') == 1, str(ds.report().get('quality')))

# ====================================================================== 2) API failures and fallbacks (Section 11)
class DeadAngel:
    dead = False; gap = 0.0
    def token_for(self, s): return '1'
    def candles(self, *a, **k): raise RuntimeError('connection reset')
    def slow_down(self): pass
ds.reset(); ds.angel = (lambda: DeadAngel())
y_calls = []
def yahoo_ok(sy, pe, iv): y_calls.append(list(sy)); return ({s: frame([[100, 101, 99, 100.5, 10]] * 3) for s in sy}, [])
got, failed = ds.fetch(['AAA', 'BBB', 'CCC'], '5d', '5m', yahoo=yahoo_ok)
check('Angel One down: every symbol falls back to Yahoo, none lost', set(got) == {'AAA', 'BBB', 'CCC'} and failed == [] and sorted(y_calls[0]) == ['AAA', 'BBB', 'CCC'])
ds.reset(); ds.angel = (lambda: None)
got, failed = ds.fetch(['AAA', 'BBB'], '5d', '5m', yahoo=lambda sy, pe, iv: ({}, list(sy)))
check('Yahoo down too: nothing is returned and both symbols are reported as failed (no invented candles)', got == {} and sorted(failed) == ['AAA', 'BBB'])
def yahoo_garbage(sy, pe, iv): return ({'AAA': pd.DataFrame([[np.nan, np.nan, np.nan, np.nan, np.nan]], columns=COLS, index=[T('2026-11-17 10:00')])}, [])
got, failed = ds.fetch(['AAA'], '5d', '5m', yahoo=yahoo_garbage)
check('an invalid API answer (all NaN) never becomes a candle', got == {})
class SlowAngel(DeadAngel):
    def candles(self, *a, **k): time.sleep(0.15); return frame([[100, 101, 99, 100.5, 10]] * 3)
ds.reset(); ds.angel = (lambda: SlowAngel()); ds.set_budget(0.2); ds.WORKERS = 1
t0 = time.time(); got, failed = ds.fetch([f'S{i}' for i in range(12)], '5d', '5m', yahoo=yahoo_ok); took = time.time() - t0
check('slow Angel One: the per-run time budget stops waiting and Yahoo serves the rest (all 12 returned)', len(got) == 12 and took < 2.5, f'{took:.2f}s, {len(got)} returned')
ds.reset(); ds.set_budget(None)

# ====================================================================== 3) the stale-data fail-safe (Section 3: DATA UNAVAILABLE, NO TRADE)
it = lambda sym='NIFTY 50': dict(symbol=sym, direction='long', label='CALL', grade='A+', score=9, status='TRIGGERED', entry=100.0, sl=90.0, t1=110.0, t2=120.0, t3=130.0, bos_date='2026-11-18 09:30', zone_bot=95.0, zone_top=101.0)
led = sg.load('/x'); a = it(); sg.update(led, 'options', [a], {}, {'NIFTY 50': frame([[99, 101, 98, 100]], '2026-11-18 10:50')}, T('2026-11-18 11:00'))
check('fresh 5m candles (closed 5 min ago): the trigger opens a tracked trade', len(led['signals']) == 1 and a['status'] == 'TRIGGERED')
led = sg.load('/x'); a = it(); sg.update(led, 'options', [a], {}, {'NIFTY 50': frame([[99, 101, 98, 100]], '2026-11-18 10:00')}, T('2026-11-18 11:00'))
check('5m candles that stopped 55 min ago: NO trade, and the page says why', led['signals'] == [] and a['status'].startswith('TRIGGERED (not taken: data stale') and a.get('data_stale'), a['status'])
led = sg.load('/x'); a = dict(it('PBK'), label='LONG', stage=5); sg.update(led, 'swing', [a], {}, {'PBK': frame([[99, 101, 98, 100]], '2026-11-17 14:15', '1h')}, T('2026-11-18 08:37'))
check("swing pre-open scan reading yesterday's 15m entry: not opened at yesterday's price", led['signals'] == [] and 'data stale' in a['status'], a['status'])
led = sg.load('/x'); a = dict(it('PBK'), label='LONG'); sg.update(led, 'swing', [a], {}, {'PBK': frame([[99, 101, 98, 100]], '2026-11-18 15:15', '1h')}, T('2026-11-18 16:17'))
check('swing post-close scan (last 1H candle closed this session): still allowed', len(led['signals']) == 1)
led = sg.load('/x'); a, b = it('AAA'), it('BBB'); sg.update(led, 'intraday', [a, b], {}, {'AAA': frame([[99, 101, 98, 100]], '2026-11-18 10:00'), 'BBB': frame([[99, 101, 98, 100]], '2026-11-18 10:50')}, T('2026-11-18 11:00'))
check('a stale stock does not use a daily slot: the fresh one is still taken', [s['symbol'] for s in led['signals']] == ['BBB'] and 'data stale' in a['status'])
os.environ['STALE_CHECK'] = 'off'; led = sg.load('/x'); a = it(); sg.update(led, 'options', [a], {}, {'NIFTY 50': frame([[99, 101, 98, 100]], '2026-11-18 10:00')}, T('2026-11-18 11:00')); os.environ.pop('STALE_CHECK')
check('STALE_CHECK=off (replay tests only) switches the gate off', len(led['signals']) == 1)

# ====================================================================== 4) trade tracker arithmetic (Section 6, independent)
def run_walk(section, direction, entry, sl, t, rows, start, freq='5min', now=None):
    item = dict(symbol='X', direction=direction, label=direction.upper(), grade='A+', score=9, entry=entry, sl=sl, t1=t[0], t2=t[1], t3=t[2], bos_date='b', status='TRIGGERED')
    s = sg.new_signal(section, item, T(start) - pd.Timedelta(minutes=5)); sg.walk(s, frame(rows, start, freq), now or T(start) + pd.Timedelta(hours=1)); return s
# swing long: T1 (half, stop stays), T2 (quarter, stop to entry), then the trail is hit at entry: 0.5*1 + 0.25*2 + 0.25*0 = 1.0R
s = run_walk('swing', 'long', 100, 90, (110, 120, 130), [[100, 111, 99, 110], [110, 121, 109, 120], [120, 121, 99, 100]], '2026-11-18 10:15', '1h', T('2026-11-18 14:00'))
check('swing long: half at T1 with NO breakeven, a quarter at T2, the rest stopped at entry = +1.00R', s['status'] == 'CLOSED' and s['r_final'] == 1.0 and s['booked'] == [(0.5, 110), (0.25, 120)], f"{s['r_final']} {s['booked']}")
s = run_walk('swing', 'long', 100, 90, (110, 120, 130), [[100, 111, 99, 110], [110, 111, 89, 92]], '2026-11-18 10:15', '1h', T('2026-11-18 14:00'))
check('swing long: T1 then the ORIGINAL stop (no early breakeven) = 0.5*1 + 0.5*(-1) = 0.00R', s['r_final'] == 0.0 and s['outcome'] == 'TRAIL', f"{s['r_final']} {s['outcome']}")
s = run_walk('intraday', 'short', 100, 104, (96, 92, 88), [[100, 100.5, 95.5, 96], [96, 100.5, 95, 100]], '2026-11-18 10:00')
check('intraday short: half at T1 (stop to entry), then out at entry = +0.50R', s['r_final'] == 0.5 and s['stop'] == 100, f"{s['r_final']} {s['stop']}")
s = run_walk('intraday', 'long', 100, 95, (105, 110, 115), [[100, 106, 94, 101]], '2026-11-18 10:00')
check('stop and target in the same candle: the stop is assumed first (never the favourable fill) = -1.00R', s['r_final'] == -1.0 and s['outcome'] == 'SL', f"{s['r_final']}")
s = run_walk('intraday', 'long', 100, 95, (105, 110, 115), [[100, 116, 99, 115]], '2026-11-18 10:00')
check('all three targets in one candle: 0.5*1 + 0.25*2 + 0.25*3 = +1.75R', s['r_final'] == 1.75 and s['outcome'] == 'TARGET', f"{s['r_final']}")
s = run_walk('swing', 'long', 100, 90, (110, 120, 130), [[100, 104, 99, 103], [84, 86, 80, 85]], '2026-11-18 14:15', '1h', T('2026-11-19 12:00'))
check('GAP through the stop: filled at the open 84, not at the stop 90 = (84-100)/10 = -1.60R', s['exit'] == 84 and s['r_final'] == -1.6, f"exit {s['exit']} r {s['r_final']}")
s = run_walk('intraday', 'short', 100, 104, (96, 92, 88), [[100, 101, 99, 100], [107, 108, 106, 107]], '2026-11-18 10:00')
check('GAP through a short stop: filled at the open 107 = -(107-100)/4 = -1.75R', s['exit'] == 107 and s['r_final'] == -1.75, f"exit {s['exit']} r {s['r_final']}")
s = run_walk('intraday', 'long', 100, 95, (105, 110, 115), [[100, 102, 99, 101], [101, 103, 100, 102]], '2026-11-18 14:55', now=T('2026-11-18 15:20'))
check('intraday still open at 15:15: squared off at the last close 102 = +0.40R', s['outcome'] == 'EXPIRED' and s['r_final'] == 0.4, f"{s['outcome']} {s['r_final']}")
check('R with a zero-width stop is 0, never a division error', sg._r(dict(entry=100, sl=100, direction='long'), 105) == 0.0)

# ====================================================================== 5) backtest statistics, by hand (Sections 6 and 7)
rs = [1.0, -1.0, 2.0, -1.0, -1.0, 0.5, -0.2, 3.0]
st = bt.stats(rs)
wins = [1.0, 2.0, 0.5, 3.0]; losses = [-1.0, -1.0, -1.0, -0.2]
eq = np.cumsum(rs); dd = max(max([0.0] + list(eq[:i + 1])) - eq[i] for i in range(len(rs)))
check('win rate = 4 wins / 8 = 50.0%', st['win'] == 50.0)
check('expectancy = mean R = 3.3 / 8 = 0.4125', abs(st['avg'] - 0.4125) < 1e-3, str(st['avg']))
check('profit factor = 6.5 / 3.2 = 2.03', st['pf'] == round(6.5 / 3.2, 2), str(st['pf']))
check('average win 1.62 and average loss -0.80', st['avg_win'] == round(np.mean(wins), 2) and st['avg_loss'] == round(np.mean(losses), 2), f"{st['avg_win']} {st['avg_loss']}")
check(f'max drawdown in R = {dd:.2f} (equity peaks at 2.0 after trade 3, falls to 0.0 after trade 5)', abs(st['max_dd'] - dd) < 1e-9 and abs(dd - 2.0) < 1e-9, str(st['max_dd']))
check('longest losing streak = 2 (trades 4 and 5; the -0.2 after the +0.5 is a streak of 1)', st['streak'] == 2, str(st['streak']))
check('stats of no trades: empty, not an error', bt.stats([])['n'] == 0 and bt.stats([])['pf'] is None)
check('profit factor with no losses is undefined (None), not infinite', bt.stats([1.0, 2.0])['pf'] is None)
tr = lambda d, r, sc=9, h=2: dict(sym='X', score=sc, entry_t=f'{d} 10:15', exit_t=f'{d} {10 + h}:15', r_net=r, closed=True, held=[])
acct = dict(bt.ACCOUNT, max_per_day=2)
r1 = bt.simulate_account([tr('2026-11-02', -1.0)], 8, True, acct)
check('account: one A+ loss of 1R at 0.75% risk leaves 99.25 of 100', abs(r1['ret'] - (-0.75)) < 0.051, str(r1['ret']))
r2 = bt.simulate_account([tr('2026-11-02', -1.0, 7)], 6, True, acct)
check('account: a score-7 loss uses the normal 0.5% risk', abs(r2['ret'] - (-0.5)) < 0.051, str(r2['ret']))
r3 = bt.simulate_account([tr('2026-11-02', 1.0, 9, 1), tr('2026-11-02', 1.0, 9, 2), tr('2026-11-02', 1.0, 9, 3)], 8, True, acct)
check('account: strict 2 a day, the third A+ that day is skipped', r3['n'] == 2 and r3['skipped']['day_cap'] == 1, str(r3['skipped']))
r4 = bt.simulate_account([tr('2026-11-02', 2.0), tr('2026-11-03', 2.0)], 8, True, acct)
check('account: compounding, +1.5% then +1.5% on the new base = +3.02%', abs(r4['ret'] - round((1.015 * 1.015 - 1) * 100, 1)) < 0.051, str(r4['ret']))

# ====================================================================== 6) option costs and Black-Scholes (Section 6)
p0, pe = 120.0, 150.0
cost = tf.OPT_FIXED_INR + tf.OPT_VAR * (p0 + pe) * tf.LOT
check('option cost model: 40 rupees + 0.15% of premium turnover x lot 65 = 40 + 26.33 = 66.33', abs(cost - (40 + 0.0015 * 270 * 65)) < 1e-9 and tf.LOT == 65, f'{cost:.2f}')
stt_now = 0.0015 * pe * 65; check('statutory check: STT since 1 Apr 2026 is 0.15% of the SELL premium (14.63 rupees here), which the 0.15%-of-turnover allowance covers', tf.OPT_VAR * (p0 + pe) * 65 >= stt_now, f'allowance {tf.OPT_VAR * (p0 + pe) * 65:.2f} vs STT {stt_now:.2f}')
S, K, Tt, v = 24000.0, 24000.0, 5 / 365, 0.13
c, p = greeks.bs(S, K, Tt, v, 'CE'), greeks.bs(S, K, Tt, v, 'PE')
parity = S * math.exp(-greeks.Q_DIV * Tt) - K * math.exp(-greeks.R_FREE * Tt)
check('Black-Scholes: put-call parity C - P = S e^-qT - K e^-rT', abs((c['price'] - p['price']) - parity) < 1e-6, f"{c['price'] - p['price']:.4f} vs {parity:.4f}")
check('Black-Scholes: call delta in (0,1), put delta in (-1,0), call delta - put delta = e^-qT', 0 < c['delta'] < 1 and -1 < p['delta'] < 0 and abs(c['delta'] - p['delta'] - math.exp(-greeks.Q_DIV * Tt)) < 1e-9)
check('Black-Scholes at expiry: intrinsic value only', greeks.bs(24100, 24000, 0, 0.13, 'CE')['price'] == 100 and greeks.bs(24100, 24000, 0, 0.13, 'PE')['price'] == 0)
import datetime as _dt
check('weekly expiry: Tuesday 24 Nov 2026 is a holiday (Guru Nanak Jayanti), so expiry moves to Monday 23 Nov', greeks.weekly_expiry(_dt.datetime(2026, 11, 19, 10, 0, tzinfo=greeks.IST), ['2026-11-24']) == _dt.date(2026, 11, 23))
check('weekly expiry: on Tuesday after 15:30 the next one is the following week', greeks.weekly_expiry(_dt.datetime(2026, 11, 17, 15, 45, tzinfo=greeks.IST)) == _dt.date(2026, 11, 24))

# ====================================================================== 7) swing replay uses only what was known at the time (Section 7)
import swing, strategy_scanner as sc
VIOL = []; real = swing.analyse
def stand_in(w, h1=None, m15=None, weekly=None, levels=(), cfg=None):
    """A data-dependent stand-in: its answer changes with every candle it is given, so any future candle would change past trades."""
    if h1 is None: return dict(stage=2, bos_date=str(w.index[-30])[:10], zone_top=float(w.Close.iloc[-1]) * 2)
    if pd.Timestamp(w.index[-1]).normalize() >= pd.Timestamp(h1.index[-1]).tz_localize(None).normalize(): VIOL.append(('daily', str(w.index[-1]), str(h1.index[-1])))
    c = h1.Close.values
    if len(c) < 8 or not (c[-1] > c[-6:-1].max()): return dict(stage=3, score=9)
    sl = float(h1.Low.values[-8:].min()) - 0.5
    return dict(stage=4, score=9, grade='A+', structure=2, zone_q=2, confirm=3, context=2, sl=sl, zone_top=float(c[-1]), atr=10.0, weekly=dict(up=True), holds=[], cf=dict(confirm_age=0), room_r=None, bos_date=str(w.index[-30])[:10])
swing.analyse = stand_in
r_ = np.random.default_rng(11); days = pd.bdate_range('2025-06-02', periods=320)
dc = 500 * np.exp(np.cumsum(r_.normal(0.0005, 0.015, len(days)))); do = np.r_[dc[0], dc[:-1]]
D = pd.DataFrame({'Open': do, 'High': np.maximum(do, dc) * 1.01, 'Low': np.minimum(do, dc) * 0.99, 'Close': dc, 'Volume': 5e6}, index=days)
hidx = [pd.Timestamp(f'{d.date()} {t}', tz=TZ) for d in days[-140:] for t in ('09:15', '10:15', '11:15', '12:15', '13:15', '14:15', '15:15')]
hc = np.concatenate([np.linspace(do[len(days) - 140 + i], dc[len(days) - 140 + i], 7) * (1 + r_.normal(0, 0.003, 7)) for i in range(140)]); ho = np.r_[hc[0], hc[:-1]]
H1 = pd.DataFrame({'Open': ho, 'High': np.maximum(ho, hc) * 1.003, 'Low': np.minimum(ho, hc) * 0.997, 'Close': hc, 'Volume': 1e6}, index=pd.DatetimeIndex(hidx))
full = bt.replay_symbol('RND', D, H1, min_score=4)
cut = T(str(days[-50].date()) + ' 09:00'); Dc = D[D.index < cut.tz_localize(None).normalize()]; Hc = H1[H1.index < cut]
part = bt.replay_symbol('RND', Dc, Hc, min_score=4)
key = lambda x: (x['entry_t'], x['exit_t'], x['entry'], x['sl'], x['r'], x['outcome'])
done_before = [key(x) for x in full if x['exit_t'] < str(cut.tz_localize(None))[:16] and x['outcome'] != 'OPEN']
check('swing replay: the data-dependent stand-in finds plenty of trades', len(full) >= 10, f'{len(full)} trades')
check('swing replay: cutting the history leaves every trade that had closed before the cut exactly as before', done_before == [key(x) for x in part if x['outcome'] != 'OPEN' and x['exit_t'] < str(cut.tz_localize(None))[:16]] and len(done_before) >= 5, f'{len(done_before)} compared')
check('swing replay: the daily frame given to the engine never included the session being replayed', not VIOL, str(VIOL[:2]))
check('swing replay: entries are at the close of the confirming 1H candle and exits come after it', all(x['exit_t'] >= x['entry_t'] for x in full))
swing.analyse = real

# ====================================================================== 8) System health validation (Section 13)
od = tempfile.mkdtemp(); now = T('2026-11-18 11:00')
good = dict(symbol='GOOD', direction='long', section='swing', entry=100.0, sl=90.0, t1=110.0, t2=120.0, t3=130.0, risk_pct=10.0, times=['a', 'b'], candles=[[1, 2, 0.5, 1.5], [1.5, 2, 1, 1.8]])
bad = dict(symbol='BAD', direction='long', section='swing', entry=100.0, sl=105.0, t1=110.0, t2=108.0, t3=130.0, risk_pct=1.0, times=['a', 'a'], candles=[[1, 0.8, 0.5, 1.5]])
json.dump(dict(generated_at=(now - pd.Timedelta(minutes=5)).isoformat(), setups=[good]), open(os.path.join(od, 'swing.json'), 'w'))
v = validation.run(od, now, dict(data=dict(angel=dict(configured=False), quality={}), sections=dict(swing=dict(ok=True))))
S_ = {c['check']: c['status'] for c in v['checks']}
check('validation: a correct plan passes, and green is shown only for checks that ran', S_['Entry, stop and target maths'] == 'pass' and v['errors'] == [], str(v['errors']))
check('validation: sections with no file are NOT TESTED (never green)', S_['Nifty options: data freshness'] == 'not_tested' and S_['Intraday: data freshness'] == 'not_tested')
check('validation: Angel One not configured is UNAVAILABLE, not passed', S_['Angel One connection'] == 'unavailable')
json.dump(dict(generated_at=(now - pd.Timedelta(minutes=300)).isoformat(), setups=[good, bad]), open(os.path.join(od, 'swing.json'), 'w'))
v = validation.run(od, now, dict(data=dict(angel=dict(configured=True, ok=False, error='Invalid totp')), sections=dict(swing=dict(ok=False, error='boom'))))
S_ = {c['check']: c['status'] for c in v['checks']}; E_ = {(e['instrument'].split()[0], e['description']) for e in v['errors']}
check('validation: stop on the wrong side and targets out of order are CRITICAL errors', ('BAD', 'stop on the wrong side of the entry') in E_ and ('BAD', 'targets out of order') in E_ and v['errors'][0]['severity'] == 'CRITICAL')
check('validation: an impossible chart candle and a repeated time are caught', S_['OHLC consistency (published charts)'] == 'fail')
check('validation: a swing file 5 hours old in market hours fails freshness', S_['Swing: data freshness'] == 'fail')
check('validation: Angel One configured but failing is a WARNING (Yahoo used)', S_['Angel One connection'] == 'warn')
check('validation: a failed scan section is a failed check with an error record', S_.get('Scan section: swing') == 'fail' and any(e['check'] == 'section' for e in v['errors']))
e0 = v['errors'][0]; check('validation: every error has id, time, instrument, module, description, expected, actual, severity, suggestion, status', all(e0.get(k) for k in ('id', 'at', 'instrument', 'module', 'description', 'expected', 'actual', 'severity', 'suggestion', 'status')))
led_ok = dict(signals=[dict(id='a', symbol='Z', direction='long', entry=100, sl=90, t1=110, t2=120, t3=130, status='CLOSED', exit=100, booked=[[0.5, 110], [0.25, 120]], r_final=1.0)])
json.dump(led_ok, open(os.path.join(od, 'signals_swing.json'), 'w')); v = validation.run(od, now, {})
check("validation: a tracked trade's booked R is recomputed (0.5*1 + 0.25*2 + 0.25*0 = 1.0) and agrees", {c['check']: c['status'] for c in v['checks']}['Trade tracker records'] == 'pass')
led_ok['signals'][0]['r_final'] = 1.5; led_ok['signals'].append(dict(led_ok['signals'][0])); json.dump(led_ok, open(os.path.join(od, 'signals_swing.json'), 'w')); v = validation.run(od, now, {})
check('validation: a wrong booked R and a duplicate trade record are both reported', {e['description'] for e in v['errors']} >= {'booked result does not add up', 'duplicate trade records'})
check('validation: closed market makes freshness NOT TESTED rather than green', {c['check']: c['status'] for c in validation.run(od, T('2026-11-21 11:00'), {})['checks']}['Swing: data freshness'] == 'not_tested')

print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: ' + '; '.join(fails))
sys.exit(1 if fails else 0)
