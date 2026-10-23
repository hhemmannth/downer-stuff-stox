"""Market regime (trending, range-bound, volatile), breadth and sector strength for the Market page.
Everything is computed from the data the scanner already downloads: Nifty and Bank Nifty daily, India VIX,
Nifty 5-minute candles and the daily candles of the Nifty 500."""
import math
import numpy as np
import pandas as pd

def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def true_range(df):
    return pd.concat([df.High - df.Low, (df.High - df.Close.shift()).abs(), (df.Low - df.Close.shift()).abs()], axis=1).max(axis=1)

def adx(df, n=14):
    """Wilder ADX with +DI and -DI."""
    up, dn = df.High.diff(), -df.Low.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index); mdm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = true_range(df).ewm(alpha=1 / n, adjust=False).mean()
    pdi = 100 * pdm.ewm(alpha=1 / n, adjust=False).mean() / a; mdi = 100 * mdm.ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean(), pdi, mdi

def pct_rank(s, v=None):
    s = s.dropna(); v = s.iloc[-1] if v is None else v
    return 100.0 * float((s <= v).mean()) if len(s) else 50.0

def efficiency_ratio(close, n=10):
    path = float(close.diff().abs().iloc[-n:].sum())
    return float(abs(close.iloc[-1] - close.iloc[-n - 1]) / path) if path > 0 and len(close) > n else 0.0

MIN_BARS = 60          # a stock needs this many daily candles to count in breadth
LABELS = {'trending_up': 'Trending up', 'trending_down': 'Trending down', 'range': 'Range-bound', 'volatile': 'Volatile / choppy', 'transition': 'Mixed / transitioning', 'unclear': 'Too early to tell'}

def classify_daily(df, vix_hist=None):
    """Daily regime of an index from ADX, EMA stack, efficiency ratio, ATR and Bollinger-width percentiles and India VIX."""
    c = df.Close; a, pdi, mdi = adx(df); e9, e21, e50 = ema(c, 9), ema(c, 21), ema(c, 50)
    atr = true_range(df).rolling(14).mean(); atr_pct = 100 * atr / c; ma = c.rolling(20).mean(); bbw = 4 * c.rolling(20).std() / ma
    er = efficiency_ratio(c, 10); a_v = float(a.iloc[-1]); price = float(c.iloc[-1])
    up_stack = bool(e9.iloc[-1] > e21.iloc[-1] > e50.iloc[-1] and price > e21.iloc[-1]); dn_stack = bool(e9.iloc[-1] < e21.iloc[-1] < e50.iloc[-1] and price < e21.iloc[-1])
    atr_rank = pct_rank(atr_pct.tail(250)); bbw_rank = pct_rank(bbw.tail(250))
    vix = float(vix_hist.iloc[-1]) if vix_hist is not None and len(vix_hist) else None; vix_rank = pct_rank(vix_hist.tail(250)) if vix_hist is not None and len(vix_hist) > 20 else None
    if a_v >= 22 and er >= 0.30 and (up_stack or dn_stack): regime = 'trending_up' if up_stack else 'trending_down'
    elif atr_rank >= 75 or (vix is not None and vix >= 18): regime = 'volatile'          # not a clean trend, but big swings
    elif a_v < 20 and er < 0.30: regime = 'range'                                    # no trend strength and no direction
    else: regime = 'transition'
    vol = 'high' if (atr_rank >= 75 or (vix is not None and vix >= 20)) else 'low' if (atr_rank <= 25 and (vix is None or vix < 13)) else 'normal'
    hi20, lo20 = float(df.High.tail(20).max()), float(df.Low.tail(20).min())
    return dict(regime=regime, label=LABELS[regime], volatility=vol, adx=round(a_v, 1), plus_di=round(float(pdi.iloc[-1]), 1), minus_di=round(float(mdi.iloc[-1]), 1),
                er10=round(er, 2), atr=round(float(atr.iloc[-1]), 1), atr_pct=round(float(atr_pct.iloc[-1]), 2), atr_rank=round(atr_rank), bbw_rank=round(bbw_rank),
                ema9=round(float(e9.iloc[-1]), 1), ema21=round(float(e21.iloc[-1]), 1), ema50=round(float(e50.iloc[-1]), 1), stack='up' if up_stack else 'down' if dn_stack else 'mixed',
                range20=dict(high=round(hi20, 1), low=round(lo20, 1), pos=round((price - lo20) / (hi20 - lo20), 2) if hi20 > lo20 else 0.5),
                vix=round(vix, 2) if vix is not None else None, vix_rank=round(vix_rank) if vix_rank is not None else None,
                reading=reading_daily(regime, a_v, er, up_stack, dn_stack, atr_rank, vix))

