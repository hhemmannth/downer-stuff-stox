"""Audit tests, part 2 (18 Nov 2026): XAUUSD spot gold, frozen strategy versions and unbiased evaluation, paper-trade immutability,
theoretical options labelling, and the central NSE holiday calendar. Expected values are worked out here, not taken from the code.
No network (the spot feed is served from recorded JSON in Twelve Data's own shape), no orders. Run: python test_audit2.py"""
import glob, json, os, re, sys, tempfile
for k in ('STALE_CHECK', 'GOLD_MAX_JUMP_PCT', 'GOLD_VOLUME_RULE', 'TWELVEDATA_API_KEY', 'GOLD_SYMBOL', 'BACKTEST_VALIDATION_FROM'): os.environ.pop(k, None)
os.environ['GOLD_FEED_GAP_S'] = '0'
import datetime as dt
import numpy as np, pandas as pd
import gold_feed, backtest as bt, backtest_tf as tf, signals as sg, publish, validation, evaluation, strategy_config, market_calendar, greeks, loop, newsfeed
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
IST = 'Asia/Kolkata'; T = lambda s: pd.Timestamp(s, tz=IST)
HERE = os.path.dirname(os.path.abspath(__file__))

def td(rows, interval='5min', symbol='XAU/USD', quote='US Dollar', base='Gold Spot', typ='Physical Currency', start='2026-11-18 08:00', freq='5min', vol=True):
    idx = pd.date_range(start, periods=len(rows), freq=freq, tz='UTC'); fmt = '%Y-%m-%d' if interval == '1day' else '%Y-%m-%d %H:%M:%S'
    vals = [dict(datetime=t.strftime(fmt), open=str(o), high=str(h), low=str(l), close=str(c), **({'volume': '0'} if vol else {})) for t, (o, h, l, c) in zip(idx, rows)]
    return dict(meta=dict(symbol=symbol, interval=interval, currency_base=base, currency_quote=quote, type=typ), values=vals, status='ok')
walk = lambda n, p0=4000.0, s=1: [(p0 + i * s, p0 + i * s + 1.5, p0 + i * s - 1.2, p0 + i * s + 0.6) for i in range(n)]
NOW = T('2026-11-18 16:00')              # 10:30 UTC: the last 5m candle of the 08:00 UTC series below ends 10:00 UTC... see each case

# ====================================================================== GOLD: identity, validation, no futures
f = gold_feed.parse(td(walk(24)), '5m', now=T('2026-11-18 15:28'))
check('spot: a clean XAU/USD answer becomes candles tagged XAUUSD Spot / USD / USD per troy ounce / spot source',
      len(f) == 23 and f.attrs['source'] == gold_feed.SOURCE_ID and f.attrs['instrument']['instrument'] == 'XAUUSD Spot' and f.attrs['instrument']['unit'] == 'USD per troy ounce' and f.attrs['instrument']['quote_currency'] == 'USD', f'{len(f)} candles')
check('spot: timestamps arrive in UTC and are converted to IST (08:00 UTC = 13:30 IST)', str(f.index.tz) == IST and str(f.index[0])[11:16] == '13:30')
check('spot: the unfinished last candle is dropped (the 15:25-15:30 IST candle is still forming at 15:28 IST)', f.index[-1] == T('2026-11-18 15:20'), str(f.index[-1]))
def refused(js, iv='5m', now=T('2026-11-18 15:35')):
    try: gold_feed.parse(js, iv, now); return ''
    except gold_feed.FeedError as ex: return str(ex)
