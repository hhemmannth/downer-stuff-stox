"""Trade lifecycle ledger. A setup that TRIGGERS becomes a signal and stays on the page until it closes: target, stop,
trailing stop or expiry, with every step time-stamped. Setups that disappear before triggering are listed as invalidated
with the reason, so nothing you were watching or trading silently vanishes after a refresh."""
import json, os
import datetime as dt
import pandas as pd

KEEP_DAYS = {'swing': 30, 'options': 5, 'intraday': 5}            # how long closed signals and dropped setups stay listed
SWING_EXPIRY_DAYS = 28                                            # calendar days a swing signal may stay open
SQUARE_OFF = (15, 15)                                             # options and intraday are closed by 15:15 IST
LAST_ENTRY = '15:00'                                              # and no new options or intraday trade after 15:00 IST
REASONS = {'BROKEN': 'Zone broken: price closed through the zone, so the setup is cancelled.',
           'EXTENDED': 'The trigger came after price had already run more than 1 ATR from the zone: no chase, no entry.',
           'FAR': 'Price moved away from the zone without a trigger.',
           'STALE': 'The structure became too old.',
           'WIDE': 'The zone became too wide for a sensible stop.',
           'NO_BIAS': 'The 15m bias turned against the trade.',
           'SCORE': 'The score fell below the minimum.',
           None: 'The structure is no longer there: a new swing changed the picture.'}

def key(section, it): return f"{section}|{it['symbol']}|{it['direction']}|{it['bos_date']}"

def load(path):
    try: led = json.load(open(path))
    except Exception: led = {}
    led.setdefault('signals', []); led.setdefault('dropped', []); led.setdefault('watch', {}); return led

def save(path, led, now):
    led['updated'] = now.isoformat(timespec='seconds'); tmp = path + '.tmp'
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(tmp, 'w') as f: json.dump(led, f, separators=(',', ':'), default=str)
    os.replace(tmp, path)

def _r(sig, price):
    risk = abs(sig['entry'] - sig['sl']); s = 1 if sig['direction'] == 'long' else -1
    return round(s * (price - sig['entry']) / risk, 2) if risk > 0 else 0.0

def _event(sig, ts, kind, text):
    ev = dict(t=pd.Timestamp(ts).isoformat(timespec='minutes'), kind=kind, text=text); sig['events'].append(ev); return dict(ev, id=sig['id'], symbol=sig['symbol'], section=sig['section'], label=sig['label'])

def _close(sig, ts, price, outcome, text):
    sig.update(status='CLOSED', outcome=outcome, exit=round(float(price), 2), closed=pd.Timestamp(ts).isoformat(timespec='minutes'))
    booked = sig.get('booked', [])                                  # (fraction, price) already taken at targets
    rest = 1.0 - sum(f for f, _ in booked); sig['r_final'] = round(sum(f * _r(sig, p) for f, p in booked) + rest * _r(sig, price), 2)
    return _event(sig, ts, outcome.lower(), text + f" Result {sig['r_final']:+.2f}R (half at the first target, a quarter at the second, the rest at exit).")

def new_signal(section, it, ts):
    lvl = lambda k: it.get(k)
    sig = dict(id=key(section, it), section=section, symbol=it['symbol'], direction=it['direction'], label=it.get('label', it['direction'].upper()), grade=it['grade'], score=it['score'],
               instrument=(it.get('options_trade') or {}).get('instrument'), created=pd.Timestamp(ts).isoformat(timespec='minutes'), entry=lvl('entry'), sl=lvl('sl'), t1=lvl('t1'), t2=lvl('t2'), t3=lvl('t3'),
               stage=it.get('stage'), checklist=it.get('checklist'), stop=lvl('sl'), hits={}, booked=[], status='ACTIVE', outcome=None, last=lvl('entry'), best=lvl('entry'), worst=lvl('entry'), r_now=0.0, events=[], checked_to=pd.Timestamp(ts).isoformat(), item=it)
    _event(sig, ts, 'trigger', f"Triggered at {it['entry']}. Stop {it['sl']}, T1 {it['t1']}, T2 {it['t2']}, T3 {it['t3']}.")
    return sig

