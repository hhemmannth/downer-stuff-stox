"""Failure and degradation alerts for the scanner (item 28), with a cool-down so a broken thing never floods your phone.

Every alert has a key. The first time a problem appears it is sent; the same key is not sent again until the cool-down has passed.
When the problem clears, one "recovered" message is sent and the key is forgotten. State lives in pub/state/alerts.json, which is
published with the data, so it survives from one run to the next. Nothing is sent unless ALERTS_STATE (the file path) is set and
at least one channel (ntfy or Telegram) is configured."""
import datetime as dt, json, os, sys
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

def _now(): return dt.datetime.now(IST)

def _load(path):
    try: return json.load(open(path))
    except Exception: return {}

def _save(path, st):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True); tmp = path + '.tmp'
    with open(tmp, 'w') as f: json.dump(st, f, separators=(',', ':'))
    os.replace(tmp, path)

def _push(title, body, tags, click=None):
    import notify
    topic = os.environ.get('NTFY_TOPIC', '').strip(); base = os.environ.get('NTFY_URL', 'https://ntfy.sh').rstrip('/')
    if not topic and not notify.telegram_ready(): return False
    page = click if click is not None else os.environ.get('PAGE_URL', '').strip()
    if page and click is None: page = page.rstrip('/') + '/#/health'
    try: notify.post(base, topic, title, body, tags, page); return True
    except Exception as ex: print(f'  alert not sent: {ex}', file=sys.stderr); return False

def send(key, title, body, state_path, cooldown_min=60, tags='warning', now=None, click=None):
    """Send unless the same key was sent within the cool-down. Returns True if a message went out."""
    if not state_path: return False
    now = now or _now(); st = _load(state_path); last = st.get(key)
    if last:
        try:
            if (now - dt.datetime.fromisoformat(last)).total_seconds() < cooldown_min * 60: return False
        except Exception: pass
    if not _push(title, body, tags, click): return False
    st[key] = now.isoformat(timespec='seconds'); _save(state_path, st); return True

def resolve(key, title, body, state_path, click=None):
    """The problem went away: tell you once, then forget the key so it can alert again later."""
    if not state_path: return False
    st = _load(state_path)
    if key not in st: return False
    _push(title, body, 'white_check_mark', click); st.pop(key, None); _save(state_path, st); return True

def watch(key, bad, title, body, state_path, cooldown_min=60, ok_title=None, ok_body='', tags='warning', now=None):
    """Alert while `bad` is true; send one recovery note when it turns false."""
    if bad: return send(key, title, body, state_path, cooldown_min, tags, now)
    return resolve(key, ok_title or f'Recovered: {title}', ok_body or 'It is working again.', state_path)

def findings(health, options_snapshot=None):
    """Pure rules. health = the dict a scan writes to data/health/<mode>.json. Returns (problems, healthy) where each entry is
    (key, title, body, cooldown_min) for problems and (key, title, body) for things that are fine (so earlier alerts can resolve)."""
    bad, good, mode = [], [], health.get('mode', 'scan')
    for name, sec in (health.get('sections') or {}).items():
        if not sec.get('ok'): bad.append((f'scan-fail:{name}', f'Scan failed: {name}', f"The {name} section failed in the {mode} run: {sec.get('error') or 'unknown error'}. Other sections kept running.", 120))
        else: good.append((f'scan-fail:{name}', f'Recovered: {name} scan', f'The {name} section is working again.'))
        un, sc = sec.get('universe'), sec.get('scanned')
        if un and sc is not None:
            if un - sc > max(25, 0.08 * un): bad.append((f'data-gap:{name}', f'Data gap: {name}', f'Only {sc} of {un} symbols returned data in the {mode} run. Yahoo may be blocking the runner; the setups shown are from fewer stocks than usual.', 180))
            else: good.append((f'data-gap:{name}', f'Recovered: {name} data', 'Symbol coverage is back to normal.'))
    data = health.get('data') or {}; ang = data.get('angel') or {}
    if ang.get('configured') and ang.get('ok') is False:
        bad.append(('angel-down', 'Angel One is not working', f"{ang.get('error') or 'unknown error'}. Yahoo is being used instead, so no data is missing, but option prices are model estimates.", 180))
    elif ang.get('ok'): good.append(('angel-down', 'Angel One is back', 'Official exchange data and live option prices are available again.'))
    gaps = [x for x in (data.get('xcheck') or []) if (x.get('max_diff_pct') or 0) > 1.5]
    if gaps: bad.append(('data-mismatch', 'Yahoo and Angel One disagree', 'Recent closes differ by more than 1.5%: ' + ', '.join(f"{x['symbol']} {x['max_diff_pct']}%" for x in gaps[:4]) + '. Check the chart before trusting these setups.', 720))
    elif data.get('xcheck'): good.append(('data-mismatch', 'Data sources agree again', 'Yahoo and Angel One closes match.'))
    snap = options_snapshot or {}
    if (snap.get('losses_today') or 0) >= 2:
        sd = snap.get('session_date') or ''
        bad.append((f'options-paused:{sd}', 'Options paused for today', 'Two tracked option signals were stopped out today. Your rule is to stop for the day, so no new option setups will be shown until tomorrow.', 24 * 60))
    return bad, good

def process(health, options_snapshot, state_path, now=None):
    """Run the rules for one scan and send/resolve alerts. Never raises."""
    if not state_path: return 0
    sent = 0
    try:
        bad, good = findings(health, options_snapshot)
        for key, title, body, cd in bad: sent += bool(send(key, title, body, state_path, cd, now=now))
        bad_keys = {b[0] for b in bad}
        for key, title, body in good:
            if key not in bad_keys: resolve(key, title, body, state_path)
    except Exception as ex: print(f'  alert rules failed: {ex}', file=sys.stderr)
    return sent
