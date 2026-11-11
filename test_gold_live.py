"""Live XAUUSD gold: scanning through the sessions, long and short, tracked trades with the 02:00 IST square-off, your open-trade and
daily limits, phone alerts sent once, the gold loop's timing and the gold watchdog. Stand-in data, no network. Run: python test_gold_live.py"""
import datetime as dt, json, os, tempfile
for k in ('BACKTEST_FROM', 'MIN_SCORE', 'GOLD_SESSIONS', 'GOLD_MAX_OPEN', 'GOLD_ACCOUNT', 'NTFY_TOPIC', 'TELEGRAM_BOT_TOKEN'): os.environ.pop(k, None)
import numpy as np, pandas as pd
import backtest as bt, backtest_tf as tf, gold_live as gl, gold_loop, signals, strategy_scanner as sc, tf_fixture as fx, watchdog, notify
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
sc.CFG_B.update(min_bars=20); sc.CFG_I.update(min_turnover_cr=0, min_bars=30, rvol_n=10, max_zone_pct=6, max_zone_atr=5)
SENT = []; notify.post = lambda base, topic, title, body, tags, click, **k: SENT.append((title, body, click)) or ['ntfy']; os.environ['NTFY_TOPIC'] = 't'; os.environ['PAGE_URL'] = 'https://x.github.io/app'
IST = 'Asia/Kolkata'

# ---- 1. when gold trades
T = lambda s: pd.Timestamp(s, tz='UTC')
check('market hours: Saturday closed, Sunday before 22:00 UTC closed, Sunday night open, Friday until 22:00 UTC, midweek open',
      [gl.market_open(T(x)) for x in ('2026-11-14 12:00', '2026-11-15 21:00', '2026-11-15 22:30', '2026-11-13 21:30', '2026-11-13 22:30', '2026-11-11 10:00')] == [False, False, True, True, False, True])
check('sessions in IST: Asia in the morning, London 12:30, the overlap 17:30, New York 21:30',
      [gl.session_name(pd.Timestamp(f'2026-11-11 {h}', tz=IST)) for h in ('08:00', '13:00', '19:00', '23:00')] == ['Asia', 'London', 'London + New York', 'New York'])
check('entry window, every session (your choice): open at 08:00 IST (Asia) and 23:00 IST, closed 01:00-03:59 IST',
      gl.entry_window(pd.Timestamp('2026-11-11 08:00', tz=IST)) and gl.entry_window(pd.Timestamp('2026-11-11 23:00', tz=IST)) and not gl.entry_window(pd.Timestamp('2026-11-12 01:00', tz=IST)) and not gl.entry_window(pd.Timestamp('2026-11-12 03:30', tz=IST)))
os.environ['GOLD_SESSIONS'] = 'london_ny'
check('GOLD_SESSIONS=london_ny: no Asia entries (08:00 IST closed), London still open', not gl.entry_window(pd.Timestamp('2026-11-11 08:00', tz=IST)) and gl.entry_window(pd.Timestamp('2026-11-11 14:00', tz=IST)))
os.environ.pop('GOLD_SESSIONS')

# ---- 2. one live intraday run on the engineered setup, placed in the London afternoon
def stand_in(f5, f15, daily=None, h1=None):
    def u(df):
        x = df.copy(); x.index = pd.DatetimeIndex(x.index).tz_convert('UTC'); return x
    def fetch(syms, period, interval):
        f = {'5m': f5, '15m': f15, '1h': h1, '1d': daily}[interval]
        return ({syms[0]: u(f) if interval != '1d' else f} if f is not None else {}), []
    return fetch
