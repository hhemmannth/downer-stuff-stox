#!/usr/bin/env python3
"""Decrypt a nightly backup on your own computer.

  pip install cryptography
  python restore.py journal-20261110-2300-ab12cd34.dsbk            (asks for your BACKUP_PASSPHRASE)
  python restore.py FILE --out restored                              (folder for the results, default: restored)

Writes, into the output folder:
  raw.json                       everything in the backup
  <journal name>.restore.json    one file per journal, in the format the app's Journal > Import accepts

To put a journal back: open the app, Journal > Import, choose the .restore.json file. It is added as a new journal, nothing is overwritten."""
import argparse, getpass, json, os, re, sys

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--out', default='restored'); a = ap.parse_args(argv)
    import backup
    pw = os.environ.get('BACKUP_PASSPHRASE') or getpass.getpass('Backup passphrase: ')
    try: data = json.loads(backup.decrypt(open(a.file, 'rb').read(), pw))
    except ValueError as ex: print(f'Could not open it: {ex}', file=sys.stderr); return 1
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'raw.json'), 'w') as f: json.dump(data, f, indent=1)
    n = 0
    for row in data.get('journal_state', []):
        for j in (row.get('payload') or {}).get('journals', []):
            if j.get('demo'): continue
            name = re.sub(r'[^\w]+', '-', j.get('name') or 'journal').strip('-') or 'journal'
            with open(os.path.join(a.out, f'{name}.restore.json'), 'w') as f:
                json.dump(dict(format='trade-insight', version=1, exported=data.get('taken_at'), journal=dict(name=j.get('name'), set=j.get('set'), lists=j.get('lists'), trades=j.get('trades', []))), f, indent=1)
            n += 1
    print(f"Backup taken {data.get('taken_at')}: {n} journal file(s) written to {a.out}/"); return 0

if __name__ == '__main__':
    sys.exit(main())
