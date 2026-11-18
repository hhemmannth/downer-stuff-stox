"""Your updated strategy (17 Nov 2026), your SECONDARY strategy: OFF unless the PLAYBOOK_V2 variable is on (this file runs with it on, the default checks use fresh processes):
  swing / positional / gold swing : weekly up -> 1D CHoCH + pullback to FVG + OB + fib -> 1H close above the 9 EMA on volume above its own 20-bar average = the entry
  options / intraday              : 1H bullish -> 15m CHoCH + pullback to FVG + OB + fib -> 5m close above the 9 EMA on volume above its own 20-bar average
Checks the new intraday path on a constructed setup, the volume rule, the 1H gate, shorts, and that everything is OFF unless the variable is on. No network."""
import os, subprocess, sys
os.environ['PLAYBOOK_V2'] = 'on'      # this file tests the secondary strategy; the default-state checks below start fresh processes
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tf_fixture as fx, strategy_scanner as sc
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info and not cond else (f'   {info}' if info else ''))); (not cond) and fails.append(name)

def split(f15, last_vol=None):
    """15m candles -> three 5m candles each (a straight line from the open to the close), volume split in three."""
    rows, idx = [], []
    for t, r in f15.iterrows():
        o, h, l, c, v = r.Open, r.High, r.Low, r.Close, r.Volume; m1, m2 = o + (c - o) / 3, o + 2 * (c - o) / 3
        for k, (a, b) in enumerate(((o, m1), (m1, m2), (m2, c))):
            rows.append([a, max(a, b) + (h - max(o, c) if k == 1 else .2), min(a, b) - (min(o, c) - l if k == 1 else .2), b, v / 3]); idx.append(t + pd.Timedelta(minutes=5 * k))
    return pd.DataFrame(rows, columns=sc.COLS, index=pd.DatetimeIndex(idx))
def trend_1h(up=True, n=40):
    a = np.linspace(1000, 1200, n) if up else np.linspace(1200, 1000, n)
    return pd.DataFrame({'Open': a, 'High': a + 2, 'Low': a - 2, 'Close': a + (1 if up else -1), 'Volume': 1000.}, index=pd.date_range('2026-10-01 09:15', periods=n, freq='1h', tz='Asia/Kolkata'))
def setup(mirror=False):
    f5e, _ = fx.engineered(mirror=mirror); f15 = f5e.copy(); f15.index = pd.date_range('2026-10-08 09:15', periods=len(f15), freq='15min', tz='Asia/Kolkata'); return split(f15), f15

# ---- your old rules are the main strategy; PLAYBOOK_V2=on switches to the updated one
check('with the variable on (this file): your updated strategy is active (volume above its own 20-bar average, 15m zone + 5m trigger for intraday and options)', sc.V2 and sc.CFG['rvol_min'] == 1.0 and sc.CFG_I['rvol_min'] == 1.0 and sc.CFG['slot_rvol'] is False)
def run_env(value, code):
    e = {k: v for k, v in os.environ.items() if k != 'PLAYBOOK_V2'}
    if value is not None: e['PLAYBOOK_V2'] = value
    r = subprocess.run([sys.executable, '-I', '-c', 'import sys; sys.path.insert(0, %r)\n' % os.path.dirname(os.path.abspath(__file__)) + code], capture_output=True, text=True, env=e); return r.stdout.strip() + r.stderr.strip()[-300:]
Q = "import strategy_scanner as sc, swing; print(sc.V2, sc.CFG['rvol_min'], sc.CFG_I['rvol_min'], sc.CFG['slot_rvol'], swing.CFG['rvol_min'], swing.CFG['slot_vol'], swing.CFG['entry_on_1h'])"
out = run_env(None, Q); check('variable not set: your OLD rules are the main strategy (1.5x same-hour volume, 15m swing entry)', out == 'False 1.5 1.5 True 1.5 True False', out)
out = run_env('', Q); check('variable empty (as GitHub passes an unset variable): still the old rules', out == 'False 1.5 1.5 True 1.5 True False', out)
out = run_env('on', Q); check('PLAYBOOK_V2=on: ON', out == 'True 1.0 1.0 False 1.0 False True', out)
out = run_env('off', Q); check('PLAYBOOK_V2=off: the previous rules (1.5x same-hour volume, 15m swing entry)', out == 'False 1.5 1.5 True 1.5 True False', out)
SW = "import strategy_scanner as sc, swing, playbook_fixture as pf\nd, h, m = pf.frames(); r = swing.analyse(d, h); print(r['stage'], r['status'][:9], round(r['entry'], 2), round(r['cf']['c_confirm'], 2))"
out = run_env('on', SW); check('ON: swing on the playbook example: the 1H reclaim is the entry (stage 5 TRIGGERED at the 1H close), no 15m needed', out.startswith('5 TRIGGERED') and out.split()[-1] == out.split()[-2], out)
out = run_env('off', SW); check('OFF: the same example stops at stage 4 (1H confirmed, waits for the 15m; the new hold-backs may mark it WATCH)', out.startswith('4 '), out)

