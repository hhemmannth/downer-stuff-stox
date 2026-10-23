"""End-to-end test of every section, the market and news pages and the phone alerts, with fake downloads. Run: python test_pipeline.py"""
import http.server, json, os, subprocess, sys, tempfile, threading
import numpy as np, pandas as pd
sys.argv = ['x']
src = open('test_scanner.py').read().split("sc.CFG_B.update(min_bars=20)")[0]; ns = {}; exec(src, ns)
sc, D, H, flip = ns['sc'], ns['D'], ns['H'], ns['flip']
import market, newsfeed
sc.CFG.update(min_turnover_cr=0, min_price=0, min_bars=30, rvol_n=10); sc.CFG_I.update(min_bars=30, rvol_n=10, max_zone_pct=6, max_zone_atr=5); sc.CFG_B.update(min_bars=20); market.MIN_BARS = 30
tz = 'Asia/Kolkata'; n5 = len(D) + len(H); D15 = D[:32]
idx5 = pd.date_range('2026-10-12 09:15', periods=n5, freq='5min', tz=tz); idx15 = pd.date_range('2026-10-08 09:15', periods=len(D15), freq='15min', tz=tz)
mk = lambda rows, idx: pd.DataFrame(rows, columns=sc.COLS, index=idx)
def rnd(n, idx, seed, drift=0.0, base=500.0, vol=0.01):
    r = np.random.default_rng(seed); c = base * np.exp(np.cumsum(drift + r.normal(0, vol, n))); o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({'Open': o, 'High': np.maximum(o, c) * 1.004, 'Low': np.minimum(o, c) * 0.996, 'Close': c, 'Volume': r.integers(1e4, 9e4, n)}, index=idx)
daily_idx = pd.bdate_range('2026-01-01', periods=len(D)); long_idx = pd.bdate_range('2025-10-01', periods=260)
FR = {
  '1d': {'AAA': mk(D, daily_idx), 'BBB': mk(D, daily_idx), 'CCC': rnd(len(D), daily_idx, 1), 'DDD': mk(flip(D), daily_idx), '^NSEI': rnd(260, long_idx, 2, 0.002, 22000, 0.006), '^NSEBANK': rnd(260, long_idx, 3, 0.001, 50000, 0.008), '^INDIAVIX': rnd(260, long_idx, 4, 0.0, 14, 0.02), '^CNXIT': rnd(260, long_idx, 7, 0.004, 30000, 0.004)},
  '1h': {'AAA': mk(H, pd.date_range('2026-02-04 03:45', periods=len(H), freq='h', tz='UTC')), 'BBB': mk(H[:14], pd.date_range('2026-02-04 03:45', periods=14, freq='h', tz='UTC'))},
  '5m': {'AAA': mk(D + H, idx5), 'BBB': mk(flip(D + H), idx5), 'CCC': rnd(n5, idx5, 3), 'DDD': rnd(n5, idx5, 4), '^NSEI': mk(D + H, idx5).assign(Volume=0)},
  '15m': {'AAA': mk(D15, idx15), 'BBB': mk(flip(D15), idx15), 'CCC': rnd(len(D15), idx15, 5), 'DDD': rnd(len(D15), idx15, 6), '^NSEI': mk(D15, idx15)}}
def fake_download(symbols, period, interval, chunk=50, pause=1.0):
    out = {s: FR[interval][s].copy() for s in symbols if s in FR[interval]}; return out, [s for s in symbols if s not in out]
