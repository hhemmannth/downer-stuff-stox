"""Alert upgrades: chart picture (15), action alerts (16), Log button (4). A local stand-in plays Telegram. Run: python test_notify2.py"""
import http.server, json, os, tempfile, threading
import chartimg, notify
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
LOG = []; MODE = dict(photo_ok=True)
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        raw = self.rfile.read(int(self.headers['Content-Length'])); kind = self.path.rsplit('/', 1)[-1]
        LOG.append((kind, self.headers.get('Content-Type', ''), raw))
        ok = not (kind == 'sendPhoto' and not MODE['photo_ok'])
        self.send_response(200 if ok else 400); self.end_headers(); self.wfile.write(b'{"ok":true}' if ok else b'{"ok":false}')
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ.update(TELEGRAM_BOT_TOKEN='1:A', TELEGRAM_CHAT_ID='5', TELEGRAM_API=f'http://127.0.0.1:{srv.server_port}'); os.environ.pop('NTFY_TOPIC', None)

C = [[100 + i * 0.5, 101 + i * 0.5, 99 + i * 0.5, 100.4 + i * 0.5] for i in range(40)]
tf = dict(times=[f'12 Aug {9 + i // 4:02d}:{15 * (i % 4):02d}' for i in range(40)], candles=C, ema=[c[3] - 0.3 for c in C])
S = dict(symbol='PBK', direction='long', label='LONG', grade='A+', score=10, status='TRIGGERED', entry=118.0, sl=112.5, t1=123.5, t2=129.0, t3=134.5, zone_bot=113.0, zone_top=116.0, bos_date='2026-08-03', price=118.2, ticks='Key level', notes='')
png = chartimg.render(tf, S, 'PBK · 15m · A+ 10/10')
check('chart: a PNG picture is produced from the candles and the levels', png and png[:8] == b'\x89PNG\r\n\x1a\n' and 5000 < len(png) < 200000, str(len(png or b'')))
check('chart: too few candles gives no picture (the alert still goes as text)', chartimg.render(dict(candles=C[:3]), S) is None)
check('chart: picks the most precise timeframe available', chartimg.pick_tf({'1D': dict(candles=C), '1H': dict(candles=C)})[0] == '1H' and chartimg.pick_tf({'1D': dict(candles=C), '15m': dict(candles=C)})[0] == '15m' and chartimg.pick_tf({})[0] is None)

link = 'https://x.github.io/app/#/trade?s=swing&id=PBK%7Clong'
notify.send_alert('http://127.0.0.1:9', '', S, 'Swing', link, {'PBK': {'15m': tf}}, link + '&log=1')
kind, ctype, raw = LOG[-1]
check('alert: a trigger goes to Telegram as a photo with the caption', kind == 'sendPhoto' and 'multipart/form-data' in ctype and b'\x89PNG' in raw and b'TRIGGERED A+ PBK LONG' in raw)
check('alert: two buttons: Open in DownerStuff and Log this trade (which opens the journal form)', b'Open in DownerStuff' in raw and b'Log this trade' in raw and b'log=1' in raw)
MODE['photo_ok'] = False; LOG.clear(); notify.send_alert('http://127.0.0.1:9', '', S, 'Swing', link, {'PBK': {'15m': tf}}, link + '&log=1'); MODE['photo_ok'] = True
check('alert: if the photo is refused, the same alert goes out as text', [k for k, _, _ in LOG] == ['sendPhoto', 'sendMessage'] and 'Log this trade' in json.loads(LOG[-1][2])['reply_markup']['inline_keyboard'][1][0]['text'])
LOG.clear(); notify.send_alert('http://127.0.0.1:9', '', S, 'Swing', link, {}, None)
check('alert: no chart data -> plain text message, one button', LOG[-1][0] == 'sendMessage' and len(json.loads(LOG[-1][2])['reply_markup']['inline_keyboard']) == 1)
os.environ['ALERT_CHARTS'] = 'off'; LOG.clear(); notify.send_alert('http://127.0.0.1:9', '', S, 'Swing', link, {'PBK': {'15m': tf}}, None); os.environ.pop('ALERT_CHARTS')
check('alert: ALERT_CHARTS=off switches the pictures off', LOG[-1][0] == 'sendMessage')

