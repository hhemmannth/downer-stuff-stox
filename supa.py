"""A tiny Supabase client for the GitHub jobs (standard library only). It signs in as the scanner user (SUPABASE_BOT_EMAIL and
SUPABASE_BOT_PASSWORD secrets), never as you, and only does what the database rules in supabase/setup.sql allow: read the journal
for the encrypted backup, add and read broker fills.

The project URL and the publishable key are already public in site/js/core.js, so the jobs read them from there."""
import json, os, re, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))

def site_defaults():
    try: s = open(os.path.join(ROOT, 'site', 'js', 'core.js'), encoding='utf-8').read()
    except Exception: return '', ''
    m = re.search(r"App\.SUPA\s*=\s*\{\s*url:\s*'([^']+)',\s*key:\s*'([^']+)'", s)
    return (m.group(1), m.group(2)) if m else ('', '')

class SupaError(Exception): pass

class Supa:
    def __init__(self, env=None):
        e = env if env is not None else os.environ; url, key = site_defaults()
        self.url = (e.get('SUPABASE_URL') or url).rstrip('/'); self.key = e.get('SUPABASE_ANON_KEY') or key
        self.email = (e.get('SUPABASE_BOT_EMAIL') or '').strip(); self.password = e.get('SUPABASE_BOT_PASSWORD') or ''; self.token = None

    @property
    def configured(self): return bool(self.url and self.key and self.email and self.password)

    def _req(self, method, path, body=None, headers=None, auth=True, timeout=40):
        h = {'apikey': self.key, 'Content-Type': 'application/json', 'Accept': 'application/json'}
        if auth and self.token: h['Authorization'] = 'Bearer ' + self.token
        h.update(headers or {})
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode() if body is not None else None, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r: raw = r.read().decode() or 'null'
        except urllib.error.HTTPError as ex:
            try: j = json.loads(ex.read().decode() or '{}'); msg = j.get('message') or j.get('msg') or j.get('error_description') or j.get('hint') or j.get('code') or ''
            except Exception: msg = ''
            raise SupaError(f'HTTP {ex.code}{": " + str(msg) if msg else ""}') from None
        except urllib.error.URLError as ex: raise SupaError(f'could not reach Supabase ({ex.reason})') from None
        return json.loads(raw)

    def login(self):
        if self.token: return self.token
        if not self.configured: raise SupaError('SUPABASE_BOT_EMAIL and SUPABASE_BOT_PASSWORD are not both set')
        try: j = self._req('POST', '/auth/v1/token?grant_type=password', dict(email=self.email, password=self.password), auth=False)
        except SupaError as ex: raise SupaError(f'login as the scanner user failed ({ex}). Check the two secrets and that the user exists and is confirmed.') from None
        if not j or not j.get('access_token'): raise SupaError('login as the scanner user returned no session')
        self.token = j['access_token']; return self.token

    def select(self, table, query='select=*'):
        self.login(); return self._req('GET', f'/rest/v1/{table}?{query}') or []

    def insert_ignore(self, table, rows, conflict):
        """Insert rows, skipping any whose `conflict` column already exists. Returns only the rows that were really inserted."""
        if not rows: return []
        self.login()
        return self._req('POST', f'/rest/v1/{table}?on_conflict={urllib.parse.quote(conflict)}', rows,
                         headers={'Prefer': 'resolution=ignore-duplicates,return=representation'}) or []
