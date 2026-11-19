"""Audit tests (19 Nov 2026), on top of test_audit.py and test_audit2.py: the worked examples B, C and D of the four corrections, the 08:50
readiness probe of the XAUUSD spot feed, the honest labels of the evaluation windows, the 15 Jan 2026 NSE holiday amendment, and the explicit
slippage field of paper records. No network (Twelve Data is served by a stand-in in its real answer format), no orders. Run: python test_audit3.py"""
import os; os.environ['PLAYBOOK_V2'] = 'off'; os.environ['GOLD_FEED_GAP_S'] = '0'
for k in ('BACKTEST_FROM', 'MIN_SCORE', 'GOLD_SESSIONS', 'GOLD_MAX_OPEN', 'GOLD_ACCOUNT', 'NTFY_TOPIC', 'TELEGRAM_BOT_TOKEN', 'STALE_CHECK', 'TWELVEDATA_API_KEY', 'GOLD_VOLUME_RULE'): os.environ.pop(k, None)
import datetime as dt, json, sys, tempfile
import swing; swing.GOLD_HB.update(min_zone_q=0, min_hold_rvol=0)                      # mechanics, as in test_gold_live.py (the hold-backs have their own tests)
import holdbacks; holdbacks.RULES['gold_intraday'] = {}
import pandas as pd
import backtest as bt, evaluation, gold_feed, gold_live as gl, greeks, loop, market_calendar, notify, readiness, signals as sg, strategy_scanner as sc, tf_fixture as fx
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
sc.CFG_B.update(min_bars=20); sc.CFG_I.update(min_turnover_cr=0, min_bars=30, rvol_n=10, max_zone_pct=6, max_zone_atr=5)
notify.post = lambda *a, **k: ['ntfy']
IST = 'Asia/Kolkata'; HERE = os.path.dirname(os.path.abspath(__file__))

def td_json(f, interval, symbol='XAU/USD', quote='US Dollar'):
    """A frame served exactly the way Twelve Data answers (UTC datetimes, strings, meta block)."""
    if f is None: return {'status': 'error', 'code': 400, 'message': 'No data is available on the specified dates'}
    idx = pd.DatetimeIndex(f.index); idx = idx.tz_convert('UTC') if idx.tz is not None else idx
    fmt = '%Y-%m-%d' if interval == '1d' else '%Y-%m-%d %H:%M:%S'
    vals = [dict(datetime=t.strftime(fmt), open=str(r.Open), high=str(r.High), low=str(r.Low), close=str(r.Close), **({'volume': str(r.Volume)} if 'Volume' in f else {})) for t, r in zip(idx, f.itertuples())]
    return dict(meta=dict(symbol=symbol, interval=interval, currency_base='Gold Spot', currency_quote=quote, type='Physical Currency'), values=vals, status='ok')
def stand_in(f5, f15, symbol='XAU/USD', log=None):
    def get(url):
        if log is not None: log.append(url)
        iv = {'5min': '5m', '15min': '15m', '1h': '1h', '1day': '1d'}[url.split('interval=')[1].split('&')[0]]
        return td_json({'5m': f5, '15m': f15}.get(iv), iv, symbol)
    return get

# ====================================================================== EXAMPLE B: a gold signal computed from XAUUSD spot, not futures
f5, f15 = fx.engineered('2026-11-11 15:00'); now = f5.index[-1] + pd.Timedelta(minutes=5, seconds=40)
urls = []; doc = gl.run(tempfile.mkdtemp(), tempfile.mkdtemp(), ('intraday',), now, stand_in(f5, f15, log=urls))
trig = [x for x in doc['styles']['intraday']['setups'] if x['status'] == 'TRIGGERED']
check('B: the gold scan asks the provider for XAU/USD only (every request URL), never GC=F or any other symbol', urls and all('symbol=XAU%2FUSD' in u for u in urls) and not any('GC' in u for u in urls), str(urls[:1]))
check('B: gold.json names the instrument: XAUUSD Spot, USD, USD per troy ounce, Spot Gold, source spot:Twelve Data:XAU/USD',
      doc['source'] == gold_feed.SOURCE_ID and doc['instrument']['instrument'] == 'XAUUSD Spot' and doc['instrument']['quote_currency'] == 'USD' and doc['instrument']['unit'] == 'USD per troy ounce' and doc['instrument']['market_type'] == 'Spot Gold')