check('identity: an answer for GC=F is refused', 'GC=F' in refused(td(walk(10), symbol='GC=F')))
check('identity: an answer for MCX gold mini (GOLDM) is refused', refused(td(walk(10), symbol='GOLDM')) != '')
check('identity: a quote in EUR is refused (USD only)', 'USD' in refused(td(walk(10), quote='Euro')))
check('identity: base currency silver (XAG) is refused', 'gold' in refused(td(walk(10), base='XAG')).lower())
check('identity: an instrument typed as a future is refused', 'future' in refused(td(walk(10), typ='Futures')).lower())
check('identity: an error answer (bad key, no data) is refused with the provider message', 'Invalid API key' in refused({'status': 'error', 'code': 401, 'message': 'Invalid API key'}))
check('OHLC: a price of 40 (not gold) is refused (plausible range 100 to 100,000)', 'outside' in refused(td(walk(10, p0=40.0, s=0.01))))
jump = walk(10); jump[6] = tuple(x * 1.09 for x in jump[6])
check('OHLC: a 9% jump between two 5-minute candles is refused (a switched or broken feed, e.g. a futures roll)', 'jump' in refused(td(jump)))
check('OHLC: candles stamped in the future are refused (wrong timezone)', 'future' in refused(td(walk(10), start='2026-11-18 11:00'), now=T('2026-11-18 15:35')))
bad = walk(12); bad[3] = (4003.0, 4001.0, 4005.0, 4003.5)                 # high below low
g = gold_feed.parse(td(bad), '5m', now=T('2026-11-18 15:35'))
import dataquality as dq
check('OHLC: an impossible candle (high below low) is removed before any rule sees it; what is left passes the invariant check', len(g) == 11 and dq.ohlc_problems(g) == [], f'{len(g)} candles')
check('volume: spot XAU/USD sends none, so the frame says volume_available = False (your volume rule then cannot be met)', f.attrs['volume_available'] is False)
d1 = gold_feed.parse(td(walk(5, s=3), interval='1day', start='2026-11-14', freq='1D'), '1d', now=T('2026-11-18 16:00'))
check('daily spot candles: one per UTC day, today (18 Nov, still trading) left out', list(d1.index.strftime('%m-%d')) == ['11-14', '11-15', '11-16', '11-17'])
try: gold_feed.fetch('5m', NOW, env={}); nokey = ''
except gold_feed.FeedError as ex: nokey = str(ex)
check('no key: the feed refuses with the reason and returns nothing (no Yahoo, no GC=F)', 'TWELVEDATA_API_KEY' in nokey, nokey)
fr, info = gold_feed.frames(('intraday',), NOW, None, env={})
check('no key: the live frame loader reports the feed as unusable and gives no candles at all', info['ok'] is False and fr == {}, info['reason'])
try: gold_feed.fetch_like(['GC=F'], '5d', '5m', get=lambda u: td(walk(10))); sub = False
except gold_feed.FeedError: sub = True
check('no silent substitution: asking the gold downloader for GC=F is refused', sub)
check('the gold symbol is XAU/USD whatever the old GOLD_SYMBOL repo variable says', tf.gold_symbol({'GOLD_SYMBOL': 'GC=F'}) == 'XAU/USD')

# static proof: no GC=F in any code path that produces gold data or levels (only in labels for archived history, tests and docs)
code = {p: open(p, encoding='utf-8').read() for p in glob.glob(os.path.join(HERE, '*.py')) + glob.glob(os.path.join(HERE, 'site', 'js', '*.js')) + glob.glob(os.path.join(HERE, '.github', 'workflows', '*.yml'))}
hits = []
for p, src in code.items():
    if os.path.basename(p).startswith('test_'): continue
    for i, line in enumerate(src.splitlines(), 1):
        if 'GC=F' in line and not re.search(r'historical|archiv|futures-based|FUTURES_SOURCES|refus|not COMEX|never COMEX|Never COMEX|ignored|old futures|Before: Yahoo GC=F|GOLD_SYMBOL|from COMEX futures \(GC=F\)|Never +GC=F|NOT GC=F|never GC=F|Older|old feed|old default|before 18 Nov', line, re.I):
            hits.append(f'{os.path.basename(p)}:{i}')
check('no GC=F left in the gold data or level pipeline (every remaining mention is a label for archived futures history)', not hits, ', '.join(hits[:8]))
check('workflows pass the spot key and no longer pass GOLD_SYMBOL', all('GOLD_SYMBOL' not in code[os.path.join(HERE, '.github', 'workflows', w)] and 'TWELVEDATA_API_KEY' in code[os.path.join(HERE, '.github', 'workflows', w)] for w in ('gold-loop.yml', 'backtest.yml', 'backtest-intraday.yml')))