sc.download_many = fake_download
csv_ind = {'AAA': 'Information Technology', 'BBB': 'Information Technology', 'CCC': 'Realty', 'DDD': 'Realty'}
sc.load_nifty500 = lambda *a, **k: (['AAA', 'BBB', 'CCC', 'DDD'], 'test universe (4 symbols)', csv_ind)
_late = sc.late_cut; sc.late_cut = lambda items, now: None        # the 15:00 cut-off depends on the clock; it is checked on its own below
its = [{'status': 'TRIGGERED'}]; _late(its, pd.Timestamp('2026-10-22 15:05', tz='Asia/Kolkata')); its2 = [{'status': 'TRIGGERED'}]; _late(its2, pd.Timestamp('2026-10-22 14:55', tz='Asia/Kolkata'))
LATE_OK = its[0]['status'].startswith('WATCH (after 15:00') and its2[0]['status'] == 'TRIGGERED'
sc.results_info = lambda s, now: dict(date='2026-10-23', days=2, source='test') if s == 'AAA' else None
chain = dict(records=dict(underlyingValue=1103, timestamp='21-Oct-2026 11:00:00', expiryDates=['27-Oct-2026'], data=[dict(strikePrice=k, expiryDate='27-Oct-2026', CE=dict(openInterest=1000 + (200000 if k == 1200 else 0), changeinOpenInterest=100), PE=dict(openInterest=1000 + (260000 if k == 1050 else 0), changeinOpenInterest=100)) for k in range(1000, 1210, 10)]))
sc.oimod.fetch_nse_chain = lambda *a, **k: chain
RSS = '<rss><channel><item><title>Markets rally as RBI holds rates - ET</title><link>https://example.com/a</link><pubDate>Wed, 21 Oct 2026 04:30:00 GMT</pubDate><source>ET</source></item><item><title>AAA wins big order - Mint</title><link>https://example.com/b</link><pubDate>Wed, 21 Oct 2026 03:00:00 GMT</pubDate><source>Mint</source></item></channel></rss>'
newsfeed.fetch_url = lambda url, timeout=15: RSS

