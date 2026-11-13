"""Swing fast lane (15m entry checks between the hourly scans), the shared context rules, the loop schedule and the 2 ATR SET ALERT limit.
No network. Run: python test_fastlane.py"""
import argparse, copy, datetime as dt, json, os, sys, tempfile
import numpy as np, pandas as pd
import strategy_scanner as sc, swing, signals, loop
from playbook_fixture import frames
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
sc.CFG.update(min_turnover_cr=0, min_price=0); sc.ex_dividend_info = lambda s, now: None
tz = 'Asia/Kolkata'; NOW = pd.Timestamp('2026-08-13 11:00', tz=tz)

# ---------------------------------------------------------------- the shared context rules
def R(**k): return dict(dict(stage=4, notes='', holds=[], status='1H CONFIRMED (wait for 15m entry)'), **k)
r = sc.apply_swing_context(R(), dict(index_check=dict(state='falling', sector_index='Nifty IT')))
check('context rules: sector index falling -> note and the setup is held (WATCH)', r['status'] == 'WATCH (index falling)' and r['holds'] == ['index falling'] and 'Nifty IT is falling' in r['notes'])
r = sc.apply_swing_context(R(), dict(results=dict(days=3), index_check=dict(state='unknown', sector_index='x')))
check('context rules: results inside the hold -> held; unknown sector data -> note only', r['holds'] == ['results inside hold'] and 'results in 3 days' in r['notes'] and 'sector index data unavailable' in r['notes'])
r = sc.apply_swing_context(R(stage=3), dict(index_check=dict(state='falling', sector_index='Nifty IT'), ex_dividend=dict(date='2026-08-14'), data_flags=[dict(text='gap in the data')]))
check('context rules: before 1H confirmed a falling sector is only a note (not held), no ex-dividend note, data check note first', not r['holds'] and r['status'].startswith('1H CONFIRMED') and r['notes'].startswith('data check: gap in the data') and 'ex-dividend' not in r['notes'])
r = sc.apply_swing_context(R(), dict(ex_dividend=dict(date='2026-08-14'), regime_edge=dict(verdict='weak', label='Range-bound', avg=-0.2, n=40)))
check('context rules: ex-dividend and weak-regime notes (the regime only holds when REGIME_FILTER=hold)', 'ex-dividend on 2026-08-14' in r['notes'] and 'Range-bound' in r['notes'] and not r['holds'])

# ---------------------------------------------------------------- a swing.json as the full scan leaves it
D, H, M_BEFORE = frames(vol=5_000_000); _, _, M_TRIG = frames(vol=5_000_000, m15_after=20)
rr = swing.analyse(D, H)
def pbk(extra=None, sym='PBK'):
    return sc.swing_item(sym, rr, D, H, None, extra or {}, float(H.Close.iloc[-1]))
def stage3(sym):
    it = pbk(sym=sym); it.update(stage=3, status='IN ZONE (wait for 1H)', stage_label='In zone', bos_date='2026-07-0' + str(len(sym) % 9 + 1)); return it
def stage2(sym):
    it = stage3(sym); it.update(stage=2, status='SET ALERT (wait for pullback)', stage_label='Set alert', bos_date='2026-06-01'); return it
def write_scan(out, items, gen='2026-08-13T10:21:00+05:30'):
    light, charts = sc.split_charts(items); os.makedirs(out, exist_ok=True)
    doc = sc.meta('swing', pd.Timestamp(gen), 500, 499, [], 'test', light, stages={str(k): sum(1 for i in light if i['stage'] == k) for k in range(1, 6)}, heat=dict(clusters=[]))
    sc.write_json(out, 'swing.json', doc); sc.write_json(out, 'swing_charts.json', dict(generated_at=gen, charts=charts))
    sc.write_json(out, 'explain.json', dict(generated_at=gen, min_score=4, top=60, rows={i['symbol']: [i['stage'], 'listed', f"Listed: stage {i['stage']}", i['score'], 1000.0, 'IT'] for i in items}))
    return light
FR = {'1d': {'PBK': D}, '1h': {'PBK': H}, '15m': {'PBK': M_TRIG}}; CALLS = []
def fake(symbols, period, interval, chunk=50, pause=1.0, source='auto'):
    CALLS.append((tuple(symbols), interval)); out = {s: FR[interval][s].copy() for s in symbols if s in FR[interval]}; return out, [s for s in symbols if s not in out]
