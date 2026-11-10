"""Failure alerts (item 28): cool-down, recovery notes, the rules, and the loop's watcher. No network. Run: python test_alerts.py"""
import datetime as dt, json, os, tempfile
import alerts, loop, notify
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)

IST = alerts.IST; T0 = dt.datetime(2026, 11, 11, 10, 0, tzinfo=IST)
SENT = []; notify.post = lambda base, topic, title, body, tags, click: SENT.append((title, body, tags, click))
os.environ.update(NTFY_TOPIC='test-topic', PAGE_URL='https://x.github.io/app/'); os.environ.pop('TELEGRAM_BOT_TOKEN', None)
sp = os.path.join(tempfile.mkdtemp(), 'state', 'alerts.json')

check('first alert goes out, with a link to System health', alerts.send('k', 'Boom', 'body', sp, 60, now=T0) and SENT[-1][3] == 'https://x.github.io/app/#/health')
check('the same alert within the cool-down is not repeated', not alerts.send('k', 'Boom', 'body', sp, 60, now=T0 + dt.timedelta(minutes=30)) and len(SENT) == 1)
check('after the cool-down it is sent again', alerts.send('k', 'Boom', 'body', sp, 60, now=T0 + dt.timedelta(minutes=61)) and len(SENT) == 2)
check('a different key is independent', alerts.send('other', 'Other', 'b', sp, 60, now=T0 + dt.timedelta(minutes=62)) and len(SENT) == 3)
check('recovery sends one note and forgets the key', alerts.resolve('k', 'Recovered', 'fine now', sp) and SENT[-1][0] == 'Recovered' and not alerts.resolve('k', 'Recovered', 'again', sp) and len(SENT) == 4)
check('after recovery the problem can alert again at once', alerts.send('k', 'Boom', 'body', sp, 60, now=T0 + dt.timedelta(minutes=63)))
n = len(SENT); check('no state path: nothing is sent (tests and local runs stay quiet)', not alerts.send('z', 't', 'b', None) and len(SENT) == n)
os.environ.pop('NTFY_TOPIC'); sp2 = os.path.join(tempfile.mkdtemp(), 'a.json')
check('no channel configured: nothing is sent and nothing is recorded', not alerts.send('z', 't', 'b', sp2, now=T0) and not os.path.exists(sp2))
os.environ['NTFY_TOPIC'] = 'test-topic'

H = dict(mode='live', sections=dict(options=dict(ok=True, seconds=3), intraday=dict(ok=False, seconds=1, error='no data downloaded'), market=dict(ok=True, universe=100, scanned=100)),
         data=dict(angel=dict(configured=True, ok=False, error='login failed: Invalid totp'), xcheck=[dict(symbol='COFORGE', max_diff_pct=2.4), dict(symbol='^NSEI', max_diff_pct=0.0)]))
bad, good = alerts.findings(H, dict(losses_today=2, session_date='2026-11-11')); keys = {b[0] for b in bad}
check('a failed section is a problem, a working one is "good"', 'scan-fail:intraday' in keys and any(g[0] == 'scan-fail:options' for g in good))
check('Angel One failing is reported with its reason and the Yahoo fallback', any(b[0] == 'angel-down' and 'Invalid totp' in b[2] and 'Yahoo' in b[2] for b in bad))
check('a source mismatch over 1.5% names the symbol', any(b[0] == 'data-mismatch' and 'COFORGE 2.4%' in b[2] for b in bad))
check('two option losses today pause options, once per session date', 'options-paused:2026-11-11' in keys)
H2 = dict(mode='swing', sections=dict(swing=dict(ok=True, universe=501, scanned=420)), data={})
check('swing seeing only 420 of 501 stocks is a data gap', any(b[0] == 'data-gap:swing' for b in alerts.findings(H2)[0]))
H3 = dict(mode='swing', sections=dict(swing=dict(ok=True, universe=501, scanned=499)), data=dict(angel=dict(configured=True, ok=True), xcheck=[dict(symbol='^NSEI', max_diff_pct=0.1)]))
b3, g3 = alerts.findings(H3); check('2 missing symbols of 501 is normal: no alert', not b3 and any(g[0] == 'angel-down' for g in g3))

sp3 = os.path.join(tempfile.mkdtemp(), 'p.json'); SENT.clear()
c1 = alerts.process(H, dict(losses_today=2, session_date='2026-11-11'), sp3, now=T0); c2 = alerts.process(H, dict(losses_today=2, session_date='2026-11-11'), sp3, now=T0 + dt.timedelta(minutes=5))
check('process: the alerts go out once, the repeat 5 minutes later is silent', c1 == 4 and c2 == 0 and len(SENT) == 4, f'{c1}, {c2}')
SENT.clear(); alerts.process(dict(mode='live', sections=dict(options=dict(ok=True), intraday=dict(ok=True)), data=dict(angel=dict(configured=True, ok=True), xcheck=[dict(symbol='^NSEI', max_diff_pct=0.0)])), {}, sp3, now=T0 + dt.timedelta(minutes=10))
check('process: when everything is fine again, each earlier problem sends one recovery note', sorted(s[0] for s in SENT) == sorted(['Recovered: intraday scan', 'Angel One is back', 'Data sources agree again']), str([s[0] for s in SENT]))

pub = tempfile.mkdtemp(); SENT.clear()
loop.watch_loop(pub, dict(bad_ticks=1, bad_publish=0)); check('loop: one failed tick is not an alert yet', not SENT)
loop.watch_loop(pub, dict(bad_ticks=2, bad_publish=0, last_rc=2, run_url='https://x/runs/1')); check('loop: two failed ticks in a row alert, with the run link', SENT and SENT[-1][0] == 'Live scan is failing' and 'https://x/runs/1' in SENT[-1][1])
loop.watch_loop(pub, dict(bad_ticks=0, bad_publish=0)); check('loop: a good tick afterwards sends the recovery note', SENT[-1][0] == 'Live scan recovered')
loop.watch_loop(pub, dict(bad_ticks=0, bad_publish=3, publish='failed: rejected')); check('loop: three failed publishes in a row alert', SENT[-1][0] == 'Publishing is failing')
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED'); raise SystemExit(1 if fails else 0)
