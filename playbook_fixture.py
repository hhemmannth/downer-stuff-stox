"""Your swing playbook's illustrative example as real-looking 1D, 1H and 15m frames (for the tests)."""
import json, os
import numpy as np, pandas as pd
COLS = ['Open', 'High', 'Low', 'Close', 'Volume']
P = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playbook_example.json')))
TZ = 'Asia/Kolkata'

def _session_after(start, n, step):
    out = []; t = start
    while len(out) < n:
        t = t + pd.Timedelta(minutes=step)
        if t.weekday() < 5 and (9 * 60 + 15) <= t.hour * 60 + t.minute <= (15 * 60 + 15): out.append(t)
    return pd.DatetimeIndex(out)

def frames(n_daily=38, n_1h=23, n_15m=24, vol=100000, start='2026-04-01'):
    """1D: a 60-day uptrend, then the playbook's sell-off, sweep, CHoCH, BOS and pullback. 1H: the pullback, rejection and trigger.
    15m: CHoCH 1,061, BOS 1,065, FVG 1,065-1,069, retest and the 1,070 entry."""
    r = np.random.default_rng(7); pre = []; px = 900.0
    for i in range(60):
        o = px; c = px * (1 + 0.0032 + r.normal(0, 0.004)); pre.append([o, max(o, c) * 1.003, min(o, c) * 0.997, c, 100]); px = c
    k = 1090 / pre[-1][3]; pre = [[x * k for x in row[:4]] + [row[4]] for row in pre]
    D = pre + P['1D'][:n_daily]; didx = pd.bdate_range(start, periods=len(D))
    daily = pd.DataFrame([row[:4] + [row[4] * vol / 100] for row in D], columns=COLS, index=didx)
    idx, day = [], didx[-5]
    while len(idx) < n_1h:
        if day.weekday() < 5:
            for t in ('09:15', '10:15', '11:15', '12:15', '13:15', '14:15', '15:15'):
                if len(idx) < n_1h: idx.append(pd.Timestamp(f'{day.date()} {t}', tz=TZ))
        day += pd.Timedelta(days=1)
    h1 = pd.DataFrame([row[:4] + [row[4] * vol / 100] for row in P['1H'][:n_1h]], columns=COLS, index=pd.DatetimeIndex(idx))
    m15 = pd.DataFrame([row[:4] + [row[4] * vol / 400] for row in P['15m'][:n_15m]], columns=COLS, index=_session_after(h1.index[13], n_15m, 15))
    return daily, h1, m15