sc.download_many = fake
def ns(out): return argparse.Namespace(out=out, min_score=4, top=60, state_dir=tempfile.mkdtemp(), watchlist='watchlist.txt', universe_csv=None, events='events.json', intraday_top=100)
RD = lambda out, f: json.load(open(os.path.join(out, f)))
def SIGS(out):
    try: return RD(out, 'signals_swing.json')['signals']
    except FileNotFoundError: return []                  # nothing changed, so no ledger was written

out = tempfile.mkdtemp(); light0 = write_scan(out, [pbk(), stage3('KEEP'), stage2('OTHER')]); before = {x['symbol']: copy.deepcopy(x) for x in RD(out, 'swing.json')['setups']}; ch0 = RD(out, 'swing_charts.json')['charts']
check('start: PBK is 1H confirmed (stage 4), waiting for the 15m entry, with no 15m chart yet', before['PBK']['stage'] == 4 and before['PBK']['status'].startswith('1H CONFIRMED') and '15m' not in ch0['PBK'])
CALLS.clear(); items = sc.run_swing_fast(ns(out), NOW); after = {x['symbol']: x for x in RD(out, 'swing.json')['setups']}
check('fast lane: the playbook 15m sequence is found, PBK is TRIGGERED at entry 1,070', after['PBK']['stage'] == 5 and after['PBK']['status'] == 'TRIGGERED' and after['PBK']['entry'] == 1070, str((after['PBK']['stage'], after['PBK']['status'], after['PBK']['entry'])))
check('fast lane: downloads ONLY the setup it checks (1D, 1H, 15m for PBK), not the other ~85', sorted(CALLS) == sorted([(('PBK',), '1d'), (('PBK',), '1h'), (('PBK',), '15m')]), str(CALLS))
check('fast lane: every other setup is left exactly as it was', after['KEEP'] == before['KEEP'] and after['OTHER'] == before['OTHER'])
doc = RD(out, 'swing.json')
check('swing.json: the full scan\'s generated_at is kept, fast_at is added, the stage counts are recomputed', doc['generated_at'] == '2026-08-13T10:21:00+05:30' and doc['fast_at'] == NOW.isoformat(timespec='seconds') and doc['stages']['5'] == 1 and doc['stages']['4'] == 0 and doc['stages']['3'] == 1 and doc['fast_refreshed'] == 1 and doc['heat'] == dict(clusters=[]))
led = RD(out, 'signals_swing.json')
check('the trade ledger: PBK became ONE active trade at 1,070 (so the alert goes out in this same tick)', [(s['symbol'], s['status'], s['entry']) for s in led['signals']] == [('PBK', 'ACTIVE', 1070)] and 'swing|PBK|long|' + after['PBK']['bos_date'] not in led['watch'], str(led['signals'][:1])[:200])
ch = RD(out, 'swing_charts.json')
check('charts: PBK now has its 15m chart; the other charts are untouched', '15m' in ch['charts']['PBK'] and ch['charts']['KEEP'] == ch0['KEEP'] and ch['charts']['OTHER'] == ch0['OTHER'])
check('the trade page reloads its cached charts: swing.json and swing_charts.json carry the same new charts_at stamp', doc['charts_at'] == ch['charts_at'] == NOW.isoformat(timespec='seconds') and ch['generated_at'] == '2026-08-13T10:21:00+05:30')

ex = RD(out, 'explain.json')['rows']
check('explain.json: PBK\'s row says TRIGGERED; the other rows are untouched', 'TRIGGERED' in ex['PBK'][2] and ex['KEEP'][2] == 'Listed: stage 3' and ex['OTHER'][2] == 'Listed: stage 2')
CALLS.clear(); sc.run_swing_fast(ns(out), NOW + pd.Timedelta(minutes=15))
check('the next fast run (15 minutes later, same data): no second trade, still one active', len(SIGS(out)) == 1)
import notify
sent = []; notify.post = lambda base, topic, title, body, tags, click, **k: sent.append((title, body)) or ['ntfy']; os.environ['NTFY_TOPIC'] = 't'; os.environ['NTFY_MIN_SCORE'] = '6'; os.environ['NTFY_STATUSES'] = 'TRIGGER'
out_n = tempfile.mkdtemp(); write_scan(out_n, [pbk()]); sc.run_swing_fast(ns(out_n), NOW)
import subprocess; rc = subprocess.run([sys.executable, 'notify.py', '--dir', out_n, '--state', os.path.join(out_n, 'n.json')], capture_output=True, text=True, env=dict(os.environ, NTFY_URL='http://127.0.0.1:9'))
check('notify.py (the step after the fast lane in the loop) picks up the new PBK trigger from the files the fast lane wrote and tries to send it', 'could not send PBK' in rc.stderr, (rc.stdout + rc.stderr)[-200:])

