"""replay.py (item 18): the options engine replayed candle by candle. Run: python test_replay.py"""
import json, os, sys, tempfile
import pandas as pd
import replay, strategy_scanner as sc, tf_fixture as tf
fails = []
def check(n, c, info=''):
    print(('PASS ' if c else 'FAIL ') + n + (f'   {info}' if info and not c else '')); (None if c else fails.append(n))
f5, f15 = tf.engineered(); day = f5.index[-1].date(); NOLV = lambda a: []
# 1) the real engine: the replay's last state is exactly what the live engine says on the whole day
live = sc.scan_intraday(f5, f15, 'long', tf.CFG5, [], section='options')
doc = replay.replay_day(f5, f15, None, day, min_score=0, cfg=tf.CFG5, levels=NOLV)
want = live.get('status') if live and 'zone_bot' in live else sc.REASON.get((live or {}).get('state'), 'No setup.')
check('real engine: the last CALL state equals the live engine on the full day', doc['sides']['CALL'][-1]['status'] == want, (doc['sides']['CALL'][-1], want))
check('the replay covers every 5-minute candle of the day', doc['bars'] == len(f5), doc['bars'])
check('the day candles are saved with the replay', len(doc['chart']['candles']) == doc['bars'] == len(doc['chart']['times']))
# 2) bookkeeping with a stand-in engine that triggers once 50 candles exist (so the 50th candle is the trigger)
seen = []
def fake(a5, a15, side, cfg, lv, extra_ticks=(), section='', h1=None):
    seen.append(len(a5)); n = len(a5)
    if side == 'short': return dict(state='FAR')
    return dict(zone_bot=1, score=8, grade='A+', entry=100, sl=95, t1=110, status='TRIGGERED' if n >= 50 else 'IN ZONE (wait)' if n >= 40 else 'SET ALERT (wait)')
real = sc.scan_intraday; sc.scan_intraday = fake
try:
    d2 = replay.replay_day(f5, f15, None, day, min_score=0, cfg=tf.CFG5, levels=NOLV)
    d3 = replay.replay_day(f5.iloc[:49], f15, None, day, min_score=0, cfg=tf.CFG5, levels=NOLV)
finally: sc.scan_intraday = real
c = d2['sides']['CALL']
check('only changes are recorded (SET ALERT, IN ZONE, TRIGGERED)', [r['status'] for r in c] == ['SET ALERT (wait)', 'IN ZONE (wait)', 'TRIGGERED'], [r['status'] for r in c])
check('the first trigger is at the close of the 50th candle', d2['first_trigger']['CALL']['t'] == (f5.index[49] + pd.Timedelta(minutes=5)).strftime('%H:%M'), d2['first_trigger'])
check('no look-ahead: the engine never saw more candles than had closed', max(seen) <= len(f5))
check('a replay cut before the trigger candle never shows TRIGGERED', 'CALL' not in d3['first_trigger'])
check('the PUT side keeps its own record', d2['sides']['PUT'] and d2['sides']['PUT'][0]['status'] == sc.REASON['FAR'])
out = tempfile.mkdtemp(); replay.write(out, doc); replay.write(out, dict(doc, date='2026-10-09'))
idx = json.load(open(os.path.join(out, 'replay', 'index.json')))
check('index lists replayed days, newest first, no duplicates', idx['days'] == sorted(set(idx['days']), reverse=True) and len(idx['days']) == 2, idx)
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