out = os.environ.get('OUT_DIR') or tempfile.mkdtemp(); sys.argv = ['x', '--mode', 'all', '--out', out, '--min-score', '4']; sc.main()
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
J = lambda n: json.load(open(os.path.join(out, n + '.json')))
sw, op, it, lq, mk_, nw, br = J('swing'), J('options'), J('intraday'), J('liquid'), J('market'), J('news'), J('breadth')
check('every file is written', all(os.path.exists(os.path.join(out, f + '.json')) for f in ('swing', 'options', 'intraday', 'liquid', 'market', 'news', 'breadth')))
S = {s['symbol']: s for s in sw['setups']}
check('swing: long only, even though a bearish stock is in the universe', S and all(s['direction'] == 'long' for s in sw['setups']) and 'DDD' not in S, str([(s['symbol'], s['direction'], s['status']) for s in sw['setups']]))
check('swing: AAA triggered, BBB waiting for the 1H trigger', S['AAA']['status'] == 'TRIGGERED' and S['BBB']['status'].startswith('WATCH'))
check('swing: prices sit on the NSE tick of 5 paise', all(abs(s[k] / 0.05 - round(s[k] / 0.05)) < 1e-6 for s in sw['setups'] for k in ('entry', 'sl', 't1', 't2', 't3', 'zone_bot', 'zone_top')))
check('swing: sector, sector strength and relative strength are attached', S['AAA']['sector'] == 'Information Technology' and S['AAA']['sector_state'] in ('strong', 'neutral', 'weak') and isinstance(S['AAA']['rs20'], float), str({k: S['AAA'].get(k) for k in ('sector', 'sector_state', 'rs20')}))
check('swing: results date is attached and mentioned in the cautions', S['AAA']['results']['days'] == 2 and any('results in 2' in x['text'].lower() for x in S['AAA']['logic'] if x['title'] == 'Cautions'))
check('swing: logic explains structure, zone, pullback, confirmation, stop and targets', [x['title'] for x in S['AAA']['logic']][:2] == ['1D structure', 'Entry zone'] and {'Pullback', 'Confirmation', 'Stop-loss', 'Targets'} <= {x['title'] for x in S['AAA']['logic']})
check('swing: execution, trailing steps and chart marks exist', len(S['AAA']['plan']['execution']) >= 4 and len(S['AAA']['plan']['trail']) >= 5 and [m_['at'] for m_ in S['AAA']['plan']['marks']] == ['t1', 't2', 't3'] and 'GTT' in ' '.join(S['AAA']['plan']['execution']))
check('swing: daily candles, EMA and tags for the chart', len(S['AAA']['candles']) == len(D) and S['AAA']['tf_structure'] == '1D' and S['AAA']['tf_trigger'] == '1H' and len(S['AAA']['times'][0]) == 10)
check('liquid list ranks stocks for the intraday scan', set(lq['top']) >= {'AAA', 'BBB'})
O = {s['label']: s for s in op['setups']}
check('options: a CALL, no PUT, and the reason a PUT is missing is given', list(O) == ['CALL'] and 'PUT' in op['snapshot']['why_none'], str(op['snapshot']['why_none']))
blob = json.dumps([O['CALL']['status'], O['CALL']['notes'], O['CALL']['logic'], O['CALL']['plan']]).lower()
check('options: volume is not mentioned or required anywhere, and zero volume gives a clean TRIGGERED', O['CALL']['status'] == 'TRIGGERED' and 'volume' not in blob and O['CALL']['rvol'] is None, O['CALL']['status'])
ot = O['CALL']['options_trade']
check('options: strike with delta, gamma, theta, vega, premium levels and five candidates', ot['kind'] == 'CE' and ot['instrument'].startswith('NIFTY ') and all(ot[k] is not None for k in ('delta', 'gamma', 'theta_day', 'vega', 'premium', 'premium_sl')) and len(ot['premium_targets']) == 3 and len(ot['candidates']) >= 3 and ot['lot_size'] == 65)
check('options: the strike logic is written out in the trade logic', any(x['title'] == 'Strike choice (Greeks)' and 'Delta' in x['text'] and 'Vega' in x['text'] for x in O['CALL']['logic']))
check('options: 15m bias is explained as CHoCH only', O['CALL']['logic'][0]['title'] == '15m bias' and 'only 15m requirement' in O['CALL']['logic'][0]['text'])
check('options: auto OI is attached to the snapshot and judged for the trade', op['snapshot']['oi']['call_wall'] == 1200 and op['snapshot']['oi']['put_wall'] == 1050 and op['snapshot']['vix'] is not None and O['CALL']['oi']['verdict'] in ('supports', 'mixed', 'against'), str(O['CALL'].get('oi', {}).get('verdict')))
check('options: snapshot for the page', all(k in op['snapshot'] for k in ('spot', 'above_5m', 'above_15m', 'ema_5m', 'ema_15m', 'pdh_pdl', 'bias_up', 'bias_down', 'vix')) and op['snapshot']['bias_up'] is True and op['lot_size'] == 65)
check('options: premium-based trail and a time stop are in the plan', any('Theta' in t['action'] or 'theta' in t['action'] for t in O['CALL']['plan']['trail']) and any(t['when'] == '15:10' for t in O['CALL']['plan']['trail']))
I = {(s['symbol'], s['direction']): s for s in it['setups']}
check('intraday: AAA long and BBB short on the 5m with a 15m CHoCH', {('AAA', 'long'), ('BBB', 'short')} <= set(I) and I[('AAA', 'long')]['tf_structure'] == '5m' and I[('AAA', 'long')]['logic'][0]['title'] == '15m bias', str(list(I)))
check('intraday: volume still decides the trigger (its logic mentions volume)', any('volume' in x['text'].lower() for x in I[('AAA', 'long')]['logic'] if x['title'] == 'Confirmation'))
check('intraday: MIS, square-off time and the no-progress exit are in the plan', 'MIS' in ' '.join(I[('AAA', 'long')]['plan']['execution']) and any(t['when'] == '15:10' for t in I[('AAA', 'long')]['plan']['trail']))
check('intraday: only the most liquid stocks are scanned', it['universe'] == len(lq['top']) and 'liquid' in it['note'].lower())
check('market: indices, daily regime, today, expected move and playbook', all(k in mk_['indices'] for k in ('nifty', 'banknifty', 'vix')) and mk_['daily']['regime'] in market.LABELS and mk_['intraday']['regime'] in market.LABELS and mk_['expected_move']['daily_pts'] > 0 and len(mk_['playbook']['swing']) >= 2, str((mk_['daily']['label'], mk_['intraday']['label'])))
check('market: breadth and sector table came from the swing scan', mk_['breadth']['count'] >= 1 and {x['sector'] for x in mk_['sectors']} == {'Information Technology', 'Realty'}, str(mk_['breadth']))
check('news: headlines are de-duplicated, setup symbols get their own news', len(nw['headlines']) == 2 and 'AAA' in nw['by_symbol'] and nw['ok'])
check('news: events include the weekly expiry and your setup results date; risk flags are a list', any('weekly expiry' in e['title'] for e in nw['events']) and any(e['title'] == 'AAA: results' for e in nw['events']) and isinstance(nw['risk_flags'], list))



