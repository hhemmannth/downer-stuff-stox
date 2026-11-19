"""XAUUSD SPOT gold candles: the only gold data the scanner, the tracker and the gold backtests use (18 Nov 2026).

Before: Yahoo GC=F, the COMEX front-month gold FUTURE, labelled XAUUSD. Futures trade above spot by the basis and the continuous series
jumps at every contract roll, so every gold level was a futures level. Now:

  Provider    Twelve Data, symbol XAU/USD (gold spot, US dollars per troy ounce). Free Basic plan: 8 requests a minute, 800 a day,
              needs a free API key in the repo secret TWELVEDATA_API_KEY (no card). No key, no gold recommendations.
  Why not Yahoo XAUUSD=X: rejected. Users reported in 2022 that Yahoo stopped carrying gold spot under XAUUSD=X, and the gold symbol that
              works on Yahoo is GC=F, the futures contract, which is refused here. A feed that cannot be shown to be spot is not used, and it is never a fallback.
  Never       GC=F, MGC, any '=F' or futures symbol, MCX gold, gold mini. There is NO fallback to any other instrument: if the spot feed
              is missing, fails validation or is stale, gold says 'XAUUSD SPOT DATA UNAVAILABLE: NO GOLD RECOMMENDATION'.

Every download is validated before a rule sees it: the answer must name XAU/USD, quote USD, not be a futures contract; candles pass
dataquality.sanitize (duplicates, order, impossible candles); prices must be plausible (100 to 100,000 dollars) and continuous
(no 6% jump between consecutive intraday candles, 12% daily: a jump that size is a broken or switched feed, not gold); the unfinished
last candle is dropped; timestamps are requested in UTC and converted to IST.

Volume: spot gold trades over the counter, so there is no exchange volume. If the provider sends none, Volume is 0 and the frame is marked
volume_available=False: your 1.5x volume rule then cannot be met and no gold trigger is taken (GOLD_VOLUME_RULE=off runs gold without
that rule: your decision, it changes your strategy)."""
import datetime as dt, json, os, re, time, urllib.parse, urllib.request
import numpy as np, pandas as pd
import dataquality

PROVIDER = 'Twelve Data'; SYMBOL = 'XAU/USD'; BASE = 'https://api.twelvedata.com'
LABEL = 'XAUUSD'
INSTRUMENT = dict(instrument='XAUUSD Spot', symbol=SYMBOL, quote_currency='USD', unit='USD per troy ounce', market_type='Spot Gold', provider=PROVIDER,
                  source=f'{PROVIDER} {SYMBOL} spot, checked on every download (symbol, quote currency, not a futures contract)')
SOURCE_ID = f'spot:{PROVIDER}:{SYMBOL}'                 # stored on every gold trade and backtest file; anything else is 'historical futures-based'
FUTURES_SOURCES = ('GC=F', 'MGC=F', 'COMEX')            # what older files say they came from
FORBIDDEN = re.compile(r'(=F$|^/?GC[A-Z0-9]*$|^/?MGC|COMEX|FUTURE|MCX|GOLDM|GOLDMINI)', re.I)
DAY_TZ = 'UTC'                                          # daily spot candles are requested in UTC: one candle = one UTC day
INTERVAL = {'1m': '1min', '5m': '5min', '15m': '15min', '1h': '1h', '1d': '1day'}
MINUTES = {'1m': 1, '5m': 5, '15m': 15, '1h': 60, '1d': 1440}
MAX_JUMP = {'1d': 0.12}                                 # largest believable move between consecutive candles; intraday default 6%
IST = 'Asia/Kolkata'
STATE = dict(last=0.0, calls=0)

class FeedError(Exception): pass

def api_key(env=None):
    return str((env if env is not None else os.environ).get('TWELVEDATA_API_KEY', '') or '').strip()

def is_futures(source):
    """True for anything that is not the verified spot source: GC=F, other futures, and old files that recorded no source (the old default was GC=F)."""
    return not is_spot(source)

