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
# ---- 17 Nov 2026: each loop watches the other one, and a refused restart is reported instead of failing silently
import os, json, tempfile
calls, pushes = [], []
W.push = lambda title, body: pushes.append(title); W.time.sleep = lambda s: None
def fake_gh(runs):
    def g(m, p, tok, body=None):
        calls.append((m, p))
        if m == 'GET': return {'workflow_runs': runs}
        return {}
    return g
os.environ.update(GITHUB_REPOSITORY='a/b', GITHUB_TOKEN='x')
d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, 'health'))
put = lambda name, h: json.dump(h, open(os.path.join(d, 'health', name), 'w'))
put('loop.json', dict(hb(T(9, 5), T(12, 15)), state='running'))
W._GUARD.clear(); W.gh = fake_gh([run('completed', T(9, 5))]); calls.clear(); pushes.clear()
r = W.guard('market', T(12, 40), d, log=lambda s: None)
check('gold loop -> market loop silent since 12:15 and no run going: starts it and says so on the phone', r == 'start' and any(m == 'POST' and p.endswith('/workflows/market-loop.yml/dispatches') for m, p in calls) and pushes and 'gold loop' in pushes[-1], f'{r} {calls} {pushes}')
calls.clear(); r2 = W.guard('market', T(12, 45), d, log=lambda s: None)
check('...and does not call GitHub again within 10 minutes', r2 == 'wait' and not calls, r2)
put('loop.json', dict(hb(T(9, 5), T(12, 40)), state='running')); W._GUARD.clear(); calls.clear()
check('market loop beating: the guard does not even call the GitHub API', W.guard('market', T(12, 44), d, log=lambda s: None) == 'ok' and not calls)
check('outside market hours or on a holiday the market guard does nothing', W.guard('market', T(16, 0), d, log=lambda s: None) == 'skip')
put('gold_loop.json', dict(hb(T(4, 0), T(9, 30)), state='running')); W._GUARD.clear(); calls.clear(); W.gh = fake_gh([run('in_progress', T(4, 0), 5)])
r3 = W.guard('gold', T(10, 30), d, log=lambda s: None)
check('market loop -> gold loop frozen for an hour: cancels that run and starts a new one', r3 == 'restart' and ('POST', '/repos/a/b/actions/runs/5/cancel') in calls, f'{r3} {calls}')
def refuse(m, p, tok, body=None):
    if m == 'POST': raise RuntimeError('HTTP Error 422: Workflow does not have workflow_dispatch trigger or is disabled')
    return {'workflow_runs': []}
W.gh = refuse; pushes.clear()
ok = W.dispatch('a/b', 'x', 'main', 'market-loop.yml', 'market loop', 'no run was going', T(11, 0))
check('GitHub refuses to start the loop (workflow disabled): the phone is told, with how to fix it', ok is False and pushes and 'Could not start' in pushes[-1], str(pushes))
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED')
raise SystemExit(1 if fails else 0)
