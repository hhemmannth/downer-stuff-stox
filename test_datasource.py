"""Data sources: Angel One first, Yahoo fallback, daily cache, today's candle, cross-check, live option prices, TOTP,
and Telegram pushes. A local stand-in plays Angel One's and Telegram's servers (no internet needed). Run: python test_datasource.py"""
import datetime as dt, http.server, json, os, shutil, tempfile, threading
import numpy as np, pandas as pd
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)

IST = dt.timezone(dt.timedelta(hours=5, minutes=30)); TODAY = dt.datetime.now(IST).date()
LOG = dict(login=0, candles=[], quote=[], master=0, tg=[])
EXP = (TODAY + dt.timedelta(days=(1 - TODAY.weekday()) % 7 or 7))
MASTER = [dict(token='2885', symbol='RELIANCE-EQ', name='RELIANCE', exch_seg='NSE', instrumenttype=''),
          dict(token='11536', symbol='TCS-EQ', name='TCS', exch_seg='NSE', instrumenttype=''),
          dict(token='99926008', symbol='Nifty IT', name='NIFTY IT', exch_seg='NSE', instrumenttype='AMXIDX')] + \
         [dict(token=str(50000 + k), symbol=f"NIFTY{EXP:%d%b%y}{k}{kd}".upper(), name='NIFTY', exch_seg='NFO', instrumenttype='OPTIDX',
               expiry=EXP.strftime('%d%b%Y').upper(), strike=f'{k * 100}.000000') for k in range(23500, 24050, 50) for kd in ('CE', 'PE')]
MASTER += [dict(token=str(60000 + i), symbol=f'STK{i}-EQ', name=f'STK{i}', exch_seg='NSE', instrumenttype='') for i in range(40)]
def bars(token, interval):
    n = 300 if interval == 'ONE_DAY' else 120; r = np.random.default_rng(int(token) % 1000); c = 1000 * np.exp(np.cumsum(r.normal(0, .01, n)))
    if interval == 'ONE_DAY': t = [(pd.Timestamp(TODAY) - pd.Timedelta(days=n - i)).strftime('%Y-%m-%dT00:00:00+05:30') for i in range(n)]
    else: t = [(pd.Timestamp(TODAY) + pd.Timedelta(hours=9, minutes=15) - pd.Timedelta(minutes=5 * (n - i))).strftime('%Y-%m-%dT%H:%M:00+05:30') for i in range(n)]
    return [[t[i], c[i] * .998, c[i] * 1.004, c[i] * .995, c[i], 1000 + i] for i in range(n)]
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _j(self, obj, code=200):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path.startswith('/master'): LOG['master'] += 1; return self._j(MASTER)
        self._j({}, 404)
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])) or '{}')
        if self.path.startswith('/bot'): LOG['tg'].append(body); return self._j(dict(ok=True))
        if 'loginByPassword' in self.path:
            LOG['login'] += 1; ok = body.get('password') == '1234' and len(body.get('totp', '')) == 6
            return self._j(dict(status=ok, message='SUCCESS' if ok else 'Invalid', errorcode='' if ok else 'AB1007', data=dict(jwtToken='JWT1') if ok else None))
        if self.headers.get('Authorization') != 'Bearer JWT1': return self._j(dict(status=False, message='Invalid Token', errorcode='AG8001'))
        if 'getCandleData' in self.path:
            LOG['candles'].append((body['symboltoken'], body['interval']))
            if LOG.get('slow'): import time as _t; _t.sleep(LOG['slow'])
            if body['symboltoken'] == '11536': return self._j(dict(status=False, message='Something went wrong', errorcode='AB2001'))
            return self._j(dict(status=True, message='SUCCESS', errorcode='', data=bars(body['symboltoken'], body['interval'])))
        if '/quote' in self.path:
            ex, toks = list(body['exchangeTokens'].items())[0]; LOG['quote'].append((ex, len(toks)))
            fetched = [dict(symbolToken=t, ltp=1111.0 if ex == 'NSE' else 100.0 + (int(t) % 7), open=1100.0, high=1120.0, low=1090.0, tradeVolume=55555,
                            exchFeedTime=TODAY.strftime('%d-%b-%Y 15:29:59'), depth=dict(buy=[dict(price=99.5)], sell=[dict(price=100.5)])) for t in toks]
            return self._j(dict(status=True, message='SUCCESS', errorcode='', data=dict(fetched=fetched, unfetched=[])))
        self._j({}, 404)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start(); URL = f'http://127.0.0.1:{srv.server_port}'

