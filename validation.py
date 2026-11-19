"""System health: independent validation of what the scanner just published (audit 18 Nov 2026).

After every scan, this re-checks the published files with its own arithmetic (it does not reuse the engine's numbers) and writes
data/health/validation.json for the System health page. Each check ends in exactly one status:
  pass         the check ran and everything it looked at was right
  fail         the check ran and found an error (each error is listed with an ID)
  warn         the check ran and found something to look at that is not an error
  not_tested   the check could not run this time (no setups to check, market closed, file missing), so it is NOT shown as green
  unavailable  the input the check needs does not exist in this setup (for example Angel One not configured)
Every error carries: id, at, instrument, module, description, expected, actual, severity (CRITICAL, HIGH, MEDIUM, LOW), suggestion, status.
Standard library + pandas only; it never changes a setup and never places anything anywhere."""
import hashlib, json, math, os, time
import datetime as dt
import pandas as pd

IST = 'Asia/Kolkata'
SECTIONS = (('swing', 'Swing', 100), ('options', 'Nifty options', 12), ('intraday', 'Intraday', 12))       # file, name, minutes before it is late in market hours
LEDGERS = ('swing', 'options', 'intraday', 'gold_intraday', 'gold_swing', 'gold_positional')
TOL_TICK = 0.11            # two NSE ticks (prices are rounded to 0.05 before they are published)

def _num(x):
    try: f = float(x)
    except (TypeError, ValueError): return None
    return None if math.isnan(f) or math.isinf(f) else f

def _read(path):
    try: return json.load(open(path))
    except Exception: return None

class Report:
    def __init__(self, now):
        self.now = now; self.checks = []; self.errors = []
    def error(self, check, module, instrument, description, expected, actual, severity, suggestion):
        eid = 'E-' + hashlib.sha1(f'{check}|{instrument}|{description}|{expected}'.encode()).hexdigest()[:8].upper()
        if any(e['id'] == eid for e in self.errors): return
        self.errors.append(dict(id=eid, at=self.now.isoformat(timespec='seconds'), instrument=instrument, module=module, check=check, description=description,
                                expected=str(expected), actual=str(actual), severity=severity, suggestion=suggestion, status='open'))
    def add(self, check, module, status, detail, severity=None, n=None):
        self.checks.append(dict(check=check, module=module, status=status, detail=detail, severity=severity, checked=n))

# ------------------------------------------------------------------ the checks
def plan_errors(it):
    """Independent geometry of one published plan. Returns [(description, expected, actual, severity)]."""
    out = []; e, sl = _num(it.get('entry')), _num(it.get('sl')); t = [_num(it.get(k)) for k in ('t1', 't2', 't3')]
    if e is None or sl is None: return out
    long = (it.get('direction') or 'long') == 'long'
    if (long and not sl < e) or (not long and not sl > e): out.append(('stop on the wrong side of the entry', 'stop below entry' if long else 'stop above entry', f'entry {e}, stop {sl}', 'CRITICAL'))
    if all(x is not None for x in t):
        if long and not (e < t[0] <= t[1] <= t[2]): out.append(('targets out of order', 'entry < T1 <= T2 <= T3', f'{e} / {t}', 'CRITICAL'))
        if not long and not (e > t[0] >= t[1] >= t[2]): out.append(('targets out of order', 'entry > T1 >= T2 >= T3', f'{e} / {t}', 'CRITICAL'))
    rp = _num(it.get('risk_pct'))
    if rp is not None and e:
        mine = abs(e - sl) / e * 100.0
        if abs(mine - rp) > max(0.05, 0.02 * mine) + 100 * TOL_TICK / e: out.append(('risk % does not match entry and stop', f'{mine:.2f}%', f'{rp:.2f}%', 'HIGH'))
    if it.get('section') == 'swing' and all(x is not None for x in t) and abs(e - sl) > 0:
        R = abs(e - sl)
        for k, (x, m) in enumerate(zip(t, (1, 2, 3))):
            if abs((x - e) - m * R) > TOL_TICK + 1e-9: out.append((f'T{k + 1} is not {m}R from the entry', f'{e + m * R:.2f}', f'{x:.2f}', 'MEDIUM'))
    return out

def candle_errors(times, candles):
    """[o, h, l, c] rows as published for the charts: every row a possible candle, every time unique and in order."""
    bad = []
    for i, row in enumerate(candles or []):
        try: o, h, l, c = (float(x) for x in row[:4])
        except Exception: bad.append(f'row {i}: not numbers'); continue
        if h < l or h < max(o, c) - 1e-6 or l > min(o, c) + 1e-6: bad.append(f'row {i} ({times[i] if times and i < len(times) else "?"}): O {o} H {h} L {l} C {c}')
    if times and len(set(times)) != len(times): bad.append('repeated candle times')
    return bad

