"""Publish the site to the gh-pages branch (GitHub Pages "Deploy from a branch").
Each publish is ONE orphan commit (no history, so the repo never grows) pushed with a lease, and files another writer
changed in the meantime are merged in first, so the 5-minute loop and the manual/hourly runs never wipe each other's data."""
import os, shutil, subprocess, time

BRANCH = 'gh-pages'

def sh(args, cwd=None, check=True):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0: raise RuntimeError(f"{' '.join(args[:3])} failed: {r.stderr.strip()[:300]}")
    return r

def remote_url():
    if os.environ.get('PUBLISH_REMOTE'): return os.environ['PUBLISH_REMOTE']
    return f"https://x-access-token:{os.environ['GITHUB_TOKEN']}@github.com/{os.environ['GITHUB_REPOSITORY']}.git"

def prepare(pub):
    """Get the currently published site (with all earlier data) into `pub`, or start an empty branch the first time."""
    if os.path.isdir(os.path.join(pub, '.git')): return pub
    url = remote_url()
    if sh(['git', 'clone', '-q', '--depth', '1', '--branch', BRANCH, url, pub], check=False).returncode != 0:
        shutil.rmtree(pub, ignore_errors=True); os.makedirs(pub)
        sh(['git', 'init', '-q'], pub); sh(['git', 'remote', 'add', 'origin', url], pub); sh(['git', 'checkout', '-q', '--orphan', BRANCH], pub)
    sh(['git', 'config', 'user.name', 'DownerStuffScreener'], pub); sh(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], pub)
    os.makedirs(os.path.join(pub, 'data'), exist_ok=True); os.makedirs(os.path.join(pub, 'state'), exist_ok=True)
    open(os.path.join(pub, '.gitignore'), 'w').write('*.tmp\n')
    return pub

def _files(root):
    out = {}
    for d, dirs, files in os.walk(root):
        if '.git' in dirs: dirs.remove('.git')
        for f in files: p = os.path.join(d, f); out[os.path.relpath(p, root)] = os.path.getmtime(p)
    return out

def publish(pub, since, site_dir='site', message='update', tries=5):
    """Push everything in `pub`. Files modified after `since` (or the site files) are ours; for any other file,
    the version already on the branch wins, because another run may have refreshed it while we were scanning."""
    for item in os.listdir(site_dir):
        s, d = os.path.join(site_dir, item), os.path.join(pub, item)
        (shutil.copytree(s, d, dirs_exist_ok=True) if os.path.isdir(s) else shutil.copy2(s, d))
    open(os.path.join(pub, '.nojekyll'), 'w').close()
    site = set(_files(site_dir))
    for attempt in range(tries):
        lease = None
        if sh(['git', 'fetch', '-q', '--depth', '1', 'origin', BRANCH], pub, check=False).returncode == 0:
            lease = sh(['git', 'rev-parse', 'FETCH_HEAD'], pub).stdout.strip()
            mine = {f for f, m in _files(pub).items() if m >= since} | site
            for f in sh(['git', 'ls-tree', '-r', '--name-only', lease], pub).stdout.split():
                if f not in mine: sh(['git', 'checkout', lease, '--', f], pub)
        sh(['git', 'add', '-A'], pub); tree = sh(['git', 'write-tree'], pub).stdout.strip()
        commit = sh(['git', 'commit-tree', tree, '-m', message], pub).stdout.strip()
        push = ['git', 'push', '-q', 'origin', f'{commit}:refs/heads/{BRANCH}', '--force-with-lease=' + (f'{BRANCH}:{lease}' if lease else f'{BRANCH}:')]
        r = sh(push, pub, check=False)
        if r.returncode == 0:
            sh(['git', 'update-ref', f'refs/heads/{BRANCH}', commit], pub); return commit
        time.sleep(2 + attempt * 2)                              # someone else published in between: merge again and retry
    raise RuntimeError('publish failed after retries: ' + r.stderr.strip()[:300])

if __name__ == '__main__':          # python publish.py prepare pub | python publish.py push pub <since-epoch> <message>
    import sys
    if sys.argv[1] == 'prepare': prepare(sys.argv[2])
    elif sys.argv[1] == 'push': print('published', publish(sys.argv[2], float(sys.argv[3]), message=' '.join(sys.argv[4:]) or 'update'))
