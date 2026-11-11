"""Shared synthetic data for the time-frame backtest tests: the engineered long setup (also used by test_scanner.py), its mirror image,
tiled copies across days, and random-walk frames."""
import numpy as np, pandas as pd
import strategy_scanner as sc

closes = [1115,1117,1118,1119,1119,1120,1112,1103,1094,1085,1088,1093,1097,1100,1090,1079,1069,1062,1067,1072,1076,1080,1071,1060,1049,1040,
          1047,1056,1065,1074,1090,1084,1078,1112,1122,1130,1122,1114,1106,1100,1096,1094]
wick_up = {5: 5, 13: 5, 21: 5}; wick_dn = {9: 5, 17: 5, 25: 5}; vols = {30: 190, 33: 220, 25: 200}
def _daily_rows():
    rows = []; prev = 1114
    for i, c in enumerate(closes):
        o = prev; h = max(o, c) + wick_up.get(i, 2); l = min(o, c) - wick_dn.get(i, 2)
        if i == 25: l = 1028
        rows.append([o, h, l, c, vols.get(i, 100)]); prev = c
    return rows
D = _daily_rows()
h1c = [1122,1120,1123,1116,1112,1115,1108,1104,1107,1100,1096,1099,1094,1090,1093,1088,1094,1096,1093,1092,1101,1103]
def _hourly_rows():
    rows = []; prev = 1124
    for i, c in enumerate(h1c):
        o = prev; h = max(o, c) + 3; l = min(o, c) - 3
        if i == 15: l = 1083
        rows.append([o, h, l, c, 175 if i == 20 else 100 + (i % 4) * 5]); prev = c
    return rows
H = _hourly_rows()
CFG5 = dict(sc.CFG_I, min_turnover_cr=0, min_bars=30, rvol_n=10, max_zone_pct=6, max_zone_atr=5)
flip = lambda rows: [[2300 - a, 2300 - c_, 2300 - b, 2300 - d_, v] for a, b, c_, d_, v in rows]

def engineered(start='2026-10-12 09:15', mirror=False):
    """The engineered setup on 5-minute candles (64 bars, the trigger at the 63rd bar). Its 15m frame (32 bars) sits on the
    earlier trading days, so every 15m bar has finished before the session starts, as it would in real data."""
    rows = flip(D + H) if mirror else D + H; r15 = flip(D[:32]) if mirror else D[:32]
    idx5 = pd.date_range(start, periods=len(rows), freq='5min', tz='Asia/Kolkata'); day15 = (pd.Timestamp(start) - pd.Timedelta(days=4)).normalize() + pd.Timedelta(hours=9, minutes=15)
    f5 = pd.DataFrame(rows, columns=sc.COLS, index=idx5); f15 = pd.DataFrame(r15, columns=sc.COLS, index=pd.date_range(day15, periods=32, freq='15min', tz='Asia/Kolkata'))
    return f5, f15

def with_future(f5, closes_after, wick=0.1):
    """Append 5m bars after the last one; each bar opens at the previous close and closes at the given price."""
    rows, t, prev = [], f5.index[-1], float(f5.Close.iloc[-1]); idx = []
    for c in closes_after:
        t = t + pd.Timedelta(minutes=5); idx.append(t); o = prev
        rows.append([o, max(o, c) + wick, min(o, c) - wick, c, 150]); prev = c
    return pd.concat([f5, pd.DataFrame(rows, columns=sc.COLS, index=pd.DatetimeIndex(idx))])

def tiled(seed, days=6, start='2026-09-01'):
    """The engineered setup repeated on several sessions (every second calendar day) at different price levels with a little noise, each with its
    own 15m bars on the day before, so the real engine triggers in every session."""
    rng = np.random.default_rng(seed); rows, idx, b15, i15 = [], [], [], []
    for d in range(days):
        day = pd.Timestamp(start, tz='Asia/Kolkata') + pd.Timedelta(days=2 * d); s = rng.uniform(0.85, 1.25); base = np.array(D + H, dtype=float)
        for b in range(75):
            if b < len(base): o, h, l, c, v = base[b]; o, h, l, c = [x * s * (1 + rng.normal(0, 0.0002)) for x in (o, h, l, c)]
            else: o = rows[-1][3]; c = o * (1 + rng.normal(0, 0.0004)); h = max(o, c) * 1.0003; l = min(o, c) * 0.9997; v = 100
            rows.append([o, max(h, o, c), min(l, o, c), c, v]); idx.append(day + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=5 * b))
        for k, (o, h, l, c, v) in enumerate(D[:32]):
            b15.append([o * s, h * s, l * s, c * s, v]); i15.append(day - pd.Timedelta(days=1) + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=15 * k))
    return pd.DataFrame(rows, columns=sc.COLS, index=pd.DatetimeIndex(idx)), pd.DataFrame(b15, columns=sc.COLS, index=pd.DatetimeIndex(i15))

def walk5(seed, days=8, start='2026-09-01', p0=24000.0, vol=1000):
    """Random-walk 5m candles for a number of sessions, and the 15m frame built from them."""
    rng = np.random.default_rng(seed); rows, idx, p = [], [], p0
    for d in range(days):
        day = pd.Timestamp(start, tz='Asia/Kolkata') + pd.Timedelta(days=d + (2 * (d // 5)))
        for b in range(75):
            o = p; p = p * (1 + rng.normal(0.00005, 0.0009)); h = max(o, p) * (1 + abs(rng.normal(0, 0.0003))); l = min(o, p) * (1 - abs(rng.normal(0, 0.0003)))
            rows.append([o, h, l, p, vol * (2.5 if rng.random() < 0.07 else 1.0) * rng.uniform(0.7, 1.3)]); idx.append(day + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=5 * b))
    f5 = pd.DataFrame(rows, columns=sc.COLS, index=pd.DatetimeIndex(idx))
    return f5, f5.resample('15min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

def daily_walk(seed, n=700, p0=500.0, start='2020-01-01', vol=1_000_000):
    rng = np.random.default_rng(seed); idx = pd.bdate_range(start, periods=n); c = p0 * np.exp(np.cumsum(rng.normal(0.0004, 0.014, n))); o = np.r_[p0, c[:-1]] * (1 + rng.normal(0, 0.003, n))
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.006, n))); l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.006, n))); v = vol * np.where(rng.random(n) < 0.1, 2.2, 1.0) * rng.uniform(0.7, 1.3, n)
    return pd.DataFrame({'Open': o, 'High': h, 'Low': l, 'Close': c, 'Volume': v}, index=idx)