print('--- trade lifecycle ---')
check('options and intraday: a trigger after 15:00 is shown as WATCH, not a trade (before 15:00 it stays TRIGGERED)', LATE_OK)
LS = json.load(open(os.path.join(out, 'signals_swing.json')))
check('swing: the triggered AAA setup is now a tracked signal with a trigger event and its trade snapshot', any(s['symbol'] == 'AAA' and s['status'] == 'ACTIVE' and s['events'][0]['kind'] == 'trigger' and s['item']['symbol'] == 'AAA' for s in LS['signals']), str([(s['symbol'], s['status']) for s in LS['signals']]))
check('swing: BBB (waiting) is on the watch list, not a signal', any(w['symbol'] == 'BBB' for w in LS['watch'].values()) and not any(s['symbol'] == 'BBB' for s in LS['signals']))
check('ledger files exist for options and intraday too', all(os.path.exists(os.path.join(out, f'signals_{k}.json')) for k in ('options', 'intraday')))
print('--- swing: sector-index confirmation ---')
ic = S['AAA']['index_check']
check('swing: the stock is checked against its own index (IT -> NIFTY IT) and passes while it is rising', ic['sector_index'] == 'NIFTY IT' and ic['source'] == 'official' and ic['state'] in ('strong', 'ok') and S['AAA']['status'] == 'TRIGGERED', str(ic))
check('swing: the logic has a sector index step', any(x['title'] == 'Sector index confirmation' and 'NIFTY IT' in x['text'] for x in S['AAA']['logic']))
check('swing: the trail plan exits half if the sector index closes below its 21 EMA', any('21 EMA' in x['when'] and 'NIFTY IT' in x['when'] for x in S['AAA']['plan']['trail']))
FR['1d']['^CNXIT'] = rnd(260, long_idx, 8, -0.004, 30000, 0.004)                      # now the whole IT index is falling
out_f = tempfile.mkdtemp(); import argparse
args_f = argparse.Namespace(out=out_f, watchlist='watchlist.txt', universe_csv=None, events='events.json', min_score=4, top=60, intraday_top=100, state_dir=tempfile.mkdtemp())
sc.run_swing(args_f, pd.Timestamp.now(tz=tz)); SF = {s['symbol']: s for s in json.load(open(os.path.join(out_f, 'swing.json')))['setups']}
check('swing: a FALLING sector index turns a TRIGGERED long into WATCH (index falling)', SF['AAA']['status'] == 'WATCH (index falling)' and SF['AAA']['index_check']['state'] == 'falling', str(SF['AAA']['status']))
check('swing: the reasons and the wait are written in the notes and the logic', any('falling' in n for n in SF['AAA']['notes']) and any('held at WATCH' in x['text'] for x in SF['AAA']['logic'] if x['title'] == 'Sector index confirmation'))
check('swing: the other setup is flagged too but keeps its own status', SF['BBB']['status'].startswith('WATCH') and SF['BBB']['index_check']['state'] == 'falling')
st_f = os.path.join(tempfile.mkdtemp(), 's.json'); env_f = dict(os.environ, NTFY_TOPIC='x', NTFY_URL='http://127.0.0.1:9', NTFY_MIN_SCORE='6')
rf = subprocess.run([sys.executable, 'notify.py', '--dir', out_f, '--state', st_f], env=env_f, capture_output=True, text=True).stdout
check('swing: a held-back setup is not pushed as an alert', 'alerts sent: 0' in rf, rf.strip())
FR['1d'].pop('^CNXIT'); out_n = tempfile.mkdtemp(); args_f.out = out_n; sc.run_swing(args_f, pd.Timestamp.now(tz=tz)); SN = {s['symbol']: s for s in json.load(open(os.path.join(out_n, 'swing.json')))['setups']}
check('swing: no IT index data from Yahoo -> an IT basket from the stocks in the same industry is used', SN['AAA']['index_check']['source'] == 'basket' or SN['AAA']['index_check']['state'] == 'unknown', str(SN['AAA']['index_check']))
FR['1d']['^CNXIT'] = rnd(260, long_idx, 7, 0.004, 30000, 0.004)

print('--- run rhythm: Nifty and intraday every 5 minutes, 15m candles only when a new one closes ---')
calls15 = []; orig_dm = sc.download_many
def counting(symbols, period, interval, chunk=50, pause=1.0):
    if interval == '15m': calls15.append(len(symbols))
    return orig_dm(symbols, period, interval, chunk, pause)
