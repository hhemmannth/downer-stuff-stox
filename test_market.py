"""Regime, breadth and playbook tests on synthetic data. Run: python test_market.py"""
import sys
import numpy as np, pandas as pd
import market as m
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
def ohlc(close, noise=0.004, seed=0):
    o = np.r_[close[0], close[:-1]]; h = np.maximum(o, close) * (1 + noise); l = np.minimum(o, close) * (1 - noise)      # fixed wicks keep ATR deterministic
    return pd.DataFrame({'Open': o, 'High': h, 'Low': l, 'Close': close, 'Volume': 1e6}, index=pd.bdate_range('2025-10-01', periods=len(close)))
r = np.random.default_rng(1); n = 300
up = ohlc(22000 * np.exp(np.cumsum(0.0045 + r.normal(0, 0.003, n))))
ar = np.zeros(n); rr = np.random.default_rng(0)
for i in range(1, n): ar[i] = 0.82 * ar[i - 1] + rr.normal(0, 0.0045)                   # mean-reverting noise around a flat level
rng_ = ohlc(22000 * np.exp(ar), noise=0.002)
vol = ohlc(22000 * np.exp(np.cumsum(np.where(np.arange(n) % 2 == 0, 1, -1) * 0.012)), noise=0.01)           # big swings, no net direction
dn = ohlc(22000 * np.exp(np.cumsum(-0.0045 + r.normal(0, 0.003, n))))
vix_low = pd.Series(np.linspace(14, 12, 250)); vix_high = pd.Series(np.linspace(14, 24, 250))
a = m.classify_daily(up, vix_low); check('steady climb is trending up', a['regime'] == 'trending_up' and a['stack'] == 'up' and a['adx'] >= 22, f"{a['regime']} adx {a['adx']} er {a['er10']}")
a = m.classify_daily(dn, vix_low); check('steady fall is trending down', a['regime'] == 'trending_down' and a['stack'] == 'down', f"{a['regime']} adx {a['adx']}")
a = m.classify_daily(rng_, vix_low); check('sideways oscillation is range-bound', a['regime'] == 'range' and a['adx'] < 20, f"{a['regime']} adx {a['adx']} er {a['er10']}")
a = m.classify_daily(vol, vix_high); check('big two-way swings with VIX 24 are volatile', a['regime'] == 'volatile' and a['volatility'] == 'high', f"{a['regime']} adx {a['adx']} vol {a['volatility']}")
check('daily reading explains the numbers', 'ADX' in a['reading'] and 'India VIX' in a['reading'])
check('ADX is between 0 and 100 and +DI/-DI exist', 0 <= m.adx(up)[0].iloc[-1] <= 100 and m.adx(up)[1].iloc[-1] > m.adx(up)[2].iloc[-1])
check('efficiency ratio: straight line = 1, zig-zag near 0', m.efficiency_ratio(pd.Series(np.arange(30.0))) == 1.0 and m.efficiency_ratio(pd.Series([1, 2] * 15, dtype=float)) < 0.15)
em = m.expected_move(22700, 14.0); check('VIX 14 on 22,700: about 200 points a day, 450 a week', 190 <= em['daily_pts'] <= 215 and 440 <= em['weekly_pts'] <= 470, str(em))
idx = pd.date_range('2026-10-21 09:15', periods=60, freq='5min', tz='Asia/Kolkata')
tr = pd.DataFrame({'Open': np.linspace(22700, 22900, 60) - 1, 'High': np.linspace(22700, 22900, 60) + 3, 'Low': np.linspace(22700, 22900, 60) - 4, 'Close': np.linspace(22700, 22900, 60), 'Volume': 0}, index=idx)
t = m.classify_intraday(tr, daily_atr=250, prev_close=22690); check('one-way day is a trend day (up)', t['regime'] == 'trending_up' and 'Trend day' in t['label'], str(t['reading']))
ch = pd.DataFrame({'Open': 22800 + 12 * np.sin(np.arange(60) / 2.0), 'High': 22800 + 12 * np.sin(np.arange(60) / 2.0) + 3, 'Low': 22800 + 12 * np.sin(np.arange(60) / 2.0) - 3, 'Close': 22800 + 12 * np.sin(np.arange(60) / 2.0), 'Volume': 0}, index=idx)
t = m.classify_intraday(ch, daily_atr=250, prev_close=22800); check('small oscillation is a range day', t['regime'] == 'range', str(t['reading']))
sv = ch.copy(); sv['Close'] = 22800 + 90 * np.sign(np.sin(np.arange(60) / 1.3)); sv['Open'] = sv.Close.shift().fillna(22800); sv['High'] = sv[['Open', 'Close']].max(axis=1) + 5; sv['Low'] = sv[['Open', 'Close']].min(axis=1) - 5
t = m.classify_intraday(sv, daily_atr=150, prev_close=22800); check('wild whipsaw is volatile', t['regime'] == 'volatile', str(t['regime']) + ' ' + t['reading'])
check('under an hour of candles: too early', m.classify_intraday(tr.iloc[:6], 250, 22690)['regime'] == 'unclear')
dq = m.classify_daily(up, vix_low); iq = m.classify_intraday(ch, 250, 22800); pb = m.playbook(dq, iq, 12.0)
check('playbook for a trending-up day lists swing, options and intraday advice', 'Trending up' in pb['headline'] and len(pb['swing']) >= 2 and len(pb['options']) >= 2 and len(pb['intraday']) >= 2)
check('choppy day inside an uptrend warns the intraday trader', any('choppy' in x.lower() or 'chop' in x.lower() for x in pb['intraday']) or any('mean reversion' in x.lower() for x in pb['intraday']))
check('high VIX adds a risk warning', any('India VIX' in x for x in m.playbook(m.classify_daily(vol, vix_high), iq, 24.0)['risk']))
# breadth and sectors
fr = {f'A{i}': ohlc(100 * np.exp(np.cumsum(0.004 + r.normal(0, 0.004, 250))), seed=i) for i in range(6)}
fr.update({f'B{i}': ohlc(100 * np.exp(np.cumsum(-0.004 + r.normal(0, 0.004, 250))), seed=20 + i) for i in range(6)})
ind = {**{f'A{i}': 'Capital Goods' for i in range(6)}, **{f'B{i}': 'Realty' for i in range(6)}}
flat = ohlc(22000 + r.normal(0, 20, 300))
s, secs, per = m.breadth(fr, ind, flat)
check('breadth counts every stock and splits strong from weak', s['count'] == 12 and 40 <= s['above50'] <= 60 and s['new_highs'] >= 0, str(s))
check('rising industry is strong, falling industry is weak', {x['sector']: x['state'] for x in secs} == {'Capital Goods': 'strong', 'Realty': 'weak'}, str(secs))
check('per-stock sector tag and relative strength', per['A0']['sector'] == 'Capital Goods' and per['A0']['sector_state'] == 'strong' and isinstance(per['B0']['rs20'], float))
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
