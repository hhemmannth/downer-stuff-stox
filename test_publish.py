"""Publishing and loop-timing tests with a local bare git repo (no GitHub needed). Run: python test_publish.py"""
import datetime as dt, os, subprocess, sys, tempfile, time
import publish, loop
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
root = tempfile.mkdtemp(); bare = os.path.join(root, 'remote.git'); subprocess.run(['git', 'init', '-q', '--bare', bare], check=True); os.environ['PUBLISH_REMOTE'] = bare
site = os.path.join(root, 'site'); os.makedirs(site); open(os.path.join(site, 'index.html'), 'w').write('<h1>v1</h1>')
A = publish.prepare(os.path.join(root, 'A')); t0 = time.time() - 1
open(os.path.join(A, 'data', 'options.json'), 'w').write('{"a":1}'); publish.publish(A, t0, site, 'first')
ls = lambda: subprocess.run(['git', '--git-dir', bare, 'ls-tree', '-r', '--name-only', 'gh-pages'], capture_output=True, text=True).stdout.split()
check('first publish creates gh-pages with the site, the data and .nojekyll', {'index.html', 'data/options.json', '.nojekyll'} <= set(ls()), str(ls()))
B = publish.prepare(os.path.join(root, 'B')); tb = time.time() - 1
check('a second writer starts from the published data', open(os.path.join(B, 'data', 'options.json')).read() == '{"a":1}')
time.sleep(1.1); ta = time.time()
open(os.path.join(B, 'data', 'swing.json'), 'w').write('{"s":1}'); publish.publish(B, tb, site, 'swing')
open(os.path.join(A, 'data', 'options.json'), 'w').write('{"a":2}'); publish.publish(A, ta, site, 'options again')
show = lambda f: subprocess.run(['git', '--git-dir', bare, 'show', f'gh-pages:{f}'], capture_output=True, text=True).stdout
check('two writers: A keeps B\'s swing.json and adds its own newer options.json', show('data/swing.json') == '{"s":1}' and show('data/options.json') == '{"a":2}')
log = subprocess.run(['git', '--git-dir', bare, 'log', '--oneline', 'gh-pages'], capture_output=True, text=True).stdout.strip().splitlines()
check('the branch is always a single commit (no history to grow the repo)', len(log) == 1, str(log))
open(os.path.join(site, 'index.html'), 'w').write('<h1>v2</h1>'); publish.publish(B, time.time(), site, 'ui'); check('new site files are published even with no new data', show('index.html') == '<h1>v2</h1>')
# ---- 17 Nov 2026: a file another writer refreshed must never be pushed back as our older copy
C = publish.prepare(os.path.join(root, 'C')); lc = time.time() - 1; G = publish.prepare(os.path.join(root, 'G')); lg = time.time() - 1
def pub(P, last, f, txt, msg):
    if f: open(os.path.join(P, 'data', f), 'w').write(txt)
    m = time.time(); publish.publish(P, last, site, msg); return m
