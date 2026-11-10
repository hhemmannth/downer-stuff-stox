"""Data-quality checks (item 8), relative strength rank (10), portfolio heat (11). No network. Run: python test_quality.py"""
import numpy as np, pandas as pd
import dataquality as dq, strategy_scanner as sc
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
def frame(closes, end='2026-11-09', vol=100000):
    idx = pd.bdate_range(end=end, periods=len(closes)); c = np.asarray(closes, dtype=float)
    return pd.DataFrame({'Open': c * 0.995, 'High': c * 1.01, 'Low': c * 0.985, 'Close': c, 'Volume': vol}, index=idx)
base = list(100 + np.cumsum(np.random.default_rng(1).normal(0, 0.8, 200)))
check('clean data raises no flags', dq.flags(frame(base), pd.Timestamp('2026-11-09')) == [])
sp = base[:170] + [x / 2 for x in base[170:]]; f = dq.flags(frame(sp), pd.Timestamp('2026-11-09'))
check('a 50% one-day drop is flagged as a probable split, with its date', len(f) == 1 and f[0]['kind'] == 'split' and '-5' in f[0]['text'] and f[0]['age'] == 29, str(f)[:160])
check('a split inside the last 40 sessions keeps the stock out of the scan', 'Skipped until 40 sessions' in (dq.skip_reason(f) or ''))
old = base[:100] + [x / 2 for x in base[100:]]; fo = dq.flags(frame(old), pd.Timestamp('2026-11-09'))
check('an older split is flagged on the setup but does not skip the stock', fo and fo[0]['kind'] == 'split' and dq.skip_reason(fo) is None)
check('a split older than the 150-candle window is ignored', dq.flags(frame([50.0] * 20 + base), pd.Timestamp('2026-11-09')) == [])
sk = frame(base); sk.iloc[-10, sk.columns.get_loc('High')] = sk.Close.iloc[-10] * 1.6
check('a wick 60% above the body is flagged as a bad tick', [x['kind'] for x in dq.flags(sk, pd.Timestamp('2026-11-09'))] == ['spike'])
late1 = dq.flags(frame(base, end='2026-11-06'), pd.Timestamp('2026-11-09')); late3 = dq.flags(frame(base, end='2026-11-04'), pd.Timestamp('2026-11-09'))
check('one session behind is NOT a halt (a late candle); three sessions behind is', late1 == [] and late3 and late3[0]['kind'] == 'halted' and dq.skip_reason(late3))
check('no volume for three sessions is a halt', dq.flags(frame(base).assign(Volume=[100000] * 197 + [0, 0, 0]), pd.Timestamp('2026-11-09'))[0]['kind'] == 'halted')
fr = [frame(base)] * 8 + [frame(base, end='2026-11-10')] + [frame(base, end='2026-11-02')]
check('the market date is the one most stocks share, so one early or stale stock does not shift it', dq.market_latest(fr) == pd.Timestamp('2026-11-09'))
check('too little data: no flags, no error', dq.flags(frame(base[:3])) == [] and dq.flags(None) == [])

# portfolio heat
rng = np.random.default_rng(5); m = rng.normal(0, 1, 120)
mk = lambda beta, seed: frame(list(100 * np.exp(np.cumsum(0.01 * (beta * m + np.random.default_rng(seed).normal(0, 0.25, 120))))))
daily = {'A': mk(1, 1), 'B': mk(1, 2), 'C': mk(1, 3), 'D': frame(list(100 * np.exp(np.cumsum(np.random.default_rng(9).normal(0, 0.01, 120)))))}
items = [dict(symbol=s, stage=3) for s in 'ABCD'] + [dict(symbol='E', stage=2)]
h = sc.portfolio_heat(items, [], daily, {'A': 'Banks', 'B': 'Banks', 'C': 'Banks', 'D': 'IT'})
check('heat: three candidates in one sector form a cluster', h['clusters'] == [dict(sector='Banks', n=3, symbols=['A', 'B', 'C'])])
check('heat: stocks that move together are listed as correlated pairs; the independent one is not', {(p['a'], p['b']) for p in h['pairs']} == {('A', 'B'), ('A', 'C'), ('B', 'C')} and all(p['corr'] >= 0.75 for p in h['pairs']), str(h['pairs']))
check('heat: stage-2 setups are not counted, open tracked trades are', sc.portfolio_heat(items, ['E'], daily, {})['names'] == 5 and h['names'] == 4)
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED'); raise SystemExit(1 if fails else 0)
