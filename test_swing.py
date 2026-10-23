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
r3 = swing.analyse(d, h, m)
check('15m: CHoCH 1,061, BOS 1,065, FVG 1,065-1,069, retest, trigger -> stage 5 TRIGGERED', r3['stage'] == 5 and r3['status'] == 'TRIGGERED' and r3['m15']['choch']['level'] == 1061 and r3['m15']['bos']['level'] == 1065 and r3['m15']['fvg'] == {'low': 1065.0, 'high': 1069.0}, r3['status'])
check('plan = the playbook: entry 1,070, stop below the OB with a buffer (about 1,036), T1/T2/T3 = 1R/2R/3R', r3['entry'] == 1070 and 1035 <= r3['sl'] <= 1037 and abs(r3['t1'] - (1070 + (1070 - r3['sl']))) < 1e-6 and abs(r3['t3'] - (1070 + 3 * (1070 - r3['sl']))) < 1e-6, str((r3['entry'], r3['sl'], r3['t1'])))
check('scorecard: Structure 2 + Zone 2 + Confirmation 3 + Context 3 = 10, A+', (r3['structure'], r3['zone_q'], r3['confirm'], r3['context'], r3['score'], r3['grade']) == (2, 2, 3, 3, 10, 'A+'), str((r3['structure'], r3['zone_q'], r3['confirm'], r3['context'], r3['ticks'])))
cl = swing.checklist(r3, {})
check('checklist walks the playbook: weekly, sweep, CHoCH, BOS, zone, fib, 1H x3, risk, 15m x2, room', [c['tf'] for c in cl][:6] == ['Weekly', '1D', '1D', '1D', '1D', '1D'] and sum(1 for c in cl if c['tf'] == '15m') == 2 and any(c['title'] == 'Futures OI long buildup' and c['ok'] is None for c in cl))
check('plan text: no early breakeven, trail by daily structure', any('No early breakeven' in t for t in swing.plan_text(r3)['trail']) and any('daily structure' in t for t in swing.plan_text(r3)['trail']))
_, _, m_late = frames(n_15m=30)
r4 = swing.analyse(d, h, m_late)
check('no chasing: once price runs away from the 15m entry it is no longer a fresh trigger', r4['stage'] == 4 and 'no chasing' in r4['m15']['note'], r4['m15']['note'])
d_dev, _, _ = frames(n_daily=27)
r5 = swing.analyse(d_dev)
check('right after the CHoCH and the first BOS the setup is already tracked (stage 1 or 2), never an entry', r5 and r5.get('stage') in (1, 2), str(r5 and (r5.get('stage'), r5.get('status'))))
d_brk, _, _ = frames()
d_brk = d_brk.copy(); d_brk.iloc[-1, :] = [1040, 1041, 1010, 1015, 200000]
r6 = swing.analyse(d_brk)
check('a daily close below the zone kills that zone (only a deeper, still intact zone may remain)', r6 is None or r6.get('stage') is None or (r6['zone_bot'] < 1041 and r6['price'] >= r6['zone_bot']), str(r6 and (r6.get('zone_bot'), r6.get('zone_top'))))
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
