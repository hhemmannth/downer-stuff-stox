"""Publish the site to the gh-pages branch (GitHub Pages "Deploy from a branch").
Each publish is ONE orphan commit (no history, so the repo never grows) pushed with a lease, and files another writer
changed in the meantime are merged in first, so the 5-minute loop, the gold loop and the manual/hourly runs never wipe each other's data.

Which files are "ours": every file whose content we changed since our last publish (or since the clone). The record of what the branch
held when we last saw it is kept in .git/ds_seen.json (path -> git blob id). Before (until 17 Nov 2026) "ours" meant "modified after
`since`", and a file we had just checked out from another writer counted as modified, so the next publish pushed that old copy back over
the other writer's newer one: the market loop reverted the gold loop's files and vice versa, and a once-a-day file (readiness.json) could
stay stuck on yesterday's copy for good. Trade ledgers (data/signals_*.json) and alert state (state/*.json) written by two runs at once
are merged by content instead of one copy winning."""
import json, os, shutil, subprocess, time

BRANCH = 'gh-pages'
SEEN = 'ds_seen.json'

def sh(args, cwd=None, check=True, inp=None):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, input=inp)
    if check and r.returncode != 0: raise RuntimeError(f"{' '.join(args[:3])} failed: {r.stderr.strip()[:300]}")
    return r

def remote_url():
    if os.environ.get('PUBLISH_REMOTE'): return os.environ['PUBLISH_REMOTE']
    return f"https://x-access-token:{os.environ['GITHUB_TOKEN']}@github.com/{os.environ['GITHUB_REPOSITORY']}.git"

def _tree(pub, ref):
    """{path: blob id} of a commit or tree."""
    out = {}
    for line in sh(['git', 'ls-tree', '-r', ref], pub).stdout.splitlines():
        meta, path = line.split('\t', 1); out[path] = meta.split()[2]
    return out

def _seen_path(pub): return os.path.join(pub, '.git', SEEN)
def _load_seen(pub):
    try: return json.load(open(_seen_path(pub)))
    except Exception: return None
def _save_seen(pub, seen):
    with open(_seen_path(pub) + '.tmp', 'w') as f: json.dump(seen, f)
    os.replace(_seen_path(pub) + '.tmp', _seen_path(pub))

def prepare(pub):
    """Get the currently published site (with all earlier data) into `pub`, or start an empty branch the first time."""
    if os.path.isdir(os.path.join(pub, '.git')): return pub
    url = remote_url()
    if sh(['git', 'clone', '-q', '--depth', '1', '--branch', BRANCH, url, pub], check=False).returncode != 0:
        shutil.rmtree(pub, ignore_errors=True); os.makedirs(pub)
        sh(['git', 'init', '-q'], pub); sh(['git', 'remote', 'add', 'origin', url], pub); sh(['git', 'checkout', '-q', '--orphan', BRANCH], pub)
        _save_seen(pub, {})
    else:
        _save_seen(pub, _tree(pub, 'HEAD'))                       # what the branch held when we cloned it: anything we change from here is ours
    sh(['git', 'config', 'user.name', 'DownerStuffScreener'], pub); sh(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], pub)
    os.makedirs(os.path.join(pub, 'data'), exist_ok=True); os.makedirs(os.path.join(pub, 'state'), exist_ok=True)
    open(os.path.join(pub, '.gitignore'), 'w').write('*.tmp\n')
    return pub

def _files(root):
    out = {}
    for d, dirs, files in os.walk(root):
        if '.git' in dirs: dirs.remove('.git')
        for f in files:
            if f.endswith('.tmp'): continue
            p = os.path.join(d, f); out[os.path.relpath(p, root)] = os.path.getmtime(p)
    return out

def _blobs(pub, paths):
    """git blob ids of local files (the same ids ls-tree shows), in one call."""
    paths = list(paths)
    if not paths: return {}
    ids = sh(['git', 'hash-object', '--stdin-paths'], pub, inp='\n'.join(paths) + '\n').stdout.split()
    return dict(zip(paths, ids))

# ------------------------------------------------------------------ merging two writers' copies of the same file
def _rank(sig):
    """How far a tracked trade has got: a closed trade beats an open one, then the one checked further, then more events."""
    return (1 if sig.get('status') == 'CLOSED' else 0, str(sig.get('checked_to') or ''), len(sig.get('events') or []))

def merge_ledger(mine, theirs):
    """Two runs updated the same trade ledger: keep every trade either of them has; for a trade both have, the one that got further."""
    out = dict(mine); by = {}
    for s in (theirs.get('signals') or []) + (mine.get('signals') or []):
        k = s.get('id'); cur = by.get(k)
        if cur is None or _rank(s) > _rank(cur): by[k] = s
    order = [s.get('id') for s in mine.get('signals') or []] + [s.get('id') for s in theirs.get('signals') or [] if s.get('id') not in {x.get('id') for x in mine.get('signals') or []}]
    out['signals'] = [by[k] for k in dict.fromkeys(order) if k in by]
    trades = {s.get('id') for s in out['signals']}
    w = dict(theirs.get('watch') or {}); w.update(mine.get('watch') or {}); out['watch'] = {k: v for k, v in w.items() if k not in trades}
    dd = {}
    for d in (theirs.get('dropped') or []) + (mine.get('dropped') or []):
        k = d.get('id'); cur = dd.get(k)
        if k in trades or k in out['watch']: continue
        if cur is None or str(d.get('dropped') or '') >= str(cur.get('dropped') or ''): dd[k] = d
    out['dropped'] = sorted(dd.values(), key=lambda d: str(d.get('dropped') or ''))[-200:]
    pp = {}                                                                     # paper-trading records are immutable: the copy already on the branch wins
    for p_ in (mine.get('paper') or []) + (theirs.get('paper') or []): pp[p_.get('id')] = p_
    if pp: out['paper'] = sorted(pp.values(), key=lambda p_: str(p_.get('exit_time') or ''))
    out['updated'] = max(str(mine.get('updated') or ''), str(theirs.get('updated') or '')) or mine.get('updated')
    return out