# old futures results: archived, never merged with spot, never shown as XAUUSD statistics
od = tempfile.mkdtemp()
for fn in bt.SEGMENTS['gold_intraday']['files']: json.dump(dict(params=dict(source='GC=F'), trades=[dict(sym='XAUUSD', entry_t='2026-10-01 10:00')]), open(os.path.join(od, fn), 'w'))
moved = tf.archive_futures(od, 'gold_intraday')
check('old GC=F gold backtest files are moved unchanged to *.futures-archive.json, labelled, and nothing is deleted', sorted(moved) == sorted(x.replace('.json', '.futures-archive.json') for x in bt.SEGMENTS['gold_intraday']['files'])
      and all(json.load(open(os.path.join(od, m)))['archived']['reason'].startswith('historical futures-based') for m in moved) and json.load(open(os.path.join(od, moved[0])))['trades'][0]['entry_t'] == '2026-10-01 10:00')
check('after archiving, the next run starts fresh: no futures trade can be merged into the spot results', tf._load_prev(od, 'gold_intraday') == {})
json.dump(dict(params=dict(source=gold_feed.SOURCE_ID), trades=[]), open(os.path.join(od, bt.SEGMENTS['gold_swing']['files'][0]), 'w'))
check('a spot result is never archived', tf.archive_futures(od, 'gold_swing') == [])
check('the page refuses to show a futures-based gold result as XAUUSD statistics', "!isSpot((B.params || {}).source)" in code[os.path.join(HERE, 'site', 'js', 'lab.js')])

# ====================================================================== BACKTEST: frozen versions, hashing, no leakage, theoretical options, paper immutability
vf = tempfile.mktemp(suffix='.json'); base = strategy_config.build({})
v1 = strategy_config.freeze('9.0.0', 'test', env={}, path=vf, now=dt.datetime(2026, 11, 18, 17, 0, tzinfo=greeks.IST))
check('freeze: a version records its number, freeze time, configuration hash, full configuration and the rules in words', v1['version'] == '9.0.0' and v1['hash'] == strategy_config.digest(base) and v1['frozen_at'].startswith('2026-11-18T17:00') and set(v1['rules']) >= {'entry', 'stop', 'targets', 'timeframes', 'risk'} and v1['config'] == base)
try: strategy_config.freeze('9.0.0', 'again', env={}, path=vf); dup = False
except SystemExit: dup = True
try: strategy_config.freeze('9.0.1', 'nothing changed', env={}, path=vf); same = False
except SystemExit: same = True
check('freeze: a version number is never reused, and a new version is refused when nothing changed', dup and same)
check('hash: the same rules always give the same hash', strategy_config.digest(strategy_config.build({})) == v1['hash'])
check('hash: changing ONE rule (min score 8 -> 7 through MIN_SCORE) changes the hash', strategy_config.digest(strategy_config.build({'MIN_SCORE': '7'})) != v1['hash'])
check('hash: switching the secondary strategy on (PLAYBOOK_V2=on) changes the hash', strategy_config.digest(strategy_config.build({'PLAYBOOK_V2': 'on'})) != v1['hash'])
L = strategy_config.latest()
check('the repo has a frozen version 1.0.0 and the code\'s rules match it (CI fails when a rule changes without a new version)', L and L['version'] == '1.0.0' and strategy_config.current({})[2] is True, strategy_config.current({})[1][:16])

E = evaluation
check('windows are chronological and fixed: validation before 1 Apr 2026, development 1 Apr 2026 to the freeze, out of sample after it',
      [E.window_of(x, '2025-04-01', '2026-11-18 17:02') for x in ('2025-03-31 10:00', '2025-04-01 09:15', '2026-03-31 15:00', '2026-04-01 09:15', '2026-11-18 17:01', '2026-11-18 17:03')] == ['before_validation', 'validation', 'validation', 'development', 'development', 'out_of_sample'])