f5, f15 = fx.engineered('2026-11-11 15:00')
now = f5.index[-1] + pd.Timedelta(minutes=5, seconds=40)
out, st = tempfile.mkdtemp(), tempfile.mkdtemp()
doc = gl.run(out, st, ('intraday',), now, stand_in(f5, f15))
S = doc['styles']['intraday']['setups']; trig = [x for x in S if x['status'] == 'TRIGGERED']
check('live intraday: the A+ long triggers at 20:15 IST, with entry, stop, targets and the stop in dollars', len(trig) == 1 and trig[0]['direction'] == 'long' and trig[0]['grade'] == 'A+' and trig[0]['risk_usd'] > 0 and trig[0]['sl'] < trig[0]['entry'] < trig[0]['t1'], str([(x['direction'], x['status'], x['score']) for x in S]))
led = json.load(open(os.path.join(out, 'signals_gold_intraday.json')))
check('live intraday: the trigger becomes a tracked gold trade (never an order)', [s['status'] for s in led['signals']] == ['ACTIVE'] and led['signals'][0]['section'] == 'gold_intraday')
check('gold.json: price, session, market open, open trades and today\'s count for the page', doc['market_open'] and doc['session'] == 'London + New York' and doc['open_now'] == 1 and doc['trades_today'] == 1 and doc['price'] > 0)
alert = [x for x in SENT if 'Gold intraday' in x[0]]
check('phone alert: one push with entry, stop, targets, lots and a link to the gold page', len(alert) == 1 and 'Entry' in alert[0][1] and 'T1' in alert[0][1] and '0.01 lot risks' in alert[0][1] and alert[0][2].endswith('/#/gold'), str(alert[:1])[:200])
n = len(SENT); gl.run(out, st, ('intraday',), now + pd.Timedelta(minutes=5), stand_in(f5, f15))
check('the next tick does not open it again or send the alert twice', len(json.load(open(os.path.join(out, 'signals_gold_intraday.json')))['signals']) == 1 and len(SENT) == n, f'{n} -> {len(SENT)}')
os.environ['GOLD_ACCOUNT'] = '10000'; check('lots in the alert from GOLD_ACCOUNT and the A+ risk (0.75%): $75 / (stop x 100)', gl.lots_text(5.0).startswith('0.15 lots'), gl.lots_text(5.0)); os.environ.pop('GOLD_ACCOUNT')

# ---- 3. square-off at 02:00 IST
late = pd.Timestamp('2026-11-12 02:06', tz=IST)
gl.run(out, st, ('intraday',), late, stand_in(f5, f15))
sig = json.load(open(os.path.join(out, 'signals_gold_intraday.json')))['signals'][0]
check('a gold intraday trade still open at 02:00 IST is squared off', sig['status'] == 'CLOSED' and sig['outcome'] in ('EXPIRED', 'TARGET', 'TRAIL', 'SL'), f"{sig['status']} {sig.get('outcome')}")
check('square-off time: a trade opened at 23:00 IST closes at 02:00 IST the next morning; one opened at 01:00 IST at 02:00 the same night',
      str(signals.gold_square_off(pd.Timestamp('2026-11-11 23:00', tz=IST)).tz_convert(IST))[:16] == '2026-11-12 02:00' and str(signals.gold_square_off(pd.Timestamp('2026-11-12 01:00', tz=IST)).tz_convert(IST))[:16] == '2026-11-12 02:00')

# ---- 4. shorts, and your limits
m5, m15 = fx.engineered('2026-11-11 15:00', mirror=True)
o2 = tempfile.mkdtemp(); d2 = gl.run(o2, tempfile.mkdtemp(), ('intraday',), m5.index[-1] + pd.Timedelta(minutes=5, seconds=40), stand_in(m5, m15))
sh = [x for x in d2['styles']['intraday']['setups'] if x['status'] == 'TRIGGERED']
check('live intraday short: the mirrored setup triggers a SHORT with the stop above the entry', len(sh) == 1 and sh[0]['direction'] == 'short' and sh[0]['sl'] > sh[0]['entry'] > sh[0]['t1'], str(sh[:1])[:160])
o3 = tempfile.mkdtemp()
for i in range(2):                                                      # two gold swing trades already open
    led_ = signals.load(os.path.join(o3, 'signals_gold_swing.json')); it = dict(symbol='XAUUSD', direction='long', label='LONG', grade='A+', score=9, entry=100.0 + i, sl=90.0, t1=110.0, t2=120.0, t3=130.0, bos_date=f'2026-11-0{i + 1}', stage=4, status='TRIGGERED')
    led_['signals'].append(signals.new_signal('gold_swing', it, pd.Timestamp('2026-11-10 10:00', tz=IST))); signals.save(os.path.join(o3, 'signals_gold_swing.json'), led_, pd.Timestamp('2026-11-10 10:00', tz=IST))
