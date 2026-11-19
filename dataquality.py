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

def sanitize(df):
    """Candle hygiene applied to EVERY downloaded frame before any rule sees it (audit 18 Nov 2026). Returns (clean frame, counts).
    Yahoo frames were used as they came: a repeated timestamp (Yahoo sometimes sends the live row twice), rows out of time order, or a candle
    whose high is below its low could reach the swing detector. Here:
      duplicate timestamps   -> the last one is kept (the newest print of that candle)
      out of order           -> sorted by time
      non-positive / missing price, or high below low -> the row is dropped (it cannot be a real candle)
      open or close outside the high-low range        -> high/low widened to include them (a rounding mismatch in the feed; the row is kept)
      negative volume        -> 0 (the engine already reads 0 as 'no volume data')
    Zero volume is left alone: an index (^NSEI) or a quiet candle can legitimately have none."""
    counts = dict(dupes=0, unsorted=0, dropped=0, repaired=0, neg_volume=0)
    if df is None or not len(df): return df, counts
    cols = [c for c in ('Open', 'High', 'Low', 'Close') if c in df.columns]
    if len(cols) < 4: return df, counts
    f = df
    dup = f.index.duplicated(keep='last')
    if dup.any(): counts['dupes'] = int(dup.sum()); f = f[~dup]
    if not f.index.is_monotonic_increasing: counts['unsorted'] = 1; f = f.sort_index()
    p = f[cols].apply(pd.to_numeric, errors='coerce')
    hlc = p[['High', 'Low', 'Close']]
    bad = hlc.isna().any(axis=1) | (hlc <= 0).any(axis=1) | (p.High < p.Low)
    if bad.any(): counts['dropped'] = int(bad.sum()); f = f[~bad]; p = p[~bad]
    no_open = p.Open.isna() | (p.Open <= 0)                  # some index feeds (India VIX) print no open: use the close, a doji, never a 'down candle'
    if no_open.any():
        counts['repaired'] += int(no_open.sum()); f = f.copy(); f.loc[no_open, 'Open'] = p.Close[no_open]; p = p.copy(); p.loc[no_open, 'Open'] = p.Close[no_open]
    hi = p[['Open', 'High', 'Close']].max(axis=1); lo = p[['Open', 'Low', 'Close']].min(axis=1)
    fix = (hi > p.High) | (lo < p.Low)
    if fix.any():
        counts['repaired'] += int(fix.sum()); f = f.copy(); f.loc[fix, 'High'] = hi[fix]; f.loc[fix, 'Low'] = lo[fix]
    if 'Volume' in f.columns:
        v = pd.to_numeric(f.Volume, errors='coerce'); neg = v < 0
        if neg.any(): counts['neg_volume'] = int(neg.sum()); f = f.copy(); f.loc[neg, 'Volume'] = 0
    return f, counts

def ohlc_problems(df):
    """Independent invariant check (used by the tests and the System health validation): the problems still present in a frame."""
    out = []
    if df is None or not len(df): return out
    if df.index.duplicated().any(): out.append('duplicate timestamps')
    if not df.index.is_monotonic_increasing: out.append('timestamps out of order')
    o, h, l, c = (df[k].astype(float) for k in ('Open', 'High', 'Low', 'Close'))
    if (h < l).any(): out.append('high below low')
    if (h < o).any() or (h < c).any(): out.append('high below open/close')
    if (l > o).any() or (l > c).any(): out.append('low above open/close')
    if 'Volume' in df.columns and (df.Volume.astype(float) < 0).any(): out.append('negative volume')
    return out

def market_latest(frames):
    """The session most stocks have as their last candle. Using the most common date (not the newest) means one stock with an early
    candle, or a batch that is a few minutes late, cannot make the rest look halted."""
    c = collections.Counter(pd.Timestamp(f.index[-1]).normalize() for f in frames if f is not None and len(f))
    return c.most_common(1)[0][0] if c else None
