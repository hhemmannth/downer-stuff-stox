"""Market data for the scanner.

Primary: Angel One SmartAPI. Official exchange candles and quotes, free with your Angel One account. Reading data (candles,
quotes) needs no static IP: that SEBI rule is only for placing orders, and this code never places orders.
Fallback: Yahoo Finance (unofficial) for anything Angel cannot serve: secrets not set, a failed login, an unknown symbol or an
API error. Each symbol falls back on its own, so one bad answer never empties a scan.

Speed: the year of daily candles for the Nifty 500 is downloaded once a day and cached in .cache (kept between runs by
actions/cache). The hourly swing scans reuse it, and after the close only today's candle is added (one quote call per 50 stocks).

Accuracy check: each full daily download compares a sample of closes between Angel One and Yahoo; the gaps are on the
System health page.

Secrets (all four are needed to use Angel One): ANGEL_API_KEY, ANGEL_CLIENT_CODE, ANGEL_MPIN, ANGEL_TOTP_SECRET."""
import base64, datetime as dt, hashlib, hmac, json, os, pickle, random, struct, sys, tempfile, threading, time, urllib.error, urllib.request
try: import fcntl                                    # Linux / macOS: lets the live scan and the background swing scan share one pace
except ImportError: fcntl = None
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
INTERVAL = {'1d': 'ONE_DAY', '1h': 'ONE_HOUR', '15m': 'FIFTEEN_MINUTE', '5m': 'FIVE_MINUTE'}
MAX_DAYS = {'1d': 1900, '1h': 390, '15m': 190, '5m': 95}                 # Angel's per-request limits, with a margin
PERIOD_DAYS = {'2y': 731, '1y': 366, '6mo': 183, '3mo': 92, '1mo': 31}
INDEX_TOKENS = {'^NSEI': '99926000', '^NSEBANK': '99926009', '^INDIAVIX': '99926017'}
INDEX_NAMES = {'^NSEI': ['NIFTY 50', 'NIFTY'], '^NSEBANK': ['NIFTY BANK', 'BANKNIFTY'], '^INDIAVIX': ['INDIA VIX'], '^CNXIT': ['NIFTY IT'],
               '^CNXAUTO': ['NIFTY AUTO'], '^CNXPHARMA': ['NIFTY PHARMA'], '^CNXFMCG': ['NIFTY FMCG'], '^CNXMETAL': ['NIFTY METAL'],
               '^CNXREALTY': ['NIFTY REALTY'], '^CNXENERGY': ['NIFTY ENERGY'], '^CNXMEDIA': ['NIFTY MEDIA'], '^CNXINFRA': ['NIFTY INFRA', 'NIFTY INFRASTRUCTURE'],
               '^CNXPSUBANK': ['NIFTY PSU BANK'], '^CNXFIN': ['NIFTY FIN SERVICE', 'NIFTY FINANCIAL SERVICES']}
COLS = ['Open', 'High', 'Low', 'Close', 'Volume']
STATE = dict(dir='.cache', deadline=None, budget_s=None)
STATS = dict(angel=dict(configured=False, ok=None, error=None), by_interval={}, xcheck=[], option_quotes=None, source={})

def configure(state_dir):
    STATE['dir'] = state_dir or '.cache'; os.makedirs(STATE['dir'], exist_ok=True)

def set_budget(seconds):
    """Angel One time limit for this run (the 5-minute live scan uses ~90 s): after it, whatever is left goes to Yahoo, so one
    slow day at Angel One can never make a tick overrun the next one."""
    STATE['budget_s'] = float(seconds) if seconds else None; STATE['deadline'] = None      # the clock starts at the first Angel One request

def _count(interval, src, n=1):
    if n: d = STATS['by_interval'].setdefault(interval, {}); d[src] = d.get(src, 0) + n

def report():
    """What the System health page shows under 'Data sources'."""
    a = STATS['angel']
    return dict(primary='Angel One' if a.get('ok') else 'Yahoo Finance', angel=a, by_interval=STATS['by_interval'], xcheck=STATS['xcheck'][:12],
                option_quotes=STATS['option_quotes'], notes=STATS.get('notes', []))