check('B: one A+ trigger, and its entry is the close of the last spot 5-minute candle that had finished', len(trig) == 1 and abs(trig[0]['entry'] - round(float(f5.Close.iloc[-1]), 2)) < 0.011, str([(x['entry'], x['status']) for x in trig]))
lo, hi = float(f5.Low.min()), float(f5.High.max())
check('B: every level of the trade (stop, targets, zone) lies within the spot candles it was read from', all(lo - 50 <= trig[0][k] <= hi + 50 for k in ('sl', 't1', 'entry', 'zone_bot', 'zone_top') if trig[0].get(k) is not None), str({k: trig[0].get(k) for k in ('sl', 'entry', 't1', 'zone_bot', 'zone_top')}))
# Recalculated, not converted: the same candles 40 dollars higher (as futures sit above spot) give levels exactly 40 higher, i.e. the levels
# are computed from whatever spot candles are served, and nothing is stored or adjusted from an old futures level.
sh = lambda f, d: f.assign(Open=f.Open + d, High=f.High + d, Low=f.Low + d, Close=f.Close + d)
doc2 = gl.run(tempfile.mkdtemp(), tempfile.mkdtemp(), ('intraday',), now, stand_in(sh(f5, 40.0), sh(f15, 40.0)))
t2 = [x for x in doc2['styles']['intraday']['setups'] if x['status'] == 'TRIGGERED']
check('B: levels are recalculated from the candles served: +40 dollars of price gives entry, stop and T1 exactly +40 (no stored or converted level)',
      len(t2) == 1 and all(abs((t2[0][k] - trig[0][k]) - 40.0) < 0.011 for k in ('entry', 'sl', 't1')), str([(k, t2[0][k] - trig[0][k]) for k in ('entry', 'sl', 't1')] if t2 else 'no trigger'))
doc3 = gl.run(tempfile.mkdtemp(), tempfile.mkdtemp(), ('intraday',), now, stand_in(f5, f15, symbol='GC=F'))
check('B: the same candles answered as GC=F (futures) are refused: no setup, no price, "no gold recommendation"', doc3['feed']['ok'] is False and doc3['styles']['intraday']['setups'] == [] and 'GC=F' in doc3['feed']['reason'], doc3['feed']['reason'])
out4 = tempfile.mkdtemp(); doc4 = gl.run(out4, tempfile.mkdtemp(), ('intraday',), now + pd.Timedelta(minutes=90), stand_in(f5, f15))
led4 = [s for s in json.load(open(os.path.join(out4, 'signals_gold_intraday.json'))).get('signals', [])] if os.path.exists(os.path.join(out4, 'signals_gold_intraday.json')) else []
check('B: spot candles 90 minutes old in an open gold market: NO tracked trade is opened (stale-data fail-safe)', led4 == [] and not any(x['status'] == 'TRIGGERED' for x in doc4['styles']['intraday']['setups']), str([x['status'] for x in doc4['styles']['intraday']['setups']])[:200])
f5nv, f15nv = f5.assign(Volume=0.0), f15.assign(Volume=0.0)
doc5 = gl.run(tempfile.mkdtemp(), tempfile.mkdtemp(), ('intraday',), now, stand_in(f5nv, f15nv))
check('B: real spot has no exchange volume: with your volume rule as written (default), no gold trigger is taken, and the page says why', not any(x['status'] == 'TRIGGERED' for x in doc5['styles']['intraday']['setups']) and 'volume' in json.dumps(doc5.get('volume') or {}).lower(), json.dumps(doc5.get('volume'))[:200])

# ====================================================================== readiness at 08:50 probes the real spot feed (one request)
RN = dt.datetime(2026, 11, 19, 8, 50, tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)))
ok = readiness.check_gold_feed({'TWELVEDATA_API_KEY': 'k'}, lambda: (True, 'XAU/USD spot answered and passed the checks'))
bad = readiness.check_gold_feed({'TWELVEDATA_API_KEY': 'k'}, lambda: (False, 'the feed answered for "GC=F", not XAU/USD'))
nokey = readiness.check_gold_feed({}, lambda: (True, 'never called'))
check('readiness: key set and the spot answer passes validation -> OK', ok[0] == readiness.OK)
check('readiness: key set but the answer fails validation (e.g. GC=F) -> FAIL, gold recommendations OFF', bad[0] == readiness.FAIL and 'OFF' in bad[2] and 'GC=F' in bad[2])
check('readiness: no key -> WARN, gold OFF, the probe is not even called', nokey[0] == readiness.WARN and 'OFF' in nokey[2])
import numpy as np
_c = 4050 + np.cumsum(np.random.default_rng(7).normal(0, 4, 24)); _o = np.r_[_c[0], _c[:-1]]
h1 = pd.DataFrame({'Open': _o, 'High': np.maximum(_o, _c) + 2, 'Low': np.minimum(_o, _c) - 2, 'Close': _c}, index=pd.date_range('2026-11-17 00:00', periods=24, freq='1h', tz='UTC'))   # smooth spot hours near 4,050 USD/oz
os_get = gold_feed._http; gold_feed._http = lambda url: td_json(h1, '1h')
try: okp, msgp = readiness.probe_gold({'TWELVEDATA_API_KEY': 'k'})
finally: gold_feed._http = os_get
check('readiness probe: one real-format request goes through gold_feed validation and reports the last spot close in USD/oz', okp is True and 'USD/oz' in msgp and 'XAU/USD' in msgp, msgp)
gold_feed._http = lambda url: td_json(h1, '1h', symbol='GC=F')
try: okf, msgf = readiness.probe_gold({'TWELVEDATA_API_KEY': 'k'})
finally: gold_feed._http = os_get
check('readiness probe: a futures answer fails the probe with the reason', okf is False and 'GC=F' in msgf, msgf)