lg = pub(G, lg, 'gold.json', 'g1', 'gold 1'); time.sleep(1.1); lc = pub(C, lc, 'loop.json', 'c1', 'loop 1')        # the loop picks up g1
time.sleep(1.1); lg = pub(G, lg, 'gold.json', 'g2', 'gold 2'); time.sleep(1.1); lc = pub(C, lc, 'loop.json', 'c2', 'loop 2')
check('two loops: the market loop never pushes back an older copy of the gold loop\'s file (it used to restore g1 over g2)', show('data/gold.json') == 'g2' and show('data/loop.json') == 'c2', show('data/gold.json'))
R = publish.prepare(os.path.join(root, 'R')); open(os.path.join(R, 'data', 'readiness.json'), 'w').write('today'); publish.publish(R, time.time() - 1, site, 'readiness')
time.sleep(1.1); lc = pub(C, lc, 'loop.json', 'c3', 'loop 3'); time.sleep(1.1); lc = pub(C, lc, 'loop.json', 'c4', 'loop 4')
check('a once-a-day file (readiness) survives the loop\'s next publishes', show('data/readiness.json') == 'today', show('data/readiness.json'))
import json as _j
L1 = dict(signals=[dict(id='a', status='ACTIVE', checked_to='2026-11-17T10:00', events=[1])], watch={'w1': {}}, dropped=[], updated='2026-11-17T10:00')
open(os.path.join(C, 'data', 'signals_swing.json'), 'w').write(_j.dumps(L1)); time.sleep(1.1); lc = pub(C, lc, None, '', 'ledger 1')
S2 = publish.prepare(os.path.join(root, 'S2')); L2 = _j.load(open(os.path.join(S2, 'data', 'signals_swing.json')))
L2['signals'].append(dict(id='b', status='ACTIVE', checked_to='2026-11-17T11:00', events=[1])); open(os.path.join(S2, 'data', 'signals_swing.json'), 'w').write(_j.dumps(L2)); publish.publish(S2, time.time() - 1, site, 'scan adds b')
L1['signals'][0].update(status='CLOSED', checked_to='2026-11-17T11:05', events=[1, 2]); open(os.path.join(C, 'data', 'signals_swing.json'), 'w').write(_j.dumps(L1)); time.sleep(1.1); lc = pub(C, lc, None, '', 'loop closes a')
M = _j.loads(show('data/signals_swing.json')); byid = {x['id']: x for x in M['signals']}
check('two runs update the trade ledger at once: both trades are kept and the closed one stays closed', set(byid) == {'a', 'b'} and byid['a']['status'] == 'CLOSED', str(list(byid)))
st = publish.merge_state({'date': '2026-11-17', 'sent': ['x', 'y']}, {'date': '2026-11-17', 'sent': ['y', 'z']})
check('alert state from two runs: everything already sent stays sent (no duplicate phone alerts)', sorted(st['sent']) == ['x', 'y', 'z'] and publish.merge_state({'date': '2026-11-18', 'sent': ['n']}, {'date': '2026-11-17', 'sent': ['o']})['sent'] == ['n'])
IST = loop.IST; T = lambda h, m, s=0: dt.datetime(2026, 10, 22, h, m, s, tzinfo=IST)
check('next tick: 10:03:10 -> 10:05:40, 10:05:20 -> 10:05:40, 10:05:50 -> 10:10:40', loop.next_tick(T(10, 3, 10)) == T(10, 5, 40) and loop.next_tick(T(10, 5, 20)) == T(10, 5, 40) and loop.next_tick(T(10, 5, 50)) == T(10, 10, 40))
check('a loop started at 09:05 stops by 14:50 (job limit), one started at 14:55 stops at 15:40', loop.end_time(T(9, 5)) == T(14, 50) and loop.end_time(T(14, 55)) == T(15, 40))
check('swing scan: due on the first tick after each 1H candle closes (:15 from 10:15 to 15:15) and again at 15:30 for the day\'s last candle', loop.swing_due(T(10, 15), None) and loop.swing_due(T(10, 20), None) and not loop.swing_due(T(9, 40), None) and not loop.swing_due(T(10, 10), None) and not loop.swing_due(T(10, 20), loop.swing_slot(T(10, 15))) and loop.swing_due(T(11, 15), loop.swing_slot(T(10, 20))) and loop.swing_due(T(15, 30), loop.swing_slot(T(15, 20))) and not loop.swing_due(T(15, 35), loop.swing_slot(T(15, 30))) and loop.swing_due(T(15, 20), loop.swing_slot(T(14, 50))))
A = lambda h, m: T(h, m)
check('swing catch-up: a scan older than 75 min in market hours is due at once (the 08:37 run was skipped); a fresh one is not',
      loop.swing_catchup_due(T(9, 10), 17 * 60) and loop.swing_catchup_due(T(9, 10), None) and not loop.swing_catchup_due(T(10, 40), 40) and loop.swing_catchup_due(T(11, 50), 90))
check('swing catch-up: never before 09:00 or after 15:30, and a failed try waits 40 minutes before the next',
      not loop.swing_catchup_due(T(8, 45), 17 * 60) and not loop.swing_catchup_due(T(15, 35), 300) and not loop.swing_catchup_due(T(10, 0), 300, T(9, 45)) and loop.swing_catchup_due(T(10, 30), 300, T(9, 45)))
d = tempfile.mkdtemp(); open(os.path.join(d, 'swing.json'), 'w').write('{"generated_at": "2026-10-22T02:12:04+05:30"}')
check('swing_age_min reads the published scan time (7h 58 min before 10:10) and is None when there is no file', abs(loop.swing_age_min(d, T(10, 10)) - 478) < 1 and loop.swing_age_min(tempfile.mkdtemp(), T(10, 10)) is None)
calls = []; import watchdog; real_gh = watchdog.gh; watchdog.gh = lambda m, p, tok, body=None: calls.append((m, p, body)) or {}
os.environ.update(GITHUB_REPOSITORY='a/b', GITHUB_TOKEN='x'); ok = loop.relay(lambda s: None); watchdog.gh = real_gh
check('relay: queues the next market-loop run through the Actions API', ok and calls and calls[0][0] == 'POST' and calls[0][1].endswith('/workflows/market-loop.yml/dispatches'), str(calls))
os.environ.pop('GITHUB_REPOSITORY'); check('relay: without a repo/token it does nothing and does not crash', loop.relay(lambda s: None) is False)
check('weekends and holidays are not trading days', not loop.trading_day(dt.date(2026, 10, 24)) and not loop.trading_day(dt.date(2026, 11, 10)) and loop.trading_day(dt.date(2026, 10, 22)))
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
