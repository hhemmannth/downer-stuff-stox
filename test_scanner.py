"""Rule-engine tests on synthetic setups with clear swings. Run: python test_scanner.py"""
import sys
import numpy as np, pandas as pd
import strategy_scanner as sc

closes = [1115,1117,1118,1119,1119,1120,1112,1103,1094,1085,1088,1093,1097,1100,1090,1079,1069,1062,1067,1072,1076,1080,1071,1060,1049,1040,
          1047,1056,1065,1074,1090,1084,1078,1112,1122,1130,1122,1114,1106,1100,1096,1094]
wick_up = {5: 5, 13: 5, 21: 5}; wick_dn = {9: 5, 17: 5, 25: 5}; vols = {30: 190, 33: 220, 25: 200}
def daily_rows():
    rows = []; prev = 1114
    for i, c in enumerate(closes):
        o = prev; h = max(o, c) + wick_up.get(i, 2); l = min(o, c) - wick_dn.get(i, 2)
        if i == 25: l = 1028
        rows.append([o, h, l, c, vols.get(i, 100)]); prev = c
    return rows
D = daily_rows()
h1c = [1122,1120,1123,1116,1112,1115,1108,1104,1107,1100,1096,1099,1094,1090,1093,1088,1094,1096,1093,1092,1101,1103]
def hourly_rows():
    rows = []; prev = 1124
    for i, c in enumerate(h1c):
        o = prev; h = max(o, c) + 3; l = min(o, c) - 3
        if i == 15: l = 1083
        rows.append([o, h, l, c, 175 if i == 20 else 100 + (i % 4) * 5]); prev = c
    return rows
H = hourly_rows()
def frame(rows, freq, tz=None):
    return pd.DataFrame(rows, columns=sc.COLS, index=pd.date_range('2026-01-01', periods=len(rows), freq=freq, tz=tz))
flip = lambda rows: [[2300 - a, 2300 - c_, 2300 - b, 2300 - d_, v] for a, b, c_, d_, v in rows]

sc.CFG_B.update(min_bars=20)
CFG = dict(sc.CFG, pivot=3, min_turnover_cr=0, min_price=0, min_bars=30, rvol_n=10)
CFG5 = dict(sc.CFG_I, min_turnover_cr=0, min_bars=30, rvol_n=10, max_zone_pct=6, max_zone_atr=5)
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
h = [r[1] for r in D]; l = [r[2] for r in D]; o = [r[0] for r in D]
daily = frame(D, 'D'); hourly = frame(H, 'h', 'Asia/Kolkata')

print('--- swing (1D structure, 1H trigger, long only) ---')
r = sc.scan_symbol(daily, hourly, 'long', CFG, ['weekly trend', 'Nifty trend'])
check('long setup found', r is not None and 'zone_bot' in r, str(r and r.get('state')))
if r and 'zone_bot' in r:
    check('CHoCH on bar 30 above the lower high', r['choch_date'].startswith(str(daily.index[30])[:10]) and abs(r['choch_level'] - h[21]) < .01, r['choch_date'])
    check('BOS on bar 33', r['bos_date'].startswith(str(daily.index[33])[:10]), r['bos_date'])
    check('OB = last down candle before the BOS', abs(r['ob_low'] - l[32]) < .01 and abs(r['ob_high'] - o[32]) < .01, f"{r['ob_low']}-{r['ob_high']}")
    check('FVG = gap between bar 32 high and bar 34 low', abs(r['fvg_low'] - h[32]) < .01 and abs(r['fvg_high'] - l[34]) < .01, f"{r['fvg_low']}-{r['fvg_high']}")
    rng = max(h[33:]) - l[32]
    check('fib 0.618-0.705 of the leg', abs(r['fib_hi'] - (max(h[33:]) - .618 * rng)) < .01 and abs(r['fib_lo'] - (max(h[33:]) - .705 * rng)) < .01)
    check('in the zone and TRIGGERED', r['state'] == 'IN_ZONE' and r['status'] == 'TRIGGERED', f"{r['state']} / {r['status']}")
    check('confirmation 3/3 and ticks counted', r['confirm'] == 3 and all(t in r['ticks'] for t in ['key level', 'fib', 'MTF EMA', 'weekly trend']), r['ticks'])
    check('score 10 = A+ (context capped at 3)', r['score'] == 10 and r['grade'] == 'A+', f"{r['score']} {r['grade']}")
    check('SL below the OB and T2 = 2R', r['sl'] < r['ob_low'] and abs((r['t2'] - r['entry']) - 2 * (r['entry'] - r['sl'])) < .01, f"entry {r['entry']:.1f} sl {r['sl']:.1f} r_t1 {r['r_t1']:.2f}")
