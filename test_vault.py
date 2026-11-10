"""Encrypted backup (29), restore, tradebook import (21) and the Supabase client. A local stand-in plays Supabase and Angel One,
including the database rules (the scanner can read the journal, add fills, nothing else). Run: python test_vault.py"""
import datetime as dt, http.server, json, os, shutil, subprocess, sys, tempfile, threading, urllib.parse
import backup, restore, supa, tradebook, datasource
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
IST = backup.IST; NOW = dt.datetime(2026, 11, 11, 23, 0, tzinfo=IST)
JOURNAL = [dict(user_id='uid-1', updated_at='2026-11-11T09:00:00Z', payload=dict(cur='j_main', journals=[dict(id='j_main', name='Hemanth’s journal', set=dict(capital=500000), lists=dict(setups=['Pullback from OB']), trades=[dict(id='t1', d='2026-11-09', inst='PBK', entry=1070, sl=1036.5)]), dict(id='demo1', name='Demo', demo=True, trades=[])]))]
FILLS = []; STATE = dict(rows=JOURNAL, journal_visible=True, auth_ok=True, angel=[], angel_error=None); LOG = []
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _j(self, obj, code=200): b = json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(b)
    def _body(self): n = int(self.headers.get('Content-Length') or 0); return json.loads(self.rfile.read(n) or b'null') if n else None
    def _scanner(self): return self.headers.get('Authorization') == 'Bearer JWT-SCANNER' and bool(self.headers.get('apikey'))
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); LOG.append(('GET', u.path))
        if u.path.startswith('/rest/v1/journal_state'): return self._j(STATE['rows'] if (self._scanner() and STATE['journal_visible']) else ([] if self._scanner() else dict(message='JWT expired')), 200 if self._scanner() else 401)
        if u.path.startswith('/rest/v1/broker_fills'): return self._j(list(FILLS) if self._scanner() else dict(message='no'), 200 if self._scanner() else 401)
        if u.path.endswith('/getTradeBook'):
            if STATE['angel_error']: return self._j(dict(status=False, message=STATE['angel_error'], errorcode='AB1010'))
            return self._j(dict(status=True, message='SUCCESS', errorcode='', data=STATE['angel']))
        self._j({}, 404)
    def do_POST(self):
        u = urllib.parse.urlparse(self.path); body = self._body(); LOG.append(('POST', u.path))
        if u.path == '/auth/v1/token':
            ok = body.get('email') == 'hhemmannth+scanner@gmail.com' and body.get('password') == 'correct horse' and STATE['auth_ok']
            return self._j(dict(access_token='JWT-SCANNER') if ok else dict(error_description='Invalid login credentials'), 200 if ok else 400)
        if 'loginByPassword' in u.path: return self._j(dict(status=True, message='SUCCESS', data=dict(jwtToken='JWT-ANGEL')))
        if u.path.startswith('/rest/v1/broker_fills'):
            if not self._scanner(): return self._j(dict(message='denied'), 401)
            have = {r['fill_id'] for r in FILLS}; new = [r for r in body if r['fill_id'] not in have]; FILLS.extend(new); return self._j(new, 201)
        self._j({}, 404)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start(); URL = f'http://127.0.0.1:{srv.server_port}'
ENV = dict(SUPABASE_URL=URL, SUPABASE_ANON_KEY='anon', SUPABASE_BOT_EMAIL='hhemmannth+scanner@gmail.com', SUPABASE_BOT_PASSWORD='correct horse')
PW = 'a long test passphrase'

# ---- the Supabase client reads its defaults from the public site code
u, k = supa.site_defaults()
check('supabase client: the project URL and publishable key come from site/js/core.js, nothing extra to configure', u.startswith('https://') and u.endswith('.supabase.co') and k.startswith('sb_publishable_'), u)

# ---- encryption
blob = backup.encrypt(b'{"x": 1}', PW)
check('crypto: encrypts and decrypts with the right passphrase; the file does not contain the text', backup.decrypt(blob, PW) == b'{"x": 1}' and b'"x"' not in blob and blob.startswith(b'DSBK1'))
bad = None
try: backup.decrypt(blob, 'a different passphrase')
except ValueError as e: bad = str(e)
check('crypto: a wrong passphrase is refused with a clear message', bad and 'wrong passphrase' in bad)
tampered = bytearray(blob); tampered[-3] ^= 1
try: backup.decrypt(bytes(tampered), PW); t_ok = False
except ValueError: t_ok = True
check('crypto: a damaged file is detected, never half-decrypted', t_ok and backup.encrypt(b'a', PW) != backup.encrypt(b'a', PW))

