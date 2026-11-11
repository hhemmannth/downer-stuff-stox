#!/usr/bin/env python3
"""Gold loop for GitHub Actions: through every gold session (Sunday night to Friday night), every 5 minutes it runs the gold intraday
scan, and once an hour (just after the hourly candle closes) the gold swing and positional scans, then publishes. One job runs up to
about 5h45m (GitHub's limit is 6h); the gold-loop workflow is started again on a schedule and by the gold watchdog, so the loop keeps
going all day. It writes data/health/gold_loop.json on every tick so the app and the watchdog can see it is alive."""
import argparse, datetime as dt, os, subprocess, sys, time
import pandas as pd
import loop, publish, gold_live

def hourly_due(t, last):
    """The swing and positional scans run once an hour, from 2 minutes past (the 1H candle has closed by then)."""
    return t.minute >= 2 and last != (t.date(), t.hour)

def heartbeat(pub, **kw):
    d = os.path.join(pub, 'data', 'health'); os.makedirs(d, exist_ok=True); path = os.path.join(d, 'gold_loop.json')
    kw['updated_at'] = loop.now_ist().isoformat(timespec='seconds')
    e = os.environ; kw['run_url'] = f"{e.get('GITHUB_SERVER_URL', 'https://github.com')}/{e['GITHUB_REPOSITORY']}/actions/runs/{e['GITHUB_RUN_ID']}" if e.get('GITHUB_REPOSITORY') and e.get('GITHUB_RUN_ID') else None
    import json
    with open(path + '.tmp', 'w') as f: json.dump(kw, f, default=str)
    os.replace(path + '.tmp', path)

def relay(log):
    """Before this job ends, queue the next gold loop so there is no gap (the watchdog is the backup). Needs actions: write."""
    repo, token = os.environ.get('GITHUB_REPOSITORY'), os.environ.get('GITHUB_TOKEN')
    if not repo or not token: return False
    try:
        import watchdog; watchdog.gh('POST', f'/repos/{repo}/actions/workflows/gold-loop.yml/dispatches', token, {'ref': os.environ.get('GITHUB_REF_NAME') or 'main'}); log('next gold loop queued'); return True
    except Exception as ex: log(f'could not queue the next gold loop ({ex}); the gold watchdog will start it'); return False

def main(argv=None):
    p = argparse.ArgumentParser(); p.add_argument('--pub', default='pub'); p.add_argument('--every', type=int, default=5); p.add_argument('--offset', type=int, default=50)
    p.add_argument('--max-hours', type=float, default=5.75); p.add_argument('--once', action='store_true'); p.add_argument('--no-publish', action='store_true')
    a = p.parse_args(argv); log = lambda s: print(f"[{loop.now_ist():%a %H:%M:%S} IST] {s}", flush=True)
    start = loop.now_ist(); end = start + dt.timedelta(hours=a.max_hours)
    if not gold_live.market_open(pd.Timestamp(start)) and not a.once: log('Gold market is closed (weekend): nothing to do.'); return 0
    pub = a.pub if a.no_publish else publish.prepare(a.pub); data = os.path.join(pub, 'data'); state = os.path.join(pub, 'state')
    os.makedirs(data, exist_ok=True); os.makedirs(state, exist_ok=True); py = sys.executable; last_pub = time.time() - 1; last_hour = None
    hb = dict(state='running', started=start.isoformat(timespec='seconds'), until=end.isoformat(timespec='seconds'), ticks=0, last_tick=None, last_rc=None, publish='-', bad_ticks=0)
    log(f'Gold loop until {end:%a %H:%M} IST')
    while True:
        t = loop.next_tick(loop.now_ist(), a.every, a.offset)
        if t > end and not a.once: break
        if not a.once:
            wait = (t - loop.now_ist()).total_seconds()
            if wait > 0: time.sleep(wait)
        tick = loop.now_ist()
        if not gold_live.market_open(pd.Timestamp(tick)) and not a.once: log('Gold market closed for the weekend: stopping.'); break
        styles = ['intraday'] + (['swing', 'positional'] if hourly_due(tick, last_hour) else [])
        if len(styles) > 1: last_hour = (tick.date(), tick.hour)
        t0 = time.time(); r = subprocess.run([py, 'gold_live.py', '--out', data, '--state', state, '--styles', ','.join(styles)], capture_output=True, text=True)
        log(f"tick {', '.join(styles)} -> {r.returncode} in {time.time() - t0:.0f}s\n{(r.stdout + r.stderr)[-1200:]}")
        hb.update(ticks=hb['ticks'] + 1, last_tick=tick.isoformat(timespec='seconds'), last_rc=r.returncode, bad_ticks=0 if r.returncode == 0 else hb['bad_ticks'] + 1,
                  next_tick=loop.next_tick(loop.now_ist() + dt.timedelta(seconds=1), a.every, a.offset).isoformat(timespec='seconds'))
        heartbeat(pub, **hb)
        if not a.no_publish:
            mark = time.time()
            try: publish.publish(pub, last_pub, message=f'gold {tick:%Y-%m-%d %H:%M} IST'); last_pub = mark; hb['publish'] = 'ok'
            except Exception as ex: hb['publish'] = f'failed: {str(ex)[:120]}'; log(f'publish failed: {ex}')
        try:
            import alerts
            alerts.watch('gold-scan', hb['bad_ticks'] >= 3, 'Gold scan is failing', f"{hb['bad_ticks']} gold ticks in a row failed. {hb.get('run_url') or ''}", os.path.join(state, 'alerts.json'), 60,
                         'Gold scan recovered', 'Gold ticks are succeeding again.')
        except Exception as ex: log(f'loop alerts failed: {ex}')
        if a.once: break
    hb.update(state='finished', next_tick=None); heartbeat(pub, **hb)
    if not a.once and gold_live.market_open(pd.Timestamp(loop.now_ist() + dt.timedelta(minutes=10))): relay(log)
    if not a.no_publish:
        try: publish.publish(pub, last_pub, message='gold loop finished')
        except Exception as ex: log(f'publish failed: {ex}')
    log('Gold loop finished'); return 0

if __name__ == '__main__':
    sys.exit(main())
