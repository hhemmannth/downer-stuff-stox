"""Digests (item 3), readiness check (item 27) and the CI helpers (item 26). No network. Run: python test_digest.py"""
import datetime as dt, json, os, tempfile
import digest, readiness, run_tests, ci_alert, notify
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
IST = digest.IST; NOW = dt.datetime(2026, 11, 11, 8, 45, tzinfo=IST)

S = lambda sym, stage, score, **k: {**dict(symbol=sym, stage=stage, stage_label={5: 'Entry', 4: '1H confirmed', 3: 'In zone', 2: 'Set alert'}.get(stage, '?'), grade='A+' if score >= 8 else 'A', score=score, max_score=10, zone_bot=1041, zone_top=1052, sl=1036.5, status='TRIGGERED', holds=[]), **k}
swing = dict(generated_at='2026-11-10T16:20:00+05:30', stages={'5': 1, '4': 0, '3': 3, '2': 1}, setups=[
    S('AAA', 3, 6, results=dict(days=9)), S('PBK', 5, 10, results=dict(days=40)), S('BBB', 3, 7), S('HOLD', 4, 9, holds=['results in 5 days']), dict(S('WTCH', 4, 8), status='WATCH: sector falling'), S('LOW', 2, 5)])
market = dict(indices=dict(nifty=dict(price=24310.4, change_pct=0.42), banknifty=dict(price=52100.0, change_pct=-0.1), vix=dict(price=14.2)), expected_move=dict(daily_pts=182), daily=dict(label='Trending up'), playbook=dict(headline='Calm: normal size'))
news = dict(events=[dict(title='RBI policy', days=0, time='10:00', impact='high', type='macro'), dict(title='Q2 results: INFY', days=1, impact='medium', type='results'), dict(title='Holiday', days=2, impact='high', type='holiday'), dict(title='Minor', days=1, impact='low', type='macro')], risk_flags=['RBI policy today: expect volatility'])
sig = lambda sym, sec, status, **k: dict(id=f'{sec}|{sym}', symbol=sym, section=sec, instrument=sym, status=status, entry=100, sl=95, stop=95, r_now=0.4, events=[], **k)
led = dict(swing={'signals': [sig('PBK', 'swing', 'ACTIVE')]}, options={'signals': [dict(sig('NIFTY', 'options', 'CLOSED', outcome='T2', r_final=1.4, closed='2026-11-11T14:10+05:30'), events=[dict(t='2026-11-11T11:05+05:30', kind='trigger', text='x')])]},
           intraday={'signals': [dict(sig('RELIANCE', 'intraday', 'CLOSED', outcome='SL', r_final=-1.0, closed='2026-11-11T13:20+05:30'), events=[dict(t='2026-11-11T10:15+05:30', kind='trigger', text='x')])]})
D = dict(swing=swing, options={}, intraday={}, market=market, news=news, led=led)

t, b, tag = digest.morning_text(D, NOW)
check('morning: title carries the date, icon is sunrise', t == 'Morning brief · Wed 11 Nov' and tag == 'sunrise')
check('morning: market line, expected move and regime', 'Nifty 24,310.4 (+0.42%)' in b and 'VIX 14.20' in b and '±182 pts' in b and 'Trending up' in b and 'Calm: normal size' in b)
sl = [l for l in b.splitlines() if l.startswith('• ') and 'zone' in l]
check('morning: shortlist sorted by stage then score, WATCH, held-back and weak stage-2 excluded', [l.split(' · ')[0][2:] for l in sl] == ['PBK', 'BBB', 'AAA'], str(sl))
check('morning: results within 14 days are flagged on the setup', any('AAA' in l and 'results in 9d' in l for l in sl) and not any('PBK' in l and 'results in' in l for l in sl))
check('morning: a held-back setup is listed with its reason', 'HOLD: results in 5 days' in b)
check('morning: events today and tomorrow, holiday and low-impact ones left out', 'RBI policy (today, 10:00)' in b and 'INFY (tomorrow)' in b and 'Holiday' not in b and 'Minor' not in b)
check('morning: open tracked trades with R and stop', 'PBK (swing): +0.40R · stop 95' in b)
check('morning: says how old the swing data is, no warning when recent', 'Swing data from Tue 16:20 IST' in b and 'older than expected' not in b)
D_old = dict(D, swing=dict(swing, generated_at='2026-11-08T16:20:00+05:30')); check('morning: warns when the swing data is more than 30 hours old', 'older than expected' in digest.morning_text(D_old, NOW)[1])
empty = dict(D, swing=dict(setups=[]), led={}, news={}); b0 = digest.morning_text(empty, NOW)[1]
check('morning: with nothing to show it says waiting is part of the plan', 'Waiting is part of the plan' in b0)

