"""Telegram bot (item 18): commands, access control, offsets. A local stand-in plays Telegram. Run: python test_bot.py"""
import datetime as dt, http.server, json, os, tempfile, threading
import bot
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
NOW = dt.datetime(2026, 11, 11, 11, 0, tzinfo=bot.IST); TS = int(NOW.timestamp()); UPD = []; OUT = []; ASKED = []
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length']))); kind = self.path.rsplit('/', 1)[-1]
        if kind == 'getUpdates': ASKED.append(body['offset']); res = dict(ok=True, result=[u for u in UPD if u['update_id'] >= body['offset']])
        else: OUT.append(body); res = dict(ok=True)
        b = json.dumps(res).encode(); self.send_response(200); self.end_headers(); self.wfile.write(b)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
ENV = dict(TELEGRAM_BOT_TOKEN='1:A', TELEGRAM_CHAT_ID='5', TELEGRAM_API=f'http://127.0.0.1:{srv.server_port}', ACCOUNT_CAPITAL='500000', RISK_PCT='0.5', RISK_PCT_APLUS='0.75')
d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, 'health'))
S = lambda sym, stage, score, grade: dict(symbol=sym, stage=stage, stage_label='Entry' if stage == 5 else 'In zone', grade=grade, score=score, max_score=10, zone_bot=1041, zone_top=1052, entry=1070.0, sl=1036.5, t1=1103.5, t2=1137.0, status='TRIGGERED', holds=[], notes='')
json.dump(dict(generated_at='2026-11-11T10:57:00+05:30', setups=[S('PBK', 5, 10, 'A+'), S('AAA', 3, 6, 'A')]), open(os.path.join(d, 'swing.json'), 'w'))
json.dump(dict(rows={'PBK': [5, 'listed', 'Listed: stage 5 (Entry), TRIGGERED', 10], 'COFORGE': [2, 'score', 'Stage 2 (BOS), but the score 3/10 is below your minimum 4/10', 3]}), open(os.path.join(d, 'explain.json'), 'w'))
json.dump(dict(signals=[dict(symbol='PBK', status='ACTIVE', r_now=0.4, entry=1070, stop=1036.5, events=[])]), open(os.path.join(d, 'signals_swing.json'), 'w'))
json.dump(dict(state='running', last_tick='2026-11-11T10:55:40+05:30', last_scan_s=41.0, publish='ok'), open(os.path.join(d, 'health', 'loop.json'), 'w'))
json.dump(dict(data=dict(primary='Angel One', angel=dict(configured=True, ok=True))), open(os.path.join(d, 'health', 'live.json'), 'w'))
A = lambda t: bot.answer(t, d, ENV, NOW)
check('/setups lists the shortlist, strongest first', A('/setups').splitlines()[1].startswith('• PBK') and 'AAA' in A('/setups'))
check('/why explains a listed stock and one that was filtered out', 'Listed: stage 5' in A('/why pbk') and 'below your minimum' in A('/why COFORGE') and 'Score 3/10' in A('/why COFORGE'))
check('/why for an unknown symbol and with no symbol', 'not in the last swing scan' in A('/why XYZ') and 'Send it like this' in A('/why'))
z = A('/size PBK')
check('/size: A+ uses 0.75% of capital: Rs 3,750 risk / Rs 33.50 per share = 111 shares', 'risk per share ₹33.50' in z and 'Risk 0.75% of ₹500,000 = ₹3,750' in z and 'Quantity 111 shares' in z, z.replace('\n', ' | '))
check('/size: an A setup uses 0.5%', 'Risk 0.5% of ₹500,000 = ₹2,500' in A('/size AAA') and 'Quantity 74 shares' in A('/size AAA'))
check('/size without capital set explains the formula instead of guessing', 'ACCOUNT_CAPITAL' in bot.answer('/size PBK', d, dict(ENV, ACCOUNT_CAPITAL=''), NOW))
check('/size for a stock that is not a setup', 'not a listed swing setup' in A('/size TCS'))
check('/open shows tracked trades with R and stop', 'PBK (swing): +0.40R' in A('/open'))
st = A('/status'); check('/status: loop heartbeat, section ages, data source', 'last tick 4 min ago' in st and 'Swing: 3 min ago' in st and 'Data: Angel One' in st, st.replace('\n', ' | '))
check('/brief and /recap give the digests on demand', A('/brief').startswith('Morning brief') and A('/recap').startswith('Day recap'))
check('/help, /start and unknown commands list the commands; a group-style /help@bot works', '/setups' in A('/help') and '/setups' in A('/start') and 'did not understand' in A('/dance') and '/setups' in A('/help@DownerStuff_bot'))

msg = lambda uid, chat, text, age=10: dict(update_id=uid, message=dict(chat=dict(id=chat), text=text, date=TS - age))
UPD[:] = [msg(100, 5, '/setups'), msg(101, 999, '/setups'), msg(102, 5, 'hello'), msg(103, 5, '/why PBK'), msg(104, 5, '/status', age=7 * 3600)]
sp = os.path.join(tempfile.mkdtemp(), 'state', 'bot.json'); n = bot.poll(d, sp, ENV, NOW)
check('poll: answers your commands only: a stranger, plain chatter and a stale message get no reply', n == 2 and [o['chat_id'] for o in OUT] == ['5', '5'] and 'PBK' in OUT[0]['text'] and 'Listed' in OUT[1]['text'], f'{n} {[o["chat_id"] for o in OUT]}')
check('poll: remembers its place so nothing is answered twice', json.load(open(sp))['offset'] == 105)
OUT.clear(); UPD.append(msg(105, 5, '/open')); n = bot.poll(d, sp, ENV, NOW)
check('poll: the next run asks only for newer messages and answers the new one', ASKED[-1] == 105 and n == 1 and 'PBK' in OUT[0]['text'])
check('poll: replies are HTML-escaped (a symbol like M&M cannot break the message)', bot.html.escape('M&M') == 'M&amp;M' and OUT[0]['parse_mode'] == 'HTML')
check('poll: no Telegram secrets, nothing happens', bot.poll(d, sp, {}, NOW) == 0)
srv.shutdown(); print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED'); raise SystemExit(1 if fails else 0)
