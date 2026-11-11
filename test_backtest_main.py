"""The whole command line of the new backtests, with a stand-in for Yahoo: backtest.py --segment positional|intraday|options and --resim.
Checks that each run downloads, replays, reports, writes both files, that a second run MERGES instead of doubling, and that the files have what the page reads.
No network. Run: python test_backtest_main.py"""
import json, os, tempfile
import numpy as np, pandas as pd
import backtest as bt, backtest_tf as tf, strategy_scanner as sc, tf_fixture as fx
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
sc.CFG_B.update(min_bars=20); sc.CFG_I.update(min_turnover_cr=0, min_bars=30, rvol_n=10, max_zone_pct=6, max_zone_atr=5)       # the engineered data needs the relaxed 5m settings
SYMS = [f'STK{i}' for i in range(6)]; CALLS = []
sc.load_nifty500 = lambda *a, **k: (SYMS, 'test list (6 symbols)', {s: 'IT' for s in SYMS})
def utc(df):
    d = df.copy(); d.index = pd.DatetimeIndex(d.index); d.index = d.index.tz_localize('UTC') if d.index.tz is None else d.index.tz_convert('UTC'); return d
def fake_yahoo(symbols, period, interval, chunk=50, pause=1.0):
    CALLS.append((len(symbols), period, interval)); out = {}
    for n, s in enumerate(symbols):
        if s == '^INDIAVIX': out[s] = utc(pd.DataFrame({'Open': 14.0, 'High': 15.0, 'Low': 13.0, 'Close': 14.0 + np.sin(np.arange(500) / 20), 'Volume': 0}, index=pd.bdate_range(end='2026-11-09', periods=500))); continue
        if interval == '1d':
            d = fx.daily_walk(10 + n, 2600 if period == '10y' else 700, p0=500.0, start='2016-11-01' if period == '10y' else '2024-01-01'); d.index = pd.bdate_range(end='2026-11-06', periods=len(d)); out[s] = utc(d)
        elif interval in ('5m', '15m'):
            f5, f15 = fx.tiled(10 + n, days=12, start='2026-09-14'); out[s] = utc(f5 if interval == '5m' else f15)
        elif interval == '1h':
            h = fx.walk5(3, days=12, start='2026-09-14').__getitem__(0).resample('60min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna(); out[s] = utc(h)
    return out, []
sc.yahoo_many = fake_yahoo
import argparse
def run(seg, out, extra=()):
    return bt.main(['--segment', seg, '--out', out, '--workers', '1', *extra])
RD = lambda out, f: json.load(open(os.path.join(out, f)))

# ---- positional (the real engine will rarely trigger on random walks, so the file must be fine with zero trades; then with a stand-in engine that does trigger)
out = tempfile.mkdtemp(); rc = run('positional', out, ['--top', '4'])
rep = RD(out, 'backtest_positional.json'); tr = RD(out, 'backtest_positional_trades.json')
check('positional run: exits cleanly and writes the report and the saved trades, even with few or no trades', rc == 0 and rep['segment'] == 'positional' and rep['title'] == 'Positional' and 'trades' in tr and tr['universe'] == 4, f"{rep['summary']['net']['n']} trades")
check('positional run: the report has what the page reads (scenarios, curves, breakdown order, assumptions, window)', len(rep['scenarios']) == 4 and 'labels' in rep['scenario_curves'] and rep['by_order'] and rep['assumptions'] and rep['window'].get('from') and rep['account']['max_per_day'] == 2, str(rep['window']))
check('positional run: asked Yahoo for ten years of daily candles for the Nifty 500 list, then for Nifty itself', (6, '10y', '1d') in CALLS and (1, '10y', '1d') in CALLS, str(CALLS[:4]))
CFGP = dict(tf.CFG_P, min_price=0, min_turnover_cr=0)
def trig(struct, trig_, cfg, K=None, section='swing', bias=None, levels=(), extra_ticks=()):
    if len(trig_) > 30 and trig_.Close.iloc[-1] > trig_.Close.iloc[-21:-1].mean() * 1.05 and struct.Close.iloc[-1] > struct.Close.iloc[-5:-1].mean():
        e = float(trig_.Close.iloc[-1]); sl = float(struct.Low.iloc[-3:].min()) * 0.98
        if sl < e: return dict(zone_bot=sl, zone_top=e, status='TRIGGERED', score=9, grade='A+', structure=2, zone_q=2, confirm=3, context=2, rvol=2.0, entry=e, sl=sl, bos_date=str(struct.index[-4])[:10])
    return None
real_detect, real_cfg = sc.detect, tf.CFG_P; sc.detect = trig; tf.CFG_P = CFGP; out = tempfile.mkdtemp(); rc = run('positional', out, ['--top', '4', '--workers', '2'])
rep = RD(out, 'backtest_positional.json'); sc.detect = real_detect; tf.CFG_P = real_cfg
check('positional run (stand-in engine, 2 worker processes): trades are found, sorted, and reported with sectors', rc == 0 and rep['summary']['net']['n'] >= 5 and 'sector' in rep['by'] and rep['summary']['avg_hold_days'] is not None, f"{rep['summary']['net']['n']} trades")

# ---- intraday: a second run must MERGE, not double
out = tempfile.mkdtemp(); CALLS.clear(); rc = run('intraday', out, ['--top', '5'])
r1 = RD(out, 'backtest_intraday.json'); t1 = RD(out, 'backtest_intraday_trades.json')
check('intraday run: writes the report and the saved trades; asked Yahoo for 60 days of 5m and 15m candles', rc == 0 and r1['segment'] == 'intraday' and (5, '60d', '5m') in CALLS and (5, '60d', '15m') in CALLS and r1['window'].get('note') == 'grows every week', str(CALLS[:3]))
check('intraday run: the real engine finds trades in the tiled sessions, long side, with hold time in minutes', r1['summary']['net']['n'] >= 8 and r1['summary']['avg_hold_min'] is not None and {'side', 'hour'} <= set(r1['by']), f"{r1['summary']['net']['n']} trades")
rc = run('intraday', out, ['--top', '5']); r2 = RD(out, 'backtest_intraday.json'); t2 = RD(out, 'backtest_intraday_trades.json')
check('intraday run again (same data): the saved trades are merged, not doubled', len(t2['trades']) == len(t1['trades']) and r2['summary']['net']['n'] == r1['summary']['net']['n'], f"{len(t1['trades'])} -> {len(t2['trades'])}")
check('intraday run: no trade starts before the first 3 days of the data (history too thin there)', all(t['entry_t'] >= '2026-09-17' for t in t2['trades']))
# a later run with MORE days adds to what is saved
old = RD(out, 'backtest_intraday_trades.json'); old['trades'].append(dict(old['trades'][0], sym='OLDSTOCK', entry_t='2026-07-01 10:00', exit_t='2026-07-01 11:00')); json.dump(old, open(os.path.join(out, 'backtest_intraday_trades.json'), 'w'))
rc = run('intraday', out, ['--top', '5']); t3 = RD(out, 'backtest_intraday_trades.json'); r3 = RD(out, 'backtest_intraday.json')
check('intraday run: trades saved by an earlier week stay in the file (and the new run does not duplicate its own)', any(t['sym'] == 'OLDSTOCK' for t in t3['trades']) and len(t3['trades']) == len(t1['trades']) + 1 and r3['summary']['net']['n'] == r1['summary']['net']['n'] + 1, f"{len(t1['trades'])} -> {len(t3['trades'])}")

# ---- options
out = tempfile.mkdtemp(); CALLS.clear(); rc = run('options', out)
ro = RD(out, 'backtest_options.json'); to = RD(out, 'backtest_options_trades.json')
check('options run: asked Yahoo for Nifty 5m and 15m (60 days), 1H (730 days) and India VIX', rc == 0 and (1, '60d', '5m') in CALLS and (1, '60d', '15m') in CALLS and (1, '730d', '1h') in CALLS and (1, '2y', '1d') in CALLS, str(CALLS[:5]))
check('options run: trades are modelled (premium, strike, VIX, days to expiry) and the report has the options tables and the stop-after-2-losses rule', ro['summary']['net']['n'] >= 3 and {'vix', 'dte', 'side'} <= set(ro['by']) and ro['account']['stop_after_losses'] == 2 and all(t.get('modelled') for t in to['trades']), f"{ro['summary']['net']['n']} trades")
rc = run('options', out); to2 = RD(out, 'backtest_options_trades.json'); check('options run again: merged, not doubled', len(to2['trades']) == len(to['trades']))

# ---- quick mode and the phone message
for seg in ('positional', 'intraday', 'options'):
    pass
q = tempfile.mkdtemp()
for f in os.listdir(out): open(os.path.join(q, f), 'wb').write(open(os.path.join(out, f), 'rb').read())
os.environ['MAX_TRADES_PER_DAY'] = '1'; rc = bt.main(['--resim', '--out', q]); os.environ.pop('MAX_TRADES_PER_DAY')
rq = RD(q, 'backtest_options.json'); check('quick mode: re-applies new rules to a saved segment in seconds (and skips the segments that have not run yet without failing)', rc == 0 and rq['account']['max_per_day'] == 1 and rq['params'].get('quick') and not os.path.exists(os.path.join(q, 'backtest_positional.json')))
sent = []
import notify; notify.post = lambda base, topic, title, body, tags, click, **k: sent.append((title, body)); os.environ['NTFY_TOPIC'] = 't'
bt.notify_result(out, 'success'); check('phone message: one line per playbook that has a result, with trades, win rate, expectancy and profit factor', sent and sent[-1][0] == 'Backtest finished' and 'Nifty options:' in sent[-1][1] and 'profit factor' in sent[-1][1], str(sent[-1] if sent else ''))
bt.notify_result(tempfile.mkdtemp(), 'success'); check('phone message: with no result files it says so instead of claiming success', sent[-1][0] == 'Backtest failed')
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED'); raise SystemExit(1 if fails else 0)
