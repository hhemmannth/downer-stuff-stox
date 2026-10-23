"""Robustness check: run the engine on many random markets and assert that every reported setup is self-consistent.
Run: python test_invariants.py"""
import sys
import numpy as np, pandas as pd
import strategy_scanner as sc
fails = []; counts = {}
def bump(k): counts[k] = counts.get(k, 0) + 1
def market(n, seed, freq, start, vol, tz=None, hours=None):
    r = np.random.default_rng(seed); drift = r.choice([-1, 0, 1]) * vol * 0.15
    c = 1000 * np.exp(np.cumsum(drift + r.normal(0, vol, n) + vol * 0.8 * np.sin(np.arange(n) / r.uniform(3, 9))))
    o = np.r_[c[0], c[:-1]]; h = np.maximum(o, c) * (1 + np.abs(r.normal(0, vol / 2, n))); l = np.minimum(o, c) * (1 - np.abs(r.normal(0, vol / 2, n)))
    idx = pd.date_range(start, periods=n, freq=freq, tz=tz)
    return pd.DataFrame({'Open': o, 'High': h, 'Low': l, 'Close': c, 'Volume': r.integers(5e5, 3e6, n).astype(float)}, index=idx)
ALLOWED = ('TRIGGERED', 'WATCH (in zone)', 'APPROACHING (set alert)', 'WATCH (trigger, low volume)')
def check_setup(r, side, tag):
    bad = []
    if not r['zone_bot'] < r['zone_top']: bad.append('zone order')
    if r['status'] not in ALLOWED: bad.append('status ' + r['status'])
    if r['grade'] != sc.grade(r['score']) or not 0 <= r['score'] <= 10: bad.append('score/grade')
    if side == 'long':
        if not (r['sl'] < r['zone_bot'] and r['sl'] < r['entry'] < r['t2'] < r['t3']): bad.append('long levels')
        if not r['t1'] > r['zone_bot']: bad.append('long T1')
    else:
        if not (r['sl'] > r['zone_top'] and r['sl'] > r['entry'] > r['t2'] > r['t3']): bad.append('short levels')
        if not r['t1'] < r['zone_top']: bad.append('short T1')
    if abs(abs(r['t2'] - r['entry']) - 2 * abs(r['entry'] - r['sl'])) > 1e-6 * max(1, abs(r['entry'])): bad.append('2R')
    if bad: fails.append(f"{tag}: {bad} {({k: r.get(k) for k in ('status', 'entry', 'sl', 't1', 't2', 't3', 'zone_bot', 'zone_top')})}")
cfg_s = dict(sc.CFG, min_turnover_cr=0, min_price=0)
for seed in range(60):                                    # swing: daily + hourly
    d = market(220, seed, 'B', '2026-01-01', 0.018); h = market(320, 1000 + seed, 'h', '2026-08-01', 0.006, 'Asia/Kolkata')
    h = h * (d.Close.iloc[-1] / h.Close.iloc[-1]); h['Volume'] = market(320, 2000 + seed, 'h', '2026-08-01', 0.006).Volume.values
    try: r = sc.scan_symbol(d, h, 'long', cfg_s, ['weekly trend'])
    except Exception as ex: fails.append(f'swing {seed}: crash {ex!r}'); continue
    if r is None: bump('swing none')
    elif 'zone_bot' not in r: bump('swing ' + str(r['state']))
    else: bump('swing ' + r['status'].split(' (')[0]); check_setup(r, 'long', f'swing {seed}')
for seed in range(60):                                    # options and intraday: 5m + 15m
    f5 = market(400, 3000 + seed, '5min', '2026-10-12 09:15', 0.0015, 'Asia/Kolkata')
    f15 = f5.resample('15min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
    for section in ('options', 'intraday'):
        for side in ('long', 'short'):
            try: r = sc.scan_intraday(f5, f15, side, sc.CFG_I, sc.prev_day_levels(f5), section=section)
            except Exception as ex: fails.append(f'{section} {side} {seed}: crash {ex!r}'); continue
            if r is None: bump(f'{section} none')
            elif 'zone_bot' not in r: bump(f'{section} {r["state"]}')
            else:
                bump(f'{section} ' + r['status'].split(' (')[0]); check_setup(r, side, f'{section} {side} {seed}')
                if section == 'options' and 'volume' in (r['status'] + r['notes']).lower(): fails.append(f'options mentions volume: {r["status"]}')
print('outcomes on random markets:'); [print(f'   {k:32s} {v}') for k, v in sorted(counts.items())]
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED:\n' + '\n'.join(fails[:15])); sys.exit(1 if fails else 0)