try: sc.scan_symbol(daily, hourly, 'short', CFG); refused = False
except ValueError: refused = True
check('swing refuses short (rule book: long only)', refused)
r2 = sc.scan_symbol(daily, frame(H[:14], 'h', 'Asia/Kolkata'), 'long', CFG)
check('no 1H trigger yet -> WATCH or APPROACHING', r2 is not None and 'zone_bot' in r2 and not r2['status'].startswith('TRIGGER'), str(r2 and r2.get('status')))
r3 = sc.scan_symbol(frame(D[:36], 'D'), None, 'long', CFG); check('just above the zone -> APPROACHING', r3 is not None and r3['status'].startswith('APPROACHING'), str(r3 and r3.get('status')))
r3b = sc.scan_symbol(frame(D[:36] + [[1130, 1160, 1128, 1156, 100]], 'D'), None, 'long', CFG); check('far above the zone is not reported', r3b is None or 'zone_bot' not in r3b, str(r3b and r3b.get('state')))
r4 = sc.scan_symbol(frame(D + [[1094, 1095, 1040, 1048, 200]], 'D'), None, 'long', CFG); check('a close below the zone cancels it', r4 is None or 'zone_bot' not in r4, str(r4 and r4.get('state')))
try: r9 = sc.scan_symbol(frame(D[:34], 'D'), None, 'long', CFG); ok9 = True
except Exception as ex: ok9 = False; r9 = str(ex)
check('BOS on the very last bar does not crash', ok9, str(r9 if not ok9 else ''))
gone = lambda x: x is None or 'zone_bot' not in x
check('old structure ignored (max_bos_age)', gone(sc.scan_symbol(daily, hourly, 'long', dict(CFG, max_bos_age=5))))
check('tall zone ignored (max_zone_atr)', gone(sc.scan_symbol(daily, hourly, 'long', dict(CFG, max_zone_atr=1.0))))
check('a trigger after price ran away is dropped', gone(sc.scan_symbol(daily, frame(H[:20] + [[1093, 1170, 1090, 1160, 175]], 'h', 'Asia/Kolkata'), 'long', CFG)))
lowvol = [row[:] for row in H]; lowvol[20][4] = 95
r8 = sc.scan_symbol(daily, frame(lowvol, 'h', 'Asia/Kolkata'), 'long', CFG); check('trigger without volume is only WATCH', r8 is not None and r8['status'].startswith('WATCH (trigger'), str(r8 and r8.get('status')))
check('weekly trend helper', sc.weekly_ok(pd.DataFrame({'Close': np.linspace(100, 200, 120)}, index=pd.bdate_range('2026-01-01', periods=120))) and not sc.weekly_ok(pd.DataFrame({'Close': np.linspace(200, 100, 120)}, index=pd.bdate_range('2026-01-01', periods=120))))

