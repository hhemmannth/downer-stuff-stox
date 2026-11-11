"""Round 6: the A+ gate, the financial-year window, "2 a day, more only if A+" and gold (XAUUSD)
on its own session clock, end to end with a stand-in for Yahoo. No network. Run: python test_rules.py"""
import json, os, tempfile
for k in ('BACKTEST_FROM', 'MIN_SCORE', 'APLUS_OVERFLOW', 'GOLD_SYMBOL', 'GOLD_COST'): os.environ.pop(k, None)
import numpy as np, pandas as pd
import backtest as bt, backtest_tf as tf, strategy_scanner as sc, tf_fixture as fx
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
sc.CFG_B.update(min_bars=20); sc.CFG_I.update(min_turnover_cr=0, min_bars=30, rvol_n=10, max_zone_pct=6, max_zone_atr=5)       # the engineered data needs the relaxed 5m settings

# ---- 1. the window and the grade gate
r = bt.rules_from_env({})
check('defaults: current financial year (from 1 April 2026) and A+ only (score 8)', r == dict(window_from='2026-04-01', min_score=8), str(r))
check('repo variables: BACKTEST_FROM=all removes the window, MIN_SCORE changes the gate', bt.rules_from_env(dict(BACKTEST_FROM='all', MIN_SCORE='6')) == dict(window_from=None, min_score=6))
check('repo variables: a typo is ignored, never widening the test silently', bt.rules_from_env(dict(BACKTEST_FROM='not a date', MIN_SCORE='x')) == dict(window_from='2026-04-01', min_score=8))
check('a date in another format is read correctly', bt.rules_from_env(dict(BACKTEST_FROM='2026-07-01'))['window_from'] == '2026-07-01')
T = lambda d, sc_, r_=1.0, sym='S', closed=True: dict(sym=sym, sector='IT', grade=sc.grade(sc_), score=sc_, structure=2, zone_q=2, confirm=3, context=2, entry_t=d, exit_t=d[:10] + ' 15:00', entry=100.0, sl=97.0, risk_pct=3.0,
                                                     outcome='TARGET' if r_ > 0 else 'SL', r=r_, r_net=r_ - 0.05, hold_days=1, closed=closed, held=[], regime='Range-bound', weekday='Mon', rvol=1.6)
mix = [T('2026-03-20 10:15', 10), T('2026-04-01 10:15', 9), T('2026-05-04 10:15', 7), T('2026-06-01 10:15', 8, -1.0), T('2026-06-02 10:15', 10, 2.0)]
g = bt.gate(mix)
check('gate: drops trades before 1 April 2026 and anything below A+', [t['entry_t'][:10] for t in g] == ['2026-04-01', '2026-06-01', '2026-06-02'])
rep = bt.report(mix, window={'from': '2024-01-01', 'to': '2026-11-06'}, universe=1)
check('report: counts only A+ trades in the window, and says so on the page', rep['summary']['net']['n'] == 3 and rep['rules']['min_score'] == 8 and 'A+ only' in rep['rules']['text'] and '01 Apr 2026' in rep['rules']['text'], rep['rules']['text'])
check('report: the window shown starts at 1 April 2026, not at the start of the downloaded history', rep['window']['from'] == '2026-04-01')
check('report: no "by grade" table (everything is A+); the score table splits 8 / 9 / 10 instead', 'grade' not in rep['by'] and [x['k'] for x in rep['by']['score']] == ['10', '9', '8'])
check('report: the four views are all A+, with your rules and a strict 2 a day side by side', [x['key'] for x in rep['scenarios']] == ['all', 'ap', 'ap2', 'p10'] and set(rep['scenario_curves']['series']) == {'all', 'ap', 'ap2', 'p10'})
check('report: the "your rules" view carries its own trade log', isinstance(rep['scenarios'][1].get('log'), list) and len(rep['scenarios'][1]['log']) == rep['scenarios'][1]['n'])
op = bt.report(mix + [T('2026-11-05 10:15', 9, 0.0, 'OPENX', closed=False)], universe=1)
check('report: trades still open are listed separately (not counted in the results)', [x['sym'] for x in op['open_now']] == ['OPENX'] and op['summary']['net']['n'] == 3)
acct = bt.account_from_env(dict(APLUS_OVERFLOW='off'))
check('repo variable APLUS_OVERFLOW=off makes it a strict 2 a day', acct['aplus_overflow'] is False and bt.account_from_env({})['aplus_overflow'] is True)

