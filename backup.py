#!/usr/bin/env python3
"""Nightly encrypted journal backup (item 29).

  python backup.py --vault vault --health pub/data/health/backup.json

Signs in as the scanner user, reads your journal (and any broker fills), encrypts it with your BACKUP_PASSPHRASE
(AES-256-GCM, key from scrypt) and writes it into the vault folder, which the workflow commits to your PRIVATE backup repo.
Nothing readable ever leaves this script: the repo holds only .dsbk files that need your passphrase.
A night with no change writes no new file. Old files are thinned: every night for 90 days, then one per month.
Only a time and a file size are published to the System health page; never any journal content.

Restore: python restore.py <file.dsbk> (see restore.py)."""
import argparse, datetime as dt, hashlib, json, os, re, sys
IST = dt.timezone(dt.timedelta(hours=5, minutes=30)); MAGIC = b'DSBK1'; NAME = re.compile(r'^journal-(\d{8})-(\d{4})-([0-9a-f]{8})\.dsbk$')

def _key(passphrase, salt):
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    return Scrypt(salt=salt, length=32, n=2 ** 15, r=8, p=1).derive(passphrase.encode('utf-8'))

def encrypt(plain, passphrase):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt, nonce = os.urandom(16), os.urandom(12)
    return MAGIC + salt + nonce + AESGCM(_key(passphrase, salt)).encrypt(nonce, plain, MAGIC)

def decrypt(blob, passphrase):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + 28: raise ValueError('this is not a DownerStuff backup file')
    salt, nonce, ct = blob[5:21], blob[21:33], blob[33:]
    try: return AESGCM(_key(passphrase, salt)).decrypt(nonce, ct, MAGIC)
    except Exception: raise ValueError('wrong passphrase, or the file is damaged') from None

def digest(data):
    """Fingerprint of the content (not the time it was taken), so an unchanged night writes no file."""
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()[:8]

def files(vault):
    out = []
    for f in sorted(os.listdir(vault)) if os.path.isdir(vault) else []:
        m = NAME.match(f)
        if m: out.append((f, m.group(1), m.group(2), m.group(3)))
    return out

def prune(vault, now, keep_days=90):
    """Keep every file from the last `keep_days`; before that keep only the last file of each month. Returns the deleted names."""
    cut = (now - dt.timedelta(days=keep_days)).strftime('%Y%m%d'); old = [x for x in files(vault) if x[1] < cut]; last = {}
    for x in old: last[x[1][:6]] = x[0]
    gone = [x[0] for x in old if last[x[1][:6]] != x[0]]
    for f in gone: os.remove(os.path.join(vault, f))
    return gone

def take(supa):
    j = supa.select('journal_state', 'select=*')
    if not j: raise RuntimeError('no journal row is visible to the scanner user. Did you run supabase/setup.sql and use the right scanner email?')
    try: fills = supa.select('broker_fills', 'select=*&order=filled_at.asc')
    except Exception: fills = []
    return dict(journal_state=j, broker_fills=fills)

def run(supa, vault, passphrase, now=None, health=None):
    now = now or dt.datetime.now(IST)
    if len(passphrase or '') < 12: raise RuntimeError('BACKUP_PASSPHRASE must be at least 12 characters')
    data = take(supa); h = digest(data); os.makedirs(vault, exist_ok=True); have = files(vault); changed = not have or have[-1][3] != h
    name = have[-1][0] if not changed else f'journal-{now:%Y%m%d-%H%M}-{h}.dsbk'
    if changed:
        blob = encrypt(json.dumps(dict(taken_at=now.isoformat(timespec='seconds'), **data), default=str).encode(), passphrase)
        if json.loads(decrypt(blob, passphrase))['journal_state'] != json.loads(json.dumps(data['journal_state'], default=str)): raise RuntimeError('verification failed: the encrypted file does not decrypt back to the journal')
        with open(os.path.join(vault, name), 'wb') as f: f.write(blob)
    gone = prune(vault, now); size = os.path.getsize(os.path.join(vault, name))
    rep = dict(at=now.isoformat(timespec='seconds'), ok=True, changed=changed, files=len(files(vault)), bytes=size, newest=name)
    if health:
        os.makedirs(os.path.dirname(health) or '.', exist_ok=True)
        with open(health, 'w') as f: json.dump(rep, f)
    return dict(rep, pruned=len(gone))

def notify_failed(msg):
    import notify
    topic = os.environ.get('NTFY_TOPIC', '').strip(); page = os.environ.get('PAGE_URL', '').strip().rstrip('/')
    if not topic and not notify.telegram_ready(): return
    try: notify.post(os.environ.get('NTFY_URL', 'https://ntfy.sh').rstrip('/'), topic, 'Journal backup failed', msg, 'warning', (page + '/#/health') if page else '')
    except Exception as ex: print(f'could not send the alert: {ex}', file=sys.stderr)

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--vault', default='vault'); ap.add_argument('--health', default=None); ap.add_argument('--failed', default=None, help='send the failure alert with this message and stop')
    a = ap.parse_args(argv)
    if a.failed is not None: notify_failed(a.failed or 'The nightly backup did not finish. Open the backup run in GitHub Actions to see why.'); return 0
    from supa import Supa
    try:
        r = run(Supa(), a.vault, os.environ.get('BACKUP_PASSPHRASE', ''), health=a.health)
        print(f"backup: {'new file ' + r['newest'] if r['changed'] else 'no change since the last backup'} ({r['bytes']:,} bytes), {r['files']} files kept, {r['pruned']} old files removed"); return 0
    except Exception as ex:
        print(f'backup failed: {ex}', file=sys.stderr); notify_failed(str(ex)[:300]); return 1

if __name__ == '__main__':
    sys.exit(main())