print('--- India-specific swing refinements ---')
locked = [row[:] for row in D]; locked[40] = [1100, 1100, 1100, 1100, 100]
check('a locked-circuit session in the last 5 days excludes the stock', sc.scan_symbol(frame(locked, 'D'), hourly, 'long', CFG) is None)
check('NSE tick size: prices are rounded to 5 paise', sc.r05(748.2349) == 748.25 and sc.r05(100.02) == 100.0 and sc.r05(float('nan')) is None)
ts = []
for i in range(22): ts.append(pd.Timestamp('2026-01-05 09:15', tz='Asia/Kolkata') + pd.Timedelta(days=i // 6) + pd.Timedelta(hours=i % 6))   # 6 candles a day: 09:15 .. 14:15
hv = [row[:] for row in H]
for i in (2, 8, 14): hv[i][4] = 160                       # earlier 11:15 candles were just as busy
hs = pd.DataFrame(hv, columns=sc.COLS, index=pd.DatetimeIndex(ts))
check('same-slot volumes are the 11:15 candles of earlier days', list(sc.slot_volumes(hs.index, hs.Volume.values, 20)) == [160, 160, 160])
rs_ = sc.scan_symbol(daily, hs, 'long', CFG); rr_ = sc.scan_symbol(daily, hs, 'long', dict(CFG, slot_rvol=False))
check('time-of-day volume: 175 vs a busy 11:15 slot (1.1x) is NOT a strong trigger', rs_['status'].startswith('WATCH (trigger') and rr_['status'] == 'TRIGGERED', f"{rs_['status']} | whole-day average: {rr_['status']}")

print('--- 15m CHoCH only (options and intraday) ---')
b = sc.choch_bias(frame(D[:32], 'D')); check('CHoCH without BOS is enough for the 15m bias', b is not None and abs(b['level'] - h[21]) < .01 and not sc.find_structures(frame(D[:32], 'D'), dict(sc.CFG_B, min_bars=20)), str(b and b['date']))
check('bias carries the 15m order block (last down candle before the CHoCH)', abs(b['ob_low'] - l[25]) < .01 and abs(b['ob_high'] - o[25]) < .01, f"{b['ob_low']}-{b['ob_high']}")
check('no CHoCH at all -> no bias', sc.choch_bias(frame(D[:20], 'D')) is None)
fl = [row[:] for row in D[:32]]; fl.append([1084, 1085, 1020, 1030, 100]); check('a CHoCH that failed (new low) gives no bias', sc.choch_bias(frame(fl, 'D')) is None)
idx5 = pd.date_range('2026-10-12 09:15', periods=len(D) + len(H), freq='5min', tz='Asia/Kolkata')
f5 = pd.DataFrame(D + H, columns=sc.COLS, index=idx5)
f15 = pd.DataFrame(D[:32], columns=sc.COLS, index=pd.date_range('2026-10-12 09:15', periods=32, freq='15min', tz='Asia/Kolkata'))
ri = sc.scan_intraday(f5, f15, 'long', CFG5, [], section='intraday')
check('intraday long found with a 15m CHoCH only', ri is not None and 'zone_bot' in ri, str(ri and ri.get('state')))
if ri and 'zone_bot' in ri:
    check('structure 2/2, TRIGGERED with volume, grade A or better', ri['structure'] == 2 and ri['status'] == 'TRIGGERED' and ri['grade'] in ('A', 'A+') and ri['confirm'] == 3, f"{ri['status']} {ri['score']} confirm {ri['confirm']}")
    check('15m details are carried for the explanation', ri['b15_date'] and abs(ri['b15_level'] - h[21]) < .01)
lowv = [row[:] for row in D + H]; lowv[len(D) + 20][4] = 95
rl = sc.scan_intraday(pd.DataFrame(lowv, columns=sc.COLS, index=idx5), f15, 'long', CFG5, [], section='intraday')
check('intraday still needs volume: weak trigger is only WATCH', rl is not None and rl['status'].startswith('WATCH (trigger'), str(rl and rl['status']))
check('no 15m CHoCH -> rejected (NO_BIAS)', (lambda x: x is None or x.get('state') == 'NO_BIAS')(sc.scan_intraday(f5, f15.iloc[:20], 'long', CFG5, [], section='intraday')))
f5s = pd.DataFrame(flip(D + H), columns=sc.COLS, index=idx5); f15s = pd.DataFrame(flip(D[:32]), columns=sc.COLS, index=f15.index)
rs = sc.scan_intraday(f5s, f15s, 'short', CFG5, [], section='intraday')
check('short (put) mirrors the long setup', rs is not None and 'zone_bot' in rs and rs['sl'] > rs['zone_top'] and rs['t2'] < rs['entry'] and rs['b15_level'] > 0, str(rs and (rs.get('grade'), rs.get('state'))))
check('mirrored 15m level is mirrored back: 2300 minus the long-side level', rs is not None and abs(rs['b15_level'] - (2300 - h[21])) < .01, f"{rs and rs['b15_level']:.2f} vs {2300 - h[21]:.2f}")
check('a long scan on mirrored data finds nothing', gone(sc.scan_intraday(f5s, f15s, 'long', CFG5, [], section='intraday')))

print('--- Nifty options: no volume, more confluences ---')
novol = pd.DataFrame(D + H, columns=sc.COLS, index=idx5).assign(Volume=0)
ro = sc.scan_intraday(novol, f15, 'long', CFG5, [], section='options')
check('options trigger works with ZERO volume and says nothing about volume', ro is not None and ro['status'] == 'TRIGGERED' and 'volume' not in ro['status'].lower() and 'volume' not in ro['notes'].lower(), str(ro and (ro['status'], ro['notes'])))
check('options confirmation is 0 to 2 (rejection + EMA close), no NaN anywhere', ro['confirm'] == 2 and not any(isinstance(v, float) and v != v for k, v in ro.items() if k in ('score', 'confirm', 'context', 'entry', 'sl', 't1')), str(ro['confirm']))
orig = sc.choch_bias; aligned = dict(call_wall=1200, put_wall=1050, pcr=1.2)
sc.choch_bias = lambda df, cfg=None: dict(orig(df, cfg) or {}, ob_low=1070.0, ob_high=1085.0)      # a 15m order block inside the 5m zone
rb = sc.scan_intraday(novol, f15, 'long', CFG5, [], section='options', oi=aligned); sc.choch_bias = orig
check('confluences: 15m order block and the OI wall are added', rb is not None and 'order block (15m)' in rb['ticks'] and 'OI wall' in rb['ticks'], str(rb and rb['ticks']))
check('options context is capped at 4, so the maximum score is 10', rb['context'] == 4 and rb['score'] == 10 and rb['grade'] == 'A+', f"ctx {rb['context']} score {rb['score']}")
check('OI verdict is carried for the page', rb['oi_verdict']['verdict'] == 'supports' and rb['oi_verdict']['aligned'])
rn = sc.scan_intraday(novol, f15, 'long', CFG5, [], section='options', oi=dict(call_wall=1100, put_wall=1200, pcr=0.7))
check('OI against the trade: no OI tick, trade still shown', rn is not None and 'OI wall' not in rn['ticks'] and rn['oi_verdict']['verdict'] in ('against', 'mixed'), str(rn and rn['oi_verdict']['verdict']))
rno = sc.scan_intraday(novol, f15, 'long', CFG5, [], section='options')
check('no OI data: unknown, no crash', rno['oi_verdict']['verdict'] == 'unknown')
nov_s = pd.DataFrame(flip(D + H), columns=sc.COLS, index=idx5).assign(Volume=0)
rp = sc.scan_intraday(nov_s, f15s, 'short', CFG5, [], section='options', oi=dict(call_wall=2300 - 1200, put_wall=2300 - 1050, pcr=0.8))
check('PUT side works the same way (mirrored OI walls)', rp is not None and rp['status'] == 'TRIGGERED' and rp['oi_verdict']['verdict'] in ('supports', 'mixed'), str(rp and (rp['status'], rp['oi_verdict'])))
pl = sc.prev_day_levels(pd.DataFrame({'High': [5, 7, 6, 9], 'Low': [1, 2, 3, 4], 'Open': 1, 'Close': 1, 'Volume': 1}, index=pd.to_datetime(['2026-10-09 10:00', '2026-10-09 11:00', '2026-10-12 10:00', '2026-10-12 11:00']).tz_localize('Asia/Kolkata')))
check('previous-day high and low', pl == [7.0, 1.0], str(pl))
check('volume availability check', sc.has_volume(f5) and not sc.has_volume(f5.assign(Volume=0)))

print("--- swing chart: today's candle from the 1H candles ---")
d_ = frame(D, 'D'); d_.index = pd.bdate_range(end='2026-10-20', periods=len(D))
hh_ = pd.DataFrame([[1100, 1112, 1096, 1108, 50], [1108, 1115, 1105, 1110, 60], [1110, 1111, 1099, 1101, 40]], columns=sc.COLS, index=pd.DatetimeIndex(['2026-10-21 09:15', '2026-10-21 10:15', '2026-10-21 11:15']).tz_localize('Asia/Kolkata'))
cf_, ltp_ = sc.with_today(d_, hh_)
check('chart gets today\'s candle: open of the first 1H, high/low so far, last 1H close, summed volume', len(cf_) == len(d_) + 1 and list(cf_.iloc[-1]) == [1100, 1115, 1096, 1101, 150] and str(cf_.index[-1].date()) == '2026-10-21')
check('LTP is the latest closed 1H close, the rules still see closed daily candles only', ltp_ == 1101 and len(d_) == len(D))
cf2, ltp2 = sc.with_today(d_, None); check('no hourly data: chart unchanged', cf2 is d_ and ltp2 is None)
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
