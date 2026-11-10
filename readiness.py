#!/usr/bin/env python3
"""Morning readiness check (item 27): at 08:50 IST, before the market opens, confirm that everything the session depends on works,
send one clear message to your phone, and publish the result to the System health page.

Checks: Angel One login and its candle API, Yahoo, the live Nifty 500 list, alert channels, that cron-job.org really triggered the
watchdog on the previous trading day, how many days are left on your cron-job token (repo variable CRON_TOKEN_EXPIRES, YYYY-MM-DD),
and that the last swing scan is recent. Does nothing on weekends and NSE holidays (unless --force).

  python readiness.py --out pub/data [--force]"""
import argparse, datetime as dt, json, os, sys, urllib.request

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
OK, WARN, FAIL, INFO = 'ok', 'warn', 'fail', 'info'

def check_angel(env, probe):
    if not all(env.get(k, '').strip() for k in ('ANGEL_API_KEY', 'ANGEL_CLIENT_CODE', 'ANGEL_MPIN', 'ANGEL_TOTP_SECRET')):
        return (INFO, 'Angel One', 'not set up (optional): Yahoo is used for everything')
    ok, msg = probe()
    return (OK if ok else WARN, 'Angel One', msg)

def probe_angel():
    import datasource
    datasource.reset(); a = datasource.angel()
    if a is None: return False, 'login failed: ' + str(datasource.STATS['angel'].get('error') or 'unknown error') + '. Yahoo will be used.'
    try: a.candles(datasource.INDEX_TOKENS['^NSEI'], '1d', 5); return True, 'login works and the candle API answers'
    except Exception as ex: return False, f'logged in, but the candle API refused ({ex}): this happens at times; Yahoo covers it'

def probe_yahoo():
    try:
        import strategy_scanner as sc
        d, _ = sc.yahoo_many(['^NSEI'], '5d', '1d')
        return (True, f"Nifty closes available up to {d['^NSEI'].index[-1]:%d %b}") if '^NSEI' in d and len(d['^NSEI']) else (False, 'returned no Nifty data')
    except Exception as ex: return False, str(ex)[:120]

def probe_universe():
    try:
        import strategy_scanner as sc
        syms, note, _ = sc.load_nifty500(); return (len(syms) >= 450, note)
    except Exception as ex: return False, str(ex)[:120]

def check_channels(env):
    tg = bool(env.get('TELEGRAM_BOT_TOKEN', '').strip() and env.get('TELEGRAM_CHAT_ID', '').strip()); nt = bool(env.get('NTFY_TOPIC', '').strip())
    if tg or nt: return (OK, 'Alerts', ' and '.join(x for x, on in (('Telegram', tg), ('ntfy', nt)) if on) + ' configured (this message is the live test)')
    return (FAIL, 'Alerts', 'no channel configured: add TELEGRAM_* or NTFY_TOPIC secrets')

def prev_trading_day(day, is_trading):
    d = day - dt.timedelta(days=1)
    for _ in range(10):
        if is_trading(d): return d
        d -= dt.timedelta(days=1)
    return None

def check_cron(env, now, is_trading, fetch_runs):
    """Did an outside timer (cron-job.org) start the watchdog on the previous trading day?"""
    if env.get('CRON_JOB_EXPECTED', 'on').strip().lower() == 'off': return (INFO, 'Outside timer', 'check turned off')
    prev = prev_trading_day(now.date(), is_trading)
    if prev is None: return (INFO, 'Outside timer', 'no earlier trading day found')
    try: runs = fetch_runs()
    except Exception as ex: return (INFO, 'Outside timer', f'could not read workflow runs ({str(ex)[:60]})')
    days = set()
    for r in runs:
        try: days.add(dt.datetime.fromisoformat(r['created_at'].replace('Z', '+00:00')).astimezone(IST).date())
        except Exception: pass
    if prev in days: return (OK, 'Outside timer', f'cron-job.org started the watchdog on {prev:%a %d %b}')
    return (WARN, 'Outside timer', f'no manual-trigger run of the watchdog on {prev:%a %d %b}: check your cron-job.org job and its GitHub token')

def check_token(env, now):
    v = env.get('CRON_TOKEN_EXPIRES', '').strip()
    if not v: return (INFO, 'Token expiry', 'set the repo variable CRON_TOKEN_EXPIRES (YYYY-MM-DD) to get a reminder before your cron-job token expires')
    try: left = (dt.date.fromisoformat(v) - now.date()).days
    except Exception: return (WARN, 'Token expiry', f'CRON_TOKEN_EXPIRES "{v}" is not a date (use YYYY-MM-DD)')
    if left < 0: return (FAIL, 'Token expiry', f'your cron-job GitHub token expired {-left} days ago: the outside timer is not working')
    if left <= 14: return (WARN if left > 3 else FAIL, 'Token expiry', f'your cron-job GitHub token expires in {left} days: create a new one and update cron-job.org')
    return (OK, 'Token expiry', f'{left} days left')