d3 = gl.run(o3, tempfile.mkdtemp(), ('intraday',), now, stand_in(f5, f15))
blk = [x for x in d3['styles']['intraday']['setups'] if x['status'].startswith('TRIGGERED')]
check('your open-trade limit: with 2 gold trades already open (2% open risk at 0.75% each), a new A+ trigger is shown but NOT taken',
      len(blk) == 1 and 'not taken' in blk[0]['status'] and not os.path.exists(os.path.join(o3, 'signals_gold_intraday.json')) or not json.load(open(os.path.join(o3, 'signals_gold_intraday.json')))['signals'], blk[0]['status'] if blk else '')
os.environ['GOLD_MAX_OPEN'] = '3'; d4 = gl.run(tempfile.mkdtemp(), tempfile.mkdtemp(), ('intraday',), now, stand_in(f5, f15)); os.environ.pop('GOLD_MAX_OPEN')
check('GOLD_MAX_OPEN changes the limit', d4['max_open'] == 3)
r = dict(grade='A', score=7, zone_bot=1, zone_top=2, bos_date='x'); its = [gl.item('intraday', 'long', r, 10, 9, 11, 12, 13, 'TRIGGERED') for _ in range(1)]
o5 = tempfile.mkdtemp(); led5 = signals.load(os.path.join(o5, 'signals_gold_intraday.json'))
for i in range(2): s_ = signals.new_signal('gold_intraday', dict(its[0], bos_date=f'b{i}'), now); s_['status'] = 'CLOSED'; led5['signals'].append(s_)
signals.save(os.path.join(o5, 'signals_gold_intraday.json'), led5, now)
check('your daily rule: after 2 trades today a trigger below A+ is not taken (only A+ may go past 2)', 'not A+' in gl.apply_rules(its, o5, now, 5, 2)[0]['status'])
its2 = [gl.item('intraday', 'long', dict(r, grade='A+', score=9), 10, 9, 11, 12, 13, 'TRIGGERED')]
check('your daily rule: past 2 trades today an A+ trigger IS taken', gl.apply_rules(its2, o5, now, 5, 2)[0]['status'] == 'TRIGGERED')
check('outside the entry window (01:30 IST) the same trigger is shown but not taken', any(x['status'].startswith('TRIGGERED (outside') for x in gl.scan_intraday(f5, f15, pd.Timestamp('2026-11-12 01:30', tz=IST), 8)[0]))