def period_days(period):
    if period in PERIOD_DAYS: return PERIOD_DAYS[period]
    if period.endswith('d'): return int(int(period[:-1]) * 1.5) + 2        # trading days -> calendar days (weekends, holidays)
    if period.endswith('mo'): return int(period[:-2]) * 31
    if period.endswith('y'): return int(period[:-1]) * 366
    return 30

def totp(secret, t=None, step=30, digits=6):
    """The 6-digit code your authenticator app shows for Angel One (RFC 6238), made from the TOTP secret."""
    s = secret.strip().replace(' ', '').upper(); key = base64.b32decode(s + '=' * (-len(s) % 8))
    h = hmac.new(key, struct.pack('>Q', int((time.time() if t is None else t) // step)), hashlib.sha1).digest(); o = h[-1] & 15
    return str((struct.unpack('>I', h[o:o + 4])[0] & 0x7fffffff) % 10 ** digits).zfill(digits)

def _norm(s): return ''.join(ch for ch in str(s).upper() if ch.isalnum())

def build_tokens(rows, today):
    """Compact symbol -> token map from Angel's instrument master (about 40 MB), kept for the day."""
    eq, be, idx, opt = {}, {}, {}, []; t0 = dt.date.fromisoformat(today)
    for r in rows:
        seg, sym, name, typ = r.get('exch_seg'), str(r.get('symbol') or ''), str(r.get('name') or ''), str(r.get('instrumenttype') or '')
        if seg == 'NSE':
            if sym.endswith('-EQ'): eq[sym[:-3]] = str(r['token'])
            elif sym.endswith('-BE'): be[sym[:-3]] = str(r['token'])
            elif typ == 'AMXIDX' or str(r['token']).startswith('999'): idx[_norm(sym)] = str(r['token']); idx.setdefault(_norm(name), str(r['token']))
        elif seg == 'NFO' and typ == 'OPTIDX' and name == 'NIFTY':
            try: ex = dt.datetime.strptime(str(r['expiry']), '%d%b%Y').date()
            except Exception: continue
            if 0 <= (ex - t0).days <= 21: opt.append([ex.isoformat(), int(round(float(r['strike']) / 100)), sym[-2:], str(r['token']), sym])
    for k, v in be.items(): eq.setdefault(k, v)
    return dict(date=today, eq=eq, idx=idx, opt=opt)

class AngelError(Exception): pass
class AngelRateLimit(AngelError): pass             # 'exceeding access rate': slow down and retry, never a reason to give up on Angel

WORKERS = 4                                      # requests in flight at once (8 tripped Angel's rate limit on 4 Nov); starts stay paced by GAP

class Angel:
    GAP = 0.40                                   # seconds between request starts (Angel allows 3 a second and 180 a minute)
    def __init__(self, env=None):
        e = env or os.environ
        self.key, self.client, self.mpin, self.secret = (str(e.get(k, '')).strip() for k in ('ANGEL_API_KEY', 'ANGEL_CLIENT_CODE', 'ANGEL_MPIN', 'ANGEL_TOTP_SECRET'))
        self.base = str(e.get('ANGEL_BASE', 'https://apiconnect.angelone.in')).rstrip('/')
        self.master = str(e.get('ANGEL_MASTER_URL', 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'))
        self.configured = all((self.key, self.client, self.mpin, self.secret)); self.jwt = None; self.dead = False; self._last = 0.0; self._tok = None
        self._pace_lock, self._login_lock = threading.Lock(), threading.RLock(); self.gap = self.GAP
        # the session token lives in the runner's temp folder, never in .cache (which is saved to GitHub's cache storage)
        self.session_file = os.path.join(tempfile.gettempdir(), 'angel_session_' + hashlib.sha1((self.client + self.key).encode()).hexdigest()[:10] + '.json')

    def _post(self, path, body, auth=True, timeout=30, method='POST'):
        h = {'Content-Type': 'application/json', 'Accept': 'application/json', 'X-UserType': 'USER', 'X-SourceID': 'WEB', 'X-ClientLocalIP': '127.0.0.1',
             'X-ClientPublicIP': '127.0.0.1', 'X-MACAddress': '00:00:00:00:00:00', 'X-PrivateKey': self.key}
        if auth: h['Authorization'] = 'Bearer ' + str(self.jwt)
        with urllib.request.urlopen(urllib.request.Request(self.base + path, data=json.dumps(body).encode() if method == 'POST' else None, headers=h, method=method), timeout=timeout) as r:
            raw = r.read().decode() or '{}'
        return json.loads(raw)

    def login(self):
        with self._login_lock:
            if self.jwt or fcntl is None: return self._login()
            with open(self.session_file + '.lock', 'a+') as lk:          # the other scanner may be logging in right now: wait, then reuse
                fcntl.flock(lk, fcntl.LOCK_EX)
                try: return self._login()
                finally: fcntl.flock(lk, fcntl.LOCK_UN)

    def _login(self):
        if self.jwt: return self.jwt
        try:
            s = json.load(open(self.session_file))
            if time.time() - s['at'] < 5 * 3600: self.jwt = s['jwt']; return self.jwt
        except Exception: pass
        for attempt in range(3):                                          # Angel allows one login a second
            try: js = self._post('/rest/auth/angelbroking/user/v1/loginByPassword', dict(clientcode=self.client, password=self.mpin, totp=totp(self.secret)), auth=False); break
            except urllib.error.HTTPError as ex:
                if ex.code in (403, 429) and attempt < 2: time.sleep(1.5 * (attempt + 1)); continue
                raise AngelError(f'login failed: HTTP {ex.code}')
        d = js.get('data') or {}
        if not js.get('status') or not d.get('jwtToken'): raise AngelError(f"login failed: {js.get('message') or js.get('errorcode') or 'no session token'}")
        self.jwt = d['jwtToken']
        try:
            fd = os.open(self.session_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600); os.write(fd, json.dumps(dict(jwt=self.jwt, at=time.time())).encode()); os.close(fd)
        except Exception: pass
        return self.jwt

    def slow_down(self):
        """Angel said 'too fast': space requests further apart for the rest of this run."""
        with self._pace_lock: self.gap = min(1.2, self.gap * 1.5)

    PACE_FILE = os.path.join(tempfile.gettempdir(), 'angel_pace')

    def _pace(self, gap):
        """Space request STARTS by `gap` seconds across all threads AND all scanner processes on this runner (the loop runs the
        live scan and the hourly swing scan at the same time; each pacing alone would together exceed Angel's limit)."""
        with self._pace_lock:
            if fcntl is None:
                wait = self._last + gap - time.time()
                if wait > 0: time.sleep(wait)
                self._last = time.time(); return
            with open(self.PACE_FILE, 'a+') as fh:
                fcntl.flock(fh, fcntl.LOCK_EX)
                try:
                    fh.seek(0); raw = fh.read().strip()
                    last = float(raw) if raw else 0.0
                    wait = last + gap - time.time()
                    if wait > 0: time.sleep(wait)
                    now = time.time(); fh.seek(0); fh.truncate(); fh.write(f'{now:.4f}'); fh.flush(); self._last = now
                finally: fcntl.flock(fh, fcntl.LOCK_UN)

    def _forget_session(self, used=None):
        with self._login_lock:
            if used is not None and self.jwt != used: return     # another thread already logged in again
            self._really_forget()

    def _really_forget(self):
        self.jwt = None
        try: os.remove(self.session_file)
        except Exception: pass

    def call(self, path, body, gap=0.0, method='POST'):
        """Authenticated POST at a polite pace: one re-login if the session expired, short waits on rate limits."""
        self.login(); err = 'no answer'
        for attempt in range(4):
            self._pace(gap); used = self.jwt
            try: js = self._post(path, body, method=method)
            except urllib.error.HTTPError as ex:
                err = f'HTTP {ex.code}'
                if ex.code in (401,) and attempt == 0: self._forget_session(used); self.login(); continue
                if ex.code in (403, 429, 500, 502, 503) and attempt < 3: time.sleep(1.5 * (attempt + 1)); continue
                raise (AngelRateLimit if ex.code in (403, 429) else AngelError)(err)
            if js.get('status'): return js.get('data')
            code, msg = str(js.get('errorcode') or ''), str(js.get('message') or ''); err = f'{code} {msg}'.strip()
            if code in ('AG8001', 'AG8002', 'AG8003') or ('token' in msg.lower() and 'invalid' in msg.lower()):
                self._forget_session(used); self.login(); continue
            if 'rate' in msg.lower() or 'exceed' in msg.lower():
                if attempt < 3: time.sleep(1.5 * (attempt + 1)); continue
                raise AngelRateLimit(err)
            raise AngelError(err or 'request failed')
        raise AngelError(err)

    def tokens(self):
        if self._tok is not None: return self._tok
        path = os.path.join(STATE['dir'], 'angel_tokens.json'); today = dt.datetime.now(IST).date().isoformat()
        try:
            t = json.load(open(path))
            if t.get('date') == today and t.get('eq'): self._tok = t; return t
        except Exception: pass
        raw = json.loads(urllib.request.urlopen(urllib.request.Request(self.master, headers={'User-Agent': 'Mozilla/5.0'}), timeout=180).read())
        self._tok = build_tokens(raw, today)
        try: os.makedirs(STATE['dir'], exist_ok=True); json.dump(self._tok, open(path, 'w'))
        except Exception: pass
        return self._tok

    def token_for(self, symbol):
        if symbol in INDEX_TOKENS: return INDEX_TOKENS[symbol]
        t = self.tokens()
        if symbol.startswith('^'):
            for n in INDEX_NAMES.get(symbol, []):
                if _norm(n) in t['idx']: return t['idx'][_norm(n)]
            return None
        return t['eq'].get(symbol)

    def candles(self, token, interval, days, exchange='NSE'):
        now = dt.datetime.now(IST); start = now - dt.timedelta(days=min(days, MAX_DAYS[interval]))
        start = start.replace(hour=0, minute=0) if interval == '1d' else start.replace(hour=9, minute=15)
        return self.candles_between(token, interval, start, now, exchange)

    def candles_between(self, token, interval, start, end, exchange='NSE'):
        """Candles for an explicit window (Angel One caps one request at MAX_DAYS[interval] days, so longer history is fetched in windows)."""
        data = self.call('/rest/secure/angelbroking/historical/v1/getCandleData', dict(exchange=exchange, symboltoken=str(token), interval=INTERVAL[interval],
                         fromdate=start.strftime('%Y-%m-%d %H:%M'), todate=end.strftime('%Y-%m-%d %H:%M')), gap=self.gap)
        if not data: raise AngelError('no candles returned')
        df = pd.DataFrame(data, columns=['t'] + COLS); t = pd.to_datetime(df['t'])
        idx = pd.DatetimeIndex(t.dt.tz_localize(None) if t.dt.tz is not None else t).normalize() if interval == '1d' else pd.DatetimeIndex(t if t.dt.tz is not None else t.dt.tz_localize(IST))
        out = df[COLS].astype(float); out.index = idx; out = out[~out.index.duplicated(keep='last')].sort_index()
        if out.empty: raise AngelError('no candles returned')
        return out

    def quote(self, tokens, exchange='NSE', mode='FULL'):
        out = {}; tokens = [str(t) for t in tokens]
        for i in range(0, len(tokens), 50):
            data = self.call('/rest/secure/angelbroking/market/v1/quote/', dict(mode=mode, exchangeTokens={exchange: tokens[i:i + 50]}), gap=1.05)
            for q in (data or {}).get('fetched', []) or []: out[str(q.get('symbolToken'))] = q
        return out

_A = dict(obj=None, init=False)
def angel():
    """The logged-in Angel One client, or None (secrets missing, login failed, or too many errors this run)."""
    if not _A['init']:
        _A['init'] = True; a = Angel(); STATS['angel']['configured'] = a.configured
        if not a.configured: print('  Angel One not set up (ANGEL_ secrets missing): using Yahoo', flush=True)
        if a.configured:
            try: a.login(); a.tokens(); _A['obj'] = a; STATS['angel'].update(ok=True, error=None)
            except Exception as ex: STATS['angel'].update(ok=False, error=str(ex)[:200]); print(f'  Angel One unavailable, using Yahoo: {ex}', file=sys.stderr)
    a = _A['obj']
    return a if a is not None and not a.dead else None

def reset():                                     # tests
    _A.update(obj=None, init=False); STATE['deadline'] = None; STATE['budget_s'] = None
    STATS.update(angel=dict(configured=False, ok=None, error=None), by_interval={}, xcheck=[], option_quotes=None, source={}, notes=[])

# ------------------------------------------------------------------ fetching
def fetch(symbols, period, interval, yahoo, source='auto'):
    """Same answer as the old Yahoo-only download: ({symbol: OHLCV frame}, [failed symbols]). source='yahoo' skips Angel One."""
    symbols = list(dict.fromkeys(symbols))
    if interval == '1d' and period in ('1y', '2y') and len(symbols) >= 30: return daily_cached(symbols, period, yahoo)
    return _fetch(symbols, period, interval, yahoo, source)

def _fetch(symbols, period, interval, yahoo, source='auto'):
    out, rest, a = {}, [], (angel() if source != 'yahoo' else None)
    if a is not None and STATE.get('budget_s') and STATE.get('deadline') is None: STATE['deadline'] = time.time() + STATE['budget_s']
    if a is not None and STATE.get('deadline') and time.time() > STATE['deadline']:
        a = None; _note(f'{interval}: Angel One time limit for this run reached, Yahoo used')
    if a is not None and interval in INTERVAL:
        days, todo = period_days(period), []
        for i, s in enumerate(symbols):
            try: tk = a.token_for(s)
            except Exception as ex: STATS['angel'].update(ok=False, error=f'instrument list: {ex}'[:200]); a.dead = True; rest += symbols[i:]; todo = []; break
            if tk is None: rest.append(s)
            else: todo.append((s, tk))
        if todo:
            t0, streak, done, limited, last = time.time(), 0, 0, 0, ''
            ex = ThreadPoolExecutor(max_workers=min(WORKERS, len(todo)))
            futs = {ex.submit(a.candles, tk, interval, days): s for s, tk in todo}
            try:
                for f in as_completed(futs):
                    s = futs[f]; done += 1
                    try: out[s] = f.result(); streak = 0; STATS['source'][s] = 'angel'; _count(interval, 'Angel One')
                    except AngelRateLimit as e:                      # too fast: slow down, this stock goes to Yahoo this time
                        rest.append(s); limited += 1; a.slow_down(); last = f'{s}: {e}'; STATS['angel']['last_error'] = last[:200]
                    except Exception as e:
                        rest.append(s); streak += 1; last = f'{s}: {e}'; STATS['angel']['last_error'] = last[:200]
                        if streak >= 12:
                            a.dead = True; STATS['angel'].update(ok=False, error=f'stopped after 12 errors in a row ({e})'[:200])
                            print(f'  Angel One stopped for this run after 12 errors in a row ({e}); using Yahoo', file=sys.stderr, flush=True); break
                    if len(todo) >= 50 and (done % 100 == 0 or done == len(todo)): print(f'  Angel One {interval}: {done}/{len(todo)} in {time.time() - t0:.0f}s', flush=True)
                    if STATE.get('deadline') and time.time() > STATE['deadline'] and done < len(todo):
                        last = last or 'time limit'; _note(f'{interval}: Angel One time limit reached after {done}/{len(todo)}, rest via Yahoo')
                        print(f'  Angel One {interval}: time limit for this run reached after {done}/{len(todo)}; the rest via Yahoo', file=sys.stderr, flush=True); break
            finally:
                ex.shutdown(wait=True, cancel_futures=True)
            got = sum(1 for s, _ in todo if s in out)
            if got < len(todo) or len(todo) >= 20:              # always say where the candles came from, and why when not Angel
                msg = f'  Angel One {interval}: {got}/{len(todo)} served'
                if got < len(todo):
                    msg += f', {len(todo) - got} via Yahoo' + (f' ({limited} rate-limited, now pacing {a.gap:.2f}s)' if limited else '') + (f'; last error: {last}' if last else '')
                print(msg, file=sys.stderr if got < len(todo) else sys.stdout, flush=True)
            for f, s in futs.items():                    # anything cancelled or still unread after a stop goes to Yahoo
                if s not in out and s not in rest:
                    try: out[s] = f.result(timeout=0); STATS['source'][s] = 'angel'; _count(interval, 'Angel One')
                    except Exception: rest.append(s)
    else: rest = list(symbols)
    failed = []
    if rest:
        y, failed = yahoo(rest, period, interval)
        for s in y: STATS['source'][s] = 'yahoo'
        out.update(y); _count(interval, 'Yahoo', len(y))
    return out, failed

def _note(msg):
    n = STATS.setdefault('notes', [])
    if msg not in n: n.append(msg)

def _naive_daily(f):
    f = f.copy(); idx = pd.DatetimeIndex(f.index)
    f.index = (idx.tz_localize(None) if idx.tz is not None else idx).normalize(); return f[COLS]

def _merge(old, new):
    new = _naive_daily(new); return pd.concat([old[~old.index.isin(new.index)], new]).sort_index()

def after_close(now): return now.hour * 60 + now.minute >= 15 * 60 + 35

def daily_cached(symbols, period, yahoo, now=None):
    """A year of daily candles, downloaded in full once a day and reused afterwards. After 15:35 today's candle is added."""
    now = now or dt.datetime.now(IST); today = now.date().isoformat(); path = os.path.join(STATE['dir'], 'daily_cache.pkl')
    try: c = pickle.load(open(path, 'rb'))
    except Exception: c = None
    fresh = bool(c) and c.get('built') == today and c.get('period') == period
    frames = dict(c['frames']) if fresh else {}
    need = [s for s in symbols if s not in frames]; failed = []
    if need:
        got, failed = _fetch(need, period, '1d', yahoo, source='yahoo')      # ~500 stocks in about a minute; Angel One's candle API is far slower
        frames.update({s: _naive_daily(f) for s, f in got.items()})
        _note('daily history: Yahoo (fast), with a sample checked against Angel One each morning')
        if not fresh: xcheck(frames, yahoo)
    reused = [s for s in symbols if s in frames and s not in need]; _count('1d', 'cache (no download)', len(reused))
    if reused and after_close(now): top_up(frames, reused, yahoo, now.date())
    try:
        os.makedirs(STATE['dir'], exist_ok=True); tmp = path + '.tmp'
        with open(tmp, 'wb') as fh: pickle.dump(dict(built=today, period=period, frames=frames), fh)
        os.replace(tmp, path)
    except Exception as ex: print(f'  daily cache not saved: {ex}', file=sys.stderr)
    return {s: frames[s].copy() for s in symbols if s in frames}, [s for s in failed if s not in frames]

def top_up(frames, syms, yahoo, today):
    """Add today's daily candle to cached history: Angel quotes (50 stocks a call), else a 5-day Yahoo download."""
    done, a = set(), angel()
    if a is not None:
        try:
            toks = {s: a.token_for(s) for s in syms}; toks = {s: t for s, t in toks.items() if t}
            q = a.quote(list(toks.values()))
            for s, t in toks.items():
                x = q.get(str(t))
                if not x or not float(x.get('open') or 0): continue
                ts = x.get('exchFeedTime') or x.get('exchTradeTime')
                try:
                    if ts and pd.to_datetime(ts, dayfirst=True).date() != today: continue
                except Exception: pass
                row = pd.DataFrame([[float(x['open']), float(x['high']), float(x['low']), float(x['ltp']), float(x.get('tradeVolume') or 0)]], columns=COLS,
                                   index=pd.DatetimeIndex([pd.Timestamp(today)]))
                frames[s] = _merge(frames[s], row); done.add(s)
        except Exception as ex: STATS['angel']['last_error'] = f'today\'s candle: {ex}'[:200]
        _count('1d', "Angel One (today's candle)", len(done))
    rest = [s for s in syms if s not in done]
    if rest:
        y, _ = yahoo(rest, '5d', '1d')
        for s, f in y.items(): frames[s] = _merge(frames[s], f)
        _count('1d', "Yahoo (today's candle)", len(y))

def xcheck(frames, yahoo, n=8):
    """Accuracy check: compare recent closes from Yahoo (what the scan uses) with Angel One's exchange data for Nifty and a few stocks.
    Gaps over 0.5% in the app's Data sources card mean Yahoo is off that day."""
    a = angel()
    if a is None or not frames: return
    pool = [s for s in frames if not s.startswith('^')]; sample = ['^NSEI'] + random.sample(pool, min(n, len(pool))); rows, yn = [], {}
    try: yn, _ = yahoo(['^NSEI'], '1mo', '1d')
    except Exception: pass
    today = dt.datetime.now(IST).date()
    for s in sample:
        if STATE.get('deadline') and time.time() > STATE['deadline']: break
        try:
            tk = a.token_for(s); ang = _naive_daily(a.candles(tk, '1d', 45)).Close if tk else None
            yh = (_naive_daily(frames[s]) if s in frames else (_naive_daily(yn['^NSEI']) if s in yn else None))
            if ang is None or yh is None: continue
            yh = yh.Close; common = [d for d in ang.index.intersection(yh.index) if d.date() < today][-5:]
            if not common: continue
            diffs = [abs(float(ang[d]) - float(yh[d])) / float(yh[d]) * 100 for d in common if float(yh[d])]; d = common[-1]
            rows.append(dict(symbol=s, date=str(d.date()), angel=round(float(ang[d]), 2), yahoo=round(float(yh[d]), 2), max_diff_pct=round(max(diffs), 2) if diffs else None, days=len(common)))
        except Exception as ex: STATS['angel']['last_error'] = f'accuracy check {s}: {ex}'[:200]
    STATS['xcheck'] = rows

def option_quotes(expiry_iso, strikes, kind):
    """Live Nifty option prices (last, best bid, best ask) for these strikes, or {} when Angel One is not available."""
    a = angel()
    if a is None: return {}
    try:
        want = {int(k) for k in strikes}; rows = [r for r in a.tokens().get('opt', []) if r[0] == str(expiry_iso)[:10] and r[2] == kind and int(r[1]) in want]
        if not rows: STATS['option_quotes'] = 'no matching contracts in the instrument list'; return {}
        q = a.quote([r[3] for r in rows], exchange='NFO'); out = {}
        for ex, k, kd, t, sym in rows:
            x = q.get(str(t))
            if not x or not float(x.get('ltp') or 0): continue
            d = x.get('depth') or {}; b = ((d.get('buy') or [{}])[0] or {}).get('price'); s = ((d.get('sell') or [{}])[0] or {}).get('price')
            out[int(k)] = dict(ltp=float(x['ltp']), bid=float(b) if b else None, ask=float(s) if s else None, symbol=sym, volume=x.get('tradeVolume'))
        STATS['option_quotes'] = f'{len(out)} live strikes'; return out
    except Exception as ex:
        STATS['option_quotes'] = f'failed: {ex}'[:160]; return {}


def deep_intraday(symbol, interval, days, now=None):
    """Intraday candles going back up to `days` days, fetched from Angel One in windows (its 5m limit is about 95 days per request). Stops
    after two empty windows in a row, because nobody can promise how far back free history goes. Returns a frame, or None."""
    a = angel()
    if a is None or interval not in INTERVAL or interval == '1d': return None
    tk = a.token_for(symbol)
    if tk is None: return None
    end = now or dt.datetime.now(IST); step = dt.timedelta(days=MAX_DAYS[interval]); floor = end - dt.timedelta(days=days); frames, empties = [], 0
    while end > floor and empties < 2:
        start = max(floor, end - step)
        try: frames.append(a.candles_between(tk, interval, start.replace(hour=9, minute=15), end)); empties = 0
        except AngelError as ex:
            if 'no candles' in str(ex): empties += 1
            else: raise
        end = start - dt.timedelta(minutes=1)
    if not frames: return None
    out = pd.concat(frames); out = out[~out.index.duplicated(keep='last')].sort_index(); _count(interval, 'Angel One (deep history)', len(frames)); return out