# ---- backup run
vault = os.path.join(tempfile.mkdtemp(), 'vault'); health = os.path.join(tempfile.mkdtemp(), 'health', 'backup.json')
r = backup.run(supa.Supa(ENV), vault, PW, NOW, health)
fl = backup.files(vault)
check('backup: one encrypted file is written, named by time and content fingerprint', r['changed'] and len(fl) == 1 and fl[0][0].startswith('journal-20261111-2300-') and fl[0][0].endswith('.dsbk'), str(fl))
raw = open(os.path.join(vault, fl[0][0]), 'rb').read()
check('backup: the file on disk holds no readable journal content', b'PBK' not in raw and b'journal' not in raw and b'Hemanth' not in raw)
data = json.loads(backup.decrypt(raw, PW))
check('backup: decrypting gives back the journal exactly, with the time it was taken', data['journal_state'] == JOURNAL and data['taken_at'].startswith('2026-11-11T23:00'))
hj = json.load(open(health))
check('backup: only a time, a size and a file name are published for the health page, never content', set(hj) == {'at', 'ok', 'changed', 'files', 'bytes', 'newest'} and hj['ok'] and 'PBK' not in json.dumps(hj))
r2 = backup.run(supa.Supa(ENV), vault, PW, NOW + dt.timedelta(days=1))
check('backup: an unchanged journal the next night writes no new file', not r2['changed'] and len(backup.files(vault)) == 1)
JOURNAL[0]['payload']['journals'][0]['trades'].append(dict(id='t2', d='2026-11-10', inst='TCS')); r3 = backup.run(supa.Supa(ENV), vault, PW, NOW + dt.timedelta(days=2))
check('backup: a changed journal writes a new file (two nightly files now)', r3['changed'] and len(backup.files(vault)) == 2)

# ---- failures say what to check
STATE['journal_visible'] = False
try: backup.run(supa.Supa(ENV), vault, PW, NOW + dt.timedelta(days=3)); msg = ''
except RuntimeError as e: msg = str(e)
check('backup: if the scanner cannot see the journal, it fails loudly and names supabase/setup.sql (never a silent empty backup)', 'setup.sql' in msg and len(backup.files(vault)) == 2, msg[:90])
STATE['journal_visible'] = True
try: backup.run(supa.Supa(dict(ENV, SUPABASE_BOT_PASSWORD='wrong')), vault, PW, NOW); msg = ''
except Exception as e: msg = str(e)
check('backup: a wrong scanner password says so', 'login as the scanner user failed' in msg and 'Invalid login credentials' in msg, msg[:100])
try: backup.run(supa.Supa(ENV), vault, 'short', NOW); msg = ''
except RuntimeError as e: msg = str(e)
check('backup: a short passphrase is refused', '12 characters' in msg)
try: backup.run(supa.Supa(dict(ENV, SUPABASE_BOT_EMAIL='')), vault, PW, NOW); msg = ''
except Exception as e: msg = str(e)
check('backup: missing secrets are named', 'not both set' in msg)

# ---- thinning old files
v2 = tempfile.mkdtemp()
for d in ['20260101-2300', '20260110-2300', '20260125-2300', '20260203-2300', '20260920-2300', '20261001-2300', '20261105-2300', '20261110-2300']:
    open(os.path.join(v2, f'journal-{d}-ab12cd34.dsbk'), 'wb').write(b'x')
gone = backup.prune(v2, NOW); left = [x[1] for x in backup.files(v2)]
check('prune: nightly for 90 days, then one per month (last of each month kept, other old ones removed)', left == ['20260125', '20260203', '20260920', '20261001', '20261105', '20261110'] and len(gone) == 2, str(left))

# ---- restore
out = os.path.join(tempfile.mkdtemp(), 'restored'); os.environ['BACKUP_PASSPHRASE'] = PW
rc = restore.main([os.path.join(vault, backup.files(vault)[-1][0]), '--out', out])
files_out = sorted(os.listdir(out)); rj = json.load(open(os.path.join(out, [f for f in files_out if f.endswith('.restore.json')][0])))
check('restore: writes raw.json and one file per real journal (the demo journal is skipped)', rc == 0 and 'raw.json' in files_out and len([f for f in files_out if f.endswith('.restore.json')]) == 1, str(files_out))
check('restore: the journal file is in the format the app\'s Journal > Import accepts, with every trade', rj['format'] == 'trade-insight' and rj['journal']['name'] == 'Hemanth’s journal' and len(rj['journal']['trades']) == 2 and rj['journal']['set']['capital'] == 500000)
os.environ['BACKUP_PASSPHRASE'] = 'not the passphrase'; check('restore: a wrong passphrase gives a clear error and writes nothing', restore.main([os.path.join(vault, backup.files(vault)[-1][0]), '--out', out + '2']) == 1 and not os.path.exists(out + '2'))
os.environ['BACKUP_PASSPHRASE'] = PW

