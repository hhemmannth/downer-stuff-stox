"""NSE trading calendar: the single source of holiday dates for every module (added 18 Nov 2026; before, the dates sat in events.json
and the calendar silently ended on 25 Dec 2026).

Only years with status 'official' (copied from an NSE circular) are applied. A year 'awaiting_official' applies nothing: its provisional
dates are shown, never used, so a guessed date can never close the scanner on a trading day or move an expiry. readiness.py warns from
1 December when next year is not official yet, and every day once that year has started."""
import datetime as dt, json, os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'market_calendar.json')
_CACHE = {}

def load(path=None):
    p = path or PATH
    if p not in _CACHE:
        try: _CACHE[p] = json.load(open(p, encoding='utf-8'))
        except Exception: _CACHE[p] = dict(years={})
    return _CACHE[p]

def reset(): _CACHE.clear()

def _d(x): return x if isinstance(x, dt.date) and not isinstance(x, dt.datetime) else (x.date() if isinstance(x, dt.datetime) else dt.date.fromisoformat(str(x)[:10]))

def holidays(path=None, with_names=False):
    """Weekday trading holidays from OFFICIAL years only, sorted. with_names: [{date, name, year}] instead of date strings."""
    out = []
    for y, Y in sorted((load(path).get('years') or {}).items()):
        if Y.get('status') != 'official': continue
        for h in Y.get('holidays') or []: out.append(dict(date=h['date'], name=h['name'], year=y))
    out.sort(key=lambda h: h['date'])
    return out if with_names else [h['date'] for h in out]

def year_status(year, path=None):
    Y = (load(path).get('years') or {}).get(str(year))
    return (Y or {}).get('status', 'missing')

def is_trading_day(day, path=None):
    """Weekday and not an official holiday. A day in a year without an official list counts as a trading day (the scans then find no
    candles if it was a holiday: harmless), while readiness.py keeps warning that the list is missing."""
    d = _d(day)
    return d.weekday() < 5 and d.isoformat() not in set(holidays(path))

def special_sessions(path=None):
    return [dict(s, year=y) for y, Y in sorted((load(path).get('years') or {}).items()) if Y.get('status') == 'official' for s in Y.get('special_sessions') or []]

def provisional(path=None):
    return [dict(p, year=y) for y, Y in sorted((load(path).get('years') or {}).items()) for p in Y.get('provisional') or []]

def coverage_end(path=None):
    """Last day covered by an official list (31 Dec of the latest official year), or None."""
    ys = [int(y) for y, Y in (load(path).get('years') or {}).items() if Y.get('status') == 'official']
    return dt.date(max(ys), 12, 31) if ys else None

def check(now, path=None):
    """(status, detail) for the readiness check and System health: ok / warn / fail."""
    d = _d(now); y = d.year; cur, nxt = year_status(y, path), year_status(y + 1, path)
    if cur != 'official': return 'fail', f'No official NSE holiday list for {y} is loaded (status: {cur}): add it to market_calendar.json from the NSE circular. Until then holidays are treated as trading days and Nifty expiries ignore them.'
    if d >= dt.date(y, 12, 1) and nxt != 'official':
        return 'warn', f'The {y + 1} NSE holiday list is not loaded yet (status: {nxt}; NSE usually publishes it in mid-December). Add it before 1 January.'
    return 'ok', f'Official NSE holidays loaded through {coverage_end(path)}.'