def is_spot(source): return str(source or '') == SOURCE_ID

def _http(url, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': 'DownerStuff/1.0', 'Accept': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8'))

def _pace(gap=None):
    """Free plan: 8 requests a minute. One process keeps at least 7.6 s between requests (GOLD_FEED_GAP_S to change)."""
    g = float(os.environ.get('GOLD_FEED_GAP_S', '7.6') if gap is None else gap); wait = STATE['last'] + g - time.time()
    if wait > 0: time.sleep(wait)
    STATE['last'] = time.time(); STATE['calls'] += 1

def validate_meta(meta):
    """The instrument check: the answer must be XAU/USD, quoted in USD, and not a futures contract. Raises FeedError otherwise."""
    if not isinstance(meta, dict): raise FeedError('no instrument description in the answer')
    sym = str(meta.get('symbol') or '').upper().replace(' ', '')
    if sym != SYMBOL: raise FeedError(f'the feed answered for "{meta.get("symbol")}", not {SYMBOL}')
    if FORBIDDEN.search(sym): raise FeedError(f'"{sym}" looks like a futures or MCX contract')
    quote = str(meta.get('currency_quote') or meta.get('currency') or 'USD').upper()
    if quote not in ('USD', 'US DOLLAR'): raise FeedError(f'quote currency is {quote}, not USD')
    base = str(meta.get('currency_base') or '').upper()
    if base and base not in ('XAU', 'GOLD SPOT', 'GOLD'): raise FeedError(f'base currency is {base}, not gold (XAU)')
    typ = str(meta.get('type') or '')
    if re.search(r'futur', typ, re.I): raise FeedError(f'instrument type is "{typ}" (a future), not spot')
    return True

def parse(js, interval, now=None):
    """Twelve Data JSON -> OHLCV frame, IST index, validated. Raises FeedError on anything that is not clean XAU/USD spot."""
    if not isinstance(js, dict): raise FeedError('the feed returned no JSON object')
    if js.get('status') == 'error' or 'values' not in js: raise FeedError(f"{js.get('code', '')} {js.get('message') or 'no candles in the answer'}".strip())
    validate_meta(js.get('meta'))
    rows = js['values'] or []
    if not rows: raise FeedError('the feed returned no candles')
    t = pd.to_datetime([r.get('datetime') for r in rows], utc=True, errors='coerce')
    f = pd.DataFrame({k.capitalize(): pd.to_numeric([r.get(k) for r in rows], errors='coerce') for k in ('open', 'high', 'low', 'close')}, index=t)
    vol = pd.to_numeric([r.get('volume') for r in rows], errors='coerce') if any('volume' in r for r in rows) else np.zeros(len(rows))
    f['Volume'] = np.nan_to_num(np.asarray(vol, dtype=float), nan=0.0)
    f = f[f.index.notna()]
    if interval == '1d': f.index = f.index.tz_convert(None).normalize()
    else: f.index = f.index.tz_convert(IST)
    f, _ = dataquality.sanitize(f)
    if f is None or not len(f): raise FeedError('no valid candles after the candle checks')
    c = f.Close.values
    if (c < 100).any() or (c > 100000).any(): raise FeedError(f'prices outside 100 to 100,000 dollars an ounce ({c.min():.2f} to {c.max():.2f}): not XAU/USD spot')
    if len(c) > 1:
        jump = np.abs(np.diff(c) / c[:-1]); lim = MAX_JUMP.get(interval, 0.06)
        try: lim = float(os.environ['GOLD_MAX_JUMP_PCT']) / 100.0 if os.environ.get('GOLD_MAX_JUMP_PCT') else lim     # tests with synthetic, stitched price levels only
        except ValueError: pass
        if (jump > lim).any():
            i = int(np.argmax(jump)); raise FeedError(f'a {jump[i] * 100:.1f}% jump between candles at {f.index[i + 1]}: a broken or switched series, not clean spot')
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz=IST)
    if interval != '1d':
        if (f.index > now + pd.Timedelta(minutes=1)).any(): raise FeedError('candles stamped in the future: wrong timezone in the feed')
        if len(f) and f.index[-1] + pd.Timedelta(minutes=MINUTES[interval]) > now: f = f.iloc[:-1]          # the unfinished candle
    else:
        today = now.tz_convert(DAY_TZ).tz_localize(None).normalize()
        f = f[f.index < today]                                                                              # today's unfinished daily candle
    f.attrs.update(instrument=INSTRUMENT, source=SOURCE_ID, interval=interval, volume_available=bool((f.Volume > 0).mean() > 0.5) if len(f) else False)
    return f