# ---------------------------------------------------------------- what the fast lane must NOT do
out2 = tempfile.mkdtemp(); write_scan(out2, [stage3('KEEP'), stage2('OTHER')]); CALLS.clear(); b2 = RD(out2, 'swing.json')['setups']; sc.run_swing_fast(ns(out2), NOW)
check('no 1H-confirmed setup -> no download at all, and nothing changes but fast_at', CALLS == [] and RD(out2, 'swing.json')['setups'] == b2 and RD(out2, 'swing.json')['fast_checked'] == 0)
check('a fast run that refreshes nothing does NOT set charts_at (the page does not refetch the big charts file for nothing)', 'charts_at' not in RD(out2, 'swing.json'))
out3 = tempfile.mkdtemp(); write_scan(out3, [pbk(), stage3('KEEP')]); b3 = RD(out3, 'swing.json')['setups']; FR_SAVE = FR; FR = {'1d': {}, '1h': {}, '15m': {}}; sc.run_swing_fast(ns(out3), NOW); FR = FR_SAVE
check('no fresh data for the setup -> it is left exactly as it was, no trade, no crash', RD(out3, 'swing.json')['setups'] == b3 and not SIGS(out3))
out4 = tempfile.mkdtemp(); write_scan(out4, [pbk()]); orig = swing.analyse; swing.analyse = lambda *a, **k: dict(state='BROKEN', score=0, grade='skip'); sc.run_swing_fast(ns(out4), NOW); swing.analyse = orig
check('the structure broke since the last full scan -> left to the hourly scan (the fast lane never deletes or invents setups)', RD(out4, 'swing.json')['setups'][0]['stage'] == 4 and not SIGS(out4))
out4b = tempfile.mkdtemp(); write_scan(out4b, [pbk()]); orig = swing.analyse
swing.analyse = lambda *a, **k: dict(orig(*a, **k), bos_date='2026-05-05')                          # the same setup, but the engine now sees a different daily BOS
sc.run_swing_fast(ns(out4b), NOW); swing.analyse = orig
check('the fast lane never swaps in a different daily structure (different BOS than the full scan found): the setup stays as it was, no trade', RD(out4b, 'swing.json')['setups'][0]['stage'] == 4 and RD(out4b, 'swing.json')['setups'][0]['bos_date'] == pbk()['bos_date'] and not SIGS(out4b))
out5 = tempfile.mkdtemp(); write_scan(out5, [pbk(dict(index_check=dict(state='falling', sector_index='Nifty IT')))]); sc.run_swing_fast(ns(out5), NOW); a5 = RD(out5, 'swing.json')['setups'][0]
check('a setup held by the sector index stays held when a 15m entry appears: WATCH, no trade (your rules still apply in the fast lane)', a5['status'] == 'WATCH (index falling)' and a5['holds'] == ['index falling'] and not SIGS(out5), a5['status'])
out6 = tempfile.mkdtemp(); many = [pbk(sym=f'S{i:02d}') for i in range(15)]
for i, it in enumerate(many): it['bos_date'] = f'2026-07-{i + 1:02d}'; it['score'] = 10 - (i % 3)
many[3].update(holds=['room < 2R'], status='WATCH (room < 2R)')
write_scan(out6, many); FR = {'1d': {x['symbol']: D for x in many}, '1h': {x['symbol']: H for x in many}, '15m': {x['symbol']: M_BEFORE for x in many}}; CALLS.clear(); sc.run_swing_fast(ns(out6), NOW)
done = CALLS[0][0]; FR = FR_SAVE
check(f'at most {sc.FAST_MAX} setups per run, the actionable ones first (a held-back one waits its turn)', len(done) == sc.FAST_MAX and many[3]['symbol'] not in done, str(len(done)))

