#!/usr/bin/env python3
"""Daily digests to your phone (item 3): a pre-market brief at 08:45 and an end-of-day recap at 15:45, through ntfy and/or Telegram.

  python digest.py --mode morning|evening --dir pub/data [--force] [--print]

Reads the data files the scans already publish, so it needs no market data of its own. It does nothing on weekends and NSE holidays
(unless --force). The text builders are plain functions so they can be tested."""
import argparse, datetime as dt, json, os, sys

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

def _read(d, name):
    try: return json.load(open(os.path.join(d, name + '.json')))
    except Exception: return {}

def load(d):
    return dict(swing=_read(d, 'swing'), options=_read(d, 'options'), intraday=_read(d, 'intraday'), market=_read(d, 'market'), news=_read(d, 'news'),
                led={k: _read(d, 'signals_' + k) for k in ('swing', 'options', 'intraday')})

def _n(x, nd=0): return f'{x:,.{nd}f}' if isinstance(x, (int, float)) else '-'
def _pct(x): return f'{x:+.2f}%' if isinstance(x, (int, float)) else ''
def _when(iso):
    try: return dt.datetime.fromisoformat(iso).astimezone(IST)
    except Exception: return None

def market_line(m):
    i = (m or {}).get('indices') or {}; parts = []
    for k, nm in (('nifty', 'Nifty'), ('banknifty', 'Bank Nifty')):
        if i.get(k): parts.append(f"{nm} {_n(i[k].get('price'), 1)} ({_pct(i[k].get('change_pct'))})")
    if i.get('vix'): parts.append(f"VIX {_n(i['vix'].get('price'), 2)}")
    return ' · '.join(parts)

def shortlist(sw, k=5):
    S = [s for s in (sw or {}).get('setups', []) if s.get('stage', 0) >= 3 and not s.get('holds') and not str(s.get('status', '')).upper().startswith('WATCH')]
    return sorted(S, key=lambda s: (-s['stage'], -s.get('score', 0)))[:k]

def held_back(sw, k=3):
    return [s for s in (sw or {}).get('setups', []) if s.get('stage', 0) >= 3 and s.get('holds')][:k]

def setup_line(s):
    r = s.get('results') or {}; flag = f" · ⚠ results in {r['days']}d" if r.get('days') is not None and r['days'] <= 14 else ''
    return f"{s['symbol']} · {s.get('stage_label', 'stage ' + str(s['stage']))} · {s.get('grade', '')} {s.get('score', '')}/{s.get('max_score', 10)} · zone {_n(s.get('zone_bot'))}-{_n(s.get('zone_top'))} · stop {_n(s.get('sl'))}{flag}"

def active(led):
    return [(k, s) for k, L in led.items() for s in (L or {}).get('signals', []) if s.get('status') == 'ACTIVE']

def events(news, lo, hi, impact=None):
    out = []
    for e in (news or {}).get('events', []):
        d = e.get('days')
        if d is None or not (lo <= d <= hi) or e.get('type') == 'holiday' and d != 0: continue
        if impact and e.get('impact') not in impact: continue
        out.append(e)
    return out

def ev_line(e):
    d = e.get('days'); when = 'today' if d == 0 else 'tomorrow' if d == 1 else f'in {d}d'
    return f"• {e.get('title', '')} ({when}{', ' + e['time'] if e.get('time') else ''})"