def fetch(interval, now=None, outputsize=1000, start=None, end=None, env=None, get=None, gap=None):
    """One validated request. get(url) -> dict is injectable for tests (no network)."""
    key = api_key(env)
    if not key and get is None: raise FeedError('TWELVEDATA_API_KEY is not set: no XAUUSD spot data, so no gold recommendations')
    q = dict(symbol=SYMBOL, interval=INTERVAL[interval], timezone='UTC', order='ASC', apikey=key or 'test')
    if outputsize: q['outputsize'] = int(min(5000, outputsize))
    if start is not None: q['start_date'] = pd.Timestamp(start).strftime('%Y-%m-%d %H:%M:%S')
    if end is not None: q['end_date'] = pd.Timestamp(end).strftime('%Y-%m-%d %H:%M:%S')
    url = f'{BASE}/time_series?' + urllib.parse.urlencode(q)
    if get is None: _pace(gap)
    try: js = (get or _http)(url)
    except FeedError: raise
    except Exception as ex: raise FeedError(f'{PROVIDER} did not answer: {str(ex)[:120]}')
    return parse(js, interval, now)

def history(interval, days, now=None, env=None, get=None, gap=None, max_requests=8):
    """`days` of candles, newest first in windows of 5,000 (the provider's limit), joined and validated. Stops when the provider has nothing older."""
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz=IST); stop = now - pd.Timedelta(days=days); end = None; parts = []
    for _ in range(max_requests):
        try: f = fetch(interval, now, 5000, None, end, env, get, gap)
        except FeedError as ex:
            if parts and ('no candles' in str(ex) or 'No data' in str(ex)): break
            raise
        parts.append(f); first = f.index[0]
        if len(f) < 4999 or (first.tz_localize(None) if first.tzinfo is None else first) <= (stop if first.tzinfo else stop.tz_localize(None)): break
        end = (first.tz_convert('UTC').tz_localize(None) if first.tzinfo else first) - pd.Timedelta(seconds=1)
    f = pd.concat(parts).sort_index(); f = f[~f.index.duplicated(keep='last')]
    cut = stop if f.index.tz is not None else stop.tz_convert(DAY_TZ).tz_localize(None)
    f = f[f.index >= cut]; f, _ = dataquality.sanitize(f); f.attrs.update(parts[0].attrs); return f

def resample(f5, minutes=15):
    """15m (or 1h) candles built from the 5m spot candles: buckets on the clock (:00, :15, :30, :45 UTC), only complete ones, so the
    bias frame is the same instrument and the same prints as the trigger frame (and costs no extra request)."""
    if f5 is None or not len(f5): return f5
    g = f5.copy(); u = g.index.tz_convert('UTC')
    key = u.floor(f'{minutes}min'); g['_k'] = key
    agg = g.groupby('_k').agg(Open=('Open', 'first'), High=('High', 'max'), Low=('Low', 'min'), Close=('Close', 'last'), Volume=('Volume', 'sum'))
    last_end = u[-1] + pd.Timedelta(minutes=5)
    agg = agg[agg.index + pd.Timedelta(minutes=minutes) <= last_end]                     # drop the bucket still filling
    agg.index = pd.DatetimeIndex(agg.index).tz_convert(IST); agg.attrs.update(f5.attrs); agg.attrs['interval'] = f'{minutes}m (from 5m)'
    return agg

