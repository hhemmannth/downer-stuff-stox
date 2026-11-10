#!/usr/bin/env python3
"""Sent by the `ci` workflow when an upload fails its tests: tells your phone which commit, which checks, and how to undo it."""
import json, os, subprocess, sys

def build(result, sha, subject, run_url, repo_url):
    failing = [r for r in result.get('results', []) if not r.get('ok')]
    L = [f"Commit {sha[:7]}: {subject}", '', result.get('headline', 'Tests failed'), '']
    for r in failing[:5]: L.append(f"• {r['name']}" + (f": {r['fails'][0]}" if r.get('fails') else ''))
    L += ['', 'The scanner runs this code on its next scan, so something may break.',
          'To undo this upload: GitHub → Actions → rollback → Run workflow → type yes.' + (f'\nTest run: {run_url}' if run_url else '')]
    return 'Your last upload failed its tests', '\n'.join(L)

def main():
    try: result = json.load(open('ci_result.json'))
    except Exception: result = {'headline': 'The test run did not finish', 'results': []}
    sha = os.environ.get('GITHUB_SHA', '0000000')
    try: subject = subprocess.run(['git', 'log', '-1', '--format=%s'], capture_output=True, text=True).stdout.strip()[:100]
    except Exception: subject = ''
    e = os.environ; repo = f"{e.get('GITHUB_SERVER_URL', 'https://github.com')}/{e.get('GITHUB_REPOSITORY', '')}"
    run_url = f"{repo}/actions/runs/{e['GITHUB_RUN_ID']}" if e.get('GITHUB_RUN_ID') else ''
    title, body = build(result, sha, subject, run_url, repo); print(title + '\n' + body)
    import notify
    topic = e.get('NTFY_TOPIC', '').strip(); base = e.get('NTFY_URL', 'https://ntfy.sh').rstrip('/')
    if not topic and not notify.telegram_ready(): print('no alert channel configured'); return 0
    try: notify.post(base, topic, title, body, 'rotating_light', run_url); print('alert sent')
    except Exception as ex: print(f'alert failed: {ex}', file=sys.stderr)
    return 0

if __name__ == '__main__':
    sys.exit(main())
