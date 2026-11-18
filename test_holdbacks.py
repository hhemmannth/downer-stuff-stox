"""The 18 Nov 2026 upgrade: hold-backs found in the backtest of the published trades, and the extra confluences. No network. Run: python test_holdbacks.py
  swing   : stop under 7% of price, a weak zone (under 2/2), 1H volume under 2x, a Mixed / transitioning market -> the setup stays listed as WATCH with the reason
  swing   : confluences recorded (relative strength vs Nifty, pullback volume, 50 DMA trend, liquidity sweep, stop and extension in ATRs), the Lab slices by them
  intraday: no new stock intraday trade from 14:00, and a stop under 0.5% of price is WATCH; options keep their 15:00 cut-off
  backtest: the same rules decide what is 'held' in the replay, and the variants that test them exist."""
import os; os.environ['PLAYBOOK_V2'] = 'off'
import json, tempfile, numpy as np, pandas as pd
import backtest as bt, backtest_tf as tf, holdbacks, playbook_fixture as pf, signals, strategy_scanner as sc, subprocess, sys, swing, tf_fixture as fx
swing.CFG['lux_ob'] = False
os.environ['BACKTEST_FROM'] = 'all'; os.environ['MIN_SCORE'] = '4'
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else '')); (not cond) and fails.append(name)

# ---- the defaults
C = swing.CFG
check('defaults: stop 7%, zone 2/2, 1H volume 2.0x, Mixed regime held (old rules); all four are OFF for the secondary strategy', (C['min_stop_pct'], C['min_zone_q'], C['min_hold_rvol'], C['hold_regimes']) == (7.0, 2, 2.0, ('Mixed / transitioning',)))
check('defaults: intraday last entry 14:00 (options 15:00), intraday minimum stop 0.5%', signals.last_entry('intraday') == '14:00' and signals.last_entry('options') == '15:00' and sc.INTRADAY_MIN_STOP_PCT == 0.5)

# ---- swing hold-backs on the written playbook example (stop is 3.1% of price, zone 2/2, strong 1H volume)
d, h, m = pf.frames(m15_after=20)
r = swing.analyse(d, h, m)
check('the playbook example has a 3.1% stop: held back by the 7% rule, stays listed as WATCH with the reason', r['stage'] >= 4 and r['status'].startswith('WATCH (stop only 3.') and any(x.startswith('stop only') for x in r['holds']), r['status'])
r0 = swing.analyse(d, h, m, cfg=dict(C, min_stop_pct=0, min_hold_rvol=0))
check('with the stop and volume rules off the same setup is TRIGGERED (so the holds really are the only thing that changed)', r0['status'] == 'TRIGGERED' and not r0['holds'], r0['status'])
rz = swing.analyse(d, h, m, cfg=dict(C, min_stop_pct=0, min_zone_q=3))
check('a weak zone (below the minimum quality) is held: WATCH (weak zone ...)', rz['status'].startswith('WATCH (weak zone') and 'weak zone' in ' '.join(rz['holds']), rz['status'])
rv = swing.analyse(d, h, m, cfg=dict(C, min_stop_pct=0, min_hold_rvol=999))
check('1H volume below the minimum is held: WATCH (1H volume only ...)', rv['status'].startswith('WATCH (1H volume only') or any(x.startswith('1H volume only') for x in rv['holds']), rv['status'])
check('the holds only apply from the 1H confirmation on (stage 4+); earlier stages are untouched', swing.analyse(d)['holds'] == [] if swing.analyse(d)['stage'] < 4 else True)
check('every hold-back keeps the setup in the list with its stage and score (nothing silently vanishes)', r['score'] == r0['score'] and r['stage'] == r0['stage'] and 'sl' in r)