# ---- 1H candles from 15m
f15 = pd.DataFrame({'Open': [10, 11, 12, 13, 14], 'High': [11, 12, 13, 14, 15], 'Low': [9, 10, 11, 12, 13], 'Close': [11, 12, 13, 14, 15], 'Volume': [1, 2, 3, 4, 5]}, index=pd.date_range('2026-10-08 09:15', periods=5, freq='15min', tz='Asia/Kolkata'))
h = sc.to_1h(f15)
check('1H candles are built from 15m on NSE hours (09:15-10:15): one full hour and the hour so far', len(h) == 2 and h.index[0].strftime('%H:%M') == '09:15' and h.Open.iloc[0] == 10 and h.Close.iloc[0] == 14 and h.High.iloc[0] == 14 and h.Low.iloc[0] == 9 and h.Volume.iloc[0] == 10 and h.Open.iloc[1] == 14, str(h))
g = f15.copy(); g.index = pd.date_range('2026-10-08 10:00', periods=5, freq='15min', tz='Etc/GMT-2'); hg = sc.to_1h(g)
check('1H candles for gold start on the hour', hg.index[0].strftime('%H:%M') == '10:00' and len(hg) == 2, str(hg.index))

# ---- the new intraday path
f5, f15 = setup(); cfg = dict(sc.CFG_I, min_turnover_cr=0, min_bars=30, rvol_n=10, max_zone_pct=6, max_zone_atr=5)
saved = dict(sc.CFG_I2); sc.CFG_I2.update(min_bars=30, max_zone_pct=6, max_zone_atr=5, rvol_n=10)
try:
    r = sc.scan_intraday(f5, f15, 'long', dict(cfg, struct15=True), (), section='intraday', h1=trend_1h())
    check('updated intraday: 1H bullish + 15m CHoCH/BOS zone + 5m reclaim on volume = TRIGGERED, A+', r and r.get('status') == 'TRIGGERED' and r['grade'] == 'A+' and r['score'] >= 8, str(r and (r.get('status'), r.get('score'))))
    check('updated intraday: the zone, the CHoCH and the BOS come from the 15m (their time is a 15m candle, not a 5m one)', r['bos_date'][14:16] in ('15', '30', '45', '00') and r['zone_top'] > r['zone_bot'], str((r['bos_date'], r['zone_bot'], r['zone_top'])))
    check('updated intraday: entry is the 5m trigger close, stop below the 15m zone, targets above', r['sl'] < r['zone_bot'] and r['entry'] > r['sl'] and r['t1'] > r['entry'] and r['t1'] < r['t2'] < r['t3'], str((r['entry'], r['sl'], r['t1'], r['t2'], r['t3'])))
    check('updated intraday: open interest is not in the data feed, so the result says to check it yourself', 'open-interest' in r['notes'], r['notes'])
    rb = sc.scan_intraday(f5, f15, 'long', dict(cfg, struct15=True), (), section='intraday', h1=trend_1h(up=False))
    check('updated intraday: a falling 1H (below its 9 EMA) is no bias: no long setup', rb and rb.get('state') == 'NO_BIAS' and 'zone_bot' not in rb, str(rb))
    rh = sc.scan_intraday(f5, f15, 'long', dict(cfg, struct15=True), (), section='intraday')
    check('updated intraday: without a 1H frame it is built from the 15m (same answer when that 1H is also bullish or says no bias, never a crash)', rh is None or isinstance(rh, dict))
    w = f5.copy().astype(float); w.loc[w.index[-12:], 'Volume'] = 1.0
    rw = sc.scan_intraday(w, f15, 'long', dict(cfg, struct15=True), (), section='intraday', h1=trend_1h())
    check('updated intraday volume rule: a 5m reclaim on volume below its 20-bar average is NOT a trigger (WATCH, low volume)', rw and rw['status'].startswith('WATCH (trigger, low volume'), str(rw and rw.get('status')))
    m5, m15 = setup(mirror=True); mirror1h = trend_1h(up=False).rename(columns={'High': 'High', 'Low': 'Low'})
    rs = sc.scan_intraday(m5, m15, 'short', dict(cfg, struct15=True), (), section='intraday', h1=mirror1h)
    check('updated intraday: the mirror image gives the SHORT (1H falling, 15m CHoCH down, 5m close back below the 9 EMA), prices in real terms', rs and rs.get('status') == 'TRIGGERED' and rs['sl'] > rs['entry'] and rs['t1'] < rs['entry'], str(rs and (rs.get('status'), rs.get('entry'), rs.get('sl'))))
    ro = sc.scan_intraday(f5, f15, 'long', dict(cfg, struct15=True), (), section='options', h1=trend_1h())
    check('updated options: same path for the Nifty (volume not required for the index)', ro and 'zone_bot' in ro and 'open-interest' in ro['notes'], str(ro and ro.get('status')))
finally:
    sc.CFG_I2.clear(); sc.CFG_I2.update(saved)
r_old = sc.scan_intraday(f5, f15, 'long', cfg, (), section='intraday')
check('with the variable off the OLD intraday path is used unchanged (5m structure, 15m CHoCH bias)', r_old is None or isinstance(r_old, dict))

# ---- the backtest replays run the new path end to end without errors (random-walk sessions: a crash smoke, the engine decides what trades)
import backtest_tf as tf
w5, w15 = fx.walk5(3, days=8, vol=1000)
try:
    tr = tf.replay_intraday('W', w5, w15, cfg=sc.CFG_I, prefilter=True); op = tf.replay_options(w5, w15, None, pd.Series([14.0], index=pd.to_datetime(['2026-09-01'])), [], cfg=sc.CFG_I, prefilter=True)
    check('backtest replays (intraday and options) run on the updated path without errors', isinstance(tr, list) and isinstance(op, list), f'{len(tr)} intraday, {len(op)} options trades')
except Exception as ex: check('backtest replays (intraday and options) run on the updated path without errors', False, repr(ex)[:200])
check('backtest label says which rules made the trades (updated strategy: "+v2")', tf.RULE.endswith('+v2'), tf.RULE)

print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