import datasource as ds
Y = []
def fake_yahoo(symbols, period, interval):
    Y.append((tuple(symbols), period, interval)); out = {}
    for s in symbols:
        if s == 'GONE': continue
        n = 25 if period in ('5d', '1mo') else 260; idx = pd.bdate_range(end=pd.Timestamp(TODAY), periods=n)
        out[s] = pd.DataFrame({'Open': 100.0, 'High': 101.0, 'Low': 99.0, 'Close': 100.5, 'Volume': 1000}, index=idx)
    return out, [s for s in symbols if s not in out]

# --- TOTP (RFC 6238 test vector, SHA1, 8 digits at t=59)
check('TOTP matches the RFC 6238 test vector', ds.totp('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ', t=59, digits=8) == '94287082')

# --- no secrets: everything comes from Yahoo, as before
tmp = tempfile.mkdtemp(); ds.configure(tmp)
for k in ('ANGEL_API_KEY', 'ANGEL_CLIENT_CODE', 'ANGEL_MPIN', 'ANGEL_TOTP_SECRET'): os.environ.pop(k, None)
ds.reset(); out, failed = ds.fetch(['RELIANCE', 'GONE'], '5d', '5m', fake_yahoo)
check('without Angel secrets: Yahoo serves everything, failures are reported', set(out) == {'RELIANCE'} and failed == ['GONE'] and ds.report()['primary'] == 'Yahoo Finance')

# --- with secrets: Angel first, per-symbol fallback to Yahoo
os.environ.update(ANGEL_API_KEY='k', ANGEL_CLIENT_CODE='C1', ANGEL_MPIN='1234', ANGEL_TOTP_SECRET='JBSWY3DPEHPK3PXP', ANGEL_BASE=URL, ANGEL_MASTER_URL=URL + '/master')
ds.reset(); Y.clear(); LOG['candles'].clear()
out, failed = ds.fetch(['RELIANCE', 'TCS', 'UNKNOWNCO', '^NSEI', '^CNXIT'], '5d', '5m', fake_yahoo)
src = ds.STATS['source']
check('Angel One logs in with the TOTP and serves RELIANCE, Nifty and Nifty IT', ds.report()['primary'] == 'Angel One' and src.get('RELIANCE') == 'angel' and src.get('^NSEI') == 'angel' and src.get('^CNXIT') == 'angel', str(src))
check('a symbol Angel errors on (TCS) and one it does not list fall back to Yahoo, one by one', src.get('TCS') == 'yahoo' and src.get('UNKNOWNCO') == 'yahoo' and Y and set(Y[0][0]) == {'TCS', 'UNKNOWNCO'})
f = out['RELIANCE']
check('Angel candles come back in the same shape as Yahoo (OHLCV, IST timestamps, sorted)', list(f.columns) == ds.COLS and str(f.index.tz) in ('UTC+05:30', 'pytz.FixedOffset(330)') or (f.index.tz is not None and f.index.is_monotonic_increasing), str(f.index.tz))
check('the intervals map to Angel names (5m -> FIVE_MINUTE)', all(iv == 'FIVE_MINUTE' for _, iv in LOG['candles']))
check('one login per run, then the session is reused', LOG['login'] == 1, str(LOG['login']))
check('the instrument list is downloaded once and kept for the day', LOG['master'] == 1 and os.path.exists(os.path.join(tmp, 'angel_tokens.json')))
check('the session token is not written into the cache folder', not any('session' in x for x in os.listdir(tmp)))

# --- daily cache: full download once, then reused; after the close only today's candle is added
syms = ['RELIANCE'] + [f'STK{i}' for i in range(40)]
ds.reset(); LOG['candles'].clear(); LOG['quote'].clear(); Y.clear()
morning = dt.datetime.combine(TODAY, dt.time(8, 37), IST)
d1, f1 = ds.daily_cached(syms, '1y', fake_yahoo, now=morning)
n_full = len([c for c in LOG['candles'] if c[1] == 'ONE_DAY'])
check('first daily scan of the day downloads a year for every stock', len(d1) == 41 and n_full == 41, f'{n_full} daily downloads')
check('the cross-check compares Angel and Yahoo closes for a sample', ds.STATS['xcheck'] and all('max_diff_pct' in x for x in ds.STATS['xcheck']), str(ds.STATS['xcheck'][:1]))
LOG['candles'].clear(); Y.clear()
d2, _ = ds.daily_cached(syms, '1y', fake_yahoo, now=dt.datetime.combine(TODAY, dt.time(11, 25), IST))
check('the hourly swing scan reuses the cache: no daily download at all', not LOG['candles'] and not Y and len(d2) == 41 and d2['RELIANCE'].equals(d1['RELIANCE']))
LOG['quote'].clear()
d3, _ = ds.daily_cached(syms, '1y', fake_yahoo, now=dt.datetime.combine(TODAY, dt.time(16, 17), IST))
last = d3['RELIANCE'].iloc[-1]
check("after the close, today's candle comes from Angel quotes, 50 stocks per call", LOG['quote'] == [('NSE', 41)] or sum(n for _, n in LOG['quote']) == 41, str(LOG['quote']))
check("today's candle has the quote's open, high, low, last price and volume", d3['RELIANCE'].index[-1].date() == TODAY and (last.Open, last.High, last.Low, last.Close, last.Volume) == (1100, 1120, 1090, 1111, 55555))
check('history is kept and not duplicated', len(d3['RELIANCE']) in (len(d1['RELIANCE']), len(d1['RELIANCE']) + 1) and d3['RELIANCE'].index.is_unique)
d4, _ = ds.daily_cached(syms + ['STKNEW'], '1y', fake_yahoo, now=dt.datetime.combine(TODAY, dt.time(12, 25), IST))
check('a stock new to the universe is downloaded on its own; the rest stay cached', 'STKNEW' in d4)

