#!/usr/bin/env python3
"""Watchdog: keeps the 5-minute market loop alive during market hours.

Runs every ~10 minutes (GitHub schedule, and ideally also from cron-job.org, because GitHub sometimes skips schedules).
  * No market-loop run running or queued      -> start one.
  * A run is going but its heartbeat (data/health/loop.json on gh-pages) has been quiet for 20 minutes -> cancel it, start a fresh one.
  * Otherwise                                  -> do nothing.
It only sends a phone push when it had to act. Outside 09:10-15:25 IST, on weekends and on NSE holidays it does nothing.
Needs: GITHUB_TOKEN with actions: write (the workflow grants it). Optional: NTFY_TOPIC, NTFY_URL, PAGE_URL."""
import base64, datetime as dt, json, os, sys, time, urllib.request
import loop

API = 'https://api.github.com'
WORKFLOW = 'market-loop.yml'
ACTIVE = {'queued', 'in_progress', 'waiting', 'pending', 'requested'}
OPEN, LAST = dt.time(9, 10), dt.time(15, 25)
STALE_MIN, GRACE_MIN = 20, 15          # heartbeat silence that counts as frozen; how long a new run gets before it must have beaten

def gh(method, path, token, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                                          'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'downerstuff-watchdog'})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}

def _ts(s):
    if not s: return None
    t = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    return t if t.tzinfo else t.replace(tzinfo=loop.IST)

def minutes(now, s):
    t = _ts(s); return None if t is None else (now - t).total_seconds() / 60

def decide(now, runs, hb, trading=True, window=None, name='market-loop'):
    """Pure decision, so it can be tested. runs: market-loop runs from the API (newest first). hb: the loop heartbeat or None.
    Returns (action, reason, run_id) with action in skip / ok / start / restart."""
    if not trading: return 'skip', 'not a trading day' if name == 'market-loop' else 'the gold market is closed', None
    o, l = window or (OPEN, LAST)
    if not (o <= now.time() <= l): return 'skip', f'outside {o:%H:%M}-{l:%H:%M} IST', None
    active = [r for r in runs if r.get('status') in ACTIVE]
    running = [r for r in active if r.get('status') == 'in_progress']
    if not active: return 'start', f'no {name} run was running or queued', None
    if not running: return 'ok', f'a {name} run is queued and about to start', None
    r = running[0]; age_run = minutes(now, r.get('run_started_at') or r.get('created_at')) or 0
    beat = minutes(now, (hb or {}).get('last_tick') or (hb or {}).get('started')) if hb else None
    if hb and _ts(hb.get('started')) and _ts(r.get('run_started_at') or r.get('created_at')) and _ts(hb['started']) < _ts(r.get('run_started_at') or r.get('created_at')) - dt.timedelta(minutes=2):
        beat = None                                   # the heartbeat is from an older loop: this run has not beaten yet
    if age_run < GRACE_MIN: return 'ok', f'loop started {age_run:.0f} min ago', None
    if beat is None or beat > STALE_MIN:
        return 'restart', f"the running loop has been silent for {'over ' + str(int(age_run)) if beat is None else int(beat)} min", r.get('id')
    return 'ok', f'loop alive, last tick {beat:.0f} min ago', None

def heartbeat(repo, token, path='data/health/loop.json'):
    try:
        js = gh('GET', f'/repos/{repo}/contents/{path}?ref=gh-pages', token)
        return json.loads(base64.b64decode(js['content']).decode())
    except Exception as ex:
        print(f'heartbeat unavailable: {ex}'); return None

def push(title, body):
    """Phone push through ntfy and/or Telegram, whichever is configured."""
    import notify
    topic = os.environ.get('NTFY_TOPIC', '').strip(); click = os.environ.get('PAGE_URL', '').strip()
    if not topic and not notify.telegram_ready(): return
    try: notify.post(os.environ.get('NTFY_URL', 'https://ntfy.sh').rstrip('/'), topic, title, body, 'rotating_light', click.rstrip('/') + '/#/health' if click else '')
    except Exception as ex: print(f'push failed: {ex}')

def gold_market_open(now):
    """Gold trades from Sunday 22:00 UTC (23:00 in the northern winter) to Friday 22:00 UTC, with a short daily break. Weekends are closed."""
    u = now.astimezone(dt.timezone.utc); wd, h = u.weekday(), u.hour
    if wd == 5: return False
    if wd == 6: return h >= 22
    if wd == 4: return h < 22
    return True

def main_gold(now, repo, token, ref):
    """--gold: keep the gold loop alive through every gold session (Sunday night to Friday night IST), the same way."""
    trading = gold_market_open(now); full = (dt.time(0, 0), dt.time(23, 59, 59))
    if not trading: print('gold watchdog:', decide(now, [], None, trading, full, 'gold-loop')[1]); return 0
    runs = gh('GET', f'/repos/{repo}/actions/workflows/gold-loop.yml/runs?per_page=15', token).get('workflow_runs', [])
    hb = heartbeat(repo, token, 'data/health/gold_loop.json')
    action, reason, run_id = decide(now, runs, hb, trading, full, 'gold-loop')
    print(f'gold watchdog {now:%a %H:%M} IST: {action} ({reason})')
    if action == 'restart':
        try: gh('POST', f'/repos/{repo}/actions/runs/{run_id}/cancel', token); time.sleep(15)
        except Exception as ex: print(f'cancel failed: {ex}')
    if action in ('start', 'restart'):
        if not dispatch(repo, token, ref, 'gold-loop.yml', 'gold loop', reason, now): return 1
        if action == 'restart' or os.environ.get('GOLD_WATCHDOG_PUSH', '').strip().lower() in ('on', 'all'):
            push(f"Gold loop {'restarted' if action == 'restart' else 'started'} by the watchdog", f"{now:%H:%M} IST: {reason}. Gold scans resume within about 5 minutes.")
    return 0

def main():
    now = loop.now_ist(); repo = os.environ['GITHUB_REPOSITORY']; token = os.environ['GITHUB_TOKEN']; ref = os.environ.get('GITHUB_REF_NAME') or 'main'
    if '--gold' in sys.argv[1:]: return main_gold(now, repo, token, ref)
    trading = loop.trading_day(now.date())
    if not trading or not (OPEN <= now.time() <= LAST):
        print('watchdog:', decide(now, [], None, trading)[1]); return 0
    runs = gh('GET', f'/repos/{repo}/actions/workflows/{WORKFLOW}/runs?per_page=15', token).get('workflow_runs', [])
    hb = heartbeat(repo, token)
    action, reason, run_id = decide(now, runs, hb, trading)
    print(f'watchdog {now:%H:%M} IST: {action} ({reason})')
    if action == 'restart':
        try: gh('POST', f'/repos/{repo}/actions/runs/{run_id}/cancel', token); time.sleep(15)
        except Exception as ex: print(f'cancel failed: {ex}')
    if action in ('start', 'restart'):
        if not dispatch(repo, token, ref, WORKFLOW, 'market loop', reason, now): return 1
        push(f"Market loop {'restarted' if action == 'restart' else 'started'} by the watchdog",
             f"{now:%H:%M} IST: {reason}. Live scans resume within about 5 minutes.")
    return 0

def dispatch(repo, token, ref, workflow, what, reason, now):
    """Start a workflow run. If GitHub refuses (workflow disabled, token without actions: write, API down), say so on your phone
    instead of failing silently: before, the watchdog run just went red in Actions and nobody knew the loop was still down."""
    try: gh('POST', f'/repos/{repo}/actions/workflows/{workflow}/dispatches', token, {'ref': ref}); return True
    except Exception as ex:
        msg = str(ex); hint = ' Is the workflow disabled? Actions > the workflow > Enable workflow.' if '403' in msg or '422' in msg or 'disabled' in msg.lower() else ''
        print(f'could not start the {what}: {msg}'); push(f'Could not start the {what}', f"{now:%H:%M} IST: {reason}, but GitHub refused to start it ({msg[:120]}).{hint}"); return False

def _local_hb(path):
    try: return json.load(open(path))
    except Exception: return None

_GUARD = {}
GUARD_LOG = {}                          # kind -> the last check, written into the calling loop's heartbeat (System health shows it)
def guard(kind, now, data_dir, log=print, every_min=10):
    """Each loop watches the other one (17 Nov 2026). The gold loop runs every 5 minutes all week, the market loop every 5 minutes in
    market hours, and both run inside GitHub without depending on GitHub's schedule, which skips runs (the watchdog workflow is itself
    a scheduled run, so when GitHub drops schedules the watchdog drops too: on 17 Nov the market loop was down from about 12:20 to 14:02).
    kind: 'market' (called by the gold loop) or 'gold' (called by the market loop). Uses the same decide() as the watchdog, the other
    loop's heartbeat from the published data, and calls the Actions API only when that heartbeat is stale, at most every `every_min`."""
    repo, token = os.environ.get('GITHUB_REPOSITORY'), os.environ.get('GITHUB_TOKEN')
    if not repo or not token: return 'skip'
    if kind == 'market':
        trading = loop.trading_day(now.date()); window = (OPEN, LAST); wf, name, hbf = WORKFLOW, 'market-loop', 'loop.json'
    else:
        trading = gold_market_open(now); window = (dt.time(0, 0), dt.time(23, 59, 59)); wf, name, hbf = 'gold-loop.yml', 'gold-loop', 'gold_loop.json'
    if not trading or not (window[0] <= now.time() <= window[1]): return 'skip'
    hb = _local_hb(os.path.join(data_dir, 'health', hbf)); beat = minutes(now, (hb or {}).get('last_tick') or (hb or {}).get('started')) if hb else None
    note = lambda act, why: GUARD_LOG.__setitem__(kind, dict(at=now.isoformat(timespec='minutes'), action=act, reason=why)) or act
    if beat is not None and beat <= STALE_MIN and (hb or {}).get('state') == 'running': return note('ok', f'last tick {beat:.0f} min ago')
    last = _GUARD.get(kind)
    if last is not None and (now - last).total_seconds() < every_min * 60: return 'wait'
    _GUARD[kind] = now
    try: runs = gh('GET', f'/repos/{repo}/actions/workflows/{wf}/runs?per_page=15', token).get('workflow_runs', [])
    except Exception as ex: log(f'guard {name}: could not read runs ({ex})'); return note('error', f'could not read the runs: {str(ex)[:80]}')
    action, reason, run_id = decide(now, runs, hb, trading, window, name)
    log(f'guard {name}: {action} ({reason})'); note(action, reason)
    if action == 'restart':
        try: gh('POST', f'/repos/{repo}/actions/runs/{run_id}/cancel', token); time.sleep(10)
        except Exception as ex: log(f'guard {name}: cancel failed ({ex})')
    if action in ('start', 'restart'):
        what = 'market loop' if kind == 'market' else 'gold loop'; by = 'the gold loop' if kind == 'market' else 'the market loop'
        if not dispatch(repo, token, os.environ.get('GITHUB_REF_NAME') or 'main', wf, what, reason, now): note('refused', f'{reason}; GitHub refused to start it')
        else:
            push(f"{what.capitalize()} {'restarted' if action == 'restart' else 'started'} by {by}", f"{now:%H:%M} IST: {reason}. It resumes within about 5 minutes.")
    return action

if __name__ == '__main__':
    sys.exit(main())
