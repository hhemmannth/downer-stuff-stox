"""Deeper error checks (items 401-430, 463-478, 324, 497), added to System health after every scan (25 Nov 2026).

validation.py already checks plan geometry, chart candles, freshness, the sealed paper records, the frozen strategy version, the gold
instrument, the holiday calendar, data sources and the test suite. This file adds the checks it did not have. Each one only READS the
published files (and, for the secret checks, the names of environment variables). Nothing here changes a setup, a rule, a hold-back,
a level or a credential, and nothing here can place anything anywhere.

  extra(rep, out_dir, now, env=None, repo_dir=None)   adds its checks to validation's Report
  history(out_dir, doc, keep=90)                       appends one line per run to data/health/checks_history.json (the errors history page)

Secret values are never printed, logged or written: the secret checks report only a variable's NAME and whether it is set."""
import datetime as dt, glob, json, math, os, re

SECRET_NAMES = ('ANGEL_API_KEY', 'ANGEL_CLIENT_CODE', 'ANGEL_MPIN', 'ANGEL_TOTP_SECRET', 'NTFY_TOPIC', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID')
SECRET_LIKE = re.compile(r'(KEY|TOKEN|SECRET|PASSWORD|MPIN|TOTP|PASS)$', re.I)
SECTIONS = ('swing', 'options', 'intraday')
WORKFLOWS = {'scan': 'schedule', 'market-loop': 'schedule', 'gold-loop': 'schedule', 'ci': 'push', 'backup': 'schedule', 'readiness': 'schedule', 'digest': 'schedule', 'watchdog': 'schedule'}

def _num(x):
    try: v = float(x); return v if math.isfinite(v) else None
    except (TypeError, ValueError): return None

def _read(p):
    try:
        with open(p) as f: return json.load(f)
    except Exception: return None

def _ts(s):
    try: return dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except Exception: return None

def _safe(rep, name, module, fn):
    """A check that crashes is reported as not tested, never as passed, and never stops the scan."""
    try: fn()
    except Exception as ex: rep.add(name, module, 'not_tested', f'check could not run: {type(ex).__name__}: {str(ex)[:80]}')

# ------------------------------------------------------------------ published setups
def setup_problems(sec, items, today=None):
    """[(instrument, description, expected, actual, severity)] for one section's published setups."""
    out, seen = [], {}
    for it in items or []:
        sym, side = it.get('symbol'), it.get('direction', '')
        key = (sym, side, it.get('instrument'))
        if key in seen: out.append((f'{sym} {side}', 'the same setup is listed twice', 'one row per symbol and side', 'two rows', 'MEDIUM'))
        seen[key] = 1
        st = it.get('stage')
        if st is not None and (not isinstance(st, (int, float)) or not 1 <= st <= 5): out.append((f'{sym} {side}', 'stage outside 1 to 5', '1-5', st, 'HIGH'))
        sc, mx = _num(it.get('score')), _num(it.get('max_score'))
        if sc is not None and mx is not None and not 0 <= sc <= mx: out.append((f'{sym} {side}', 'score outside 0 and the maximum', f'0-{mx:g}', sc, 'HIGH'))
        status = str(it.get('status') or '').upper()
        if (it.get('holds') or []) and status.startswith('TRIGGER') and '(NOT TAKEN' not in status:
            out.append((f'{sym} {side}', 'a held-back setup is shown as triggered', 'held back or NOT TAKEN', it.get('status'), 'HIGH'))
        px, e = _num(it.get('price')), _num(it.get('entry'))
        if px is not None and px <= 0: out.append((f'{sym} {side}', 'price is zero or negative', '> 0', px, 'HIGH'))
        if sec == 'swing' and px and e and abs(px - e) / e > 0.25: out.append((f'{sym} {side}', 'price is more than 25% away from the entry', 'within 25%', f'price {px}, entry {e}', 'MEDIUM'))
        r = it.get('results') or {}
        if today and r.get('date') and r.get('days') is not None:
            try:
                d = (dt.date.fromisoformat(str(r['date'])[:10]) - today).days
                if abs(d - int(r['days'])) > 4: out.append((f'{sym}', 'results countdown does not match the results date', f'{d} days', f"{r['days']} days", 'LOW'))
            except Exception: pass
    return out

def chart_gaps(times, max_days=6):
    """Daily chart: a gap of more than `max_days` calendar days between two candles means missing sessions."""
    bad = []; prev = None
    for t in times or []:
        try: d = dt.date.fromisoformat(str(t)[:10])
        except Exception: continue
        if prev and (d - prev).days > max_days: bad.append(f'{prev} to {d}')
        if prev and d < prev: bad.append(f'{d} before {prev}')
        prev = d
    return bad

def ledger_problems(led):
    """Tracked trades: a stop must never be loosened, events must be in time order, a closed trade needs an exit."""
    out = []
    for s in (led or {}).get('signals') or []:
        sid = s.get('id') or s.get('symbol'); long = s.get('direction', 'long') == 'long'
        sl0, stop = _num(s.get('sl')), _num(s.get('stop'))
        if sl0 is not None and stop is not None and ((long and stop < sl0 - 1e-6) or (not long and stop > sl0 + 1e-6)):
            out.append((sid, 'the stop was moved against the trade', f"no looser than {sl0}", stop, 'CRITICAL'))
        ts = [_ts(e.get('t')) for e in s.get('events') or []]; ts = [t for t in ts if t]
        if any(b < a for a, b in zip(ts, ts[1:])): out.append((sid, 'trade events out of time order', 'oldest first', 'out of order', 'MEDIUM'))
        c = _ts(s.get('created'))
        for k, v in (s.get('hits') or {}).items():
            h = _ts(v)
            if c and h and h < c: out.append((sid, f'{k} hit before the trade was created', f'after {s.get("created")}', v, 'HIGH'))
        if s.get('outcome') and _num(s.get('exit')) is None and str(s.get('status', '')).upper() not in ('EXPIRED', 'CANCELLED'):
            out.append((sid, 'closed trade without an exit price', 'exit price', 'missing', 'HIGH'))
    return out

def leak_hits(out_dir, env):
    """Names of secret variables whose VALUE appears in any published file. The value itself is never returned."""
    vals = {k: v for k, v in env.items() if (k in SECRET_NAMES or SECRET_LIKE.search(k)) and k not in ('GITHUB_TOKEN',) and isinstance(v, str) and len(v.strip()) >= 8}
    if not vals: return None, 0
    hits, n = set(), 0
    for p in glob.glob(os.path.join(out_dir, '**', '*'), recursive=True):
        if not os.path.isfile(p) or os.path.getsize(p) > 25_000_000: continue
        n += 1
        try: txt = open(p, 'rb').read().decode('utf-8', 'ignore')
        except Exception: continue
        for k, v in vals.items():
            if v.strip() in txt: hits.add(k)
    return sorted(hits), n

def workflow_problems(repo_dir):
    """Workflows the desk depends on, each with its trigger (item 324). Reads the YAML as text: no extra library needed."""
    wd = os.path.join(repo_dir, '.github', 'workflows')
    if not os.path.isdir(wd): return None
    out = []
    for name, need in WORKFLOWS.items():
        p = os.path.join(wd, name + '.yml')
        if not os.path.exists(p): out.append(f'{name}.yml is missing'); continue
        txt = open(p).read()
        if need == 'schedule' and not re.search(r'^\s*schedule:\s*$', txt, re.M): out.append(f'{name} has no schedule')
        if need == 'schedule' and re.search(r'^\s*schedule:\s*$', txt, re.M) and not re.search(r"cron:\s*['\"][^'\"]+['\"]", txt): out.append(f'{name} schedule has no cron line')
        if need == 'push' and not re.search(r'^\s*(push|pull_request):', txt, re.M): out.append(f'{name} does not run on push')
    return out

# ------------------------------------------------------------------ the extra checks
def extra(rep, out_dir, now, env=None, repo_dir=None):
    env = os.environ if env is None else env; repo_dir = repo_dir or os.path.dirname(os.path.abspath(__file__))
    files = {k: _read(os.path.join(out_dir, k + '.json')) for k in SECTIONS}; today = now.date() if hasattr(now, 'date') else None

    def c_json():                                                          # every published JSON file opens (item 327, 459)
        bad, n = [], 0
        for p in glob.glob(os.path.join(out_dir, '**', '*.json'), recursive=True):
            n += 1
            try: json.load(open(p))
            except Exception: bad.append(os.path.relpath(p, out_dir))
        if bad:
            rep.add('Published files open', 'publish', 'fail', f'{len(bad)} of {n} files are broken: ' + ', '.join(bad[:5]), 'HIGH', n)
            for b in bad[:10]: rep.error('json', 'publish', b, 'published file is not valid JSON', 'valid JSON', 'broken', 'HIGH', 'The publish step keeps the last good copy on the site; the next scan rewrites it.')
        else: rep.add('Published files open', 'publish', 'pass' if n else 'not_tested', f'{n} JSON files parsed', None, n)
    _safe(rep, 'Published files open', 'publish', c_json)

    def c_setups():                                                        # duplicates, stage, score, hold-backs, price, results (406-418)
        n = bad = 0
        for sec, d in files.items():
            if not d: continue
            items = d.get('setups') or []; n += len(items)
            for inst, desc, exp, act, sev in setup_problems(sec, items, today):
                bad += 1; rep.error('setup', sec, inst, desc, exp, act, sev, 'Check this setup on the chart before acting; report the run if it repeats.')
        rep.add('Setup rows (duplicates, stage, score, hold-backs, price)', 'scanner', 'not_tested' if not n else 'fail' if bad else 'pass', f'{n} published setups checked' + (f'; {bad} problem(s)' if bad else ''), 'HIGH' if bad else None, n)
    _safe(rep, 'Setup rows (duplicates, stage, score, hold-backs, price)', 'scanner', c_setups)

    def c_counts():                                                        # zero or too many setups, failed downloads (419-421)
        notes, warn = [], False
        for sec, d in files.items():
            if not d: continue
            sc, fl, n = d.get('scanned') or 0, d.get('failed') or 0, len(d.get('setups') or [])
            notes.append(f'{sec} {n}')
            if isinstance(fl, list): fl = len(fl)
            if sec == 'swing' and n > 150: warn = True; notes[-1] += ' (unusually many)'
            if sc and fl and fl / max(1, sc + fl) > 0.2: warn = True; notes[-1] += f' ({fl} downloads failed)'
            if not sc and (d.get('universe') or 0) and d.get('market_open') is not False and sec == 'swing': warn = True; notes[-1] += ' (no stock read)'
        rep.add('Setup counts and failed downloads', 'scanner', 'not_tested' if not notes else 'warn' if warn else 'pass', '; '.join(notes) or 'no scan files', 'MEDIUM' if warn else None)
    _safe(rep, 'Setup counts and failed downloads', 'scanner', c_counts)

    def c_tz():                                                            # every timestamp carries its timezone (424)
        bad = [k for k, d in files.items() if d and d.get('generated_at') and (_ts(d['generated_at']) is None or _ts(d['generated_at']).tzinfo is None)]
        rep.add('Timestamps carry a timezone', 'freshness', 'fail' if bad else 'pass', ('no timezone on: ' + ', '.join(bad)) if bad else 'IST offset present', 'MEDIUM' if bad else None)
    _safe(rep, 'Timestamps carry a timezone', 'freshness', c_tz)

    def c_gaps():                                                          # missing sessions in the published daily charts (401-403)
        ch = (_read(os.path.join(out_dir, 'swing_charts.json')) or {}).get('charts') or {}; n = 0; bad = []
        for sym, tfs in ch.items():
            t = ((tfs or {}).get('1D') or {}).get('times')
            if not t: continue
            n += 1; g = chart_gaps(t)
            if g: bad.append(f'{sym}: {g[0]}')
        rep.add('Daily charts: missing sessions', 'market data', 'not_tested' if not n else 'warn' if bad else 'pass', f'{n} charts checked' + (f"; gaps in {len(bad)}: {', '.join(bad[:4])}" if bad else ''), 'MEDIUM' if bad else None, n)
    _safe(rep, 'Daily charts: missing sessions', 'market data', c_gaps)

    def c_options():                                                       # Nifty spot and VIX present and sensible (409)
        o = files.get('options')
        if not o: rep.add('Nifty spot and VIX', 'options', 'not_tested', 'no options file'); return
        s = o.get('snapshot') or {}; spot, vix = _num(s.get('spot')), _num(s.get('vix')); bad = []
        if spot is None or not 5000 < spot < 100000: bad.append(f'spot {s.get("spot")}')
        if vix is None or not 5 <= vix <= 90: bad.append(f'VIX {s.get("vix")}')
        rep.add('Nifty spot and VIX', 'options', 'warn' if bad else 'pass', ('missing or out of range: ' + ', '.join(bad)) if bad else f'spot {spot:g}, VIX {vix:g}', 'MEDIUM' if bad else None)
    _safe(rep, 'Nifty spot and VIX', 'options', c_options)

    def c_sector():                                                        # sector map present and recent (425)
        m = _read(os.path.join(out_dir, 'sectors.json')) or {}; sw = (files.get('swing') or {}).get('setups') or []
        miss = [s.get('symbol') for s in sw if not s.get('sector')]; age = None; g = _ts(m.get('generated_at'))
        if g: age = (now - g).days if g.tzinfo else None
        warn = bool(miss) or (age is not None and age > 45) or not m.get('map')
        rep.add('Sector map', 'scanner', 'warn' if warn else 'pass', (f'{len(miss)} setups without a sector ({", ".join(miss[:4])})' if miss else 'every setup has a sector') + (f'; map is {age} days old' if age is not None else ''), 'LOW' if warn else None)
    _safe(rep, 'Sector map', 'scanner', c_sector)

    def c_ledger():                                                        # stops never loosened, events in order, exits present (414-417)
        n = bad = 0
        for sec in SECTIONS + ('gold_intraday', 'gold_swing', 'gold_positional'):
            led = _read(os.path.join(out_dir, f'signals_{sec}.json'))
            if not led: continue
            n += len(led.get('signals') or [])
            for sid, desc, exp, act, sev in ledger_problems(led):
                bad += 1; rep.error('ledger', sec, sid, desc, exp, act, sev, 'Check this tracked trade on the System health page; report the run.')
        rep.add('Tracked trades: stops, order of events, exits', 'tracker', 'not_tested' if not n else 'fail' if bad else 'pass', f'{n} tracked trades' + (f'; {bad} problem(s)' if bad else ''), 'HIGH' if bad else None, n)
    _safe(rep, 'Tracked trades: stops, order of events, exits', 'tracker', c_ledger)

    def c_backtest():                                                      # backtests recent and with a window (428-430)
        old, n = [], 0
        for p in glob.glob(os.path.join(out_dir, 'backtest*.json')):
            if p.endswith('_trades.json') or 'archive' in p: continue
            d = _read(p) or {}; g = _ts(d.get('generated_at')); n += 1
            if not d.get('window'): old.append(os.path.basename(p) + ' (no window)')
            elif g and g.tzinfo and (now - g).days > 10: old.append(f'{os.path.basename(p)} ({(now - g).days} days old)')
        rep.add('Backtests recent', 'backtest', 'not_tested' if not n else 'warn' if old else 'pass', f'{n} backtests' + (f"; {', '.join(old[:4])}" if old else ' within 10 days'), 'LOW' if old else None, n)
    _safe(rep, 'Backtests recent', 'backtest', c_backtest)

    def c_secrets():                                                       # which secrets are set, by NAME only (463-466)
        have = [k for k in SECRET_NAMES if str(env.get(k) or '').strip()]; miss = [k for k in SECRET_NAMES if k not in have]
        alerts = 'NTFY_TOPIC' in have or ('TELEGRAM_BOT_TOKEN' in have and 'TELEGRAM_CHAT_ID' in have)
        angel = [k for k in SECRET_NAMES if k.startswith('ANGEL')]; ang_part = 0 < sum(k in have for k in angel) < len(angel)
        if str(env.get('GITHUB_ACTIONS', '')).lower() != 'true' and not have: rep.add('Secrets present (names only)', 'setup', 'unavailable', 'not running on GitHub Actions: secrets are only checked there'); return
        st = 'fail' if not alerts else 'warn' if ang_part else 'pass'
        rep.add('Secrets present (names only)', 'setup', st, f"set: {', '.join(have) or 'none'}" + (f"; not set: {', '.join(miss)}" if miss else '') + ('; no alert channel' if not alerts else '') + ('; Angel One only partly set' if ang_part else ''), 'HIGH' if st == 'fail' else 'MEDIUM' if st == 'warn' else None)
    _safe(rep, 'Secrets present (names only)', 'setup', c_secrets)

    def c_leak():                                                          # no secret value inside any published file (467-470)
        hits, n = leak_hits(out_dir, env)
        if hits is None: rep.add('No secret in the published files', 'setup', 'not_tested', 'no secret values in this job to compare with'); return
        if hits:
            rep.add('No secret in the published files', 'setup', 'fail', f"the value of {', '.join(hits)} appears in a published file", 'CRITICAL', n)
            rep.error('leak', 'setup', ', '.join(hits), 'a secret value appears in the published site', 'never published', 'found (value not shown)', 'CRITICAL', 'Rotate that secret now (Angel One / Telegram / ntfy), then report the run so the file can be fixed.')
        else: rep.add('No secret in the published files', 'setup', 'pass', f'{n} published files searched', None, n)
    _safe(rep, 'No secret in the published files', 'setup', c_leak)

    def c_workflows():                                                     # workflows and their schedules (324, 471-474)
        w = workflow_problems(repo_dir)
        if w is None: rep.add('Workflows and schedules', 'setup', 'not_tested', 'workflow files not in this job'); return
        rep.add('Workflows and schedules', 'setup', 'warn' if w else 'pass', '; '.join(w) if w else f'{len(WORKFLOWS)} workflows found with their triggers', 'MEDIUM' if w else None)
    _safe(rep, 'Workflows and schedules', 'setup', c_workflows)

    def c_alerts():                                                        # alert log: sends that failed today (479-486)
        lg = _read(os.path.join(out_dir, 'health', 'alerts_log.json')) or {}
        items = [x for x in lg.get('items') or [] if str(x.get('at', ''))[:10] == str(today)]
        if not lg: rep.add('Phone alerts delivered', 'alerts', 'not_tested', 'no alert log yet'); return
        fails = [x for x in items if not x.get('ok')]; held = lg.get('held_today') or 0
        rep.add('Phone alerts delivered', 'alerts', 'warn' if fails or held else 'pass', f'{len(items)} sent today' + (f'; {len(fails)} failed' if fails else '') + (f'; {held} folded into a summary (rate limit)' if held else ''), 'MEDIUM' if fails else None, len(items))
    _safe(rep, 'Phone alerts delivered', 'alerts', c_alerts)

def history(out_dir, doc, keep=90):
    """One line per run for the errors history page (item 497). Only the summary and the names of failing checks are kept."""
    p = os.path.join(out_dir, 'health', 'checks_history.json'); h = _read(p) or {}; items = h.get('items') or []
    items.append(dict(at=doc.get('generated_at'), level=doc.get('level'), summary=doc.get('summary'),
                      failing=[c['check'] for c in doc.get('checks', []) if c['status'] == 'fail'][:12],
                      warning=[c['check'] for c in doc.get('checks', []) if c['status'] == 'warn'][:12], errors=len(doc.get('errors') or [])))
    os.makedirs(os.path.dirname(p), exist_ok=True); tmp = p + '.tmp'
    with open(tmp, 'w') as f: json.dump(dict(items=items[-keep:]), f, separators=(',', ':'), default=str)
    os.replace(tmp, p); return p