# ---- 5. swing and positional, both ways
import playbook_fixture as pf
d, h, _ = pf.frames(vol=5_000_000)
it_l, _s = gl.scan_swing(d, h, 8)
check('live swing long: the playbook example is found as an A+ gold long setup', any(x['direction'] == 'long' and x['grade'] == 'A+' and x['sl'] < x['entry'] for x in it_l), str([(x['direction'], x['status'], x['score']) for x in it_l]))
K0 = 3000.0; md, mh = sc.invert(d, K0), sc.invert(h, K0)
it_s, _s = gl.scan_swing(md, mh, 8)
shs = [x for x in it_s if x['direction'] == 'short']
check('live swing short: the same picture upside down is found as a SHORT, prices back in the real chart (stop above, targets below)', len(shs) == 1 and shs[0]['sl'] > shs[0]['entry'] > shs[0]['t1'] > shs[0]['t2'] and shs[0]['zone_bot'] < shs[0]['zone_top'], str([(x['direction'], x['status'], x['entry'], x['sl']) for x in it_s]))
h2 = h.iloc[:-2]; tl = gl.scan_swing(d, h2, 8)[0]; ts_ = gl.scan_swing(sc.invert(d, K0), sc.invert(h2, K0), 8)[0]
check('live swing: on the hour the 1H confirms, the long TRIGGERS at the playbook entry (1,071, stop about 1,036.5)', len(tl) == 1 and tl[0]['status'] == 'TRIGGERED' and tl[0]['entry'] == 1071.0 and abs(tl[0]['sl'] - 1036.5) < 0.6, str([(x['status'], x['entry'], x['sl']) for x in tl]))
check('live swing: the mirrored chart TRIGGERS the matching short at the mirrored prices', len(ts_) == 1 and ts_[0]['status'] == 'TRIGGERED' and ts_[0]['direction'] == 'short' and abs(ts_[0]['entry'] - (K0 - 1071.0)) < 0.01 and abs(ts_[0]['sl'] - (K0 - tl[0]['sl'])) < 0.01)
dw = fx.daily_walk(5, 1300, p0=2400.0, start='2021-11-01')
pi, _p = gl.scan_positional(dw, 4)
check('live positional: runs both ways on five years of daily gold without errors', isinstance(pi, list))
fr = dict(f5=f5, f15=f15)
o6 = tempfile.mkdtemp(); dd6 = gl.run(o6, tempfile.mkdtemp(), ('swing', 'positional'), pd.Timestamp('2026-11-11 15:02', tz=IST), stand_in(f5, f15, daily=dw, h1=fx.walk5(3, days=40, start='2026-09-14')[0].resample('60min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()))
check('an hourly run writes swing and positional to gold.json and keeps the page\'s other styles', set(dd6['styles']) >= {'swing', 'positional'} and all('scanned_at' in dd6['styles'][k] for k in ('swing', 'positional')))

# ---- 6. backtest shorts are mirrored back correctly
K = 5000.0; L = [dict(entry_t='2026-05-01 10:00', exit_t='2026-05-02 10:00', entry=100.0, sl=90.0)]; Sm = [dict(entry_t='2026-05-03 10:00', exit_t='2026-05-04 10:00', entry=4900.0, sl=4890.0)]
b = tf.both_sides(L, Sm, K)
check('backtest: gold shorts found on the mirrored chart come back as real prices (entry 100, stop 110: stop above)', b[0]['side'] == 'long' and b[1]['side'] == 'short' and b[1]['entry'] == 100.0 and b[1]['sl'] == 110.0)

# ---- 7. the loop and the watchdog
check('loop: swing and positional run once an hour, from 2 minutes past', gold_loop.hourly_due(dt.datetime(2026, 11, 11, 10, 2), None) and not gold_loop.hourly_due(dt.datetime(2026, 11, 11, 10, 7), (dt.date(2026, 11, 11), 10)) and not gold_loop.hourly_due(dt.datetime(2026, 11, 11, 11, 0), (dt.date(2026, 11, 11), 10)))
full = (dt.time(0, 0), dt.time(23, 59, 59)); nowi = dt.datetime(2026, 11, 11, 23, 0, tzinfo=watchdog.loop.IST)
check('gold watchdog: market open and no gold loop running -> start one (any hour, not only NSE hours)', watchdog.decide(nowi, [], None, True, full, 'gold-loop')[0] == 'start')
check('gold watchdog: weekend -> nothing to do', watchdog.decide(nowi, [], None, False, full, 'gold-loop')[0] == 'skip' and not watchdog.gold_market_open(dt.datetime(2026, 11, 14, 12, 0, tzinfo=dt.timezone.utc)))
check('market-loop watchdog is unchanged: 23:00 IST is outside its hours', watchdog.decide(nowi, [], None, True)[0] == 'skip')
os.environ.pop('NTFY_TOPIC'); print('ALL PASSED' if not fails else f'{len(fails)} FAILED'); raise SystemExit(1 if fails else 0)