EV = dt.datetime(2026, 11, 11, 15, 45, tzinfo=IST); t, b, tag = digest.evening_text(D, EV)
check('evening: title and icon', t == 'Day recap · Wed 11 Nov' and tag == 'city_sunset')
check('evening: triggers and closes today, with outcomes', 'Triggered today: 2' in b and 'NIFTY (options): T2 +1.40R' in b and 'RELIANCE (intraday): SL -1.00R' in b)
check('evening: total R of tracked signals closed today', 'Tracked signals total: +0.40R' in b)
check('evening: open positions and tomorrow', 'Still open: 1' in b and 'PBK (swing): +0.40R' in b and 'INFY (tomorrow)' in b)
check('evening: swing watch lists the top 3', 'Swing watch for tomorrow' in b and b.count(' · zone ') >= 3)

SENT = []; notify.post = lambda base, topic, title, body, tags, click: SENT.append((title, body, tags))
d = tempfile.mkdtemp()
for k, v in dict(swing=swing, market=market, news=news).items(): json.dump(v, open(os.path.join(d, k + '.json'), 'w'))
for k, v in led.items(): json.dump(v, open(os.path.join(d, f'signals_{k}.json'), 'w'))
os.environ['NTFY_TOPIC'] = 't'
check('main: sends the digest when forced', digest.main(['--mode', 'morning', '--dir', d, '--force']) == 0 and SENT and SENT[-1][0].startswith('Morning brief'))
n = len(SENT); sat = dt.date(2026, 11, 14)
import loop; check('main: nothing on a weekend (trading-day check)', not loop.trading_day(sat) and loop.trading_day(dt.date(2026, 11, 11)))

