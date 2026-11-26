"""Deeper error checks (items 401-486, 497): checks.py, the publish step's last-good-copy rule, the alert rate limit and log.
Run: python test_checks.py"""
import datetime as dt, http.server, json, os, shutil, subprocess, sys, tempfile, threading
import checks, notify, publish
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
IST = dt.timezone(dt.timedelta(hours=5, minutes=30)); NOW = dt.datetime(2026, 11, 25, 16, 30, tzinfo=IST)

class Rep:
    def __init__(self): self.checks, self.errors = [], []
    def add(self, check, module, status, detail, severity=None, n=None): self.checks.append(dict(check=check, module=module, status=status, detail=detail, severity=severity))
    def error(self, check, module, instrument, description, expected, actual, severity, suggestion): self.errors.append(dict(check=check, instrument=instrument, description=description, severity=severity, actual=str(actual)))
    def st(self, name): return next((c['status'] for c in self.checks if c['check'] == name), None)

# ---- setup rows
A = dict(symbol='AAA', direction='long', stage=5, score=9, max_score=10, status='TRIGGERED', holds=[], price=100, entry=101)
P = checks.setup_problems('swing', [A, dict(A), dict(A, symbol='BBB', stage=7), dict(A, symbol='CCC', holds=['Results in 2 days']), dict(A, symbol='DDD', holds=['x'], status='TRIGGERED (NOT TAKEN: daily limit)'),
                                    dict(A, symbol='EEE', price=150), dict(A, symbol='FFF', score=12)], NOW.date())
d = {p[0].split()[0]: p[1] for p in P}
check('setup rows: a duplicate row is found', d.get('AAA') == 'the same setup is listed twice', d)
check('setup rows: stage 7 and score 12 of 10 are impossible', 'stage outside' in d.get('BBB', '') and 'score outside' in d.get('FFF', ''))
check('setup rows: a held-back setup shown as triggered is flagged; NOT TAKEN is fine', 'held-back' in d.get('CCC', '') and 'DDD' not in d)
check('setup rows: price 50% away from the entry is flagged (stale or split)', '25%' in d.get('EEE', ''))
check('setup rows: a clean row gives nothing', checks.setup_problems('swing', [A], NOW.date()) == [])
r = checks.setup_problems('swing', [dict(A, results=dict(date='2026-11-27', days=2)), dict(A, symbol='Z', results=dict(date='2026-12-20', days=2))], NOW.date())
check('results countdown: matching date passes, a wrong countdown is flagged', len(r) == 1 and r[0][0] == 'Z', r)

# ---- charts and ledger
check('daily chart: a two-week hole is a gap; weekends and a holiday are not', checks.chart_gaps(['2026-11-03', '2026-11-04', '2026-11-05', '2026-11-20']) == ['2026-11-05 to 2026-11-20'] and checks.chart_gaps(['2026-11-06', '2026-11-09', '2026-11-11']) == [])
check('daily chart: candles out of order are flagged', checks.chart_gaps(['2026-11-06', '2026-11-05']) != [])
L = dict(signals=[dict(id='ok', direction='long', sl=95, stop=100, created='2026-11-03T10:00+05:30', hits={'T1': '2026-11-04T10:00+05:30'}, events=[dict(t='2026-11-03T10:00+05:30'), dict(t='2026-11-04T10:00+05:30')]),
                  dict(id='loose', direction='long', sl=95, stop=90), dict(id='sloose', direction='short', sl=105, stop=108),
                  dict(id='early', direction='long', sl=95, stop=95, created='2026-11-05T10:00+05:30', hits={'T1': '2026-11-04T10:00+05:30'}),
                  dict(id='order', direction='long', sl=95, stop=95, events=[dict(t='2026-11-04T10:00+05:30'), dict(t='2026-11-03T10:00+05:30')]),
                  dict(id='noexit', direction='long', sl=95, stop=95, outcome='TARGET', status='CLOSED', exit=None)])
lp = {x[0]: x[1] for x in checks.ledger_problems(L)}
check('ledger: a stop moved against the trade (long and short) is critical', 'against' in lp.get('loose', '') and 'against' in lp.get('sloose', '') and 'ok' not in lp, lp)
check('ledger: a target hit before the trade existed, events out of order, a closed trade with no exit', 'before the trade' in lp.get('early', '') and 'order' in lp.get('order', '') and 'exit' in lp.get('noexit', ''))

