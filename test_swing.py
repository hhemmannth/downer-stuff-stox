"""Swing engine against your swing playbook's own example. Run: python test_swing.py"""
import sys
import strategy_scanner as sc, swing
from playbook_fixture import frames
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
sc.CFG.update(min_turnover_cr=0, min_price=0)
swing.CFG['lux_ob'] = False        # the written playbook example draws the order block as the last down candle; the LuxAlgo rule has its own tests at the end
d, h, m = frames()
wk = swing.weekly_location(d)
check('weekly: trend up after the uptrend', wk['up'] is True, wk['text'])
r1 = swing.analyse(d)
check('without intraday data a stock in its zone is stage 3 (in zone, wait for the 1H)', r1['stage'] == 3 and r1['status'].startswith('IN ZONE'), r1['status'])
check('1D zone = the playbook: OB 1,041-1,052 + FVG 1,055-1,076, overlapping (Zone 2)', (round(r1['ob_low']), round(r1['ob_high']), round(r1['fvg_low']), round(r1['fvg_high'])) == (1041, 1052, 1055, 1076) and r1['zone_q'] == 2)
check('fib 0.618-0.705 of the 1,041-1,104 leg = 1,060-1,065 and sits in the zone', (round(r1['fib_lo']), round(r1['fib_hi'])) == (1060, 1065) and 'Fib 0.618' in r1['ticks'], str((r1['fib_lo'], r1['fib_hi'])))
check('BOS with displacement on about 2x volume', r1['bos_level'] == 1061 and r1['bos_rvol'] >= 1.5, str((r1['bos_level'], r1['bos_rvol'])))
r2 = swing.analyse(d, h)
check('1H: rejection at 1,053, close above the 9 EMA on 1.5x+ volume -> stage 4, confirmation 3 of 3', r2['stage'] == 4 and r2['confirm'] == 3 and round(r2['cf']['pullback_low']) == 1053 and r2['cf']['rvol'] >= 1.5, str((r2['stage'], r2['confirm'], r2['cf']['rvol'])))
r_pre = swing.analyse(d, h, m)
check('15m timing (your rule): the same 15m trigger 30 minutes BEFORE the 1H confirmation closed is not an entry: stays 1H CONFIRMED', r_pre['stage'] == 4 and 'before the 1H confirmation closed' in r_pre['m15']['note'], r_pre['m15']['note'])
_, _, m = frames(m15_after=20)                                                   # the playbook's 15m sequence, after the 1H confirmation candle
r3 = swing.analyse(d, h, m)
check('15m: CHoCH 1,061, BOS 1,065, FVG 1,065-1,069, retest, trigger -> stage 5 TRIGGERED', r3['stage'] == 5 and r3['status'] == 'TRIGGERED' and r3['m15']['choch']['level'] == 1061 and r3['m15']['bos']['level'] == 1065 and r3['m15']['fvg'] == {'low': 1065.0, 'high': 1069.0}, r3['status'])
check('plan = the playbook: entry 1,070, stop below the OB with a buffer (about 1,036), T1/T2/T3 = 1R/2R/3R', r3['entry'] == 1070 and 1035 <= r3['sl'] <= 1037 and abs(r3['t1'] - (1070 + (1070 - r3['sl']))) < 1e-6 and abs(r3['t3'] - (1070 + 3 * (1070 - r3['sl']))) < 1e-6, str((r3['entry'], r3['sl'], r3['t1'])))
check('scorecard: Structure 2 + Zone 2 + Confirmation 3 + Context 3 = 10, A+', (r3['structure'], r3['zone_q'], r3['confirm'], r3['context'], r3['score'], r3['grade']) == (2, 2, 3, 3, 10, 'A+'), str((r3['structure'], r3['zone_q'], r3['confirm'], r3['context'], r3['ticks'])))
cl = swing.checklist(r3, {})
check('checklist walks the playbook: weekly, sweep, CHoCH, BOS, zone, fib, 1H x3, risk, 15m x2, room', [c['tf'] for c in cl][:6] == ['Weekly', '1D', '1D', '1D', '1D', '1D'] and sum(1 for c in cl if c['tf'] == '15m') == 2 and any(c['title'] == 'Futures OI long buildup' and c['ok'] is None for c in cl))
check('plan text: no early breakeven, trail by daily structure', any('No early breakeven' in t for t in swing.plan_text(r3)['trail']) and any('daily structure' in t for t in swing.plan_text(r3)['trail']))
_, _, m_late = frames(n_15m=30, m15_after=20)
r4 = swing.analyse(d, h, m_late)
check('no chasing: once price runs away from the 15m entry it is no longer a fresh trigger', r4['stage'] == 4 and 'no chasing' in r4['m15']['note'], r4['m15']['note'])
d_dev, _, _ = frames(n_daily=27)
r5 = swing.analyse(d_dev)
check('right after the CHoCH and the first BOS the setup is already tracked (stage 1 or 2), never an entry', r5 and r5.get('stage') in (1, 2), str(r5 and (r5.get('stage'), r5.get('status'))))
d_brk, _, _ = frames()
d_brk = d_brk.copy(); d_brk.iloc[-1, :] = [1040, 1041, 1010, 1015, 200000]
r6 = swing.analyse(d_brk)
check('a daily close below the zone kills that zone (only a deeper, still intact zone may remain)', r6 is None or r6.get('stage') is None or (r6['zone_bot'] < 1041 and r6['price'] >= r6['zone_bot']), str(r6 and (r6.get('zone_bot'), r6.get('zone_top'))))
import playbook_fixture as _pf
_d, _h, _ = _pf.frames(vol=5_000_000)
_r = swing.analyse(_d, _h)
check('volume REQUIRED (your rule): the playbook 1H reclaim on 1.8x volume is 1H CONFIRMED', _r['stage'] == 4 and _r['cf']['rvol_ok'] == 1, f"{_r['stage']} {_r['cf']['rvol']:.2f}")
_hw = _h.copy(); _hw.loc[_hw.index[-3]:, 'Volume'] = 10
_rw = swing.analyse(_d, _hw)
check('volume REQUIRED: the same reclaim on weak volume is NOT confirmed; it says so instead of "in zone"', _rw['stage'] == 3 and _rw['status'].startswith('1H RECLAIM, WEAK VOLUME'), _rw['status'])
_hz = _h.copy(); _hz.loc[_hz.index[-3]:, 'Volume'] = 0
check('no volume in the data: not confirmed, and the status says the volume is missing', swing.analyse(_d, _hz)['status'].startswith('1H RECLAIM, NO VOLUME DATA'))
check('require_volume=False brings back the old rule (rejection OR volume)', swing.analyse(_d, _hw, cfg=dict(swing.CFG, require_volume=False))['stage'] == 4)
_rr = swing.analyse(_d, _h, weekly=dict(up=False, near=False, dist=None, text='Weekly trend not up'))
check('hold-backs apply from 1H confirmed: weekly trend against holds a stage-4 setup as WATCH (it used to wait for the 15m entry)', _rr['stage'] == 4 and _rr['status'] == 'WATCH (weekly trend against)' and _rr['holds'] == ['weekly trend against'], _rr['status'])
_hc = _h.astype(float); _vc = _hc.columns.get_loc('Volume'); _k = _hc.index.get_loc(_hc.index[_hc.index.astype(str).str.startswith(_r['cf']['t_confirm'])][0])
_hc.iloc[_k, _vc] = 10.0; _hc.iloc[_k + 1, _vc] = float(_h.Volume.iloc[_k])
_rc = swing.analyse(_d, _hc)
check('controlled continuation (your rule): weak-volume reclaim, then the next 1H close still above the 9 EMA on 1.5x -> 1H CONFIRMED at that candle', _rc['stage'] == 4 and _rc['cf'].get('continuation') and _rc['cf']['t_confirm'] > _r['cf']['t_confirm'], f"{_rc['status']} {_rc['cf'].get('t_confirm')}")
_e = sc.ema(_hc.Close, 9).values; _hx = _hc.copy(); _hx.iloc[_k + 1, _hx.columns.get_loc('Close')] = _e[_k + 1] - 5; _hx.iloc[_k + 1, _hx.columns.get_loc('Low')] = min(_hx.Low.iloc[_k + 1], _e[_k + 1] - 6)
check('continuation needs the close to stay above the 9 EMA: a strong candle that closes below it does not confirm', swing.analyse(_d, _hx)['stage'] == 3)
import numpy as _np, pandas as _pd
_ix = _pd.DatetimeIndex([f'2026-11-0{d} 11:15' for d in range(2, 8)] + ['2026-11-09 11:15'], tz='Asia/Kolkata')
_v = _np.array([1000., 0., 1000., 0., 1000., 1000., 1500.])
check('volume gaps: an hour with volume 0 is a feed gap, left out of the average (1,500 vs 1,000 = 1.5x, not 2.5x)', abs(swing._rvol(_ix, _v, 6, slot=True) - 1.5) < 1e-9, str(swing._rvol(_ix, _v, 6, slot=True)))
_v0 = _v.copy(); _v0[6] = 0.0
check('volume gaps: a confirmation candle with volume 0 reads as NO DATA (NaN), never as weak or strong', _np.isnan(swing._rvol(_ix, _v0, 6, slot=True)))
# a failed 15m zone must not set the planned entry (found False keeps its old FVG in the result)
_orig = swing.entry_15m; _z = r2['zone_top'] if 'zone_top' in r2 else None
swing.entry_15m = lambda *a, **k: dict(found=False, choch=None, bos=None, fvg=dict(low=r2['zone_top'] + 40, high=r2['zone_top'] + 60), retest=None, trigger=None, entry=None, rvol=float('nan'), age=None, note='The 15m zone failed: wait for a new 15m structure.')
try: _rf = swing.analyse(d, h, m)
finally: swing.entry_15m = _orig
_want = r2['zone_top'] - .25 * (r2['zone_top'] - r2['zone_bot'])
check('a FAILED 15m zone does not set the planned entry: it stays at the daily zone (not 60 points above it)', _rf['stage'] == 4 and abs(_rf['entry'] - _want) < 0.01, f"{_rf['entry']} vs {_want}")
swing.entry_15m = lambda *a, **k: dict(found=True, choch=dict(level=1, at='x'), bos=dict(level=1, at='x'), fvg=dict(low=r2['zone_top'] + 40, high=r2['zone_top'] + 60), retest=None, trigger=None, entry=None, rvol=float('nan'), age=None, note='15m structure is there: wait for a controlled retest of the 15m FVG.')
try: _rg = swing.analyse(d, h, m)
finally: swing.entry_15m = _orig
check('a live 15m zone (found, waiting for the retest) still plans the entry at its FVG high', abs(_rg['entry'] - (r2['zone_top'] + 60)) < 0.01, str(_rg['entry']))
# ---- the 1H step follows the LATEST pullback: an old zone touch plus a random later cross of the 9 EMA is not a confirmation
import numpy as _np2, pandas as _pd2
def _hourly(closes, vols=None):
    days = []; day = _pd2.Timestamp('2026-10-05')
    while len(days) * 7 < len(closes):
        if day.weekday() < 5: days.append(day)
        day += _pd2.Timedelta(days=1)
    ix = _pd2.DatetimeIndex([d + _pd2.Timedelta(hours=9, minutes=15) + _pd2.Timedelta(hours=k) for d in days for k in range(7)][:len(closes)]).tz_localize('Asia/Kolkata')
    c = _np2.array(closes, float); o = _np2.r_[c[0], c[:-1]]
    return _pd2.DataFrame(dict(Open=o, High=_np2.maximum(o, c) + 1.0, Low=_np2.minimum(o, c) - 1.0, Close=c, Volume=_np2.array(vols if vols is not None else [1000.0] * len(closes))), index=ix)