def reading_daily(regime, a_v, er, up, dn, atr_rank, vix):
    parts = [f'ADX {a_v:.0f} ({"strong trend" if a_v >= 25 else "trend building" if a_v >= 20 else "weak trend"})', f'efficiency {er:.2f} ({"directional" if er >= 0.3 else "choppy"})',
             'EMAs stacked up' if up else 'EMAs stacked down' if dn else 'EMAs tangled', f'volatility in the {atr_rank:.0f}th percentile of the year']
    if vix is not None: parts.append(f'India VIX {vix:.1f}')
    return ', '.join(parts) + '.'

def classify_intraday(df5, daily_atr=None, prev_close=None):
    """Today's session from the 5-minute candles: trend day, range day or volatile whipsaw."""
    day = df5[df5.index.normalize() == df5.index[-1].normalize()]
    if len(day) < 12: return dict(regime='unclear', label=LABELS['unclear'], bars=int(len(day)), reading='Fewer than an hour of 5-minute candles so far.')
    o, c = float(day.Open.iloc[0]), float(day.Close.iloc[-1]); hi, lo = float(day.High.max()), float(day.Low.min()); rng = hi - lo
    path = float(day.Close.diff().abs().sum()); er = abs(c - float(day.Close.iloc[0])) / path if path > 0 else 0.0
    ratio = rng / daily_atr if daily_atr else None
    c15 = day.Close.resample('15min').last().dropna(); sg = np.sign(c15 - ema(c15, 9)); crosses = int((sg.diff().abs() > 0).sum()) if len(c15) > 3 else 0
    gap = 100 * (o / prev_close - 1) if prev_close else None
    big = ratio is not None and ratio >= 0.6
    if er >= 0.40 and big and crosses <= 2: regime = 'trending_up' if c > day.Close.iloc[0] else 'trending_down'
    elif ratio is not None and ratio >= 1.0 and er < 0.30: regime = 'volatile'
    elif er < 0.20 and (ratio is None or ratio < 0.7) or crosses >= 4: regime = 'range'
    else: regime = 'transition'
    label = LABELS[regime].replace('Trending', 'Trend day') if regime.startswith('trending') else LABELS[regime].replace('Range-bound', 'Range day')
    txt = f'{rng:.0f} points so far' + (f' ({ratio:.1f}x the daily ATR)' if ratio is not None else '') + f', efficiency {er:.2f}, {crosses} crosses of the 15m 9 EMA'
    if gap is not None: txt += f', opened {gap:+.2f}% vs the previous close'
    return dict(regime=regime, label=label, open=round(o, 1), high=round(hi, 1), low=round(lo, 1), close=round(c, 1), range_pts=round(rng, 1), atr_ratio=round(ratio, 2) if ratio is not None else None,
                er=round(er, 2), crosses=crosses, gap_pct=round(gap, 2) if gap is not None else None, pos_in_range=round((c - lo) / rng, 2) if rng > 0 else 0.5, bars=int(len(day)), reading=txt + '.')

def expected_move(spot, vix):
    """What India VIX implies: one standard deviation for a day and a week."""
    if not vix or not spot: return None
    d = spot * vix / 100 / math.sqrt(252); w = spot * vix / 100 / math.sqrt(52)
    return dict(vix=round(vix, 2), daily_pts=round(d), daily_pct=round(100 * d / spot, 2), weekly_pts=round(w), weekly_pct=round(100 * w / spot, 2))

HEAD = {'trending_up': 'Trending up: trade with the trend and buy pullbacks', 'trending_down': 'Trending down: sell rallies, be picky with longs', 'range': 'Range-bound: fade the edges and take profits early',
        'volatile': 'Volatile: smaller size, wider stops, fewer trades', 'transition': 'Mixed: no clear regime, take only the best setups', 'unclear': 'Too early to classify the session'}
PLAYS = {
 'trending_up': dict(swing=['Longs are in favour: pullbacks into the order block are the best entries.', 'Hold for T2 and T3 and trail by structure instead of selling everything at T1.'],
                     options=['Prefer CALL setups. PUT setups need both the 15m and 5m to flip first.', 'Buy at the zone retest, not after a spike: theta punishes late entries.'],
                     intraday=['Long setups first. Shorts only at A+ with strong volume.', 'Let winners run to T2 while the 15m 9 EMA holds.']),
 'trending_down': dict(swing=['Long-only means fewer setups: take only A and A+ with relative strength and a strong sector.', 'Cut size by a third and book at T1 faster.'],
                       options=['Prefer PUT setups on rallies into supply. CALL setups are counter-trend, skip unless A+.', 'Premium decays fast in slow grinds: exit if there is no progress in 6 to 8 candles.'],
                       intraday=['Short setups first. Long bounces tend to fail at the 15m 9 EMA.', 'Book half at T1 and trail the rest under the 5m lower highs.']),
 'range': dict(swing=['Breakouts fail more often: prefer setups that bounce from the bottom of the range.', 'Book at T1 or the range top; do not wait for T3.'],
               options=['Trade only retests at the edges of the range; skip the middle.', 'Buying options in a range bleeds theta: aim for 1R to 1.5R and be out.'],
               intraday=['Mean reversion: fade the edges, skip trades in the middle third of the range.', 'Reduce size and take T1 quickly.']),
 'volatile': dict(swing=['Wait for daily closes, not intraday spikes.', 'Use a smaller quantity: the stop will be wider in rupees.'],
                  options=['Pick slightly ITM strikes (higher delta) so a whipsaw does not kill the premium.', 'Avoid the first 15 minutes and the last 30. IV can collapse after events.'],
                  intraday=['Skip the first 15 minutes. Expect whipsaws and stop-runs.', 'Half size, take profit at T1, no revenge trades.']),
 'transition': dict(swing=['Be selective: A+ only.', 'Check the sector and Nifty trend before you enter.'], options=['Trade only A+ with the OI wall supporting.', 'Keep size small.'], intraday=['Wait for the 15m bias to be clear.', 'Skip trades inside the opening 15 minutes.']),
 'unclear': dict(swing=['Daily regime still applies.'], options=['Wait until at least 10:15 for a read on the day.'], intraday=['Wait until at least 10:15.'])}