# ---- 2. the swing replay skips below-A+ and pre-window setups by itself (not only in the report)
import playbook_fixture as pf
d, h, _ = pf.frames(vol=5_000_000)
rows, t_, last = [], h.index[-1], float(h.Close.iloc[-1])
for c in [1078 + 9 * i for i in range(1, 14)]:
    t_ = t_ + pd.Timedelta(hours=1)
    if t_.hour > 15 or (t_.hour == 15 and t_.minute > 15): t_ = (t_ + pd.Timedelta(days=1)).normalize().tz_localize(None).tz_localize(h.index.tz) + pd.Timedelta(hours=9, minutes=15)
    while t_.weekday() >= 5: t_ += pd.Timedelta(days=1)
    rows.append((t_, last, max(last, c) + 1, min(last, c) - 1, c, 400000)); last = c
up = pd.concat([h, pd.DataFrame([r[1:] for r in rows], columns=sc.COLS, index=pd.DatetimeIndex([r[0] for r in rows]))])
base = bt.replay_symbol('PBK', d, up, 'IT', {}, min_score=4)
check('swing replay: the playbook setup is an A+ trade (score 10)', len(base) == 1 and base[0]['score'] == 10, str([(t['score'], t['entry_t']) for t in base]))
check('swing replay: with a gate above its score, the replay itself skips it', bt.replay_symbol('PBK', d, up, 'IT', {}, min_score=11) == [])
late = pd.Timestamp(base[0]['entry_t'][:10]) + pd.Timedelta(days=1) if base else None
check('swing replay: a setup before the window start is never opened', base and bt.replay_symbol('PBK', d, up, 'IT', {}, min_score=8, start_at=late) == [])

# ---- 3. the intraday engine on the tiled sessions (the base the gold checks build on)
f5, f15 = fx.tiled(21, days=6, start='2026-09-14')
normal = tf.replay_intraday('STK', f5, f15, min_score=8, first_day=pd.Timestamp('2026-09-14', tz='Asia/Kolkata'))
check('engine finds A+ trades in the tiled sessions, all closed the same day by 15:15', len(normal) >= 3 and all(t['score'] >= 8 and t['closed'] and t['exit_t'][:10] == t['entry_t'][:10] and t['exit_t'][11:16] <= '15:15' for t in normal), f'{len(normal)} trades')
check('scalping is gone: no scalping style in the engine', 'scalping' not in bt.SEGMENTS and 'gold_scalping' not in bt.SEGMENTS and not hasattr(tf, 'SCALP_TARGETS'))