def check_data(swing_iso, now):
    try: g = dt.datetime.fromisoformat(swing_iso).astimezone(IST)
    except Exception: return (WARN, 'Last swing scan', 'no swing data found: run the scan workflow once')
    h = (now - g).total_seconds() / 3600
    return (OK if h <= 30 else WARN, 'Last swing scan', f'{g:%a %d %b %H:%M} IST' + ('' if h <= 30 else ' (older than expected: the 16:17 scan may have been skipped)'))

def check_backup(bk, now):
    """The nightly encrypted journal backup (published as health/backup.json: a time and a size, never content)."""
    if not bk: return (INFO, 'Journal backup', 'not set up yet (optional): see "Journal backup" in the README')
    try: g = dt.datetime.fromisoformat(bk['at']).astimezone(IST)
    except Exception: return (WARN, 'Journal backup', 'the backup status file is unreadable')
    h = (now - g).total_seconds() / 3600
    if not bk.get('ok', True): return (FAIL, 'Journal backup', f'the last backup run failed ({g:%a %d %b %H:%M})')
    return (OK if h <= 36 else WARN, 'Journal backup', f'last run {g:%a %d %b %H:%M} IST' + ('' if h <= 36 else ' (more than 36 hours ago: check the backup workflow)'))

def run_checks(env, now, is_trading, probes=None, fetch_runs=None, swing_iso=None, backup=None):
    P = dict(angel=probe_angel, yahoo=probe_yahoo, universe=probe_universe); P.update(probes or {})
    R = [check_angel(env, P['angel'])]
    ok, msg = P['yahoo'](); R.append((OK if ok else FAIL, 'Yahoo Finance', msg if ok else 'not reachable: ' + msg))
    ok, msg = P['universe'](); R.append((OK if ok else WARN, 'Nifty 500 list', msg if ok else 'live list unavailable, the local fallback list will be used (' + msg + ')'))
    R.append(check_channels(env)); R.append(check_cron(env, now, is_trading, fetch_runs or (lambda: []))); R.append(check_token(env, now)); R.append(check_data(swing_iso or '', now)); R.append(check_backup(backup, now))
    return R

def summarize(R):
    level = FAIL if any(s == FAIL for s, _, _ in R) else WARN if any(s == WARN for s, _, _ in R) else OK
    mark = {OK: '✅', WARN: '⚠️', FAIL: '🚨', INFO: 'ℹ️'}
    title = {OK: 'Ready for the session', WARN: 'Ready, with warnings', FAIL: 'NOT ready: fix before 09:15'}[level]
    body = '\n'.join(f'{mark[s]} {n}: {m}' for s, n, m in R)
    return level, title, body

def gh_runs():
    repo, tok = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_TOKEN']
    req = urllib.request.Request(f'https://api.github.com/repos/{repo}/actions/workflows/watchdog.yml/runs?event=workflow_dispatch&per_page=30',
                                 headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'downerstuff'})
    return json.loads(urllib.request.urlopen(req, timeout=30).read()).get('workflow_runs', [])

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='pub/data'); ap.add_argument('--force', action='store_true'); a = ap.parse_args(argv)
    now = dt.datetime.now(IST); import loop
    is_trading = lambda d: loop.trading_day(d)
    if not a.force and not is_trading(now.date()): print(f'readiness: {now.date()} is not a trading day, nothing to check'); return 0
    swing_iso = ''
    try: swing_iso = json.load(open(os.path.join(a.out, 'swing.json'))).get('generated_at', '')
    except Exception: pass
    bk = None
    try: bk = json.load(open(os.path.join(a.out, 'health', 'backup.json')))
    except Exception: pass
    R = run_checks(dict(os.environ), now, is_trading, fetch_runs=gh_runs if os.environ.get('GITHUB_TOKEN') else None, swing_iso=swing_iso, backup=bk)
    level, title, body = summarize(R)
    print(title); print(body)
    os.makedirs(os.path.join(a.out, 'health'), exist_ok=True)
    with open(os.path.join(a.out, 'health', 'readiness.json'), 'w') as f:
        json.dump(dict(at=now.isoformat(timespec='seconds'), level=level, title=title, checks=[dict(status=s, name=n, detail=m) for s, n, m in R]), f)
    import notify
    topic = os.environ.get('NTFY_TOPIC', '').strip(); click = os.environ.get('PAGE_URL', '').strip(); base = os.environ.get('NTFY_URL', 'https://ntfy.sh').rstrip('/')
    if topic or notify.telegram_ready():
        try: notify.post(base, topic, f'{now:%a %d %b} · {title}', body, 'white_check_mark' if level == OK else 'warning', (click.rstrip('/') + '/#/health') if click else '')
        except Exception as ex: print(f'readiness push failed: {ex}', file=sys.stderr)
    return 0

if __name__ == '__main__':
    sys.exit(main())