def r_final_check(sig):
    """The tracker's booked result, recomputed: sum(fraction x R at each booked price) + rest x R at the exit."""
    e, sl, x = _num(sig.get('entry')), _num(sig.get('sl')), _num(sig.get('exit'))
    if e is None or sl is None or x is None or e == sl: return None
    s = 1 if sig.get('direction') == 'long' else -1; R = lambda p: s * (p - e) / abs(e - sl)
    booked = sig.get('booked') or []; rest = 1.0 - sum(float(f) for f, _ in booked)
    return round(sum(float(f) * R(float(p)) for f, p in booked) + rest * R(x), 2)

def market_hours(now):
    t = pd.Timestamp(now).tz_convert(IST); return t.weekday() < 5 and (9 * 60 + 15) <= t.hour * 60 + t.minute <= (15 * 60 + 30)

def run(out_dir, now=None, health=None):
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz=IST); now = now.tz_localize(IST) if now.tzinfo is None else now.tz_convert(IST)
    rep = Report(now)
    # 1. published plans and chart candles
    files = {k: _read(os.path.join(out_dir, k + '.json')) for k, _, _ in SECTIONS}; gold = _read(os.path.join(out_dir, 'gold.json'))
    setups = [(k, s) for k, d in files.items() if d for s in d.get('setups', [])]
    if gold: setups += [('gold_' + st, s) for st, d in (gold.get('styles') or {}).items() for s in (d or {}).get('setups', [])]
    n_plan = n_cndl = 0; plan_bad = cndl_bad = 0
    for sec, it in setups:
        if it.get('entry') is not None and it.get('sl') is not None:
            n_plan += 1
            for desc, exp, act, sev in plan_errors(dict(it, section=it.get('section', sec))):
                plan_bad += 1; rep.error('plan', 'entry / stop / target', f"{it.get('symbol')} {it.get('direction', '')} ({sec})", desc, exp, act, sev,
                                        'Do not use this plan: check the setup on the chart and report the run (the engine produced impossible levels).')
        if it.get('candles'):
            n_cndl += 1; bad = candle_errors(it.get('times'), it.get('candles'))
            if bad: cndl_bad += 1; rep.error('candles', 'market data', f"{it.get('symbol')} ({sec})", 'impossible candle in the published chart', 'high >= open, close >= low; unique times', '; '.join(bad[:3]), 'HIGH',
                                             'Compare the candle with your broker chart; the data source sent a bad candle.')
    rep.add('Entry, stop and target maths', 'plan', 'not_tested' if not n_plan else 'fail' if plan_bad else 'pass',
            f'{n_plan} published plans re-checked: stop side, target order, risk %, swing 1R/2R/3R' + (f'; {plan_bad} problem(s)' if plan_bad else ''), 'CRITICAL' if plan_bad else None, n_plan)
    rep.add('OHLC consistency (published charts)', 'market data', 'not_tested' if not n_cndl else 'fail' if cndl_bad else 'pass',
            f'{n_cndl} charts checked: high/low envelope and unique times' + (f'; {cndl_bad} with problems' if cndl_bad else ''), 'HIGH' if cndl_bad else None, n_cndl)
    # 2. freshness of each section (only meaningful in market hours)
    live = market_hours(now)
    for k, name, lim in SECTIONS:
        d = files.get(k)
        if not d or not d.get('generated_at'): rep.add(f'{name}: data freshness', 'freshness', 'not_tested', 'no results file yet'); continue
        age = (now - pd.Timestamp(d['generated_at'])).total_seconds() / 60
        if not live: rep.add(f'{name}: data freshness', 'freshness', 'not_tested', f'market closed: last update {age:.0f} min ago'); continue
        if age > lim:
            rep.add(f'{name}: data freshness', 'freshness', 'fail', f'last update {age:.0f} min ago (limit {lim})', 'HIGH')
            rep.error('freshness', name, '-', f'{name} results are stale', f'updated within {lim} min', f'{age:.0f} min', 'HIGH', 'Open System health > 5-minute market loop; restart the loop if it is silent.')
        else: rep.add(f'{name}: data freshness', 'freshness', 'pass', f'updated {age:.0f} min ago (limit {lim})')
    stale = [(k, s.get('symbol')) for k, s in setups if s.get('data_stale')]
    rep.add('Stale-data fail-safe', 'fail-safe', 'warn' if stale else ('pass' if setups else 'not_tested'),
            (f'{len(stale)} trigger(s) refused because their candles were old: ' + ', '.join(f'{a}/{b}' for a, b in stale[:6])) if stale else 'no trigger was read from stale candles', 'MEDIUM' if stale else None)
    # 3. trade ledgers: duplicate ids, impossible levels, booked results
    n_sig = 0; led_bad = 0; seen_any = False
    for sec in LEDGERS:
        led = _read(os.path.join(out_dir, f'signals_{sec}.json'))
        if not led: continue
        seen_any = True; ids = [s.get('id') for s in led.get('signals', [])]
        if len(ids) != len(set(ids)):
            led_bad += 1; rep.error('ledger', sec, '-', 'duplicate trade records', 'one record per trade', f'{len(ids) - len(set(ids))} duplicate id(s)', 'HIGH', 'Report it: the same trade would be counted twice in the stats.')
        for s in led.get('signals', []):
            n_sig += 1
            for desc, exp, act, sev in plan_errors(dict(s, section=sec if sec in ('swing',) else s.get('section'))):
                if 'is not' in desc: continue                                    # tracked trades keep the plan they opened with (live 15m entry): the R ladder is checked on the page plans
                led_bad += 1; rep.error('ledger', sec, s.get('symbol'), desc, exp, act, sev, 'Check this tracked trade against your broker order.')
            if s.get('status') == 'CLOSED':
                mine = r_final_check(s)
                if mine is not None and s.get('r_final') is not None and abs(mine - float(s['r_final'])) > 0.02:
                    led_bad += 1; rep.error('ledger', sec, s.get('symbol'), 'booked result does not add up', f'{mine:+.2f}R', f"{float(s['r_final']):+.2f}R", 'HIGH', 'Report it: the R shown for this trade is wrong.')
    # 3b. sealed signals and paper records (18 Nov 2026): the original signal must never have been rewritten
    import signals as _sg
    n_seal = 0; seal_bad = 0
    for sec in LEDGERS:
        led = _read(os.path.join(out_dir, f'signals_{sec}.json')) or {}
        for rec in list(led.get('signals') or []) + list(led.get('paper') or []):
            if not rec.get('signal_hash') or rec.get('signal') is None: continue
            n_seal += 1
            if _sg.seal(rec['signal']) != rec['signal_hash']:
                seal_bad += 1; rep.error('seal', sec, rec.get('symbol'), 'original signal was rewritten after it was recorded', rec['signal_hash'][:16], _sg.seal(rec['signal'])[:16], 'CRITICAL', 'Do not trust this paper record; report the run that changed it.')
    rep.add('Paper records: original signals sealed', 'paper trading', 'not_tested' if not n_seal else 'fail' if seal_bad else 'pass', f'{n_seal} sealed signals re-hashed' + (f'; {seal_bad} rewritten' if seal_bad else ''), 'CRITICAL' if seal_bad else None, n_seal)
    try:
        import strategy_config; ver, h, ok = strategy_config.current()
        rep.add('Strategy rules match the frozen version', 'strategy version', 'pass' if ok else 'warn', f'version {ver}, hash {h[:12]}' if ok else f'the rules running now (hash {h[:12]}) differ from frozen version {(strategy_config.latest() or {}).get("version")}: a repo variable or the code changed a rule, so paper results from now on belong to a new version', None if ok else 'MEDIUM')
    except Exception as ex: rep.add('Strategy rules match the frozen version', 'strategy version', 'not_tested', f'could not compute: {str(ex)[:80]}')
    if gold:
        import gold_feed as _gf
        inst = gold.get('instrument') or {}
        if not _gf.is_spot(gold.get('source')) or inst.get('instrument') != 'XAUUSD Spot':
            rep.add('Gold instrument is XAUUSD spot', 'gold data', 'fail', f"gold.json source is {gold.get('source') or 'missing'} (an old futures-based scan or an unverified feed)", 'CRITICAL')
            rep.error('gold', 'gold data', 'XAUUSD', 'gold results not from the verified XAUUSD spot feed', _gf.SOURCE_ID, gold.get('source') or 'missing', 'CRITICAL', 'Ignore these gold levels until the gold loop has run on the spot feed.')
        elif (gold.get('feed') or {}).get('ok') is False: rep.add('Gold instrument is XAUUSD spot', 'gold data', 'warn', 'spot feed unavailable on the last run: no gold recommendations (by design)', 'MEDIUM')
        else: rep.add('Gold instrument is XAUUSD spot', 'gold data', 'pass', f"{inst.get('instrument')} · {inst.get('quote_currency')} · {inst.get('unit')} · {_gf.PROVIDER} {_gf.SYMBOL}")
    else: rep.add('Gold instrument is XAUUSD spot', 'gold data', 'not_tested', 'no gold scan file in this folder')
    try:
        import market_calendar; st_c, msg_c = market_calendar.check(now.date())
        rep.add('NSE holiday calendar', 'calendar', {'ok': 'pass', 'warn': 'warn', 'fail': 'fail'}[st_c], msg_c, None if st_c == 'ok' else 'MEDIUM' if st_c == 'warn' else 'HIGH')
    except Exception as ex: rep.add('NSE holiday calendar', 'calendar', 'not_tested', str(ex)[:80])
    rep.add('Trade tracker records', 'tracker', 'not_tested' if not seen_any else 'fail' if led_bad else 'pass',
            f'{n_sig} tracked trades re-checked: unique ids, levels, booked R' + (f'; {led_bad} problem(s)' if led_bad else ''), 'HIGH' if led_bad else None, n_sig)
    # 4. data sources and candle repairs (from this run's health record)
    data = (health or {}).get('data') or {}
    if not data: rep.add('Market data sources', 'market data', 'not_tested', 'no data-source report in this run')
    else:
        a = data.get('angel') or {}
        if not a.get('configured'): rep.add('Angel One connection', 'market data', 'unavailable', 'not set up: everything came from Yahoo Finance (unofficial, can be delayed)')
        elif a.get('ok'): rep.add('Angel One connection', 'market data', 'pass', 'connected')
        else:
            rep.add('Angel One connection', 'market data', 'warn', f"configured but not working ({a.get('error') or 'unknown'}): Yahoo was used", 'MEDIUM')
        q = data.get('quality') or {}; fixed = {iv: m for iv, m in q.items() if m}
        tot = sum(sum(v for k, v in row.items() if isinstance(v, int)) for m in fixed.values() for row in m.values())
        rep.add('Candle hygiene (duplicates, order, impossible candles)', 'market data', 'warn' if tot else 'pass',
                ('repaired or removed before the rules ran: ' + '; '.join(f"{iv}: " + ', '.join(f"{s} {sum(v for v in r.values() if isinstance(v, int))}" for s, r in list(m.items())[:5]) for iv, m in fixed.items())) if tot else 'no duplicate, out-of-order or impossible candles in this run', 'LOW' if tot else None)
        bigx = [x for x in (data.get('xcheck') or []) if (x.get('max_diff_pct') or 0) > 1.5]
        if data.get('xcheck'): rep.add('Angel One vs Yahoo closes', 'market data', 'warn' if bigx else 'pass', f"{len(data['xcheck'])} compared" + (f"; {len(bigx)} differ by more than 1.5%" if bigx else ''), 'MEDIUM' if bigx else None)
    for m, x in ((health or {}).get('sections') or {}).items():
        if not x.get('ok'):
            rep.add(f'Scan section: {m}', 'scanner', 'fail', x.get('error') or 'failed', 'HIGH')
            rep.error('section', m, '-', f'the {m} scan failed', 'section finishes', (x.get('error') or 'failed')[:160], 'HIGH', 'Open the run log from System health > Last scans.')
    ci_path = os.environ.get('CI_RESULT', '') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ci_result.json'); ci = _read(ci_path)
    try: ci_age_h = (time.time() - os.path.getmtime(ci_path)) / 3600.0
    except OSError: ci_age_h = None
    if ci and 'ok' in ci and ci_age_h is not None and ci_age_h > 24: rep.add('Automated test suite (last local/CI run)', 'tests', 'not_tested', f'the last test result on this machine is {ci_age_h:.0f} h old: not counted')
    elif ci and 'ok' in ci: rep.add('Automated test suite (last local/CI run)', 'tests', 'pass' if ci['ok'] else 'fail', ci.get('headline', ''), None if ci['ok'] else 'HIGH')
    else: rep.add('Automated test suite (last local/CI run)', 'tests', 'not_tested', 'no test result available to this job: see the ci workflow on GitHub')
    summ = {k: sum(1 for c in rep.checks if c['status'] == k) for k in ('pass', 'fail', 'warn', 'not_tested', 'unavailable')}
    level = 'fail' if summ['fail'] else 'warn' if summ['warn'] else 'pass' if summ['pass'] else 'not_tested'
    return dict(generated_at=now.isoformat(timespec='seconds'), level=level, summary=summ, checks=rep.checks, errors=sorted(rep.errors, key=lambda e: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].index(e['severity'])))

def write(out_dir, now=None, health=None):
    doc = run(out_dir, now, health); d = os.path.join(out_dir, 'health'); os.makedirs(d, exist_ok=True); p = os.path.join(d, 'validation.json'); tmp = p + '.tmp'
    with open(tmp, 'w') as f: json.dump(doc, f, separators=(',', ':'), default=str)
    os.replace(tmp, p); return doc

if __name__ == '__main__':
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else '_site/data'
    doc = write(out); print(json.dumps(doc['summary']), doc['level'])
    for e in doc['errors'][:20]: print(f"  {e['severity']:<8} {e['id']} {e['instrument']}: {e['description']} (expected {e['expected']}, got {e['actual']})")