PERIOD_DAYS = {'5d': 5, '30d': 30, '60d': 60, '180d': 180, '730d': 730, '3y': 1100, '5y': 1830, '10y': 3660}
def fetch_like(symbols, period, interval, env=None, get=None, gap=None, now=None):
    """Drop-in for the old Yahoo downloader signature ({symbol: frame}, failed). Only XAU/USD spot is ever returned, whatever was asked."""
    asked = [s for s in symbols]
    bad = [s for s in asked if s not in (LABEL, SYMBOL)]
    if bad: raise FeedError(f'refused {bad}: the gold pipeline only serves {SYMBOL} spot (no futures, no other instrument)')
    days = PERIOD_DAYS.get(period, 60); mins = MINUTES[interval]
    if interval == '1d' or days * 24 * 60 / mins > 5000: f = history(interval, days, now, env, get, gap)
    else: f = fetch(interval, now, int(days * 24 * 60 / mins) + 10, None, None, env, get, gap)
    return {asked[0]: f}, []

CACHE_AGE = {'15m': pd.Timedelta(minutes=15), '1h': pd.Timedelta(minutes=55), '1d': pd.Timedelta(hours=12)}
def frames(styles, now, state_dir=None, env=None, get=None, gap=None):
    """Everything the live gold scan needs: 5m every run, 15m once per quarter hour, 1h about hourly, 1d twice a day (the rest from a cache):
    about 410 of the free plan's 800 requests a day at one run every 5 minutes. All four are the same instrument (XAU/USD spot).
    Returns (frames dict, info dict). info['ok'] is False with a reason when the spot feed is unusable: then nothing is scanned."""
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz=IST); fr, info = {}, dict(ok=True, reason='', instrument=INSTRUMENT, source=SOURCE_ID, requests=0)
    cache_p = os.path.join(state_dir, 'gold_spot_cache.pkl') if state_dir else None; cache = {}
    if cache_p:
        try: cache = pd.read_pickle(cache_p)
        except Exception: cache = {}
    def get_iv(iv, size):
        c = cache.get(iv)
        same_q = iv != '15m' or (c and pd.Timestamp(c['at']).floor('15min') == now.floor('15min'))
        if c and iv in CACHE_AGE and now - c['at'] < CACHE_AGE[iv] and same_q and is_spot(c['df'].attrs.get('source')): return c['df']
        df = fetch(iv, now, size, None, None, env, get, gap); info['requests'] += 1; cache[iv] = dict(at=now, df=df); return df
    try:
        if 'intraday' in styles:
            fr['f5'] = get_iv('5m', 1200); fr['f15'] = get_iv('15m', 1000)
        if 'swing' in styles: fr['h1'] = get_iv('1h', 2300)
        if 'swing' in styles or 'positional' in styles: fr['daily'] = get_iv('1d', 2000)
    except FeedError as ex:
        info.update(ok=False, reason=str(ex)[:200])
    if cache_p:
        try: os.makedirs(state_dir, exist_ok=True); pd.to_pickle(cache, cache_p)
        except Exception: pass
    for k, f in fr.items():
        if f is None or not is_spot(f.attrs.get('source')): info.update(ok=False, reason=f'{k} candles are not verified XAU/USD spot'); break
    info['volume_available'] = all(f.attrs.get('volume_available') for f in fr.values() if f is not None) if fr else False
    return fr, info

def volume_rule(env=None):
    """'on' (default: your rule as written) or 'off' (gold runs without the volume conditions, because spot has no exchange volume)."""
    v = str((env if env is not None else os.environ).get('GOLD_VOLUME_RULE', '') or 'on').strip().lower()
    return 'off' if v in ('off', 'false', 'no', '0') else 'on'

def lag_minutes(f, now, minutes):
    if f is None or not len(f): return None
    end = pd.Timestamp(f.index[-1]) + pd.Timedelta(minutes=minutes); end = end.tz_localize(IST) if end.tzinfo is None else end
    return round((pd.Timestamp(now) - end).total_seconds() / 60, 1)