def merge_state(mine, theirs):
    """Alert/dedupe state (state/*.json): what either run already sent stays 'sent', so nothing is pushed to your phone twice."""
    if not isinstance(mine, dict) or not isinstance(theirs, dict): return mine
    out = dict(theirs); out.update(mine)
    for k in set(mine) & set(theirs):
        a, b = mine[k], theirs[k]
        if isinstance(a, list) and isinstance(b, list): out[k] = list(dict.fromkeys([json.dumps(x, sort_keys=True) for x in b + a])); out[k] = [json.loads(x) for x in out[k]]
        elif isinstance(a, dict) and isinstance(b, dict): out[k] = merge_state(a, b)
        elif k == 'offset' and isinstance(a, (int, float)) and isinstance(b, (int, float)): out[k] = max(a, b)
    if 'date' in mine and 'date' in theirs and mine['date'] != theirs['date']:        # notified.json keeps one day: the newer day wins as a whole
        return mine if str(mine['date']) > str(theirs['date']) else theirs
    return out

def _merge_file(pub, path, ref):
    """Merge the branch's copy of `path` into ours, for the files where both copies matter. Returns True if it merged."""
    name = os.path.basename(path)
    kind = 'ledger' if path.startswith('data/') and name.startswith('signals_') and name.endswith('.json') else 'state' if path.startswith('state/') and name.endswith('.json') else None
    if not kind: return False
    try:
        mine = json.load(open(os.path.join(pub, path))); theirs = json.loads(sh(['git', 'show', f'{ref}:{path}'], pub).stdout)
        merged = merge_ledger(mine, theirs) if kind == 'ledger' else merge_state(mine, theirs)
    except Exception as ex:
        print(f'  publish: could not merge {path} ({ex}); keeping this run\'s copy'); return False
    tmp = os.path.join(pub, path + '.tmp')
    with open(tmp, 'w') as f: json.dump(merged, f, separators=(',', ':'), default=str)
    os.replace(tmp, os.path.join(pub, path)); return True

def publish(pub, since, site_dir='site', message='update', tries=5):
    """Push everything in `pub`. Files we changed (and the site files) are ours; for any other file, the version already on the
    branch wins, because another run may have refreshed it while we were scanning. `since` is only used when there is no record
    of what we last saw (a pub folder made by an older version of this file)."""
    for item in os.listdir(site_dir):
        s, d = os.path.join(site_dir, item), os.path.join(pub, item)
        (shutil.copytree(s, d, dirs_exist_ok=True) if os.path.isdir(s) else shutil.copy2(s, d))
    open(os.path.join(pub, '.nojekyll'), 'w').close()
    site = set(_files(site_dir)); local = _files(pub); seen = _load_seen(pub)
    if seen is None: mine = {f for f, m in local.items() if m >= since} | site
    else:
        cur = _blobs(pub, local); mine = {f for f in local if cur.get(f) != seen.get(f)} | site
    r = None
    for attempt in range(tries):                                  # `mine` is fixed before the first try: what we restore from the branch is never ours
        lease = None
        if sh(['git', 'fetch', '-q', '--depth', '1', 'origin', BRANCH], pub, check=False).returncode == 0:
            lease = sh(['git', 'rev-parse', 'FETCH_HEAD'], pub).stdout.strip(); remote = _tree(pub, lease)
            take = [f for f in remote if f not in mine]
            if take: sh(['git', 'checkout', lease, '--'] + take, pub)
            for f in mine & set(remote):
                if seen is not None and remote[f] != seen.get(f): _merge_file(pub, f, lease)     # both of us changed it since we last looked
        sh(['git', 'add', '-A'], pub); tree = sh(['git', 'write-tree'], pub).stdout.strip()
        commit = sh(['git', 'commit-tree', tree, '-m', message], pub).stdout.strip()
        push = ['git', 'push', '-q', 'origin', f'{commit}:refs/heads/{BRANCH}', '--force-with-lease=' + (f'{BRANCH}:{lease}' if lease else f'{BRANCH}:')]
        r = sh(push, pub, check=False)
        if r.returncode == 0:
            sh(['git', 'update-ref', f'refs/heads/{BRANCH}', commit], pub); _save_seen(pub, _tree(pub, commit)); return commit
        time.sleep(2 + attempt * 2)                              # someone else published in between: merge again and retry
    raise RuntimeError('publish failed after retries: ' + (r.stderr.strip()[:300] if r is not None else 'no attempt'))

if __name__ == '__main__':          # python publish.py prepare pub | python publish.py push pub <since-epoch> <message>
    import sys
    if sys.argv[1] == 'prepare': prepare(sys.argv[2])
    elif sys.argv[1] == 'push': print('published', publish(sys.argv[2], float(sys.argv[3]), message=' '.join(sys.argv[4:]) or 'update'))
