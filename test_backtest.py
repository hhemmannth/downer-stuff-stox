"""Backtesting lab (items 2a-2e, 14): the replay uses the live engine and the live tracker; statistics, costs, the in/out-of-sample
split, the rule variants and the Monte Carlo are checked on known inputs. No network. Run: python test_backtest.py"""
import datetime as dt, json, numpy as np, pandas as pd
import backtest as bt, playbook_fixture as pf, strategy_scanner as sc
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)

def future(h, closes):
    """Hourly candles appended after the fixture: each closes at the given price."""
    rows, t, last = [], h.index[-1], float(h.Close.iloc[-1])
    for c in closes:
        t = t + pd.Timedelta(hours=1)
        if t.hour > 15 or (t.hour == 15 and t.minute > 15): t = (t + pd.Timedelta(days=1)).normalize().tz_localize(None).tz_localize(h.index.tz) + pd.Timedelta(hours=9, minutes=15)
        while t.weekday() >= 5: t += pd.Timedelta(days=1)
        rows.append((t, last, max(last, c) + 1, min(last, c) - 1, c, 400000)); last = c
    f = pd.DataFrame([r[1:] for r in rows], columns=['Open', 'High', 'Low', 'Close', 'Volume'], index=pd.DatetimeIndex([r[0] for r in rows]))
    return pd.concat([h, f])

d, h, _ = pf.frames(vol=5_000_000)
up = future(h, [1078 + 9 * i for i in range(1, 14)])                         # runs to 1195: through T1, T2 and T3
tr = bt.replay_symbol('PBK', d, up, sector='IT', regimes={'2026-08-11': 'Trending up'})
t = tr[0] if tr else {}
check('replay: the playbook setup opens one trade at the 1H confirmation close', len(tr) == 1 and t.get('entry_t') == '2026-08-12 15:15' and t.get('entry') == 1071.0, str(tr[:1])[:200])
check('replay: the stop is the engine\'s structural stop and the grade and score come from the engine', abs(t.get('sl', 0) - 1036.48) < 0.6 and t.get('grade') == 'A+' and t.get('score') == 10)
check('replay: managed by the live tracker: half at T1, a quarter at T2, the rest at T3 = +1.75R', t.get('outcome') == 'TARGET' and t.get('r') == 1.75 and t.get('hits') == 3, f"{t.get('outcome')} {t.get('r')}")
cost = 0.003 * 1071 / (1071 - t['sl']); check('costs: net result is the gross result minus 0.30% of entry, in R', abs(t['r_net'] - (1.75 - cost)) < 0.011, f"{t['r_net']} vs {1.75 - cost:.3f}")
check('replay: sector, regime on the decision day, weekday and holding time are recorded', t['sector'] == 'IT' and t['regime'] == 'Trending up' and t['weekday'] == 'Wed' and t['hold_days'] >= 1 and t['closed'])
dn = future(h, [1078 - 8 * i for i in range(1, 9)])                          # falls through the stop
t2 = bt.replay_symbol('PBK', d, dn)[0]
check('replay: when price falls through the stop the trade loses 1R (and a little more after costs)', t2['outcome'] == 'SL' and t2['r'] == -1.0 and t2['r_net'] < -1.0, f"{t2['outcome']} {t2['r']} {t2['r_net']}")
half = future(h, [1078 + 9 * i for i in range(1, 5)] + [1100 - 12 * i for i in range(1, 8)])   # T1, then back down through the original stop
t3 = bt.replay_symbol('PBK', d, half)[0]
check('replay: T1 then the original stop = half at +1R and half at -1R = 0R (no early breakeven, your rule)', t3['outcome'] == 'TRAIL' and t3['r'] == 0.0, f"{t3['outcome']} {t3['r']}")
flat = bt.replay_symbol('PBK', d, future(h, [1080, 1079] * 5))
check('replay: a trade still open when the data ends is kept apart from the statistics', len(flat) == 1 and flat[0]['outcome'] == 'OPEN' and not flat[0]['closed'])
thin, hh, _ = pf.frames(vol=1000)
check('replay: illiquid stocks are skipped, as in the live scan', bt.replay_symbol('THIN', thin, future(hh, [1078 + 9 * i for i in range(1, 14)])) == [])
check('replay: no hourly data, no trades', bt.replay_symbol('X', d, None) == [])

