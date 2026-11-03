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

def decide(now, runs, hb, trading=True):
    """Pure decision, so it can be tested. runs: market-loop runs from the API (newest first). hb: the loop heartbeat or None.
    Returns (action, reason, run_id) with action in skip / ok / start / restart."""
    if not trading: return 'skip', 'not a trading day', None
    if not (OPEN <= now.time() <= LAST): return 'skip', f'outside {OPEN:%H:%M}-{LAST:%H:%M} IST', None
    active = [r for r in runs if r.get('status') in ACTIVE]
    running = [r for r in active if r.get('status') == 'in_progress']
    if not active: return 'start', 'no market-loop run was running or queued', None
    if not running: return 'ok', 'a market-loop run is queued and about to start', None
    r = running[0]; age_run = minutes(now, r.get('run_started_at') or r.get('created_at')) or 0
    beat = minutes(now, (hb or {}).get('last_tick') or (hb or {}).get('started')) if hb else None
    if hb and _ts(hb.get('started')) and _ts(r.get('run_started_at') or r.get('created_at')) and _ts(hb['started']) < _ts(r.get('run_started_at') or r.get('created_at')) - dt.timedelta(minutes=2):
        beat = None                                   # the heartbeat is from an older loop: this run has not beaten yet
    if age_run < GRACE_MIN: return 'ok', f'loop started {age_run:.0f} min ago', None
    if beat is None or beat > STALE_MIN:
        return 'restart', f"the running loop has been silent for {'over ' + str(int(age_run)) if beat is None else int(beat)} min", r.get('id')
    return 'ok', f'loop alive, last tick {beat:.0f} min ago', None

def heartbeat(repo, token):
    try:
        js = gh('GET', f'/repos/{repo}/contents/data/health/loop.json?ref=gh-pages', token)
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

def main():
    now = loop.now_ist(); repo = os.environ['GITHUB_REPOSITORY']; token = os.environ['GITHUB_TOKEN']; ref = os.environ.get('GITHUB_REF_NAME') or 'main'
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
        gh('POST', f'/repos/{repo}/actions/workflows/{WORKFLOW}/dispatches', token, {'ref': ref})
        push(f"Market loop {'restarted' if action == 'restart' else 'started'} by the watchdog",
             f"{now:%H:%M} IST: {reason}. Live scans resume within about 5 minutes.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
