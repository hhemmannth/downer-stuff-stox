#!/usr/bin/env python3
"""Run every test file, then check the JavaScript syntax, the workflow files and the JSON files. Exit code 1 if anything fails.
Used by the `ci` workflow on every upload, and by you: python run_tests.py   (add --fast to skip the slow data-source tests)"""
import glob, json, os, shutil, subprocess, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))

def run_file(path, timeout=900):
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, path], cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        out = (p.stdout + p.stderr).strip().splitlines(); fails = [l[5:].strip()[:110] for l in out if l.startswith('FAIL ')]
        ok = p.returncode == 0
        return dict(name=os.path.basename(path), ok=ok, seconds=round(time.time() - t0, 1), fails=fails, tail=next((l for l in reversed(out) if 'PASSED' in l or 'FAILED' in l), out[-1] if out else '')[:160])
    except subprocess.TimeoutExpired:
        return dict(name=os.path.basename(path), ok=False, seconds=timeout, fails=['timed out'], tail='timed out')

def check_js():
    node = shutil.which('node')
    if not node: return [dict(name='JavaScript syntax', ok=True, seconds=0, fails=[], tail='node not installed here, skipped')]
    bad = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'site', '**', '*.js'), recursive=True)):
        p = subprocess.run([node, '--check', f], capture_output=True, text=True)
        if p.returncode != 0: bad.append(f"{os.path.relpath(f, ROOT)}: {(p.stderr.strip().splitlines() or ['syntax error'])[-1][:90]}")
    return [dict(name='JavaScript syntax', ok=not bad, seconds=0, fails=bad, tail='ok' if not bad else f'{len(bad)} file(s) with errors')]

def check_files():
    bad = []
    try: import yaml
    except ImportError: yaml = None
    if yaml:
        for f in sorted(glob.glob(os.path.join(ROOT, '.github', 'workflows', '*.yml'))):
            try: yaml.safe_load(open(f))
            except Exception as ex: bad.append(f'{os.path.basename(f)}: {str(ex).splitlines()[0][:80]}')
    for f in ('events.json',):
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            try: json.load(open(p))
            except Exception as ex: bad.append(f'{f}: {str(ex)[:80]}')
    return [dict(name='Workflow and JSON files', ok=not bad, seconds=0, fails=bad, tail='ok' if not bad else f'{len(bad)} problem(s)')]

def summarize(results):
    ok = all(r['ok'] for r in results); n_bad = sum(1 for r in results if not r['ok'])
    lines = [f"{'PASS' if r['ok'] else 'FAIL'}  {r['name']:<28} {r['seconds']:>6}s  {r['tail']}" for r in results]
    for r in results:
        for f in r['fails'][:6]:
            if not r['ok']: lines.append(f"      - {r['name']}: {f}")
    return ok, f"{'ALL GOOD' if ok else str(n_bad) + ' PROBLEM(S)'}: {len(results) - n_bad}/{len(results)} checks passed", lines

def main(argv=None):
    fast = '--fast' in (argv or sys.argv[1:]); files = sorted(glob.glob(os.path.join(ROOT, 'test_*.py')))
    if fast: files = [f for f in files if 'datasource' not in f]
    results = []
    for f in files:
        r = run_file(f); results.append(r); print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['name']}  ({r['seconds']}s)", flush=True)
    results += check_js() + check_files()
    ok, headline, lines = summarize(results)
    print('\n' + headline + '\n' + '\n'.join(lines))
    json.dump(dict(ok=ok, headline=headline, results=results), open(os.path.join(ROOT, 'ci_result.json'), 'w'))
    summ = os.environ.get('GITHUB_STEP_SUMMARY')
    if summ:
        with open(summ, 'a') as f: f.write(f'### {headline}\n\n```\n' + '\n'.join(lines) + '\n```\n')
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
