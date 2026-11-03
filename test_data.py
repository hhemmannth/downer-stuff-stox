"""Data-layer tests with a stand-in for yfinance and for the NSE list download (no internet needed)."""
import os, sys, tempfile, types
import numpy as np, pandas as pd

calls = []
def fake_download(tickers, period=None, interval=None, group_by=None, auto_adjust=False, threads=True, progress=False, multi_level_index=True):
    single = isinstance(tickers, str); names = [tickers] if single else list(tickers); calls.append((tuple(names), interval, threads))
    n = 250 if interval == '1d' else 120
    idx = pd.date_range('2025-01-01', periods=n, freq='D' if interval == '1d' else 'h', tz=None if interval == '1d' else 'UTC'); frames = {}
    for t in names:
        base = 100 + np.arange(n, dtype=float); bad = t == 'BADLOCK.NS' and not single and len(names) > 1; gone = t == 'GONE.NS'; v = np.nan if (bad or gone) else 1.0
        frames[t] = pd.DataFrame({'Open': base * v, 'High': base * v + 2, 'Low': base * v - 2, 'Close': base * v + 1, 'Volume': 1e6 * v}, index=idx)
    if single and not multi_level_index: return frames[names[0]]
    return pd.concat(frames, axis=1)
sys.modules['yfinance'] = types.SimpleNamespace(download=fake_download)
import strategy_scanner as sc
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)

syms = [f'S{i}' for i in range(120)] + ['BADLOCK', 'GONE']
data, failed = sc.download_many(syms, '1y', '1d', chunk=50, pause=0)
bulk = [c for c in calls if len(c[0]) > 1]
check('120+ symbols are downloaded in chunks of 50', len(bulk) == 3 and max(len(c[0]) for c in bulk) == 50, str([len(c[0]) for c in bulk]))
check('a symbol that failed in its chunk is recovered one by one', 'BADLOCK' in data and any(c[0] == ('BADLOCK.NS',) and c[2] is False for c in calls))
check('a symbol that never returns data is reported as failed', failed == ['GONE'] and 'GONE' not in data, str(failed))
check('a single-symbol download works', 'AAA' in sc.download_many(['AAA'], '5d', '5m', pause=0)[0])
check('index symbols keep their own ticker', '^NSEI' in sc.download_many(['^NSEI'], '5d', '5m', pause=0)[0] and any(c[0] == ('^NSEI',) for c in calls))
now = pd.Timestamp('2026-10-20 12:00', tz='Asia/Kolkata')
dd = pd.DataFrame({'Open': 1, 'High': 2, 'Low': 1, 'Close': 1, 'Volume': 1}, index=pd.to_datetime(['2026-10-19', '2026-10-20']))
check("today's unfinished daily bar is dropped before 15:45 IST", len(sc.tidy_daily(dd.copy(), now)) == 1)
hh = pd.DataFrame({'Open': 1, 'High': 2, 'Low': 1, 'Close': 1, 'Volume': 1}, index=pd.to_datetime(['2026-10-20 05:30', '2026-10-20 06:30']).tz_localize('UTC'))   # 11:00 and 12:00 IST
check('the 1H candle that is still forming is dropped', len(sc.tidy_intraday(hh, now, 60)) == 1)
check('market hours flag', sc.market_open(now) and not sc.market_open(pd.Timestamp('2026-10-18 12:00', tz='Asia/Kolkata')))

csv500 = 'Company Name,Industry,Symbol,Series,ISIN Code\n' + '\n'.join(f'Co {i},X,SYM{i},EQ,INE{i:05d}' for i in range(500)) + '\n'
check('Nifty 500 CSV is parsed', len(sc.parse_universe_csv('\ufeff' + csv500.lstrip('\ufeff'))) == 500 and sc.parse_universe_csv(csv500)[:2] == ['SYM0', 'SYM1'])
tmp = tempfile.mkdtemp(); wl = os.path.join(tmp, 'wl.txt'); open(wl, 'w').write('# starter\nAAA\nBBB\n'); local = os.path.join(tmp, 'nifty500.csv')
s1, n1, ind1 = sc.load_nifty500(local, wl, fetch=lambda u: csv500)
check('live list is used when the download works, with each stock\'s industry', len(s1) == 500 and 'live' in n1 and ind1['SYM7'] == 'X', n1)
def boom(u): raise OSError('blocked')
open(local, 'w').write(csv500)
s2, n2, _ = sc.load_nifty500(local, wl, fetch=boom)
check('your uploaded nifty500.csv is the backup', len(s2) == 500 and 'nifty500.csv' in n2, n2)
os.remove(local); s3, n3, ind3 = sc.load_nifty500(local, wl, fetch=boom)
check('the starter list is the last resort and says so (no industries then)', s3 == ['AAA', 'BBB'] and 'Upload nifty500.csv' in n3 and ind3 == {}, n3)
s4, n4, _ = sc.load_nifty500(local, wl, fetch=lambda u: 'Symbol\nA\nB\n')
check('a truncated live list is not trusted', s4 == ['AAA', 'BBB'], n4)
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}')
sys.exit(1 if fails else 0)