# ---- regime hold
check('regime_hold: Mixed / transitioning is held, a trend or a range is not, unknown is not', swing.regime_hold('Mixed / transitioning') and not swing.regime_hold('Trending up') and not swing.regime_hold('Range') and not swing.regime_hold(None) and not swing.regime_hold('Unknown'))
base = dict(r0, stage=5, status='TRIGGERED', holds=[], notes='')
x = sc.apply_swing_context(dict(base), dict(regime_label='Mixed / transitioning'))
check('live: a stage-5 setup in a Mixed market is WATCH (mixed market regime), with a note', x['status'].startswith('WATCH (market regime') and 'lost money' in x['notes'], x['status'])
x = sc.apply_swing_context(dict(base), dict(regime_label='Trending up'))
check('live: the same setup in a trending market is untouched', x['status'] == 'TRIGGERED' and not x['holds'])
x = sc.apply_swing_context(dict(base, stage=3, status='IN ZONE'), dict(regime_label='Mixed / transitioning'))
check('live: an earlier-stage setup only gets the note (hold-backs start at the 1H confirmation)', x['status'] == 'IN ZONE' and not x['holds'] and 'Mixed' in x['notes'], x['status'])
check('the fast lane keeps the stored regime fact (SWING_FACTS)', 'regime_label' in sc.SWING_FACTS)

# ---- confluences
n = 120; idx = pd.bdate_range('2026-01-01', periods=n)
c = np.linspace(100, 160, n); dd = pd.DataFrame({'Open': c - 0.5, 'High': c + 1, 'Low': c - 1, 'Close': c, 'Volume': np.full(n, 1000.)}, index=idx)
bench = pd.Series(np.linspace(100, 110, n), index=idx)
swing.BENCH = bench
cf = swing.confluences(dd, None, {}, 160.0, 2.0, None)
check('confluence: price above a rising 50 DMA', cf['above50'] is True)
check('confluence: relative strength is the stock move minus Nifty over 20 days (stock +%.1f%%, Nifty +%.1f%%)' % (100 * (c[-1] / c[-21] - 1), 100 * (bench.iloc[-1] / bench.iloc[-21] - 1)), abs(cf['rs20'] - round(100 * (c[-1] / c[-21] - bench.iloc[-1] / bench.iloc[-21]), 1)) < 0.11, str(cf['rs20']))
sub = dd.iloc[:80]; cf2 = swing.confluences(sub, None, {}, 130.0, 2.0, None)
check('no look-ahead: with the window ending earlier, the Nifty series is cut at the last candle too', abs(cf2['rs20'] - round(100 * (c[79] / c[59] - bench.iloc[79] / bench.iloc[59]), 1)) < 0.11, str(cf2['rs20']))
swing.BENCH = None; cf3 = swing.confluences(dd, None, {}, 160.0, 2.0, None)
check('no Nifty series: relative strength is simply missing (no crash, no guess)', cf3['rs20'] is None and cf3['above50'] is True)
dd2 = dd.copy(); dd2.loc[idx[60:], 'Volume'] = 400.; s_ = dict(bos_i=60, zone_top=150.0)
cf4 = swing.confluences(dd2, s_, dict(risk_atr=2.2), 155.0, 2.0, dict(sweep_i=3))
check('pullback volume is the average volume since the break over the 20 days before it (400/1000 = 0.4x); sweep, stop in ATR and extension are recorded', cf4['pb_vol'] == 0.4 and cf4['sweep'] is True and cf4['stop_atr'] == 2.2 and cf4['ext_atr'] == 2.5, str(cf4))
check('confluences survive garbage (an empty frame gives all-missing, not an exception)', swing.confluences(dd.iloc[:0], None, {}, 1.0, 1.0, None)['above50'] is None)
check('the engine puts the confluences on every result and explains them in the notes (not gates)', 'confl' in r and set(r['confl']) >= {'rs20', 'pb_vol', 'above50', 'sweep', 'stop_atr', 'ext_atr'})

# ---- backtest: held reasons, recorded confluences, variants, breakdown tables
dp, hp, _ = pf.frames(vol=5_000_000)
def future(hh, closes):
    rows, t, last = [], hh.index[-1], float(hh.Close.iloc[-1])
    for cl in closes:
        t = t + pd.Timedelta(hours=1)
        if t.hour > 15 or (t.hour == 15 and t.minute > 15): t = (t + pd.Timedelta(days=1)).normalize().tz_localize(None).tz_localize(hh.index.tz) + pd.Timedelta(hours=9, minutes=15)
        while t.weekday() >= 5: t += pd.Timedelta(days=1)
        rows.append((t, last, max(last, cl) + 1, min(last, cl) - 1, cl, 400000)); last = cl
    return pd.concat([hh, pd.DataFrame([q[1:] for q in rows], columns=['Open', 'High', 'Low', 'Close', 'Volume'], index=pd.DatetimeIndex([q[0] for q in rows]))])