TR = [dict(entry_t='2025-06-02 10:15', closed=True, score=9, r_net=1.0, held=[]), dict(entry_t='2025-07-02 10:15', closed=True, score=9, r_net=-1.0, held=['weak zone']),
      dict(entry_t='2026-05-04 10:15', closed=True, score=9, r_net=2.0, held=[]), dict(entry_t='2026-12-01 10:15', closed=True, score=9, r_net=-1.0, held=[]), dict(entry_t='2026-06-01 10:15', closed=True, score=7, r_net=5.0, held=[])]
sp = E.split(TR, 8, '2025-04-01')
check('split: each window is scored ONLY on its own trades (validation +1.0R taken, -1.0R held; development +2.0R; out of sample -1.0R)', sp['windows']['validation']['taken']['avg'] == 1.0 and sp['windows']['validation']['held']['avg'] == -1.0 and sp['windows']['development']['taken']['avg'] == 2.0 and sp['windows']['out_of_sample']['taken']['avg'] == -1.0)
check('split: development is labelled in-sample, validation and out of sample independent; below-A+ trades never counted', sp['windows']['development']['independent'] is False and sp['windows']['validation']['independent'] and sp['windows']['out_of_sample']['independent'] and sp['windows']['development']['taken']['n'] == 1)
wf = E.walk_forward(TR, 3, 8)
check('walk-forward: consecutive 3-month test windows of the frozen rules, no re-fitting (each window = plain stats of its own trades)', [(x['test_from'], x['n'], x['avg']) for x in wf] == [('2025-06-01', 1, 1.0), ('2026-03-01', 1, 2.0), ('2026-12-01', 1, -1.0)], str([(x['test_from'], x['n'], x['avg']) for x in wf]))
check('replays now start at the validation window (1 Apr 2025) so independent trades exist; headline still counts your window', str(bt.replay_start(bt.rules_from_env({}))) [:10] == '2025-04-01')
rep_o = bt.report([dict(TR[2], risk_pct=0.4, sym='NIFTY', side='long', grade='A+', outcome='TARGET', r=2.1, exit_t='2026-05-04 11:00', entry=1.0, sl=0.9, structure=2, zone_q=2, confirm=2, context=2, hold_min=45, weekday='Mon')], segment='options')
check('options: the report is classified THEORETICAL SIMULATION with the source and limit of each number (no real option prices, BS premiums, VIX as IV)', rep_o['evidence'] == 'theoretical_simulation' and 'THEORETICAL' in rep_o['evidence_text'] and {m['item']: m['used'] for m in rep_o['methodology']}['Actual historical option prices'] is False and any('India VIX' in m['how'] for m in rep_o['methodology']))
rep_s = bt.report([dict(TR[2], risk_pct=8.0, sym='X', side='long', grade='A+', outcome='TARGET', r=2.1, exit_t='2026-05-05 11:00', entry=1.0, sl=0.9, structure=2, zone_q=2, confirm=2, context=2, hold_days=1, weekday='Mon', sector='IT', regime='x')], segment='swing')
check('swing: classified historical backtest, the headline marked in-sample, and the evaluation windows reported separately (never pooled)', rep_s['evidence'] == 'historical_backtest' and 'in-sample' in rep_s['in_sample_note'] and set(rep_s['evaluation']['windows']) == {'validation', 'development', 'out_of_sample'})
check('the phone summary labels options THEORETICAL', "THEORETICAL, estimated premiums" in code[os.path.join(HERE, 'backtest.py')])
check('the Backtest lab no longer claims the hold-backs "kept you out of worse trades" on the window they were chosen on', 'The rules kept you out of worse trades: keep them' not in code[os.path.join(HERE, 'site', 'js', 'lab.js')])