# ---- secrets: names only, value never returned
tmp = tempfile.mkdtemp(); os.makedirs(os.path.join(tmp, 'health'))
json.dump(dict(generated_at=NOW.isoformat(), setups=[A]), open(os.path.join(tmp, 'swing.json'), 'w'))
SECRET = 'zz-very-secret-token-123'
hits, n = checks.leak_hits(tmp, {'TELEGRAM_BOT_TOKEN': SECRET})
check('leak scan: a clean site passes', hits == [] and n >= 1, (hits, n))
open(os.path.join(tmp, 'oops.json'), 'w').write(json.dumps({'x': SECRET}))
hits, n = checks.leak_hits(tmp, {'TELEGRAM_BOT_TOKEN': SECRET, 'HOME': '/root/abcdefgh'})
check('leak scan: a secret value inside a published file is found, by name only', hits == ['TELEGRAM_BOT_TOKEN'] and SECRET not in json.dumps(hits))
rep = Rep(); checks.extra(rep, tmp, NOW, env={'TELEGRAM_BOT_TOKEN': SECRET, 'TELEGRAM_CHAT_ID': '55', 'GITHUB_ACTIONS': 'true'})
check('extra: the leak is a CRITICAL failure and the value is not in the report', rep.st('No secret in the published files') == 'fail' and SECRET not in json.dumps(rep.checks + rep.errors))
check('extra: secrets present reports names, never values', rep.st('Secrets present (names only)') == 'pass' and '55' not in json.dumps(rep.checks))
os.remove(os.path.join(tmp, 'oops.json'))
rep = Rep(); checks.extra(rep, tmp, NOW, env={'GITHUB_ACTIONS': 'true'})
check('extra: on GitHub with no alert channel set, secrets check fails', rep.st('Secrets present (names only)') == 'fail')
rep = Rep(); checks.extra(rep, tmp, NOW, env={})
check('extra: off GitHub, secrets are not judged (unavailable, not green)', rep.st('Secrets present (names only)') == 'unavailable')
open(os.path.join(tmp, 'broken.json'), 'w').write('{"setups": [1, 2')
rep = Rep(); checks.extra(rep, tmp, NOW, env={})
check('extra: a broken JSON file fails "Published files open"', rep.st('Published files open') == 'fail' and any(e['instrument'] == 'broken.json' for e in rep.errors))
os.remove(os.path.join(tmp, 'broken.json'))
check('extra: a check that cannot read its input is "not tested", never green', rep.st('Nifty spot and VIX') == 'not_tested' and rep.st('Daily charts: missing sessions') == 'not_tested')
json.dump(dict(generated_at='2026-11-25T16:00:00', setups=[]), open(os.path.join(tmp, 'options.json'), 'w'))
rep = Rep(); checks.extra(rep, tmp, NOW, env={})
check('extra: a timestamp without a timezone fails; missing spot/VIX warns', rep.st('Timestamps carry a timezone') == 'fail' and rep.st('Nifty spot and VIX') == 'warn')

# ---- workflows (item 324)
wf = tempfile.mkdtemp(); os.makedirs(os.path.join(wf, '.github', 'workflows'))
for name in checks.WORKFLOWS: open(os.path.join(wf, '.github', 'workflows', name + '.yml'), 'w').write("on:\n  push:\n" if name == 'ci' else "on:\n  schedule:\n    - cron: '7 3 * * 1-5'\n")
check('workflows: all present with their triggers', checks.workflow_problems(wf) == [])
open(os.path.join(wf, '.github', 'workflows', 'scan.yml'), 'w').write("on:\n  workflow_dispatch:\n"); os.remove(os.path.join(wf, '.github', 'workflows', 'backup.yml'))
w = checks.workflow_problems(wf)
check('workflows: a lost schedule and a missing file are found', 'scan has no schedule' in w and 'backup.yml is missing' in w, w)
check('workflows: the real repository passes', checks.workflow_problems(os.path.dirname(os.path.abspath(__file__))) == [], checks.workflow_problems(os.path.dirname(os.path.abspath(__file__))))

# ---- history (item 497)
for i in range(95): checks.history(tmp, dict(generated_at=f'run{i}', level='pass', summary={}, checks=[dict(check='X', status='fail')], errors=[]))
h = json.load(open(os.path.join(tmp, 'health', 'checks_history.json')))['items']
check('history: one line per run, last 90 kept, with failing check names', len(h) == 90 and h[-1]['at'] == 'run94' and h[-1]['failing'] == ['X'])

# ---- the real published data from a recent run passes (no false alarms)
real = '/tmp/gp/data'
if os.path.isdir(real):
    rep = Rep(); checks.extra(rep, real, NOW, env={})
    bad = [c for c in rep.checks if c['status'] == 'fail']
    check('real data: no check fails on a good run', not bad, bad)
else: print('SKIP real data check (no copy of the published data on this machine)')