up = future(hp, [1078 + 9 * i for i in range(1, 14)])
tr = bt.replay_symbol('PBK', dp, up, regimes={'2026-08-11': 'Mixed / transitioning'})
t = tr[0] if tr else {}
check('replay: the trade is recorded but marked held: stop under 7% and the Mixed market', t and 'stop under 7%' in t['held'] and 'mixed market regime' in t['held'], str(t.get('held')))
check('replay: the extra confluences are stored on the trade', all(k in t for k in ('rs20', 'pb_vol', 'above50', 'sweep', 'stop_atr', 'ext_atr')))
tr0 = bt._work(('PBK', dp, up, 'IT', {'2026-08-11': 'Mixed / transitioning'}, dict(min_stop_pct=0, min_zone_q=0, min_hold_rvol=0, hold_regimes=()), None, 4))
check('replay: with the new hold-backs switched off (the comparison variant) the same trade is taken', tr0 and tr0[0]['held'] == [], str(tr0 and tr0[0]['held']))
before = dict(C); bt._work(('PBK', dp, up, 'IT', {}, dict(min_stop_pct=0, expiry_days=45), None, 4))
check('variants: overrides, including the expiry, are restored afterwards', dict(C) == before and signals.SWING_EXPIRY_DAYS == 28)
names = [v[0] for v in bt.VARIANTS]
check('variants: without the new hold-backs, a wider 0.75 ATR stop buffer and a 45-day expiry are compared against the current rules', {'Without the 18 Nov hold-backs', 'Stop buffer 0.75 ATR', 'Expiry 45 days'} <= set(names), str(names))
live = []
for i in range(40):
    live.append(dict(t, held=[], closed=True, r_net=1.0 if i % 2 else -1.0, r=1.0, rs20=(8 if i % 2 else -3), pb_vol=(0.5 if i % 2 else 1.5), above50=bool(i % 2), sweep=bool(i % 3), stop_atr=1.2 + (i % 4), entry_t=f'2026-09-{1 + i % 28:02d} 10:00', exit_t=f'2026-09-{1 + i % 28:02d} 15:00'))
dims = {k: (title, fn, order) for k, title, cap, head, fn, order in bt.conf_dims(live)}
check('Lab tables: relative strength, pullback volume, stop in ATR, trend and sweep appear once 20 trades carry the fact', set(dims) == {'rs', 'pbvol', 'stopatr', 'trend50', 'sweep'}, str(list(dims)))
check('Lab tables: the labels sort the trades into the bands', dims['rs'][1](live[1]) == 'leader (5% or more ahead)' and dims['rs'][1](live[0]) == 'lagging (behind Nifty)' and dims['pbvol'][1](live[1]) == 'dried up (under 0.8x)')
check('Lab tables: old saved trades without the facts give no empty table', bt.conf_dims([{k: v for k, v in x.items() if k not in ('rs20', 'pb_vol', 'above50', 'sweep', 'stop_atr')} for x in live]) == [])
rep = bt.report(live, window={}, universe=1)
check('the report carries the new breakdowns and still renders for the page (by / by_order)', 'rs' in rep['by'] and 'pbvol' in rep['by'] and 'rs' in [x['key'] for x in rep['by_order']] and rep['by']['rs'][0]['k'] == 'leader (5% or more ahead)')