def morning_text(D, now):
    sw, m, nw = D['swing'], D['market'], D['news']; L = []
    mk = market_line(m)
    if mk: L.append('Last close: ' + mk)
    if (m or {}).get('expected_move'): L.append(f"Expected move today: ±{_n(m['expected_move'].get('daily_pts'))} pts")
    if (m or {}).get('daily'): L.append(f"Regime: {m['daily'].get('label', '-')}" + (f" · {m['playbook']['headline']}" if (m.get('playbook') or {}).get('headline') else ''))
    L.append('')
    sl = shortlist(sw)
    L.append(f"Swing shortlist ({len(sl)}, pick 1 or 2):")
    L += ['• ' + setup_line(s) for s in sl] or ['• No swing setup is in its zone. Waiting is part of the plan.']
    hb = held_back(sw)
    if hb: L += ['', 'Held back:'] + [f"• {s['symbol']}: {(s['holds'][0] if isinstance(s['holds'][0], str) else s['holds'][0].get('text', 'hold'))}" for s in hb]
    st = (sw or {}).get('stages') or {}
    if st: L += ['', f"Pipeline: {st.get('5', 0)} entry · {st.get('4', 0)} 1H confirmed · {st.get('3', 0)} in zone · {st.get('2', 0)} alerts to set"]
    act = active(D['led'])
    if act: L += ['', 'Open tracked trades:'] + [f"• {s.get('instrument') or s['symbol']} ({k}): {s.get('r_now', 0):+.2f}R · stop {_n(s.get('stop'))}" for k, s in act]
    ev = events(nw, 0, 3, impact=('high', 'medium'))
    if ev: L += ['', 'Events:'] + [ev_line(e) for e in ev[:5]]
    for f in ((nw or {}).get('risk_flags') or [])[:2]:
        if f not in ' '.join(L): L.append('⚠ ' + f)
    g = _when((sw or {}).get('generated_at'))
    if g:
        age = (now - g).total_seconds() / 3600
        L += ['', f"Swing data from {g:%a %H:%M} IST" + (' ⚠ older than expected: the early scan may not have run.' if age > 30 else '')]
    return f"Morning brief · {now:%a %d %b}", '\n'.join(L).strip(), 'sunrise'

def _closed_today(led, today):
    out = []
    for k, L in led.items():
        for s in (L or {}).get('signals', []):
            if s.get('status') == 'CLOSED' and str(s.get('closed', ''))[:10] == today: out.append((k, s))
    return out

def evening_text(D, now):
    today = now.strftime('%Y-%m-%d'); L = []; mk = market_line(D['market'])
    if mk: L.append('Close: ' + mk)
    trig, closed = [], _closed_today(D['led'], today)
    for k, Lg in D['led'].items():
        for s in (Lg or {}).get('signals', []):
            for e in s.get('events', []):
                if str(e.get('t', ''))[:10] == today and e.get('kind') == 'trigger': trig.append((k, s, e))
    L += ['', f"Triggered today: {len(trig)}"] + [f"• {s.get('instrument') or s['symbol']} ({k}) at {e['t'][11:16]}" for k, s, e in trig[:6]]
    L += ['', f"Closed today: {len(closed)}"] + [f"• {s.get('instrument') or s['symbol']} ({k}): {s.get('outcome', '')} {s.get('r_final', 0):+.2f}R" for k, s in closed[:6]]
    if closed: L.append(f"Tracked signals total: {sum(s.get('r_final', 0) for _, s in closed):+.2f}R (half at T1, a quarter at T2, the rest at exit)")
    act = active(D['led'])
    L += ['', f"Still open: {len(act)}"] + [f"• {s.get('instrument') or s['symbol']} ({k}): {s.get('r_now', 0):+.2f}R · stop {_n(s.get('stop'))}" for k, s in act[:6]]
    sl = shortlist(D['swing'], 3)
    if sl: L += ['', 'Swing watch for tomorrow:'] + ['• ' + setup_line(s) for s in sl]
    ev = events(D['news'], 1, 2, impact=('high', 'medium'))
    if ev: L += ['', 'Tomorrow:'] + [ev_line(e) for e in ev[:4]]
    L += ['', 'Log your own trades and notes in the journal tonight, while you remember why.']
    return f"Day recap · {now:%a %d %b}", '\n'.join(L).strip(), 'city_sunset'

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='pub/data'); ap.add_argument('--mode', choices=('morning', 'evening'), required=True)
    ap.add_argument('--force', action='store_true'); ap.add_argument('--print', action='store_true', dest='show'); a = ap.parse_args(argv)
    now = dt.datetime.now(IST)
    import loop
    if not a.force and not loop.trading_day(now.date()): print(f'digest: {now.date()} is not a trading day, nothing sent'); return 0
    D = load(a.dir); title, body, tags = (morning_text if a.mode == 'morning' else evening_text)(D, now)
    if a.show: print(title + '\n' + body)
    import notify
    topic = os.environ.get('NTFY_TOPIC', '').strip(); click = os.environ.get('PAGE_URL', '').strip(); base = os.environ.get('NTFY_URL', 'https://ntfy.sh').rstrip('/')
    if not topic and not notify.telegram_ready(): print('digest: no alert channel configured'); return 0
    try: notify.post(base, topic, title, body, tags, click); print(f'digest sent: {title}'); return 0
    except Exception as ex: print(f'digest failed: {ex}', file=sys.stderr); return 1

if __name__ == '__main__':
    sys.exit(main())