def walk(sig, bars, now):
    """Replay the closed candles since the last check. The stop is checked before the targets inside a candle (the cautious assumption)."""
    out = []; long = sig['direction'] == 'long'
    ladder = sorted([('T1', sig['t1']), ('T2', sig['t2']), ('T3', sig['t3'])], key=lambda x: x[1], reverse=not long)
    start = pd.Timestamp(sig['checked_to'])
    if bars is not None and len(bars):
        idx = bars.index if bars.index.tz is not None or start.tzinfo is None else bars.index.tz_localize('Asia/Kolkata')
        st = start if (start.tzinfo is not None) == (idx.tz is not None) else (start.tz_localize('Asia/Kolkata') if start.tzinfo is None else start.tz_convert(None))
        for ts, row in zip(idx, bars.itertuples()):
            if ts <= st: continue
            hi, lo = float(row.High), float(row.Low)
            sig['best'] = max(sig['best'], hi) if long else min(sig['best'], lo); sig['worst'] = min(sig['worst'], lo) if long else max(sig['worst'], hi)
            if (long and lo <= sig['stop']) or (not long and hi >= sig['stop']):
                trail = bool(sig['hits']); out.append(_close(sig, ts, sig['stop'], 'TRAIL' if trail else 'SL', ('Trailing stop' if trail else 'Stop-loss') + f" {sig['stop']} hit.")); break
            for name, lvl in ladder:
                if name in sig['hits']: continue
                if (long and hi >= lvl) or (not long and lo <= lvl):
                    sig['hits'][name] = pd.Timestamp(ts).isoformat(timespec='minutes'); n = len(sig['hits'])
                    if n == 1 and sig['section'] == 'swing':        # your rules: no breakeven just because +1R was reached
                        sig['booked'].append((0.5, lvl)); out.append(_event(sig, ts, name.lower(), f"{name} {lvl} hit ({_r(sig, lvl):+.1f}R): book half. Keep the original stop: no early breakeven."))
                    elif n == 2 and sig['section'] == 'swing':
                        sig['booked'].append((0.25, lvl)); sig['stop'] = sig['entry']; out.append(_event(sig, ts, name.lower(), f"{name} {lvl} hit ({_r(sig, lvl):+.1f}R): book a quarter, protect at entry {sig['entry']} and trail behind each new daily higher low."))
                    elif n == 1: sig['booked'].append((0.5, lvl)); sig['stop'] = sig['entry']; out.append(_event(sig, ts, name.lower(), f"{name} {lvl} hit ({_r(sig, lvl):+.1f}R): book half, move the stop to entry {sig['entry']}."))
                    elif n == 2: sig['booked'].append((0.25, lvl)); sig['stop'] = ladder[0][1]; out.append(_event(sig, ts, name.lower(), f"{name} {lvl} hit ({_r(sig, lvl):+.1f}R): book a quarter, move the stop to {ladder[0][1]}."))
                    else: out.append(_close(sig, ts, lvl, 'TARGET', f"{name} {lvl} hit: final target reached.")); break
                else: break                                       # targets are reached in price order
            if sig['status'] == 'CLOSED': break
            sig['last'] = round(float(row.Close), 2); sig['r_now'] = _r(sig, sig['last']); sig['checked_to'] = pd.Timestamp(ts).isoformat()
    if sig['status'] == 'ACTIVE':
        made = pd.Timestamp(sig['created'])
        if sig['section'] in ('options', 'intraday'):
            cut = made.normalize() + pd.Timedelta(hours=SQUARE_OFF[0], minutes=SQUARE_OFF[1])
            if now >= (cut if cut.tzinfo is not None else cut.tz_localize('Asia/Kolkata')): out.append(_close(sig, now, sig['last'], 'EXPIRED', f"Squared off at {sig['last']} (15:15 rule)."))
        elif (now - (made if made.tzinfo is not None else made.tz_localize('Asia/Kolkata'))).days > SWING_EXPIRY_DAYS:
            out.append(_close(sig, now, sig['last'], 'EXPIRED', f'Closed after {SWING_EXPIRY_DAYS} days without reaching T3.'))
    return out

def update(led, section, items, states, bars, now, can_open=True):
    """items: setups from this run. states: {(symbol, direction): state or None} for everything scanned.
    bars: {symbol: closed candles to follow open trades}. Returns the new lifecycle events (for phone alerts)."""
    late = lambda s: s['section'] in ('options', 'intraday') and pd.Timestamp(s['created']).strftime('%H:%M') >= LAST_ENTRY
    led['signals'] = [s for s in led['signals'] if not (s['status'] == 'ACTIVE' and late(s))]   # no new trades after 15:00
    events = []; known = {s['id'] for s in led['signals']}
    for sig in led['signals']:
        if sig['status'] == 'ACTIVE': events += walk(sig, bars.get(sig['symbol']), now)
    current = {key(section, it): it for it in items}
    for k, it in current.items():
        frame = bars.get(it['symbol']); ts = frame.index[-1] if frame is not None and len(frame) else now
        if section in ('options', 'intraday') and pd.Timestamp(ts).strftime('%H:%M') >= LAST_ENTRY: can_open = False
        if it['status'] == 'TRIGGERED' and k not in known and can_open:
            sig = new_signal(section, it, ts); led['signals'].append(sig); events.append(dict(sig['events'][0], id=sig['id'], symbol=sig['symbol'], section=section, label=sig['label'])); led['watch'].pop(k, None)
        elif not it['status'].startswith('TRIGGER'):
            w = led['watch'].get(k) or dict(first_seen=now.isoformat(timespec='minutes'))
            w.update(id=k, section=section, symbol=it['symbol'], direction=it['direction'], label=it.get('label'), status=it['status'], grade=it['grade'], score=it['score'], entry=it['entry'], sl=it['sl'], t1=it['t1'],
                     zone_bot=it['zone_bot'], zone_top=it['zone_top'], last_seen=now.isoformat(timespec='minutes')); led['watch'][k] = w
    for k in list(led['watch']):
        if k in current or k in known: continue
        w = led['watch'].pop(k); st = states.get((w['symbol'], w['direction']), 'GONE')
        if st == 'GONE': continue                                   # not scanned this run (e.g. data missing): keep nothing, decide next time
        w.update(dropped=now.isoformat(timespec='minutes'), reason=REASONS.get(st, REASONS[None]), state=st); led['dropped'].append(w)
    cut = now - pd.Timedelta(days=KEEP_DAYS[section])
    led['signals'] = [s for s in led['signals'] if s['status'] == 'ACTIVE' or pd.Timestamp(s.get('closed') or s['created']) >= (cut if pd.Timestamp(s.get('closed') or s['created']).tzinfo is not None else cut.tz_localize(None))]
    led['dropped'] = [d for d in led['dropped'] if pd.Timestamp(d['dropped']) >= cut][-200:]
    return events
