"""Data-quality checks (item 8): never build a setup on bad candles.

flags(daily, latest) looks at one stock's daily candles and returns a list of problems, each dict(kind, text, date):
  split   a one-day price jump or drop of 35% or more: almost always a split or bonus that the data has not been adjusted for.
          Structure before that date is not comparable with structure after it.
  spike   a wick more than 25% beyond the candle's body: a bad tick in the data.
  halted  no candle on the market's latest session, or no volume on recent sessions: suspended or not trading.
skip_reason(flags) says whether the stock should be left out of the scan altogether (a split in the last 40 sessions, or halted)."""
import collections
import numpy as np, pandas as pd

def flags(daily, latest=None, lookback=150):
    out = []
    if daily is None or len(daily) < 5: return out
    d = daily.dropna(subset=['Open', 'High', 'Low', 'Close']).tail(lookback); c = d.Close.values; n = len(d)
    for i in range(1, n):
        if c[i - 1] > 0:
            ch = c[i] / c[i - 1] - 1
            if abs(ch) >= 0.35:
                out.append(dict(kind='split', date=str(d.index[i])[:10], age=n - 1 - i, text=f"price changed {ch * 100:+.0f}% on {str(d.index[i])[:10]}: probably a split or bonus that the data is not adjusted for, so levels before that date are not comparable"))
    t = d.tail(60)
    for ts, r in zip(t.index, t.itertuples()):
        body_hi, body_lo = max(r.Open, r.Close), min(r.Open, r.Close)
        if body_hi > 0 and (r.High > body_hi * 1.25 or r.Low < body_lo * 0.75):
            out.append(dict(kind='spike', date=str(ts)[:10], age=int((t.index[-1] - ts).days), text=f"a wick of more than 25% on {str(ts)[:10]}: likely a bad tick in the data, check the chart")); break
    gap = int(np.busday_count(pd.Timestamp(d.index[-1]).date(), pd.Timestamp(latest).date())) if latest is not None else 0
    if gap >= 3:                                   # 3 or more sessions behind the rest of the market (a late candle on one day is not a halt)
        out.append(dict(kind='halted', date=str(d.index[-1])[:10], age=0, text=f"no candle since {str(d.index[-1])[:10]} ({gap} sessions behind the market): the stock may be suspended or not trading"))
    elif 'Volume' in d and n >= 5 and float(d.Volume.tail(3).sum()) == 0:
        out.append(dict(kind='halted', date=str(d.index[-1])[:10], age=0, text='no volume in the last 3 sessions: the stock may be suspended'))
    return out

def skip_reason(fl):
    for f in fl:
        if f['kind'] == 'split' and f['age'] <= 40: return f"Data check: {f['text']}. Skipped until 40 sessions have passed."
        if f['kind'] == 'halted': return f"Data check: {f['text']}."
    return None

def market_latest(frames):
    """The session most stocks have as their last candle. Using the most common date (not the newest) means one stock with an early
    candle, or a batch that is a few minutes late, cannot make the rest look halted."""
    c = collections.Counter(pd.Timestamp(f.index[-1]).normalize() for f in frames if f is not None and len(f))
    return c.most_common(1)[0][0] if c else None
