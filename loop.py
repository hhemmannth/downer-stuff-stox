#!/usr/bin/env python3
"""Market-hours loop for GitHub Actions: on the minute, every 5 minutes, scan Nifty options + intraday stocks + market,
publish, and run the swing scan every hour at :25 in the background. One job runs up to about 5h45m (GitHub's job limit is 6h),
so the workflow starts a second loop for the end of the session. Nothing outside GitHub is needed."""
import argparse, datetime as dt, json, os, subprocess, sys, time
import publish

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
CLOSE = dt.time(15, 40)

def now_ist(): return dt.datetime.now(IST)

def end_time(start, max_hours=5.75):
    return min(dt.datetime.combine(start.date(), CLOSE, tzinfo=IST), start + dt.timedelta(hours=max_hours))

def next_tick(now, every=5, offset=40):
    """The next 5-minute boundary plus `offset` seconds (so the candle that just closed is in Yahoo's data)."""
    base = now.replace(second=0, microsecond=0); m = (base.minute // every + 1) * every
    t = base.replace(minute=0) + dt.timedelta(minutes=m, seconds=offset)
    if t - dt.timedelta(minutes=every) > now: t -= dt.timedelta(minutes=every)
    return t

def trading_day(day, events='events.json'):
    if day.weekday() >= 5: return False
    try: hol = {h['date'] for h in json.load(open(events)).get('holidays', [])}
    except Exception: hol = set()
    return day.isoformat() not in hol

def swing_due(t, last_hour, minute=25):
    return 10 <= t.hour <= 15 and t.minute >= minute and last_hour != (t.date(), t.hour)

def heartbeat(pub, **kw):
    """data/health/loop.json: proof the 5-minute loop is alive. The app shows a red banner when it goes quiet during market hours,
    and the watchdog restarts the loop when it stops or freezes."""
    d = os.path.join(pub, 'data', 'health'); os.makedirs(d, exist_ok=True); path = os.path.join(d, 'loop.json')
    kw['updated_at'] = now_ist().isoformat(timespec='seconds')
    e = os.environ; kw['run_url'] = f"{e.get('GITHUB_SERVER_URL', 'https://github.com')}/{e['GITHUB_REPOSITORY']}/actions/runs/{e['GITHUB_RUN_ID']}" if e.get('GITHUB_REPOSITORY') and e.get('GITHUB_RUN_ID') else None
    with open(path + '.tmp', 'w') as f: json.dump(kw, f, default=str)
    os.replace(path + '.tmp', path)

def run(args, log):
    r = subprocess.run(args, capture_output=True, text=True); log(f"$ {' '.join(args[1:4])} -> {r.returncode}\n{(r.stdout + r.stderr)[-1500:]}"); return r.returncode

def main(argv=None):
    p = argparse.ArgumentParser(); p.add_argument('--pub', default='pub'); p.add_argument('--every', type=int, default=5); p.add_argument('--offset', type=int, default=40)
    p.add_argument('--swing-minute', type=int, default=25); p.add_argument('--max-hours', type=float, default=5.75); p.add_argument('--once', action='store_true'); p.add_argument('--no-publish', action='store_true')
    a = p.parse_args(argv); log = lambda s: print(f"[{now_ist():%H:%M:%S}] {s}", flush=True)
    start = now_ist(); end = end_time(start, a.max_hours)
    if not trading_day(start.date()) and not a.once: log('Not a trading day: nothing to do.'); return 0
    if start >= end and not a.once: log('Market session is over: nothing to do.'); return 0
    pub = a.pub if a.no_publish else publish.prepare(a.pub); os.makedirs(os.path.join(pub, 'data'), exist_ok=True); os.makedirs(os.path.join(pub, 'state'), exist_ok=True)
    py = sys.executable; data = os.path.join(pub, 'data'); state = os.path.join(pub, 'state', 'notified.json')
    last_pub = time.time() - 1; swing = None; swing_hour = None; log(f'Loop until {end:%H:%M} IST')
    hb = dict(state='running', started=start.isoformat(timespec='seconds'), until=end.isoformat(timespec='seconds'), ticks=0, last_tick=None, last_scan_s=None, last_rc=None, publish='-')
    if not a.no_publish and not a.once:
        heartbeat(pub, **hb, next_tick=next_tick(now_ist(), a.every, a.offset).isoformat(timespec='seconds'))
        mark = time.time()
        try: publish.publish(pub, last_pub, message=f'loop started {start:%H:%M} IST'); last_pub = mark
        except Exception as ex: log(f'publish failed: {ex}')
    while True:
        t = next_tick(now_ist(), a.every, a.offset)
        if t > end and not a.once: break
        if not a.once:
            wait = (t - now_ist()).total_seconds()
            if wait > 0: time.sleep(wait)
        tick = now_ist(); log(f'tick {tick:%H:%M:%S}')
        if swing is None and swing_due(tick, swing_hour, a.swing_minute):
            swing = subprocess.Popen([py, 'strategy_scanner.py', '--mode', 'swing', '--out', data, '--state-dir', '.cache']); swing_hour = (tick.date(), tick.hour); log('swing scan started in the background')
        t0 = time.time(); rc = run([py, 'strategy_scanner.py', '--mode', 'live', '--out', data, '--state-dir', '.cache'], log)
        if swing is not None and swing.poll() is not None: log(f'swing scan finished ({swing.returncode})'); swing = None
        run([py, 'notify.py', '--dir', data, '--state', state], log)
        hb.update(ticks=hb['ticks'] + 1, last_tick=tick.isoformat(timespec='seconds'), last_scan_s=round(time.time() - t0, 1), last_rc=rc, swing_running=swing is not None)
        heartbeat(pub, **hb, next_tick=next_tick(now_ist() + dt.timedelta(seconds=1), a.every, a.offset).isoformat(timespec='seconds'))
        if not a.no_publish:
            mark = time.time()
            try: publish.publish(pub, last_pub, message=f'scan {tick:%Y-%m-%d %H:%M} IST'); last_pub = mark; hb['publish'] = 'ok'; log('published')
            except Exception as ex: hb['publish'] = f'failed: {str(ex)[:120]}'; log(f'publish failed: {ex}')
        if a.once: break
    if swing is not None:
        try: swing.wait(timeout=600)
        except Exception: swing.kill()
        run([py, 'notify.py', '--dir', data, '--state', state], log)
    hb.update(state='finished', swing_running=False); heartbeat(pub, **hb, next_tick=None)
    if not a.no_publish:
        try: publish.publish(pub, last_pub, message='final'); log('published final')
        except Exception as ex: log(f'publish failed: {ex}')
    log('Loop finished'); return 0

if __name__ == '__main__':
    sys.exit(main())