Z = dict(zone_bot=100.0, zone_top=110.0)
path = [120] * 5 + [108, 105, 106] + [112, 116, 120, 124, 128] + [130] * 37 + [125, 122, 120] + [130, 134, 138] + [140] * 20          # bars 5-7 pullback, 8+ bounce, bars 50-52 dip WITHOUT touching the zone, 53 re-cross
hh = _hourly(path); ee = sc.ema(hh.Close, 9).values
xs = [i for i in range(1, len(hh)) if hh.Close.values[i] > ee[i] and hh.Close.values[i - 1] <= ee[i - 1]]
vv = _np2.full(len(hh), 1000.0); late = [i for i in xs if i >= 50][0]; vv[late] = 5000.0                       # the late cross comes on 5x volume
hh = _hourly(path, vv); cf1 = swing.confirm_1h(hh, Z, 1.0, None)
check('old pullback + random later re-cross on 5x volume is NOT a confirmation (the reclaim must follow the pullback low)', cf1['touched'] and not cf1['rvol_ok'] and cf1['t_touch'] == str(hh.index[5])[:16], str((cf1['t_touch'], cf1['rvol_ok'], cf1['t_confirm'])))
check('and that old pullback is stale: its last touch is more than 21 candles ago, so the setup is not "in zone"', cf1['touch_age'] > swing.CFG['touch_max_age'], str(cf1['touch_age']))
path2 = path[:60] + [112, 108, 106, 109] + [112, 118, 124, 130] + [132] * 12                                     # a NEW pullback into the zone at bars 61-63 and a bounce
h2 = _hourly(path2); e2 = sc.ema(h2.Close, 9).values
x2 = [i for i in range(60, len(h2)) if h2.Close.values[i] > e2[i] and h2.Close.values[i - 1] <= e2[i - 1]]
v2 = _np2.full(len(h2), 1000.0); v2[x2[0]] = 4000.0; h2 = _hourly(path2, v2); cf2 = swing.confirm_1h(h2, Z, 1.0, None)
check('the latest pullback is the one used: t_touch is the NEW pullback, not the first touch weeks earlier', cf2['t_touch'] > str(h2.index[50])[:16] and cf2['reclaim'] == 1, str((cf2['t_touch'], cf2['t_confirm'])))
check('and its reclaim on 4x volume confirms (rejection counted from that pullback only, pullback low from it too)', cf2['rvol_ok'] == 1 and cf2['rvol'] >= 1.5 and cf2['pullback_low'] > 100 and cf2['confirm_age'] is not None, str((cf2['rvol'], cf2['pullback_low'], cf2['confirm_age'])))
# ---- LuxAlgo order block (what your TradingView charts draw), on real CUPID and SANSERA daily candles ----
import json as _json, os as _os
swing.CFG['lux_ob'] = True
_L = _json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lux_fixture.json')))
def _lux_frame(sym, upto=None):
    c = _L[sym]; K = _np.array(c['candles'], float); n = len(K) if upto is None else upto
    return _pd.DataFrame(dict(Open=K[:n, 0], High=K[:n, 1], Low=K[:n, 2], Close=K[:n, 3], Volume=c['volume'][:n]), index=_pd.DatetimeIndex(c['times'][:n]))