def playbook(daily, intraday, vix=None):
    """Which setups to prefer given the daily regime, today's session and volatility."""
    key = daily['regime']; ikey = intraday.get('regime', 'unclear'); base = PLAYS[key]
    out = dict(headline=HEAD[key], today=HEAD[ikey] if ikey != key else None, swing=list(base['swing']), options=list(base['options']), intraday=list(base['intraday']), risk=[])
    if ikey in ('range', 'volatile') and key.startswith('trending'): out['intraday'] = PLAYS[ikey]['intraday'] + ['Daily trend is up/down, but today is choppy: wait for the 15m to line up.']
    if ikey.startswith('trending'): out['intraday'].append('Today is a trend day: follow the direction instead of fading.')
    if daily['volatility'] == 'high': out['risk'].append('Volatility is high: halve your usual quantity and expect wider swings against you.')
    if daily['volatility'] == 'low': out['risk'].append('Volatility is low: option premiums are cheap but moves are small. Targets will take longer.')
    if vix is not None and vix >= 18: out['risk'].append(f'India VIX is {vix:.1f}: event days can move the index in either direction, so prefer to buy only on confirmation.')
    return out

def breadth(frames, industries, nifty_daily):
    """Breadth of the universe and strength of each industry versus Nifty. frames = {symbol: daily DataFrame}."""
    rows = []
    n20 = float(100 * (nifty_daily.Close.iloc[-1] / nifty_daily.Close.iloc[-21] - 1)) if nifty_daily is not None and len(nifty_daily) > 21 else 0.0
    for s, f in frames.items():
        if len(f) < MIN_BARS: continue
        c = f.Close; last, prev = float(c.iloc[-1]), float(c.iloc[-2]); e21, e50 = float(ema(c, 21).iloc[-1]), float(ema(c, 50).iloc[-1]); e200 = float(ema(c, 200).iloc[-1]) if len(c) >= 200 else None
        rows.append(dict(sym=s, ind=industries.get(s, 'Unknown'), adv=last > prev, dec=last < prev, a21=last > e21, a50=last > e50, a200=(last > e200) if e200 is not None else None,
                         hi20=last >= float(c.iloc[-21:-1].max()), lo20=last <= float(c.iloc[-21:-1].min()), r5=100 * (last / float(c.iloc[-6]) - 1), r20=100 * (last / float(c.iloc[-21]) - 1) if len(c) > 21 else 0.0))
    if not rows: return None, [], {}
    df = pd.DataFrame(rows); pct = lambda col: round(100 * float(df[col].dropna().mean()), 1) if df[col].notna().any() else None
    summary = dict(count=int(len(df)), advancers=int(df.adv.sum()), decliners=int(df.dec.sum()), above21=pct('a21'), above50=pct('a50'), above200=pct('a200'), new_highs=int(df.hi20.sum()), new_lows=int(df.lo20.sum()),
                   avg_5d=round(float(df.r5.mean()), 2), avg_20d=round(float(df.r20.mean()), 2), nifty_20d=round(n20, 2))
    sectors = []; per = {}
    for ind, g in df.groupby('ind'):
        a50 = 100 * float(g.a50.mean()); r5, r20 = float(g.r5.mean()), float(g.r20.mean()); rs = r20 - n20
        state = 'strong' if a50 >= 55 and rs > 0 else 'weak' if a50 < 40 or rs < -2 else 'neutral'
        sectors.append(dict(sector=ind, count=int(len(g)), above50=round(a50), ret5=round(r5, 2), ret20=round(r20, 2), rs20=round(rs, 2), state=state))
        for _, r in g.iterrows(): per[r.sym] = dict(sector=ind, sector_state=state, rs20=round(float(r.r20) - n20, 2))
    sectors.sort(key=lambda x: -x['rs20'])
    return summary, sectors, per