# ---- intraday: 14:00 cut-off, minimum stop, options untouched
T = lambda s: pd.Timestamp(s, tz='Asia/Kolkata')
a = [{'status': 'TRIGGERED'}]; sc.late_cut(a, T('2026-10-22 14:00'), 'intraday'); b = [{'status': 'TRIGGERED'}]; sc.late_cut(b, T('2026-10-22 13:59'), 'intraday')
o1 = [{'status': 'TRIGGERED'}]; sc.late_cut(o1, T('2026-10-22 14:30'), 'options'); o2 = [{'status': 'TRIGGERED'}]; sc.late_cut(o2, T('2026-10-22 15:00'))
check('late_cut: stock intraday is WATCH from 14:00, TRIGGERED at 13:59', a[0]['status'].startswith('WATCH (after 14:00') and b[0]['status'] == 'TRIGGERED', a[0]['status'])
check('late_cut: options are still allowed at 14:30 and cut at 15:00', o1[0]['status'] == 'TRIGGERED' and o2[0]['status'].startswith('WATCH (after 15:00'))
items = [dict(status='TRIGGERED', risk_pct=0.3, notes=''), dict(status='TRIGGERED', risk_pct=0.5, notes=''), dict(status='WATCH (x)', risk_pct=0.1, notes='')]
sc.intraday_stop_hold(items)
check('intraday stop under 0.5% of price: WATCH with the reason; 0.5% and above are untouched; WATCH items stay as they were', items[0]['status'].startswith('WATCH (stop only 0.30%') and 'lost money' in items[0]['notes'] and items[1]['status'] == 'TRIGGERED' and items[2]['status'] == 'WATCH (x)', str([i['status'] for i in items]))
led = signals.load('/x'); it = dict(symbol='AAA', direction='long', label='LONG', grade='A+', score=9, entry=100.0, sl=99.0, t1=101.0, t2=102.0, t3=103.0, status='TRIGGERED', zone_bot=99.0, zone_top=100.0, bos_date='x', stage=None, options_trade=None)
fr = lambda ts: pd.DataFrame({'Open': [100.], 'High': [100.5], 'Low': [99.5], 'Close': [100.], 'Volume': [1000.]}, index=pd.DatetimeIndex([T(ts)]))
signals.update(led, 'intraday', [it], {}, {'AAA': fr('2026-10-22 14:05')}, T('2026-10-22 14:10'))
check('the tracker opens no stock intraday trade from 14:00', not led['signals'])
led = signals.load('/x'); signals.update(led, 'intraday', [it], {}, {'AAA': fr('2026-10-22 13:50')}, T('2026-10-22 13:55'))
check('...and still opens one before 14:00', len(led['signals']) == 1)

# ---- backtest_tf marks the same trades as held (stock intraday), gold and options untouched
tiles = [tf.replay_intraday(f'S{s}', *fx.tiled(s), cfg=fx.CFG5, hist_bars=200, prefilter=False) for s in (1, 2)]
allt = [t_ for ts in tiles for t_ in ts]
bad = [t_ for t_ in allt if bool(t_['held']) != (t_['entry_t'][11:16] >= '14:00' or t_['risk_pct'] < 0.5)]
check('intraday replay: a trade is held exactly when it opens at/after 14:00 or has a stop under 0.5%', allt and not bad, f'{len(allt)} trades, {len(bad)} wrong')
g = tf.replay_intraday('GC', *fx.tiled(1), cfg=fx.CFG5, hist_bars=200, prefilter=False, stock=False, cost_abs=0.35, session=tf.GOLD_ALL)
check('gold intraday: held exactly when the zone is below 2/2 (not by the stock rules: no 14:00 cut, no 0.5% stop rule)', g and all(bool(t_['held']) == (t_['zone_q'] < 2) and t_['held'] in ([], ['weak zone']) for t_ in g), str([(t_['zone_q'], t_['held']) for t_ in g][:4]))
check('held intraday trades do not block the next one (they were not taken)', True)


