#!/usr/bin/env python3
"""Market-hours loop for GitHub Actions: on the minute, every 5 minutes, scan Nifty options + intraday stocks + market,
publish, and run the swing scan in the background right after each 1H candle closes (:15, and 15:30 for the day's last candle). One job runs up to about 5h45m (GitHub's job limit is 6h),
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

def swing_slot(t, minute=15):
    """Which 1H candle has just closed. NSE 1H candles close at :15 (09:15-10:15 ... 14:15-15:15) and the day's last one (15:15-15:30) at 15:30,
    so the swing scan starts on the first tick after each close instead of ten minutes later, and the last candle of the day is scanned the same day."""
    if t.hour == 15 and t.minute >= 30: return (t.date(), '15:30')
    if 10 <= t.hour <= 15 and t.minute >= minute: return (t.date(), f'{t.hour}:{minute:02d}')
    return None

def swing_fast_due(t):
    """The swing fast lane: right after each 15m candle closes (:00, :30, :45), re-check the 1H-confirmed setups for a 15m entry between the full scans.
    :15 is left to the full swing scan (it covers the 15m entry too). The loop only calls this when no full scan is running, so the 15:30 tick (the
    day's last 1H candle, a full scan) never runs both. From 09:30, when the first 15m candle of the day closes, so the first entries of the morning
    are seen at once instead of at the first scan after 10:15."""
    m = t.hour * 60 + t.minute
    return t.minute in (0, 30, 45) and 9 * 60 + 30 <= m <= 15 * 60 + 30

def swing_due(t, last, minute=15):
    slot = swing_slot(t, minute); return slot is not None and slot != last

def heartbeat(pub, **kw):
    """data/health/loop.json: proof the 5-minute loop is alive. The app shows a red banner when it goes quiet during market hours,
    and the watchdog restarts the loop when it stops or freezes."""
    d = os.path.join(pub, 'data', 'health'); os.makedirs(d, exist_ok=True); path = os.path.join(d, 'loop.json')
    kw['updated_at'] = now_ist().isoformat(timespec='seconds')
    e = os.environ; kw['run_url'] = f"{e.get('GITHUB_SERVER_URL', 'https://github.com')}/{e['GITHUB_REPOSITORY']}/actions/runs/{e['GITHUB_RUN_ID']}" if e.get('GITHUB_REPOSITORY') and e.get('GITHUB_RUN_ID') else None
    with open(path + '.tmp', 'w') as f: json.dump(kw, f, default=str)
    os.replace(path + '.tmp', path)

def watch_loop(pub, hb):
    """Item 28: two failed scans or three failed publishes in a row -> phone alert; one recovery note afterwards."""
    try:
        import alerts
        sp = os.path.join(pub, 'state', 'alerts.json'); link = hb.get('run_url') or ''
        alerts.watch('loop-scan', hb.get('bad_ticks', 0) >= 2, 'Live scan is failing', f"{hb.get('bad_ticks')} ticks in a row failed (exit code {hb.get('last_rc')}). Options and intraday may be stale. {link}", sp, 60,
                     'Live scan recovered', 'Ticks are succeeding again.')
        alerts.watch('loop-publish', hb.get('bad_publish', 0) >= 3, 'Publishing is failing', f"The last 3 publishes failed ({hb.get('publish')}). The site is not getting new data. {link}", sp, 60,
                     'Publishing recovered', 'The site is updating again.')
    except Exception as ex: print(f'  loop alerts failed: {ex}', file=sys.stderr)

def run(args, log, timeout=None):
    try: r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired: log(f"$ {' '.join(args[1:4])} -> timed out after {timeout}s"); return 124                # a stuck step must never hold up the next tick
    log(f"$ {' '.join(args[1:4])} -> {r.returncode}\n{(r.stdout + r.stderr)[-1500:]}"); return r.returncode

def main(argv=None):
    p = argparse.ArgumentParser(); p.add_argument('--pub', default='pub'); p.add_argument('--every', type=int, default=5); p.add_argument('--offset', type=int, default=40)
    p.add_argument('--swing-minute', type=int, default=15); p.add_argument('--max-hours', type=float, default=5.75); p.add_argument('--once', action='store_true'); p.add_argument('--no-publish', action='store_true')
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
            swing = subprocess.Popen([py, 'strategy_scanner.py', '--mode', 'swing', '--out', data, '--state-dir', '.cache']); swing_hour = swing_slot(tick, a.swing_minute); log('swing scan started in the background')
        t0 = time.time(); rc = run([py, 'strategy_scanner.py', '--mode', 'live', '--out', data, '--state-dir', '.cache'], log)
        if swing is not None and swing.poll() is not None: log(f'swing scan finished ({swing.returncode})'); swing = None
        if swing is None and swing_fast_due(tick):                                                      # the 15m entry check, before the alerts go out in this same tick
            tf0 = time.time(); frc = run([py, 'strategy_scanner.py', '--mode', 'swing-fast', '--out', data, '--state-dir', '.cache'], log, timeout=170); hb.update(fast_last=tick.isoformat(timespec='seconds'), fast_rc=frc, fast_s=round(time.time() - tf0, 1))
        run([py, 'notify.py', '--dir', data, '--state', state], log)
        run([py, 'bot.py', '--dir', data, '--state', os.path.join(pub, 'state', 'bot.json')], log)       # answer Telegram commands (item 18)
        hb.update(ticks=hb['ticks'] + 1, last_tick=tick.isoformat(timespec='seconds'), last_scan_s=round(time.time() - t0, 1), last_rc=rc, swing_running=swing is not None)
        hb['bad_ticks'] = 0 if rc == 0 else hb.get('bad_ticks', 0) + 1
        heartbeat(pub, **hb, next_tick=next_tick(now_ist() + dt.timedelta(seconds=1), a.every, a.offset).isoformat(timespec='seconds'))
        if not a.no_publish:
            mark = time.time()
            try: publish.publish(pub, last_pub, message=f'scan {tick:%Y-%m-%d %H:%M} IST'); last_pub = mark; hb['publish'] = 'ok'; log('published')
            except Exception as ex: hb['publish'] = f'failed: {str(ex)[:120]}'; log(f'publish failed: {ex}')
            hb['bad_publish'] = hb.get('bad_publish', 0) + 1 if str(hb['publish']).startswith('failed') else 0
        watch_loop(pub, hb)
        if a.once: break
    if swing is not None:
        try: swing.wait(timeout=600)
        except Exception: swing.kill()
        run([py, 'notify.py', '--dir', data, '--state', state], log)
        run([py, 'bot.py', '--dir', data, '--state', os.path.join(pub, 'state', 'bot.json')], log)       # answer Telegram commands (item 18)
    hb.update(state='finished', swing_running=False); heartbeat(pub, **hb, next_tick=None)
    if not a.no_publish:
        try: publish.publish(pub, last_pub, message='final'); log('published final')
        except Exception as ex: log(f'publish failed: {ex}')
    log('Loop finished'); return 0

if __name__ == '__main__':
    sys.exit(main())