# ---------------------------------------------------------------- the command line mode
out7 = tempfile.mkdtemp(); write_scan(out7, [pbk()]); argv = sys.argv; sys.argv = ['strategy_scanner.py', '--mode', 'swing-fast', '--out', out7, '--state-dir', tempfile.mkdtemp()]
try: sc.main()
finally: sys.argv = argv
check('--mode swing-fast: works from the command line, writes no health file (it is a refresh, not a scan: no false failure alerts)', RD(out7, 'swing.json')['setups'][0]['status'] == 'TRIGGERED' and not os.path.exists(os.path.join(out7, 'health', 'swing-fast.json')))

# ---------------------------------------------------------------- the loop schedule and its safety
T = lambda h, m: dt.datetime(2026, 11, 13, h, m, 40, tzinfo=loop.IST)
ticks = [(h, m) for h in range(8, 17) for m in range(0, 60, 5)]
fast = [f'{h:02d}:{m:02d}' for h, m in ticks if loop.swing_fast_due(T(h, m))]
check('loop: the fast lane runs at :00, :30 and :45 from 09:30 (the first 15m candle) to 15:30; :15 belongs to the full scan', fast == ['09:30', '09:45', '10:00', '10:30', '10:45', '11:00', '11:30', '11:45', '12:00', '12:30', '12:45', '13:00', '13:30', '13:45', '14:00', '14:30', '14:45', '15:00', '15:30'], ' '.join(fast))
check('loop: with the full scans at 10:15 ... 15:15 and 15:30 there is a swing check at EVERY quarter hour from 09:30 to 15:30', all(loop.swing_fast_due(T(h, m)) or loop.swing_due(T(h, m), None) for h, m in [(9, 30), (9, 45), (10, 0), (10, 15), (10, 30), (10, 45), (11, 15), (14, 45), (15, 0), (15, 15), (15, 30)]))
check('loop: a step that hangs is stopped and reported (exit 124), it never holds up the next tick', loop.run([sys.executable, '-c', 'import time; time.sleep(30)'], lambda s: None, timeout=1) == 124)

# ---------------------------------------------------------------- SET ALERT is now 2 ATR
check('SET ALERT distance is 2 ATR (it was 4)', swing.CFG['alert_atr'] == 2.0)
def far_above(d, target_atr):
    """Three more daily candles that stay above the zone (so the zone was not touched in the last 3 sessions) and end target_atr above its top."""
    base = swing.analyse(d); zt, a = base['zone_top'], base['atr']; rows, prev = [], float(d.Close.iloc[-1])
    for c in (zt + 0.6 * a, zt + max(0.7 * target_atr, 0.9) * a, zt + target_atr * a):
        rows.append([prev, max(prev, c) + 0.2 * a, max(min(prev, c) - 0.1 * a, zt + 0.15 * a), c, float(d.Volume.iloc[-1])]); prev = c
    idx = [d.index[-1] + pd.offsets.BDay(n) for n in (1, 2, 3)]
    return pd.concat([d, pd.DataFrame(rows, columns=d.columns, index=idx)])
outcomes = {}
for k in (0.8, 1.4, 1.8, 2.3, 3.0):
    dd = far_above(D, k); res = swing.analyse(dd); old_rule = swing.analyse(dd, cfg=dict(swing.CFG, alert_atr=4.0))
    cands = swing.H.find_structures(dd, dict(swing.H.CFG, lookback=swing.CFG['lookback'], zz=swing.CFG['zz'])); dist = (float(dd.Close.iloc[-1]) - cands[0]['zone_top']) / float(swing.H.atr(dd, 14).iloc[-1])
    listed = res is not None and 'stage' in res; outcomes[k] = (round(dist, 2), listed)
    ok = (listed and res['stage'] == 2 and dist <= 2.0 + 1e-9) if dist <= 2.0 else (not listed and res.get('state') == 'FAR')
    check(f'SET ALERT: price {dist:.2f} ATR above the zone (zone not touched lately) -> ' + ('listed, stage 2 (SET ALERT)' if dist <= 2.0 else 'NOT listed (price too far: no chasing a stale zone)'), ok, str(res.get('status') if listed else res.get('state')))
far = [k for k, (dist, listed) in outcomes.items() if dist > 2.0]
check('SET ALERT: the old 4 ATR rule WOULD have listed the same far-away setups (that is what changed)', all('stage' in (swing.analyse(far_above(D, k), cfg=dict(swing.CFG, alert_atr=4.0)) or {}) for k in far), str(outcomes))
check('SET ALERT: both sides of the 2 ATR line were exercised', any(l for _, l in outcomes.values()) and bool(far), str(outcomes))

print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