# ---------- readiness
RN = dt.datetime(2026, 11, 11, 8, 50, tzinfo=IST); is_td = lambda x: x.weekday() < 5 and x != dt.date(2026, 11, 10)
ENV = dict(ANGEL_API_KEY='k', ANGEL_CLIENT_CODE='c', ANGEL_MPIN='1', ANGEL_TOTP_SECRET='s', NTFY_TOPIC='t', TELEGRAM_BOT_TOKEN='1:a', TELEGRAM_CHAT_ID='5', CRON_TOKEN_EXPIRES='2027-01-20')
P = dict(angel=lambda: (True, 'login works'), yahoo=lambda: (True, 'Nifty up to 10 Nov'), universe=lambda: (True, 'Nifty 500 (live list, 501 symbols)'))
runs = [dict(created_at='2026-11-09T09:34:00Z')]                       # a workflow_dispatch run on Mon 9 Nov (IST)
R = readiness.run_checks(ENV, RN, is_td, P, lambda: runs, '2026-11-10T16:20:00+05:30'); lv, title, body = readiness.summarize(R)
check('readiness: everything fine -> "Ready for the session"', lv == 'ok' and title == 'Ready for the session' and body.count('✅') == 7, str([(s, n) for s, n, _ in R if s != 'ok']))
check('readiness: the previous trading day skips the holiday and the weekend (Wed -> Mon, since Tue 10 Nov is a holiday)', readiness.prev_trading_day(dt.date(2026, 11, 11), is_td) == dt.date(2026, 11, 9) and readiness.prev_trading_day(dt.date(2026, 11, 16), is_td) == dt.date(2026, 11, 13))
R = readiness.run_checks(ENV, RN, is_td, dict(P, angel=lambda: (False, 'login failed: Invalid totp')), lambda: runs, '2026-11-10T16:20:00+05:30')
check('readiness: Angel One down is a warning, not a failure (Yahoo covers it)', readiness.summarize(R)[0] == 'warn' and any(s == 'warn' and n == 'Angel One' for s, n, _ in R))
R = readiness.run_checks(ENV, RN, is_td, dict(P, yahoo=lambda: (False, 'timed out')), lambda: runs, '2026-11-10T16:20:00+05:30'); check('readiness: Yahoo down is "NOT ready"', readiness.summarize(R)[0] == 'fail' and 'NOT ready' in readiness.summarize(R)[1])
R = readiness.run_checks(ENV, RN, is_td, P, lambda: [dict(created_at='2026-11-05T09:34:00Z')], '2026-11-10T16:20:00+05:30'); check("readiness: no watchdog trigger on the previous trading day -> warns about cron-job.org", any(s == 'warn' and n == 'Outside timer' for s, n, _ in R))
R = readiness.run_checks(dict(ENV, CRON_JOB_EXPECTED='off'), RN, is_td, P, lambda: [], '2026-11-10T16:20:00+05:30'); check('readiness: the outside-timer check can be switched off', any(s == 'info' and n == 'Outside timer' for s, n, _ in R))
tk = lambda v: readiness.check_token(dict(CRON_TOKEN_EXPIRES=v) if v is not None else {}, RN)
check('readiness: token expiry: 70 days ok, 10 days warn, 2 days fail, expired fail, none info, bad text warn', [tk('2027-01-20')[0], tk('2026-11-21')[0], tk('2026-11-13')[0], tk('2026-11-01')[0], tk(None)[0], tk('soon')[0]] == ['ok', 'warn', 'fail', 'fail', 'info', 'warn'])
check('readiness: old swing data warns, recent is fine', readiness.check_data('2026-11-08T16:20:00+05:30', RN)[0] == 'warn' and readiness.check_data('2026-11-10T16:20:00+05:30', RN)[0] == 'ok' and readiness.check_data('', RN)[0] == 'warn')
BK = lambda h, ok=True: dict(at=(RN - dt.timedelta(hours=h)).isoformat(), ok=ok, changed=True, files=3, bytes=2048)
check('readiness: journal backup: last night ok, 40 hours ago warns, failed run is a failure, not set up is information only', [readiness.check_backup(BK(10), RN)[0], readiness.check_backup(BK(40), RN)[0], readiness.check_backup(BK(5, False), RN)[0], readiness.check_backup(None, RN)[0]] == ['ok', 'warn', 'fail', 'info'])
check('readiness: no alert channel at all is a failure', readiness.check_channels({})[0] == 'fail')
check('readiness: Angel One not set up is information only', readiness.check_angel({}, lambda: (True, ''))[0] == 'info')
od = tempfile.mkdtemp(); readiness.probe_yahoo = P['yahoo']; readiness.probe_universe = P['universe']; readiness.probe_angel = P['angel']; readiness.gh_runs = lambda: runs
os.environ.update(ENV); os.environ.pop('GITHUB_TOKEN', None); SENT.clear(); rc = readiness.main(['--out', od, '--force'])
rj = json.load(open(os.path.join(od, 'health', 'readiness.json')))
check('readiness: main writes health/readiness.json for the app and pushes the summary', bool(rc == 0 and rj['checks'] and rj['level'] in ('ok', 'warn', 'fail') and SENT and 'ready' in SENT[-1][0].lower()), str(rj['level']))

# ---------- CI helpers
res = [dict(name='test_a.py', ok=True, seconds=1.0, fails=[], tail='ALL PASSED'), dict(name='test_b.py', ok=False, seconds=2.0, fails=['stop is moved to entry at T2'], tail='1 FAILED')]
ok, head, lines = run_tests.summarize(res)
check('ci: summary counts failures and names the failing check', not ok and head.startswith('1 PROBLEM(S): 1/2') and any('stop is moved to entry at T2' in l for l in lines))
check('ci: all good summary', run_tests.summarize(res[:1])[0] and run_tests.summarize(res[:1])[1].startswith('ALL GOOD'))
title, text = ci_alert.build(dict(headline=head, results=res), 'abc1234def', 'Upload new datasource', 'https://github.com/x/y/actions/runs/9', 'https://github.com/x/y')
check('ci alert: names the commit, the failing check, how to roll back and the run link', title == 'Your last upload failed its tests' and 'abc1234' in text and 'test_b.py' in text and 'rollback' in text and '/actions/runs/9' in text)
bad_js = tempfile.mkdtemp(); os.makedirs(os.path.join(bad_js, 'site', 'js')); open(os.path.join(bad_js, 'site', 'js', 'x.js'), 'w').write('const = ;'); old = run_tests.ROOT; run_tests.ROOT = bad_js
r = run_tests.check_js(); run_tests.ROOT = old
import shutil
check('ci: a JavaScript syntax error is caught', (not r[0]['ok'] and 'x.js' in r[0]['fails'][0]) if shutil.which('node') else True, 'node not installed: skipped' if not shutil.which('node') else '')
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED'); raise SystemExit(1 if fails else 0)