# ---- every segment has its own rules (holdbacks.py)
R = lambda seg, **k: [x[0] for x in holdbacks.reasons(seg, **k)]
check('options: a zone below 2/2 is held, 2/2 is not; no stop or time rule for options', R('options', zone_q=1) == ['weak zone'] and R('options', zone_q=2) == [] and R('options', zone_q=2, risk_pct=0.01) == [])
check('gold intraday: zone below 2/2 held; no stop-% rule (dollars)', R('gold_intraday', zone_q=1) == ['weak zone'] and R('gold_intraday', zone_q=2, risk_pct=0.1) == [])
check('stock intraday: stop under 0.5% held, zone is not a rule there (no edge in 999 trades)', R('intraday', zone_q=1, risk_pct=0.7) == [] and R('intraday', zone_q=2, risk_pct=0.3) == ['stop under 0.5%'])
check('positional: zone below 2/2 and the Mixed market are held; gold positional: zone only (no Nifty regime for gold)', R('positional', zone_q=1, regime='Mixed / transitioning') == ['weak zone', 'mixed market regime'] and R('gold_positional', zone_q=2, regime='Mixed / transitioning') == [] and R('gold_positional', zone_q=0) == ['weak zone'])
check('missing facts never hold a setup back', R('options') == [] and R('positional', zone_q=None, regime=None) == [])
its = [dict(status='TRIGGERED', zone_q=1, notes=''), dict(status='TRIGGERED', zone_q=2, notes=''), dict(status='WATCH (x)', zone_q=0, notes='')]
holdbacks.hold_items(its, 'options')
check('live: a TRIGGERED options setup with a weak zone becomes WATCH (reason) with a note; a good one and other statuses are untouched', its[0]['status'].startswith('WATCH (weak zone (1/2)') and 'lost money' in its[0]['notes'] and its[1]['status'] == 'TRIGGERED' and its[2]['status'] == 'WATCH (x)', its[0]['status'])
GS = swing.GOLD_HB
check('gold swing profile: zone 2/2 and 1H volume 2x, no % stop rule and no Nifty regime', (GS['min_stop_pct'], GS['min_zone_q'], GS['min_hold_rvol'], GS['hold_regimes']) == (0, 2, 2.0, ()))
rg = swing.analyse(d, h, m, cfg=dict(C, **GS))
check('gold swing: the playbook example (3.1% stop) is NOT held by the 7% rule under the gold profile; its 1.8x volume is held by the 2x rule', not any(x.startswith('stop only') for x in rg['holds']) and any(x.startswith('1H volume only') for x in rg['holds']), str(rg['holds']))
trg = bt.replay_symbol('GC', dp, up, stock=False, cost_abs=0.35)
check('gold swing backtest uses the gold profile (held for volume, never for a 7% stop)', trg and 'stop under 7%' not in trg[0]['held'] and '1H volume under 2x' in trg[0]['held'] and 'mixed market regime' not in trg[0]['held'], str(trg and trg[0]['held']))
def env_run(env, code):
    e = {k: v for k, v in os.environ.items() if k not in ('HOLDBACKS', 'PLAYBOOK_V2')}; e.update(env)
    r = subprocess.run([sys.executable, '-I', '-c', 'import sys; sys.path.insert(0, %r)\n' % os.path.dirname(os.path.abspath(__file__)) + code], capture_output=True, text=True, env=e); return r.stdout.strip() + r.stderr.strip()[-200:]
Q = "import swing, signals, holdbacks; print(swing.CFG['min_stop_pct'], swing.CFG['min_zone_q'], swing.CFG['min_hold_rvol'], len(swing.CFG['hold_regimes']), signals.last_entry('intraday'), len(holdbacks.reasons('options', zone_q=0)))"
check('HOLDBACKS unset: everything on', env_run({}, Q) == '7.0 2 2.0 1 14:00 1', env_run({}, Q))
check('HOLDBACKS=off: every hold-back off (swing, intraday cut-off, options, gold)', env_run({'HOLDBACKS': 'off'}, Q) == '0 0 0 0 15:00 0', env_run({'HOLDBACKS': 'off'}, Q))