d = tempfile.mkdtemp(); W = lambda sym, status, score=7: dict(id=f'swing|{sym}|long|2026-08-03', symbol=sym, direction='long', status=status, score=score, zone_bot=1041, zone_top=1052, sl=1036.5)
led = dict(signals=[], watch={w['id']: w for w in (W('AAA', 'IN ZONE (wait for 1H)', 9), W('BBB', '1H CONFIRMED (wait for 15m entry)'), W('LOW', 'IN ZONE (wait for 1H)', 3), W('MID', 'IN ZONE (wait for 1H)', 7), W('FAR', 'SET ALERT (wait for pullback)'))},
           dropped=[dict(W('GONE', 'IN ZONE (wait for 1H)'), dropped='2026-11-11T11:00+05:30', reason='Price closed below the zone: the setup failed.'), dict(W('OLD', 'IN ZONE (wait for 1H)'), dropped='2026-11-09T11:00+05:30', reason='old'), dict(W('NEVER', 'SET ALERT (wait for pullback)'), dropped='2026-11-11T11:00+05:30', reason='far')])
sw = dict(setups=[dict(symbol='AAA', direction='long', stage=3, index_check=dict(state='falling', sector_index='Nifty IT')), dict(symbol='BBB', direction='long', stage=4, index_check=dict(state='ok'))])
json.dump(led, open(os.path.join(d, 'signals_swing.json'), 'w')); json.dump(sw, open(os.path.join(d, 'swing.json'), 'w'))
state = {}; LOG.clear(); n = notify.action_alerts('http://127.0.0.1:9', '', 'https://x.github.io/app/', d, state, '2026-11-11', 6)
titles = [json.loads(r)['text'].split('</b>')[0].split('<b>')[1] for _, _, r in LOG]
check('actions: in zone, 1H confirmed, sector falling and setup off each send one message', n == 4 and sorted(titles) == sorted(['Swing: AAA is in its zone', 'Swing: BBB confirmed on the 1H', 'Swing: AAA on hold, sector index falling', 'Swing: GONE setup is off']), str(titles))
check('actions: only A+ setups announce "in zone"; low scores, far-away setups, old drops and drops you were not waiting on are left out', not any(x in t for t in titles for x in ('LOW', 'MID', 'FAR', 'OLD', 'NEVER')))
check('actions: each message says what to do', any('wait for the 1H rejection' in json.loads(r)['text'] for _, _, r in LOG) and any('Remove any price alert' in json.loads(r)['text'] for _, _, r in LOG))
LOG.clear(); n2 = notify.action_alerts('http://127.0.0.1:9', '', 'https://x.github.io/app/', d, state, '2026-11-11', 6)
check('actions: the same change is not repeated the same day', n2 == 0 and not LOG)
n3 = notify.action_alerts('http://127.0.0.1:9', '', 'https://x.github.io/app/', d, state, '2026-11-12', 6)
check('actions: a setup still in its zone the next day reminds you once more; the old drop does not', n3 == 3)
check('actions: missing files are not an error', notify.action_alerts('http://127.0.0.1:9', '', '', tempfile.mkdtemp(), {}, '2026-11-11', 6) == 0)
big = dict(signals=[], watch={f'w{i}': W(f'S{i}', '1H CONFIRMED (wait for 15m entry)') for i in range(15)}, dropped=[]); d2 = tempfile.mkdtemp()
json.dump(big, open(os.path.join(d2, 'signals_swing.json'), 'w')); json.dump(dict(setups=[]), open(os.path.join(d2, 'swing.json'), 'w')); LOG.clear()
check('actions: never more than 6 messages in one scan', notify.action_alerts('http://127.0.0.1:9', '', 'https://x.github.io/app/', d2, {}, '2026-11-11', 6) == 6 and len(LOG) == 6)
srv.shutdown(); print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED'); raise SystemExit(1 if fails else 0)
