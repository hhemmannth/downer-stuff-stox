"""Swing engine against your swing playbook's own example. Run: python test_swing.py"""
import sys
import strategy_scanner as sc, swing
from playbook_fixture import frames
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
sc.CFG.update(min_turnover_cr=0, min_price=0)
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
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