# paper trading: sealed original signal, append-only records
it = dict(symbol='TCS', direction='long', label='LONG', grade='A+', score=9, status='TRIGGERED', entry=100.0, sl=90.0, t1=110.0, t2=120.0, t3=130.0, bos_date='2026-11-18', stage=5, ticks=['Key level'])
led = sg.load('/x'); os.environ['STALE_CHECK'] = 'off'
sg.update(led, 'swing', [it], {}, {'TCS': pd.DataFrame([[99, 101, 98, 100]], columns=['Open', 'High', 'Low', 'Close'], index=[T('2026-11-18 10:15')])}, T('2026-11-18 11:20'))
s0 = led['signals'][0]; snap = json.dumps(s0['signal'], sort_keys=True)
check('a new tracked trade records the strategy version, the configuration hash and a sealed copy of the original signal', s0['strategy_version'] and len(s0['config_hash']) == 64 and s0['signal']['entry'] == 100.0 and s0['signal_hash'] == sg.seal(s0['signal']))
bars = pd.DataFrame([[100, 111, 99, 110], [110, 121, 109, 120], [120, 121, 99, 100]], columns=['Open', 'High', 'Low', 'Close'], index=pd.date_range('2026-11-18 11:15', periods=3, freq='1h', tz=IST))
sg.update(led, 'swing', [], {}, {'TCS': bars}, T('2026-11-18 15:00')); os.environ.pop('STALE_CHECK')
check('later candles move the stop, targets hit and last price, but never the sealed original signal', json.dumps(s0['signal'], sort_keys=True) == snap and s0['status'] == 'CLOSED' and s0['stop'] == 100.0)
P = led['paper']
check('the closed trade becomes ONE paper record: signal time, instrument, version, entry, stop, targets, exit price and time, observed prices, costs and slippage assumptions, net R, outcome',
      len(P) == 1 and P[0]['signal_time'] and P[0]['exit'] == 100.0 and P[0]['exit_time'] and P[0]['strategy_version'] == s0['strategy_version'] and P[0]['observed']['best'] == 121 and 'slippage' in P[0]['slippage_assumption'] and P[0]['slippage_r'] == 0.0 and P[0]['r_gross'] == 1.0 and P[0]['costs_r'] == 0.03 and P[0]['r_net'] == 0.97 and P[0]['outcome'] == 'TRAIL', json.dumps(P[0])[:240])
sg.update(led, 'swing', [], {}, {}, T('2026-12-30 10:00'))
check('paper records are never pruned (the closed trade itself leaves the 30-day list, its paper record stays)', not led['signals'] and len(led['paper']) == 1)
mine = dict(signals=[], paper=[dict(P[0], r_net=99.0)]); theirs = dict(signals=[], paper=[P[0]])
check('publishing never rewrites a paper record: the copy already published wins over a changed one', publish.merge_ledger(mine, theirs)['paper'][0]['r_net'] == 0.97)
od2 = tempfile.mkdtemp(); led['paper'][0]['signal']['entry'] = 95.0; json.dump(led, open(os.path.join(od2, 'signals_swing.json'), 'w'))
v = validation.run(od2, T('2026-11-21 10:00'), {})
check('System health catches a rewritten original signal (CRITICAL)', any(e['check'] == 'seal' and e['severity'] == 'CRITICAL' for e in v['errors']))