_cu = _lux_frame('CUPID'); _ob = sc.lux_bull_breaks(*(_cu[k].values for k in ('Open', 'High', 'Low', 'Close')))
_bi = [i for i in _ob if str(_cu.index[i])[:10] == '2026-11-11']
check('LuxAlgo OB, CUPID: the 11 Nov close above 352.8 makes the 4 Nov candle (329.6-344.0) the order block', bool(_bi) and abs(_ob[_bi[0]][0] - 329.6) < .01 and abs(_ob[_bi[0]][1] - 344.0) < .01 and str(_cu.index[_ob[_bi[0]][2]])[:10] == '2026-11-04' and abs(_ob[_bi[0]][3] - 352.85) < .01, str(_ob.get(_bi[0] if _bi else -1)))
_sa = _lux_frame('SANSERA'); _ob2 = sc.lux_bull_breaks(*(_sa[k].values for k in ('Open', 'High', 'Low', 'Close')))
_got = {str(_sa.index[i])[:10]: (round(v[0], 1), round(v[1], 1)) for i, v in _ob2.items()}
check('LuxAlgo OB, SANSERA: 3,869.2-4,050.0 (broken 4 Nov) and 3,733.7-3,833.8 (broken 9 Sep), as drawn on your chart', _got.get('2026-11-04') == (3869.2, 4050.0) and _got.get('2026-09-09') == (3733.7, 3833.8), str(_got))
_early = _lux_frame('CUPID', upto=list(_cu.index.astype(str).str[:10]).index('2026-11-11'))
check('no look-ahead: before the 11 Nov close the 4 Nov order block does not exist yet', not any(str(_early.index[i])[:10] == '2026-11-11' for i in sc.lux_bull_breaks(*(_early[k].values for k in ('Open', 'High', 'Low', 'Close')))))
_r = swing.analyse(_cu)
check('CUPID zone uses the LuxAlgo order block (329.6-344.0) plus the 344.9-356.0 gap, and the stop sits below 329.6', _r is not None and 'ob_low' in _r and abs(_r['ob_low'] - 329.6) < .01 and abs(_r['ob_high'] - 344.0) < .01 and abs(_r['zone_bot'] - 329.6) < .01 and abs(_r['zone_top'] - 356.0) < .01 and _r['sl'] < 329.6, str(_r and (_r.get('ob_low'), _r.get('zone_bot'), _r.get('zone_top'), _r.get('sl'))))
swing.CFG['lux_ob'] = False; _r0 = swing.analyse(_cu); swing.CFG['lux_ob'] = True
check('the old rule is still there as one switch (CFG lux_ob False gives the 335.65-343.9 box)', _r0 is not None and abs(_r0['ob_low'] - 335.65) < .01, str(_r0 and _r0.get('ob_low')))

_d15, _h15, _m15 = frames(); swing.CFG['lux_ob'] = True
_e = swing.entry_15m(_m15, dict(zone_bot=1041.0, zone_top=1076.0), None, 20.0)
check('15m entry check also runs on the LuxAlgo rule: the 15m CHoCH 1,061 + BOS 1,065 + FVG 1,065-1,069 are still found (no order block drawn there, the gap is the zone)', _e['found'] and _e['fvg']['low'] == 1065 and _e['fvg']['high'] == 1069 and _e['ob']['low'] is None, str((_e['found'], _e['fvg'], _e['ob'], _e['note'])))

print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