# ---- statistics
s = bt.stats([1.75, -1, -1, 0, 1.75, -1, -1, -1, 1.75, 0.5])
check('stats: win rate, expectancy, profit factor', s['n'] == 10 and s['win'] == 40.0 and s['avg'] == 0.075 and s['pf'] == 1.15, str(s))
check('stats: max drawdown is the deepest fall of the running total (from +1.75R to -1.5R = 3.25R) and a 0R trade does not break a losing streak', s['max_dd'] == 3.25 and s['streak'] == 3, str(s))
check('stats: no trades gives an empty summary, not an error', bt.stats([])['n'] == 0 and bt.stats([])['avg'] is None)

rng = np.random.default_rng(3); T = []
for i in range(300):
    day = pd.Timestamp('2025-01-01') + pd.Timedelta(days=2 * i); g = ['A+', 'A', 'B'][i % 3]; r = float(rng.choice([1.75, 0.0, -1.0], p=[0.42, 0.13, 0.45] if g != 'B' else [0.25, 0.15, 0.60]))
    T.append(dict(sym=f'S{i % 40}', sector=['IT', 'Banks', 'Auto'][i % 3], grade=g, score={'A+': 9, 'A': 7, 'B': 5}[g], structure=2, zone_q=i % 3, confirm=1 + i % 3, context=i % 4, entry_t=str(day)[:16], exit_t=str(day + pd.Timedelta(days=5))[:16],
                  entry=100.0, sl=96.0, risk_pct=4.0, outcome='TARGET' if r > 1 else 'SL' if r < 0 else 'TRAIL', r=r, r_net=round(r - 0.075, 2), hold_days=5, hits=0, rvol=[None, 1.2, 1.7, 2.4][i % 4], weekly_up=True, room_r=3.0,
                  held=['weekly trend against'] if i % 25 == 0 else [], regime=['Trending up', 'Range', 'Volatile'][i % 3], weekday=day.strftime('%a'), closed=i % 50 != 49))
R = bt.report(T, window={'from': '2025-01-01', 'to': '2026-08-30'}, universe=40)
check('report: counts split taken / held back / still open', R['counts'] == dict(all=300, closed=294, open=6, held_back=R['counts']['held_back'], taken=R['counts']['taken']) and R['counts']['taken'] + R['counts']['held_back'] == 294 and R['counts']['held_back'] > 0)
check('report: net expectancy is lower than gross by the cost', abs((R['summary']['gross']['avg'] - R['summary']['net']['avg']) - 0.075) < 0.01)
g = {x['k']: x for x in R['by']['grade']}
check('report: breakdown by grade keeps your order A+, A, B and shows B is the weak grade here', [x['k'] for x in R['by']['grade']] == ['A+', 'A', 'B'] and g['B']['avg'] < g['A+']['avg'])
check('report: breakdowns by score, confirmation, zone, context, regime, sector, weekday, month, volume and stop width', all(R['by'][k] for k in ('score', 'confirm', 'zone', 'context', 'regime', 'sector', 'weekday', 'month', 'volume', 'stop')))
check('report: equity curve ends at the net total', R['equity'] and abs(R['equity'][-1][1] - R['summary']['net']['total']) < 0.05, f"{R['equity'][-1]} vs {R['summary']['net']['total']}")
check('report: first 60% / last 40% split for honest testing', R['split'] and R['split']['train']['n'] + R['split']['test']['n'] == R['counts']['taken'] and abs(R['split']['train']['n'] / R['counts']['taken'] - 0.6) < 0.03)
check('report: trades per year and average holding time', 150 < R['summary']['trades_per_year'] < 200 and R['summary']['avg_hold_days'] == 5.0, str(R['summary']['trades_per_year']))
json.dumps(R); check('report: the file is plain JSON', True)