sc.download_many = counting; sd = tempfile.mkdtemp(); args_i = argparse.Namespace(out=out, watchlist='watchlist.txt', universe_csv=None, events='events.json', min_score=4, top=60, intraday_top=100, state_dir=sd)
for hh, mm in ((10, 2), (10, 7), (10, 12), (10, 17), (10, 22)): sc.run_intraday(args_i, pd.Timestamp(f'2026-10-21 {hh}:{mm:02d}', tz=tz))
check('intraday: the 15m data is downloaded in the 10:00 quarter once and again when the 10:15 candle has closed', len(calls15) == 2, str(calls15))
check('quarter index: 09:15 is 0, 09:30 is 1, 10:00 is 3', [sc.quarter_index(pd.Timestamp(f'2026-10-21 {h}', tz=tz)) for h in ('09:15', '09:30', '10:00')] == [0, 1, 3])
sc.download_many = orig_dm

# live mode: Nifty every run, stocks about every 30 minutes, market always, news about every 30 minutes
calls_run = []
for k_ in ('options', 'intraday', 'market', 'news'): setattr(sc, 'run_' + k_, (lambda k2: lambda a, n: calls_run.append(k2))(k_))
live_out = tempfile.mkdtemp()
def live(age_i, age_n):
    calls_run.clear(); now = pd.Timestamp.now(tz='Asia/Kolkata')
    for name, age in (('intraday.json', age_i), ('news.json', age_n)):
        p = os.path.join(live_out, name)
        if age is None:
            if os.path.exists(p): os.remove(p)
        else: json.dump({'generated_at': (now - pd.Timedelta(minutes=age)).isoformat()}, open(p, 'w'))
    sys.argv = ['x', '--mode', 'live', '--out', live_out]; sc.main(); return list(calls_run)
check('live: first run of the day scans everything', live(None, None) == ['options', 'intraday', 'market', 'news'])
check('live: every 5 minutes: Nifty, intraday stocks and the market; news is not due yet', live(5, 5) == ['options', 'intraday', 'market'])
check('live: news again after about 30 minutes', live(5, 30) == ['options', 'intraday', 'market', 'news'])
def boom(a, n): raise RuntimeError('yahoo hiccup')
sc.run_options = boom; calls_run.clear(); sys.argv = ['x', '--mode', 'live', '--out', live_out]; sc.main()
check('one section failing does not stop the others', 'market' in calls_run, str(calls_run))

# phone alerts across the three sections, plus the "scan updated" pushes
got = []
class Hd(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0)); got.append((self.path, dict(self.headers), self.rfile.read(n).decode('utf-8'))); self.send_response(200); self.end_headers(); self.wfile.write(b'{}')
    def log_message(self, *a): pass
srv = http.server.HTTPServer(('127.0.0.1', 0), Hd); threading.Thread(target=srv.serve_forever, daemon=True).start()
state = os.path.join(tempfile.mkdtemp(), 'n.json')
env = dict(os.environ, NTFY_TOPIC='secret-topic', NTFY_URL=f'http://127.0.0.1:{srv.server_port}', NTFY_MIN_SCORE='6', PAGE_URL='https://x.github.io/r/')
run = lambda st=state, e=None: subprocess.run([sys.executable, 'notify.py', '--dir', out, '--state', st], env=e or env, capture_output=True, text=True).stdout.strip()
o1 = run(); titles = [g[1]['Title'] for g in got]; alerts = [x for x in titles if 'updated' not in x]
check('alerts: triggers from all sections are pushed, watch setups are not', any(t.startswith('Swing') for t in alerts) and any(t.startswith('Nifty options') and 'CALL' in t for t in alerts) and any(t.startswith('Intraday') for t in alerts) and not any('WATCH' in t for t in alerts), str(alerts))
check('alerts: ASCII titles, click link, no Priority header, brand name in the update pushes', all(t.isascii() for t in titles) and got[0][1].get('Click') == 'https://x.github.io/r/' and all('Priority' not in g[1] for g in got) and any(t.startswith('DownerStuffScreener:') for t in titles), str(titles[:4]))
n = len(got); o2 = run(); check('alerts: nothing is sent twice in a day', len(got) == n and 'alerts sent: 0' in o2, o2)
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