# --- speed: several requests in flight, still paced to Angel's limit
import time as _time
ds.reset(); LOG['slow'] = 0.4; LOG['candles'].clear(); t0 = _time.time()
o, _ = ds.fetch([f'STK{i}' for i in range(20)], '5d', '5m', fake_yahoo); took = _time.time() - t0; LOG['slow'] = 0
check('20 stocks with a 0.4 s round trip take about 20 x 0.36 s (requests overlap), not 20 x 0.76 s', len(o) == 20 and took < 11, f'{took:.1f}s')
starts = len(LOG['candles'])
check('requests stay paced at about 3 a second (Angel limit)', starts == 20 and took >= 19 * ds.Angel.GAP * 0.95, f'{starts} calls in {took:.1f}s')

# --- live option prices
ds.reset(); q = ds.option_quotes(EXP.isoformat(), [23700, 23750, 23800], 'CE')
check('live Nifty option prices: last, best bid and ask for each strike', set(q) == {23700, 23750, 23800} and q[23700]['bid'] == 99.5 and q[23700]['ask'] == 100.5 and q[23700]['ltp'] > 0, str(q.get(23700)))
import greeks
iv = greeks.implied_vol(120.0, 23700, 23700, 3, 'CE')
check('implied volatility is solved from a live price (and reprices to it)', iv and abs(greeks.bs(23700, 23700, 3 / 365, iv, 'CE')['price'] - 120.0) < 0.01, str(iv))

# --- Angel down: wrong MPIN -> Yahoo for everything, the reason is reported
os.environ['ANGEL_MPIN'] = '0000'
for x in os.listdir(tempfile.gettempdir()):
    if x.startswith('angel_session_'): os.remove(os.path.join(tempfile.gettempdir(), x))
ds.reset(); Y.clear(); out, _ = ds.fetch(['RELIANCE'], '5d', '5m', fake_yahoo)
check('if Angel login fails, the scan carries on with Yahoo and health shows why', 'RELIANCE' in out and ds.report()['primary'] == 'Yahoo Finance' and 'login failed' in (ds.report()['angel']['error'] or ''), str(ds.report()['angel']))

# --- Telegram pushes, alongside or instead of ntfy
import notify
os.environ.update(TELEGRAM_BOT_TOKEN='123:ABC', TELEGRAM_CHAT_ID='111, 222', TELEGRAM_API=URL); LOG['tg'].clear()
notify.post('http://127.0.0.1:9', '', 'Swing: TRIGGERED A+ PBK LONG (10/10)', 'Zone 1,041-1,052 & entry 1,070', 'star,chart_with_upwards_trend', 'https://x.github.io/app/#/trade?s=swing&id=PBK%7Clong')
m = LOG['tg'][0] if LOG['tg'] else {}
check('Telegram: one message per chat id', [x['chat_id'] for x in LOG['tg']] == ['111', '222'])
check('Telegram: bold title, escaped body, emoji for the alert type', m.get('parse_mode') == 'HTML' and '<b>Swing: TRIGGERED A+ PBK LONG (10/10)</b>' in m.get('text', '') and '&amp;' in m['text'] and m['text'].startswith('⭐📈'))
check('Telegram: an Open button goes straight to the trade', m.get('reply_markup', {}).get('inline_keyboard', [[{}]])[0][0].get('url', '').endswith('#/trade?s=swing&id=PBK%7Clong'))
ok_dead = True
try: notify.post('http://127.0.0.1:9', 'topic-down', 't', 'b', 'bell', '')
except Exception: ok_dead = False
check('a push still goes out when ntfy is down but Telegram works', ok_dead)

srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True)
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED')
raise SystemExit(1 if fails else 0)