mc = R['montecarlo']; a, b = mc['risks']['0.5'], mc['risks']['1.0']
check('monte carlo: three risk levels, 2000 simulated years each', set(mc['risks']) == {'0.5', '0.75', '1.0'} and mc['sims'] == 2000)
check('monte carlo: doubling the risk per trade deepens the bad-year drawdown', b['dd_p95'] > a['dd_p95'] and b['dd_p50'] > a['dd_p50'], f"{a['dd_p95']} -> {b['dd_p95']}")
check('monte carlo: percentiles are ordered and the losing-streak estimate is sensible', a['ret_p5'] <= a['ret_p50'] <= a['ret_p95'] and 2 <= mc['streak_p50'] <= mc['streak_p95'] <= 40)
check('monte carlo: same inputs, same answer (seeded)', bt.monte_carlo([t['r_net'] for t in T], 150) == bt.monte_carlo([t['r_net'] for t in T], 150))
check('monte carlo: refuses to simulate from fewer than 20 trades', bt.monte_carlo([1, -1, 1], 50)['sims'] == 0)

good = [dict(t, r_net=t['r_net'] + 0.3) for t in T]; bad = [dict(t, r_net=t['r_net'] + (0.5 if t['entry_t'] < R['split']['cut'] else -0.4)) for t in T]
RV = bt.report(T, [('Better rule', 'd', good), ('Curve-fit rule', 'd', bad)], window={}, universe=40); v = {x['name']: x for x in RV['variants']}
check('variants: a rule that is better in BOTH halves is flagged', v['Better rule']['better'] and 'worth considering' in v['Better rule']['verdict'])
check('variants: a rule that only looks better on the first half is rejected (protection against curve-fitting)', not v['Curve-fit rule']['better'] and v['Curve-fit rule']['train']['avg'] > RV['split']['train']['avg'])

e = bt.regime_edge(R, 'Range'); check('regime edge: reports the backtest result for the current regime', e and e['n'] >= 30 and e['verdict'] in ('weak', 'ok', 'strong'))
check('regime edge: silent without enough evidence or without a backtest', bt.regime_edge(R, 'Never seen') is None and bt.regime_edge(None, 'Range') is None and bt.regime_edge(R, 'Range', min_n=10 ** 6) is None)
neg = bt.report([dict(t, r=-1.0, r_net=-1.1) for t in T], window={}, universe=1); check('regime edge: a losing regime is "weak"', bt.regime_edge(neg, 'Range')['verdict'] == 'weak')

rows = bt.run_all({'PBK': d, 'P2': d}, {'PBK': up, 'P2': dn}, {'PBK': 'IT'}, {}, workers=1, progress=False)
check('run_all: several stocks, results ordered by exit time', len(rows) == 2 and rows[0]['exit_t'] <= rows[1]['exit_t'])
import swing; before = dict(swing.CFG); bt._work(('PBK', d, up, 'IT', {}, dict(rvol_min=9.9), None))
check('variants: a rule override is restored after the run (the live settings are never left changed)', swing.CFG == before)
strict = bt._work(('PBK', d, up, 'IT', {}, dict(rvol_min=9.9), None))
check('variants: a stricter volume rule changes what the engine confirms (lower score or no trade)', strict == [] or strict[0]['score'] < 10, str([(x['score'], x['entry_t']) for x in strict]))