# ---- publish keeps the last good copy (item 327)
if shutil.which('git'):
    pub = tempfile.mkdtemp(); sh = lambda *a: subprocess.run(['git', *a], cwd=pub, check=True, capture_output=True)
    sh('init', '-q'); sh('config', 'user.email', 'a@b'); sh('config', 'user.name', 'a'); os.makedirs(os.path.join(pub, 'data'))
    open(os.path.join(pub, 'data', 'swing.json'), 'w').write('{"good": 1}'); sh('add', '-A'); sh('commit', '-qm', 'x')
    open(os.path.join(pub, 'data', 'swing.json'), 'w').write('{"good": 2, "cut off'); open(os.path.join(pub, 'data', 'new.json'), 'w').write('')
    open(os.path.join(pub, 'data', 'ok.json'), 'w').write('{"fine": true}')
    mine = publish._keep_good_json(pub, {'data/swing.json', 'data/new.json', 'data/ok.json', 'index.html'})
    check('publish: a cut-off file goes back to the last good copy and is not published', json.load(open(os.path.join(pub, 'data', 'swing.json'))) == {'good': 1} and 'data/swing.json' not in mine)
    check('publish: an empty new file is not published; good files and pages are', 'data/new.json' not in mine and {'data/ok.json', 'index.html'} <= mine and not os.path.exists(os.path.join(pub, 'data', 'new.json')), mine)
else: print('SKIP publish check (git not installed)')

# ---- alerts: rate limit and log (items 479-486)
got = []
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        got.append((self.path, self.headers.get('Title'), self.rfile.read(int(self.headers['Content-Length'])).decode())); self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
for k in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'): os.environ.pop(k, None)
os.environ.update(NTFY_TOPIC='tp', NTFY_URL=f'http://127.0.0.1:{srv.server_port}', NTFY_MAX_PER_RUN='3', NTFY_UPDATES='off', NTFY_EVENTS='off', NTFY_ACTIONS='off', ALERT_CHARTS='off', PAGE_URL='')
notify.quiet_now = lambda now=None: False
dd = tempfile.mkdtemp()
S = lambda i: dict(symbol=f'S{i}', direction='long', label='LONG', grade='A+', score=9, status='TRIGGERED', entry=100, sl=95, t1=105, t2=110, t3=115, zone_bot=96, zone_top=99, bos_date='2026-11-20', r_t1=1.0, ticks=[], notes=[])
json.dump(dict(generated_at=NOW.isoformat(), setups=[S(i) for i in range(7)]), open(os.path.join(dd, 'swing.json'), 'w'))
sys.argv = ['notify.py', '--dir', dd, '--state', os.path.join(dd, 'state.json')]; notify.LOG.clear(); notify.main()
titles = [t for _, t, _ in got]
check('rate limit: 3 trade alerts, then one summary for the other 4', len(got) == 4 and 'more setups' in titles[-1] and all(f'S{i}' in got[-1][2] for i in range(3, 7)), titles)
lg = json.load(open(os.path.join(dd, 'health', 'alerts_log.json')))
check('alert log: every send is listed with its channel, and the held count', len(lg['items']) == 4 and all(x['ok'] and x['channels'] == ['ntfy'] for x in lg['items']) and lg['held_today'] == 4)
check('alert log: never contains the topic or a token', 'tp' not in json.dumps([x.get('channels') for x in lg['items']]) and 'NTFY' not in json.dumps(lg))
got.clear(); notify.LOG.clear(); notify.main()
check('dedupe: the next run sends nothing again (summary counted as sent)', got == [], [t for _, t, _ in got])
json.dump(dict(checks=[dict(check='No secret in the published files', status='fail', detail='the value of X appears')]), open(os.path.join(dd, 'health', 'validation.json'), 'w'))
got.clear(); notify.LOG.clear(); notify.main()
check('health alert: a failing system check is pushed once', len(got) == 1 and 'system check failing' in (got[0][1] or ''), [t for _, t, _ in got])
got.clear(); notify.LOG.clear(); notify.main()
check('health alert: not repeated on the next run', got == [])
srv.shutdown()

# ---- digest lines (items 495, 496)
import digest
V = dict(summary=dict(pass_=0, fail=1, warn=0), checks=[dict(check='Published files open', status='fail')]); V['summary']['pass'] = 20
check('digest: a failing check is named in the evening message', 'Published files open' in digest.health_line(V) and 'Open System health' in digest.health_line(V))
check('digest: all passing says so; no file gives no line', 'all 20 passing' in digest.health_line(dict(summary={'pass': 20, 'fail': 0, 'warn': 0}, checks=[])) and digest.health_line({}) is None)
D = dict(led={}, gold={}, hist=dict(items=[dict(at='2026-11-24T16:00', level='fail', failing=['X']), dict(at='2026-11-25T16:00', level='pass', failing=[]), dict(at='2026-10-01T16:00', level='fail', failing=['OLD'])]))
wt = digest.weekly_text(D, NOW)[1]
check('digest: the weekly message counts this week\'s runs and failures only', '2 runs, 1 with a failure: X (1)' in wt and 'OLD' not in wt, wt)

print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
