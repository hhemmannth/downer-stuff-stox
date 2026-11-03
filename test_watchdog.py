"""Watchdog decisions (pure function, no network). Run: python test_watchdog.py"""
import datetime as dt
import watchdog as W, loop
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
IST = loop.IST
T = lambda h, m: dt.datetime(2026, 11, 4, h, m, tzinfo=IST)
iso = lambda t: t.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
run = lambda status, started, i=1: dict(id=i, status=status, run_started_at=iso(started), created_at=iso(started))
hb = lambda started, last: dict(started=started.isoformat(), last_tick=last.isoformat() if last else None)

check('holiday or weekend: does nothing', W.decide(T(11, 0), [], None, trading=False)[0] == 'skip')
check('before 09:10 and after 15:25: does nothing', W.decide(T(9, 0), [], None)[0] == 'skip' and W.decide(T(15, 30), [], None)[0] == 'skip')
check('no loop running or queued: starts one', W.decide(T(10, 15), [run('completed', T(9, 5))], None)[0] == 'start')
check('a loop is queued: leaves it alone', W.decide(T(14, 52), [run('queued', T(14, 30), 2), run('completed', T(9, 5))], None)[0] == 'ok')
check('loop running and beating: ok', W.decide(T(11, 0), [run('in_progress', T(9, 5))], hb(T(9, 5), T(10, 55)))[0] == 'ok')
a = W.decide(T(11, 0), [run('in_progress', T(9, 5), 7)], hb(T(9, 5), T(10, 30)))
check('loop running but silent for 30 min: restarts that run', a[0] == 'restart' and a[2] == 7, str(a))
check('a just-started loop gets 15 minutes before it must beat', W.decide(T(10, 10), [run('in_progress', T(10, 0))], hb(T(9, 5), T(9, 30)))[0] == 'ok')
b = W.decide(T(10, 30), [run('in_progress', T(10, 0), 9)], hb(T(9, 5), T(9, 50)))
check('a heartbeat left by an older loop does not count for the new run', b[0] == 'restart' and b[2] == 9, str(b))
check('the new run beating clears it', W.decide(T(10, 30), [run('in_progress', T(10, 0))], hb(T(10, 1), T(10, 25)))[0] == 'ok')
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED')
raise SystemExit(1 if fails else 0)