# ---- your account rules (item: the backtest now trades the way your journal rules say)
def Tr(entry, exit_, score, r, sym='X', held=False): return dict(sym=sym, entry_t=entry, exit_t=exit_, score=score, r_net=r, closed=True, held=held, grade='A+' if score >= 8 else 'A' if score >= 6 else 'B')
A0 = dict(risk=0.5, risk_aplus=0.75, aplus_score=8, open_cap=2.0, day_stop=0.75, week_stop=2.0, month_half=3.0, month_stop=5.0, max_per_day=2)
one = bt.simulate_account([Tr('2026-01-05 14:15', '2026-01-09 11:15', 10, 2.0), Tr('2026-01-12 14:15', '2026-01-14 11:15', 10, -1.0)], 8, True, A0)
check('account: two trades at 0.75% risk compound exactly: +2R makes 100 -> 101.5, then -1R costs 0.75% of 101.5 = 0.76125 -> 100.74', one['n'] == 2 and one['ret'] == 0.7 and one['curve'][0][1] == 101.5 and one['curve'][1][1] == 100.74, str(one['curve']))
check('account: a B-grade setup is never taken when you only trade A+ (score 8 or more)', bt.simulate_account([Tr('2026-01-05 14:15', '2026-01-09 11:15', 5, 3.0)], 8, True, A0)['n'] == 0 and bt.simulate_account([Tr('2026-01-05 14:15', '2026-01-09 11:15', 5, 3.0)], 8, True, A0)['skipped']['score'] == 1)
day = [Tr('2026-01-05 10:15', '2026-01-20 11:15', 10, 1.0, 'A'), Tr('2026-01-05 11:15', '2026-01-20 11:15', 10, 1.0, 'B'), Tr('2026-01-05 14:15', '2026-01-20 11:15', 10, 1.0, 'C')]
d = bt.simulate_account(day, 8, True, A0)
check('account: max 2 trades a day: the first two to trigger are taken, the third is skipped (no peeking at later signals)', d['n'] == 2 and d['skipped']['day_cap'] == 1)
check('account: with no limits all three are taken', bt.simulate_account(day, 8, False, A0)['n'] == 3)
cap = [Tr(f'2026-01-0{i} 14:15', '2026-01-30 11:15', 10, 1.0, f'S{i}') for i in (5, 6, 7)]
c = bt.simulate_account(cap, 8, True, A0)
check('account: open-risk ceiling 2%: two 0.75% trades are open, a third would make 2.25%, so it is skipped until one closes', c['n'] == 2 and c['skipped']['open_cap'] == 1)
cap2 = [Tr('2026-01-05 14:15', '2026-01-08 11:15', 10, 1.0, 'S1'), Tr('2026-01-06 14:15', '2026-01-30 11:15', 10, 1.0, 'S2'), Tr('2026-01-12 14:15', '2026-01-30 11:15', 10, 1.0, 'S3')]
check('account: once an earlier trade has closed, room opens up and the later one is taken', bt.simulate_account(cap2, 8, True, A0)['n'] == 3)
loss = [Tr('2026-01-05 10:15', '2026-01-05 11:15', 10, -1.0, 'L'), Tr('2026-01-05 14:15', '2026-01-09 11:15', 10, 2.0, 'W')]
ll = bt.simulate_account(loss, 8, True, A0)
check('account: day stop: after a full loss (0.75% of the account) that has closed, no more entries that day', ll['n'] == 1 and ll['skipped']['loss_limit'] == 1)
nxt = [Tr('2026-01-05 10:15', '2026-01-05 11:15', 10, -1.0, 'L'), Tr('2026-01-06 14:15', '2026-01-09 11:15', 10, 2.0, 'W')]
check('account: the day stop lasts only for that day', bt.simulate_account(nxt, 8, True, A0)['n'] == 2)
mon = [Tr(f'2026-02-{d:02d} 10:15', f'2026-02-{d:02d} 14:15', 10, -1.0, f'M{d}') for d in (2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 16)]
mm = bt.simulate_account(mon, 8, True, dict(A0, week_stop=99, risk_aplus=0.7))
exp = 100 * (1 - 0.007) ** 5 * (1 - 0.0035) ** 5
check('account: after the month is down 3% the risk per trade halves (0.7% -> 0.35%): five full-size losses, then half-size ones', mm['n'] == 10 and abs((100 + mm['ret']) - exp) < 0.06, f"n={mm['n']} equity={100 + mm['ret']:.2f} expected {exp:.2f}")
check('account: once the month is down 5%, no new entries until next month', mm['skipped']['loss_limit'] == 1, str(mm['skipped']))
check('account: held-back trades (weekly trend against, no room) are never candidates', bt.simulate_account([Tr('2026-01-05 14:15', '2026-01-09 11:15', 10, 2.0, held=True)], 4, True, A0)['n'] == 0)
dd = bt.simulate_account([Tr('2026-01-05 10:15', '2026-01-06 11:15', 10, 2.0, 'a'), Tr('2026-01-12 10:15', '2026-01-13 11:15', 10, -1.0, 'b'), Tr('2026-01-19 10:15', '2026-01-20 11:15', 10, -1.0, 'c'), Tr('2026-01-26 10:15', '2026-01-27 11:15', 10, 1.0, 'd')], 8, True, A0)
check('account: max drawdown is the deepest fall from the running peak, in percent of the account (101.5 -> 100.0 here = 1.5%)', dd['n'] == 4 and 1.4 <= dd['max_dd'] <= 1.6 and dd['streak'] == 2, str((dd['max_dd'], dd['streak'])))
check('account: no candidates gives an empty result, not an error', bt.simulate_account([], 8)['n'] == 0)
rows, cv = bt.scenarios([Tr(f'2026-0{1 + i % 5}-{5 + i % 20:02d} 14:15', f'2026-0{1 + i % 5}-{8 + i % 20:02d} 14:15', [10, 8, 6, 4][i % 4], [1.75, -1.0][i % 2], f'S{i}') for i in range(40)], A0)
check('scenarios: four views side by side, "every signal" takes the most trades and a stricter score takes fewer', [r['key'] for r in rows] == ['all', 'a', 'ap', 'p10'] and rows[0]['n'] >= rows[1]['n'] >= rows[2]['n'] >= rows[3]['n'] and rows[3]['n'] > 0)
check('scenarios: one equity curve per scenario on one shared monthly axis', set(cv['series']) == {'all', 'a', 'ap', 'p10'} and all(len(v) == len(cv['labels']) for v in cv['series'].values()))
Rr = bt.report(T, window={}, universe=40, acct=A0)
check('report: carries the scenarios, the curves and the account rules used', len(Rr['scenarios']) == 4 and Rr['account']['max_per_day'] == 2 and 'labels' in Rr['scenario_curves'])
env = bt.account_from_env(dict(RISK_PCT='0.4', OPEN_RISK_CAP='3', MAX_TRADES_PER_DAY='1', DAY_STOP_PCT='x'))
check('account rules can be set with repo variables; bad values fall back to your defaults', env['risk'] == 0.4 and env['open_cap'] == 3.0 and env['max_per_day'] == 1 and env['day_stop'] == 0.75)
import tempfile, os as _os
qd = tempfile.mkdtemp(); json.dump(dict(window={'from': 'a', 'to': 'b'}, universe=40, params={'top': 250}, trades=T), open(_os.path.join(qd, 'backtest_trades.json'), 'w'), default=str)
json.dump(dict(variants=[dict(name='keep me')], variant_base=dict(all={})), open(_os.path.join(qd, 'backtest.json'), 'w'))
q = bt.resim(qd, dict(A0, max_per_day=1)); q2 = json.load(open(_os.path.join(qd, 'backtest.json')))
check('quick mode: re-applies new account rules to the saved trades and keeps the last run\'s rule variants', q['account']['max_per_day'] == 1 and q2['variants'][0]['name'] == 'keep me' and q2['params'].get('quick') and len(q2['scenarios']) == 4)
no = tempfile.mkdtemp()
try: bt.resim(no); msg = ''
except SystemExit as e: msg = str(e)
check('quick mode: before any full run it says what to do instead of failing', 'full backtest first' in msg)
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED'); raise SystemExit(1 if fails else 0)