# ---- 4. gold: its own session clock, shown in IST, dollar costs
shift = lambda f, hrs: f.set_axis(f.index + pd.Timedelta(hours=hrs))
g5, g15 = shift(f5, 8), shift(f15, 8)                                         # the same sessions moved to 17:15-23:30 IST (London + New York)
gold = tf.replay_intraday('XAUUSD', g5, g15, min_score=8, session=tf.GOLD_SESSION, first_day=pd.Timestamp('2026-09-14'), cost_abs=0.35, stock=False)
nse = tf.replay_intraday('STK', g5, g15, min_score=8, first_day=pd.Timestamp('2026-09-14', tz='Asia/Kolkata'))
check('gold: trades are found in the London and New York hours, with times shown in IST', len(gold) >= 3 and all('17:15' <= t['entry_t'][11:16] <= '23:59' for t in gold), str([t['entry_t'] for t in gold][:4]))
check('gold: the same candles get NO trade under the NSE session (09:30-15:00), so the sessions really differ', nse == [])
check('gold: costs are dollars per ounce turned into R (0.35 / stop distance)', all(abs((t['r'] - t['r_net']) - 0.35 / t['risk_usd']) < 0.011 for t in gold), str([(t['r'], t['r_net'], t['risk_usd']) for t in gold][:3]))
check('gold: each trade records its stop distance in dollars, for lot sizing on the page', all(t['risk_usd'] > 0 for t in gold))
m5, m15 = shift(f5, 9.75), shift(f15, 9.75)                                   # 19:00 IST to 01:15 IST: the trigger lands at 00:15 IST, after midnight
late_g = tf.replay_intraday('XAUUSD', m5, m15, min_score=8, session=tf.GOLD_SESSION, first_day=pd.Timestamp('2026-09-14'), stock=False)
okt = lambda t: t >= '21:00' or t <= '00:30'
check('gold across midnight IST: trades after midnight are still the same session, no entry after 00:30 IST, everything closed by 02:00 IST', len(late_g) >= 3 and any(t['entry_t'][11:16] < '01:00' for t in late_g) and all(okt(t['entry_t'][11:16]) for t in late_g) and all(t['exit_t'][11:16] <= '02:00' or t['exit_t'][11:16] >= '21:00' for t in late_g), str([(t['entry_t'], t['exit_t']) for t in late_g][:4]))
check('session day: 01:00 IST on Tuesday is still Monday\'s gold session (UTC+2 clock), but Tuesday for NSE',
      bt.session_day(pd.Timestamp('2026-09-15 01:00', tz='Asia/Kolkata'), tf.GOLD_TZ) == pd.Timestamp('2026-09-14') and bt.session_day(pd.Timestamp('2026-09-15 01:00', tz='Asia/Kolkata')) == pd.Timestamp('2026-09-15'))
check('session day: 04:00 IST (22:30 UTC) belongs to the NEXT gold session', bt.session_day(pd.Timestamp('2026-09-15 04:00', tz='Asia/Kolkata'), tf.GOLD_TZ) == pd.Timestamp('2026-09-15'))

# gold data helpers drop the candle that is still forming
now = pd.Timestamp('2026-11-11 20:00', tz='Asia/Kolkata')
idx = pd.date_range('2026-11-11 09:00', periods=6, freq='5min', tz='UTC')                  # 14:30 to 14:55 IST
fake = lambda syms, period, interval: ({syms[0]: pd.DataFrame({'Open': 1.0, 'High': 2.0, 'Low': 0.5, 'Close': 1.5, 'Volume': 10}, index=idx)}, [])
gi = tf.gold_intraday('GC=F', '60d', '5m', pd.Timestamp('2026-11-11 14:57', tz='Asia/Kolkata'), fetch=fake)
check('gold candles: converted to IST and the unfinished last 5m candle (14:55-15:00) dropped', str(gi.index.tz) == 'Asia/Kolkata' and len(gi) == 5 and str(gi.index[-1])[11:16] == '14:50')
didx = pd.DatetimeIndex(['2026-11-09', '2026-11-10', '2026-11-11'])
fd_ = lambda syms, period, interval: ({syms[0]: pd.DataFrame({'Open': 1.0, 'High': 2.0, 'Low': 0.5, 'Close': 1.5, 'Volume': 10}, index=didx)}, [])
gd = tf.gold_daily('GC=F', '3y', now, fetch=fd_)
check('gold daily: today\'s session (still trading at 20:00 IST) is left out', list(gd.index.strftime('%Y-%m-%d')) == ['2026-11-09', '2026-11-10'])
gd2 = tf.gold_daily('GC=F', '3y', pd.Timestamp('2026-11-12 04:00', tz='Asia/Kolkata'), fetch=fd_)
check('gold daily: after the session ends (04:00 IST next morning) it is included', len(gd2) == 3)
check('Yahoo symbols: GC=F is passed through as it is (no .NS added), stocks still get .NS', sc._yahoo('GC=F') == 'GC=F' and sc._yahoo('TCS') == 'TCS.NS' and sc._yahoo('^NSEI') == '^NSEI')
check('gold settings: GC=F and 0.35 dollars by default; repo variables can change them; bad values fall back', tf.gold_symbol({}) == 'GC=F' and tf.gold_cost({}) == 0.35 and tf.gold_cost(dict(GOLD_COST='0.5')) == 0.5 and tf.gold_cost(dict(GOLD_COST='x')) == 0.35)