# ====================================================================== HOLIDAYS: one calendar, official 2026, 2027 awaiting
cal = market_calendar.load()
OFFICIAL_2026 = ['2026-01-15', '2026-01-26', '2026-03-03', '2026-03-26', '2026-03-31', '2026-04-03', '2026-04-14', '2026-05-01', '2026-05-28', '2026-06-26', '2026-09-14', '2026-10-02', '2026-10-20', '2026-11-10', '2026-11-24', '2026-12-25']
check('2026: exactly the 16 weekday holidays: the 15 of NSE circular NSE/CMTR/71775 (12 Dec 2025) plus 15 Jan 2026 added by NSE/CMTR/72260 and NSE/FAOP/72262 (12 Jan 2026), sources recorded', [h['date'] for h in cal['years']['2026']['holidays']] == OFFICIAL_2026 and 'NSE/CMTR/71775' in cal['years']['2026']['source'] and cal['years']['2026']['status'] == 'official' and {'NSE/CMTR/72260', 'NSE/FAOP/72262'} <= set(cal['years']['2026']['amendments'][0]['circulars']))
check('2026: every listed holiday is a weekday; the four weekend holidays are kept apart and change nothing', all(dt.date.fromisoformat(d).weekday() < 5 for d in OFFICIAL_2026) and all(dt.date.fromisoformat(h['date']).weekday() >= 5 for h in cal['years']['2026']['weekend_holidays']) and len(cal['years']['2026']['weekend_holidays']) == 4)
check('2027: marked AWAITING the official NSE circular, no dates applied, nothing invented', cal['years']['2027']['status'] == 'awaiting_official' and cal['years']['2027']['holidays'] == [] and not any(d.startswith('2027') for d in market_calendar.holidays()))
check('2027: the one provisional date (Republic Day) is labelled provisional and NOT applied: 26 Jan 2027 still counts as a trading day', market_calendar.provisional()[0]['date'] == '2027-01-26' and market_calendar.provisional()[0]['applied'] is False and market_calendar.is_trading_day(dt.date(2027, 1, 26)))
check('special sessions: Diwali Muhurat (Sun 8 Nov 2026) is recorded as a special session and is not scanned', any(s['kind'] == 'muhurat' and s['date'] == '2026-11-08' and s['scanned'] is False for s in market_calendar.special_sessions()))
check('weekends: Saturday and Sunday are never trading days; Guru Nanak Jayanti (Tue 24 Nov 2026) is closed; Mon 23 Nov is open', not market_calendar.is_trading_day(dt.date(2026, 11, 21)) and not market_calendar.is_trading_day(dt.date(2026, 11, 22)) and not market_calendar.is_trading_day(dt.date(2026, 11, 24)) and market_calendar.is_trading_day(dt.date(2026, 11, 23)))
check('holiday-aware runs: the loop, watchdog, digest and readiness (loop.trading_day) skip 24 Nov and 25 Dec 2026', not loop.trading_day(dt.date(2026, 11, 24)) and not loop.trading_day(dt.date(2026, 12, 25)) and loop.trading_day(dt.date(2026, 12, 24)))
hol = [h['date'] for h in newsfeed.load_events(os.path.join(HERE, 'events.json'))['holidays']]
check('holiday-aware expiry: the scanner\'s holiday list comes from the calendar, and the Nifty expiry of Tue 24 Nov 2026 moves to Mon 23 Nov', hol == OFFICIAL_2026 and greeks.weekly_expiry(dt.datetime(2026, 11, 19, 10, 0, tzinfo=greeks.IST), hol) == dt.date(2026, 11, 23))
check('one calendar: events.json no longer holds holiday dates, and no other code file hard-codes 2026 holiday dates', 'holidays' not in json.load(open(os.path.join(HERE, 'events.json')))
      and not [p for p, src in code.items() if not os.path.basename(p).startswith('test_') and any(d in src for d in ('2026-11-24', '2026-12-25', '2026-03-03'))])
check('readiness warns from 1 Dec when 2027 is missing, and FAILS from 1 Jan 2027 if it still is', market_calendar.check(dt.date(2026, 11, 18))[0] == 'ok' and market_calendar.check(dt.date(2026, 12, 1))[0] == 'warn' and market_calendar.check(dt.date(2027, 1, 4))[0] == 'fail')
import readiness
rc = readiness.check_calendar(dt.datetime(2026, 12, 5, 8, 50, tzinfo=greeks.IST)); rg = readiness.check_gold_feed({})
check('the 08:50 readiness message includes the holiday calendar and the XAUUSD spot feed status', rc[1] == 'NSE holiday calendar' and rc[0] == readiness.WARN and rg[1] == 'XAUUSD spot feed' and 'no futures fallback' in rg[2])

print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: ' + '; '.join(fails))
sys.exit(1 if fails else 0)
