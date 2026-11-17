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
IST = loop.IST; T = lambda h, m, s=0: dt.datetime(2026, 10, 22, h, m, s, tzinfo=IST)
check('next tick: 10:03:10 -> 10:05:40, 10:05:20 -> 10:05:40, 10:05:50 -> 10:10:40', loop.next_tick(T(10, 3, 10)) == T(10, 5, 40) and loop.next_tick(T(10, 5, 20)) == T(10, 5, 40) and loop.next_tick(T(10, 5, 50)) == T(10, 10, 40))
check('a loop started at 09:05 stops by 14:50 (job limit), one started at 14:55 stops at 15:40', loop.end_time(T(9, 5)) == T(14, 50) and loop.end_time(T(14, 55)) == T(15, 40))
check('swing scan: due on the first tick after each 1H candle closes (:15 from 10:15 to 15:15) and again at 15:30 for the day\'s last candle', loop.swing_due(T(10, 15), None) and loop.swing_due(T(10, 20), None) and not loop.swing_due(T(9, 40), None) and not loop.swing_due(T(10, 10), None) and not loop.swing_due(T(10, 20), loop.swing_slot(T(10, 15))) and loop.swing_due(T(11, 15), loop.swing_slot(T(10, 20))) and loop.swing_due(T(15, 30), loop.swing_slot(T(15, 20))) and not loop.swing_due(T(15, 35), loop.swing_slot(T(15, 30))) and loop.swing_due(T(15, 20), loop.swing_slot(T(14, 50))))
check('weekends and holidays are not trading days', not loop.trading_day(dt.date(2026, 10, 24)) and not loop.trading_day(dt.date(2026, 11, 10)) and loop.trading_day(dt.date(2026, 10, 22)))
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