# ---- 5. the command line, end to end, with a stand-in for Yahoo
SYMS = [f'STK{i}' for i in range(4)]; CALLS = []
sc.load_nifty500 = lambda *a, **k: (SYMS, 'test list', {s: 'IT' for s in SYMS})
def utc(df):
    x = df.copy(); x.index = pd.DatetimeIndex(x.index); x.index = x.index.tz_localize('UTC') if x.index.tz is None else x.index.tz_convert('UTC'); return x
def fake_yahoo(symbols, period, interval, chunk=50, pause=1.0):
    CALLS.append((tuple(symbols)[:1], period, interval)); out = {}
    for n, s in enumerate(symbols):
        gold_ = s == 'GC=F'
        if interval == '1d':
            dd = fx.daily_walk(30 + n, 2600 if period == '10y' else 750, p0=2400.0 if gold_ else 500.0); dd.index = pd.bdate_range(end='2026-11-06', periods=len(dd)); out[s] = utc(dd)
        elif interval in ('5m', '15m'):
            a5, a15 = fx.tiled(10 + n, days=10, start='2026-09-14')
            if gold_: a5, a15 = shift(a5, 8), shift(a15, 8)
            out[s] = utc(a15 if interval == '15m' else a5)
        elif interval == '1h':
            hh = fx.walk5(3, days=20, start='2026-09-14')[0].resample('60min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna(); out[s] = utc(hh)
    return out, []
sc.yahoo_many = fake_yahoo
RD = lambda out, f: json.load(open(os.path.join(out, f)))
run = lambda seg, out, extra=(): bt.main(['--segment', seg, '--out', out, '--workers', '1', *extra])
for seg in ('gold_intraday', 'gold_swing', 'gold_positional'):
    out = tempfile.mkdtemp(); CALLS.clear(); rc = run(seg, out)
    rf, tfile = bt.SEGMENTS[seg]['files']; ok = rc == 0 and os.path.exists(os.path.join(out, rf)) and os.path.exists(os.path.join(out, tfile))
    rp = RD(out, rf) if ok else {}
    check(f'{seg} run: exits cleanly, writes the report and the saved trades, A+ and the window on the page', ok and rp['segment'] == seg and rp['rules']['min_score'] == 8 and rp['window']['from'] >= '2026-04-01' and rp['assumptions'], f"rc={rc} n={(rp.get('summary') or {}).get('net', {}).get('n')}")
    if seg.startswith('gold'): check(f'{seg} run: data comes from GC=F, marked as gold, with the session table where it applies', any(c[0] == ('GC=F',) for c in CALLS) and rp.get('gold') is True and (seg != 'gold_intraday' or rp['summary']['net']['n'] == 0 or 'session' in rp['by']), str(CALLS[:3]))
out = tempfile.mkdtemp(); rc = run('gold_intraday', out); n1 = len(RD(out, 'backtest_gold_intraday_trades.json')['trades']); rc = run('gold_intraday', out); n2 = len(RD(out, 'backtest_gold_intraday_trades.json')['trades'])
check('gold intraday run again: trades are merged, not doubled', n1 == n2 and n1 >= 1, f'{n1} -> {n2}')
q = tempfile.mkdtemp()
for f in os.listdir(out): open(os.path.join(q, f), 'wb').write(open(os.path.join(out, f), 'rb').read())
os.environ['MIN_SCORE'] = '10'; rc = bt.main(['--resim', '--out', q]); os.environ.pop('MIN_SCORE')
check('quick mode covers the gold styles too, and re-applies a new gate in seconds', rc == 0 and RD(q, 'backtest_gold_intraday.json')['rules']['min_score'] == 10)

print('ALL PASSED' if not fails else f'{len(fails)} FAILED'); raise SystemExit(1 if fails else 0)