# ====================================================================== EXAMPLE C: theoretical options, separated from actual results
src_bt = open(os.path.join(HERE, 'backtest.py')).read(); src_lab = open(os.path.join(HERE, 'site', 'js', 'lab.js')).read()
check('C: the options report is classified theoretical_simulation with a written methodology (never historical performance)', "out['evidence'] = 'theoretical_simulation'" in src_bt and 'OPTIONS_METHOD' in src_bt)
check('C: the phone summary reads the class from the result file and labels options THEORETICAL, estimated premiums', "ev = r.get('evidence')" in src_bt and "(THEORETICAL, estimated premiums)" in src_bt)
check('C: the Backtest lab shows a THEORETICAL banner on the options tab', 'THEORETICAL' in src_lab)

# ====================================================================== honest evaluation windows
sp = evaluation.split([dict(entry_t='2025-06-02 10:15', closed=True, score=9, r_net=1.0), dict(entry_t='2026-06-02 10:15', closed=True, score=9, r_net=2.0), dict(entry_t='2026-12-01 10:15', closed=True, score=9, r_net=-1.0)])
W = sp['windows']
check('windows: development is in-sample; validation is independent of the hold-backs but NOT untouched (seen on 11 Nov 2026); only out of sample is untouched',
      W['development']['independent'] is False and W['validation']['independent'] is True and W['validation']['untouched'] is False and W['out_of_sample']['untouched'] is True and W['development']['untouched'] is False)
check('windows: the validation label and the note say it was seen once with the raw rules', '11 Nov 2026' in W['validation']['label'] and 'untouched' in sp['note'])
check('the Backtest lab pill reads untouched / independent of hold-backs / in-sample from those flags', "w.untouched ? 'untouched'" in src_lab and 'independent of hold-backs' in src_lab)

# ====================================================================== EXAMPLE D and the 15 Jan 2026 amendment
cal = market_calendar.load(); Y26, Y27 = cal['years']['2026'], cal['years']['2027']
check('D: 2026 is OFFICIAL (NSE circulars recorded), 2027 is AWAITING the official circular with no applied dates', Y26['status'] == 'official' and Y27['status'] == 'awaiting_official' and Y27['holidays'] == [])
check('D: the one 2027 date shown (Republic Day, Tue 26 Jan 2027) is labelled provisional and NOT applied', [(p['date'], p['applied']) for p in market_calendar.provisional()] == [('2027-01-26', False)])
check('D: 26 Jan 2027 therefore still counts as a trading day, and its Tuesday Nifty expiry is not moved by a guess', market_calendar.is_trading_day(dt.date(2027, 1, 26)) and greeks.weekly_expiry(dt.datetime(2027, 1, 21, 10, 0, tzinfo=greeks.IST), market_calendar.holidays()) == dt.date(2027, 1, 26))
check('amendment: Thu 15 Jan 2026 (Maharashtra municipal elections, NSE/CMTR/72260 and NSE/FAOP/72262) is a holiday: the loop and the backtests skip it', not market_calendar.is_trading_day(dt.date(2026, 1, 15)) and not loop.trading_day(dt.date(2026, 1, 15)) and '2026-01-15' in market_calendar.holidays())
check('amendment: 14 and 16 Jan 2026 stay trading days', market_calendar.is_trading_day(dt.date(2026, 1, 14)) and market_calendar.is_trading_day(dt.date(2026, 1, 16)))
check('weekends are never trading days, whatever the list says', not market_calendar.is_trading_day(dt.date(2026, 11, 21)) and not market_calendar.is_trading_day(dt.date(2026, 11, 22)))

# ====================================================================== paper records state their slippage assumption
it = dict(symbol='TCS', direction='long', label='LONG', grade='A+', score=9, status='TRIGGERED', entry=100.0, sl=90.0, t1=110.0, t2=120.0, t3=130.0, bos_date='2026-11-18', stage=5)
led = sg.load('/x'); os.environ['STALE_CHECK'] = 'off'
sg.update(led, 'swing', [it], {}, {'TCS': pd.DataFrame([[99, 101, 98, 100]], columns=['Open', 'High', 'Low', 'Close'], index=[pd.Timestamp('2026-11-18 10:15', tz=IST)])}, pd.Timestamp('2026-11-18 11:20', tz=IST))
sg.update(led, 'swing', [], {}, {'TCS': pd.DataFrame([[100, 101, 89, 90]], columns=['Open', 'High', 'Low', 'Close'], index=[pd.Timestamp('2026-11-18 11:15', tz=IST)])}, pd.Timestamp('2026-11-18 13:00', tz=IST)); os.environ.pop('STALE_CHECK')
P = led['paper'][0]
check('paper record: slippage is a separate, explicit field (0R) and the text says slippage must come out of the cost allowance', P['slippage_r'] == 0.0 and 'slippage' in P['slippage_assumption'] and P['r_gross'] == -1.0 and P['r_net'] == -1.03)

print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: ' + '; '.join(fails))
sys.exit(1 if fails else 0)