# ---- tradebook
AO = [dict(exchange='NSE', producttype='INTRADAY', tradingsymbol='RELIANCE-EQ', instrumenttype='', transactiontype='BUY', fillprice='1300.50', fillsize='100', orderid='2411100001', fillid='9001', filltime='09:45:12'),
      dict(exchange='NSE', producttype='INTRADAY', tradingsymbol='RELIANCE-EQ', instrumenttype='', transactiontype='SELL', fillprice='1312.00', fillsize='100', orderid='2411100002', fillid='9002', filltime='11:20:03'),
      dict(exchange='NFO', producttype='INTRADAY', tradingsymbol='NIFTY10NOV2624400CE', instrumenttype='OPTIDX', optiontype='CE', strikeprice='24400.000000', expirydate='10NOV2026', marketlot='65', transactiontype='BUY', fillprice='120.5', fillsize='65', orderid='2411100003', fillid='9003', filltime='10:05:00'),
      dict(exchange='NSE', producttype='DELIVERY', tradingsymbol='PBK-EQ', transactiontype='BUY', fillprice='1070', fillsize='100', orderid='2411100004', fillid='9004', filltime='15:16:30'),
      dict(exchange='NSE', producttype='DELIVERY', tradingsymbol='JUNK', transactiontype='HOLD', fillprice='1', fillsize='1', orderid='1', fillid='1'), dict(exchange='NSE', tradingsymbol='ZERO', transactiontype='BUY', fillprice='0', fillsize='10', orderid='2', fillid='2')]
n = tradebook.normalise(AO, '2026-11-11', 'uid-1')
check('tradebook: fills are normalised; unusable rows (not buy/sell, zero price) are dropped', len(n) == 4 and {x['side'] for x in n} == {'BUY', 'SELL'})
check('tradebook: each fill has a stable id, the right time in IST and the owner', n[0]['fill_id'] == 'ao-2026-11-11-2411100001-9001' and n[0]['filled_at'] == '2026-11-11T09:45:12+05:30' and n[0]['user_id'] == 'uid-1')
o = n[2]; check('tradebook: option details are kept (lot, strike, type, expiry)', o['option_type'] == 'CE' and o['strike'] == 24400 and o['lot'] == 65 and o['instrument'] == 'OPTIDX' and o['expiry'] == '10NOV2026')
check('tradebook: a fill with no id gets a stable fingerprint id instead', tradebook.normalise([dict(tradingsymbol='X', transactiontype='BUY', fillprice='1', fillsize='1')], '2026-11-11')[0]['fill_id'] == tradebook.normalise([dict(tradingsymbol='X', transactiontype='BUY', fillprice='1', fillsize='1')], '2026-11-11')[0]['fill_id'])
STATE['angel'] = AO; AENV = dict(ANGEL_API_KEY='k', ANGEL_CLIENT_CODE='c', ANGEL_MPIN='1', ANGEL_TOTP_SECRET='JBSWY3DPEHPK3PXP', ANGEL_BASE=URL, ANGEL_MASTER_URL=URL + '/master')
for x in os.listdir(tempfile.gettempdir()):
    if x.startswith('angel_session_'): os.remove(os.path.join(tempfile.gettempdir(), x))
rr = tradebook.run(datasource.Angel(AENV), supa.Supa(ENV), dt.datetime(2026, 11, 11, 15, 50, tzinfo=IST))
check('tradebook: reads the day\'s fills from Angel One (a GET) and saves the new ones, with your user id found from your journal row', rr == dict(day='2026-11-11', fills=4, new=4) and len(FILLS) == 4 and all(f['user_id'] == 'uid-1' for f in FILLS) and ('GET', '/rest/secure/angelbroking/order/v1/getTradeBook') in LOG, str(rr))
rr2 = tradebook.run(datasource.Angel(AENV), supa.Supa(ENV), dt.datetime(2026, 11, 11, 16, 5, tzinfo=IST))
check('tradebook: running again the same day adds nothing twice', rr2['fills'] == 4 and rr2['new'] == 0 and len(FILLS) == 4)
STATE['angel'] = AO + [dict(AO[0], fillid='9099', filltime='13:00:00')]; rr3 = tradebook.run(datasource.Angel(AENV), supa.Supa(ENV), dt.datetime(2026, 11, 11, 16, 30, tzinfo=IST))
check('tradebook: a later fill during the day is picked up on its own', rr3['new'] == 1 and len(FILLS) == 5)
STATE['angel'] = None; check('tradebook: no trades today is fine', tradebook.run(datasource.Angel(AENV), supa.Supa(ENV), NOW)['fills'] == 0)
STATE['angel_error'] = 'Static IP not registered for this API key'
try: tradebook.run(datasource.Angel(AENV), supa.Supa(ENV), NOW); msg = ''
except Exception as e: msg = str(e)
check('tradebook: an Angel One refusal comes through in its own words', 'Static IP' in msg, msg[:80])
STATE['angel_error'] = None
env0 = {k: v for k, v in os.environ.items() if not k.startswith(('ANGEL_', 'SUPABASE_'))}; p = subprocess.run([sys.executable, 'tradebook.py', '--force'], capture_output=True, text=True, env=env0, cwd=os.path.dirname(os.path.abspath(__file__)))
check('tradebook: with nothing configured it explains and exits quietly (the scheduled run stays green)', p.returncode == 0 and 'not set up' in p.stdout, p.stdout.strip()[:100])
srv.shutdown(); print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED'); raise SystemExit(1 if fails else 0)