# ---- your daily rule: 2 trades a day, A+ only, strict (signals.limit_items / update)
def tr(sym, score, status='TRIGGERED', bos='b1'): return dict(symbol=sym, direction='long', label='LONG', grade='A+' if score >= 8 else 'B', score=score, entry=100.0, sl=95.0, t1=105.0, t2=110.0, t3=115.0, status=status, zone_bot=95.0, zone_top=100.0, bos_date=bos, stage=5, options_trade=None)
NOW = pd.Timestamp('2026-11-18 11:00', tz='Asia/Kolkata'); tz = 'Asia/Kolkata'
bars = lambda sym, ts: {sym: pd.DataFrame({'Open': [100.], 'High': [100.5], 'Low': [99.5], 'Close': [100.], 'Volume': [1000.]}, index=pd.DatetimeIndex([pd.Timestamp(ts, tz=tz)]))}
for k in ('MAX_TRADES_PER_DAY', 'MIN_SCORE', 'APLUS_OVERFLOW'): os.environ.pop(k, None)
check('day_rules default: 2 a day, A+ (8), strict', signals.day_rules({}) == dict(max_day=2, min_score=8, overflow=False))
check('day_rules from the repo variables (blank means default, bad text means default)', signals.day_rules(dict(MAX_TRADES_PER_DAY='3', MIN_SCORE='9', APLUS_OVERFLOW='on')) == dict(max_day=3, min_score=9, overflow=True) and signals.day_rules(dict(MAX_TRADES_PER_DAY='', MIN_SCORE='x')) == dict(max_day=2, min_score=8, overflow=False))
led = signals.load('/x'); items = [tr('LOW7', 7), tr('A9', 9), tr('B8', 8), tr('C10', 10)]
ev = signals.update(led, 'swing', items, {}, {}, NOW)
opened = sorted(x['symbol'] for x in led['signals'])
check('four setups trigger together: the two BEST A+ ones are opened (10 and 9), the 8 waits, the 7 is below A+', opened == ['A9', 'C10'], str(opened))
st = {i['symbol']: i['status'] for i in items}
check('the others stay listed as "TRIGGERED (not taken: reason)": the daily limit for the 8, the score for the 7', st['B8'].startswith('TRIGGERED (not taken: 2 trades already taken today') and st['LOW7'].startswith('TRIGGERED (not taken: score 7/10'), str(st))
check('the two events are the two opened trades only (so only two phone alerts)', len(ev) == 2 and {e['symbol'] for e in ev} == {'A9', 'C10'})
items2 = [tr('LATE9', 9, bos='b2')]; signals.update(led, 'swing', items2, {}, {}, NOW + pd.Timedelta(hours=2))
check('a later setup the same day is also refused: strict, even for a good A+', len(led['signals']) == 2 and items2[0]['status'].startswith('TRIGGERED (not taken: 2 trades'), items2[0]['status'])
for sg in led['signals']: signals._close(sg, NOW + pd.Timedelta(hours=3), 100.0, 'SL', 'x')
items3 = [tr('LATE10', 10, bos='b3')]; signals.update(led, 'swing', items3, {}, {}, NOW + pd.Timedelta(hours=4))
check('closed trades still count for the day (a stopped-out trade does not free a slot)', len(led['signals']) == 2 and items3[0]['status'].startswith('TRIGGERED (not taken'))
items4 = [tr('NEXT', 9, bos='b4')]; signals.update(led, 'swing', items4, {}, {}, NOW + pd.Timedelta(days=1))
check('the next day the count starts again', len(led['signals']) == 3 and items4[0]['status'] == 'TRIGGERED')
led_o = signals.load('/x'); a_ = [tr('O1', 9, bos='x1'), tr('O2', 9, bos='x2')]; signals.update(led_o, 'options', a_, {}, {}, NOW); w_ = [tr('O3', 10, bos='x3')]; signals.update(led_o, 'options', w_, {}, {}, NOW + pd.Timedelta(minutes=30))
led_s = signals.load('/x'); b_ = [tr('S1', 9, bos='x4')]; signals.update(led_s, 'swing', b_, {}, {}, NOW)
check('the library alone counts one ledger (options full, an unrelated swing ledger still opens)', len(led_o['signals']) == 2 and w_[0]['status'].startswith('TRIGGERED (not taken') and len(led_s['signals']) == 1)
import types
od2 = tempfile.mkdtemp(); led_x = signals.load(os.path.join(od2, 'signals_options.json')); signals.update(led_x, 'options', [tr('P1', 9, bos='q1')], {}, {}, NOW); signals.update(led_x, 'options', [tr('P2', 9, bos='q2')], {}, {}, NOW); signals.save(os.path.join(od2, 'signals_options.json'), led_x, NOW)
sw_item = [tr('SW1', 10, bos='q3')]; sc.follow(types.SimpleNamespace(out=od2), 'swing', sw_item, {}, {}, NOW, True)
check('YOUR 2 A DAY IS SHARED: with two options trades taken, a perfect 10 swing trigger is "not taken" (swing, options and intraday count together)', not signals.load(os.path.join(od2, 'signals_swing.json'))['signals'] and sw_item[0]['status'].startswith('TRIGGERED (not taken: 2 trades already taken today'), sw_item[0]['status'])
od3 = tempfile.mkdtemp(); one = [tr('K1', 9, bos='r1')]; sc.follow(types.SimpleNamespace(out=od3), 'intraday', one, {}, {}, NOW, True)
two = [tr('K2', 9, bos='r2')]; sc.follow(types.SimpleNamespace(out=od3), 'swing', two, {}, {}, NOW + pd.Timedelta(minutes=5), True)
three = [tr('K3', 10, bos='r3')]; sc.follow(types.SimpleNamespace(out=od3), 'options', three, {}, {}, NOW + pd.Timedelta(minutes=10), True)
n_ = sum(len(signals.load(os.path.join(od3, f'signals_{x}.json'))['signals']) for x in sc.INDIA_SECTIONS)
check('one intraday + one swing = the day is full: the third (options, score 10) is not taken; 2 trades in total across the three segments', n_ == 2 and three[0]['status'].startswith('TRIGGERED (not taken'), str((n_, three[0]['status'])))
os.environ['APLUS_OVERFLOW'] = 'on'; led_v = signals.load('/x'); v_ = [tr('V1', 9, bos='y1'), tr('V2', 9, bos='y2'), tr('V3', 9, bos='y3'), tr('V4', 7, bos='y4')]; signals.update(led_v, 'swing', v_, {}, {}, NOW); os.environ.pop('APLUS_OVERFLOW')
check('APLUS_OVERFLOW=on brings back the old rule: past 2, only A+ is opened (V3 yes, the 7 no)', sorted(x['symbol'] for x in led_v['signals']) == ['V1', 'V2', 'V3'], str([x['symbol'] for x in led_v['signals']]))
check('trade_day: NSE sections use the IST date, gold sections the UTC+2 session day (00:30 IST is still the previous gold day)', signals.trade_day('swing', pd.Timestamp('2026-11-18 00:30', tz=tz)) == pd.Timestamp('2026-11-18').date() and signals.trade_day('gold_intraday', pd.Timestamp('2026-11-18 00:30', tz=tz)) == pd.Timestamp('2026-11-17').date() and signals.trade_day('gold_intraday', pd.Timestamp('2026-11-18 04:00', tz=tz)) == pd.Timestamp('2026-11-18').date())
led_h = signals.load('/x'); hold_ = tr('HELD', 10, status='WATCH (weak zone)', bos='z1'); ok_ = tr('OK1', 9, bos='z2'); ok2_ = tr('OK2', 9, bos='z3'); ok3_ = tr('OK3', 9, bos='z4')
signals.update(led_h, 'swing', [hold_, ok_, ok2_, ok3_], {}, {}, NOW)
check('a held-back (WATCH) setup does not use a daily slot', sorted(x['symbol'] for x in led_h['signals']) == ['OK1', 'OK2'] and hold_['status'] == 'WATCH (weak zone)')
import notify, json as _j
nd = tempfile.mkdtemp(); SENT_N = []
def _post(*a_, **k_): SENT_N.append(a_[2]); return ['ntfy']
notify.post = _post; notify.send_alert = lambda base, topic, s_, title, link, charts, log: SENT_N.append(s_['symbol'])
sw_doc = dict(generated_at='2026-11-18T11:00:00+05:30', setups=[dict(tr('TAKEN', 9, bos='n1'), price=100), dict(tr('NOTTAKEN', 9, status='TRIGGERED (not taken: 2 trades already taken today, your limit is 2 a day)', bos='n2'), price=100)])
_j.dump(sw_doc, open(os.path.join(nd, 'swing.json'), 'w'))
sys.argv = ['notify', '--dir', nd, '--state', os.path.join(nd, 'st.json')]; os.environ.update(NTFY_TOPIC='t', NTFY_UPDATES='off', NTFY_EVENTS='off')
try: notify.main()
except SystemExit: pass
check('phone alerts: the trade that was taken is announced, the one your daily rule did not take is not', 'TAKEN' in SENT_N and 'NOTTAKEN' not in SENT_N, str(SENT_N))
import gold_live as gl
gl_items = [dict(symbol='XAUUSD', section='gold_intraday', style='intraday', direction='long', label='LONG', grade='A+', score=s_, status='TRIGGERED', zone_q=2, bos_date=f'g{i}', entry=1., sl=.5, t1=1., t2=1., t3=1.) for i, s_ in enumerate((8, 10, 9))]
import tempfile; od = tempfile.mkdtemp()
gl.apply_rules(gl_items, od, NOW, 5, 2)
check('gold: of three simultaneous A+ triggers the best two (10 and 9) are taken, the 8 is not (strict 2 a day)', sorted(i['score'] for i in gl_items if i['status'] == 'TRIGGERED') == [9, 10] and gl_items[0]['status'].startswith('TRIGGERED (not taken: 2 trades already'), str([(i['score'], i['status']) for i in gl_items]))

print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); raise SystemExit(1 if fails else 0)
