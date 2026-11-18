"""Trade lifecycle ledger. A setup that TRIGGERS becomes a signal and stays on the page until it closes: target, stop,
trailing stop or expiry, with every step time-stamped. Setups that disappear before triggering are listed as invalidated
with the reason, so nothing you were watching or trading silently vanishes after a refresh."""
import json, os
import datetime as dt
import pandas as pd
import holdbacks

KEEP_DAYS = {'swing': 30, 'options': 5, 'intraday': 5, 'gold_intraday': 5, 'gold_swing': 30, 'gold_positional': 120}   # how long closed signals and dropped setups stay listed
SWING_EXPIRY_DAYS = 28                                            # calendar days a swing signal may stay open
POSITIONAL_EXPIRY_DAYS = 120                                      # positional trades (weekly structure, daily trigger) are held for weeks or months
SWINGLIKE = ('swing', 'positional', 'gold_swing', 'gold_positional')   # sections that follow the swing rules: half at T1 with no early breakeven, a quarter at T2
GOLD_CLOCK = 'Etc/GMT-2'                                          # gold's session clock (UTC+2): its trading day ends at this clock's midnight
GOLD_SQUARE = (22, 30)                                            # gold intraday is closed by 22:30 on that clock = 20:30 UTC = 02:00 IST

def gold_square_off(made):
    """When a gold intraday trade opened at `made` must be closed: the end of the London/New York session it belongs to."""
    t = pd.Timestamp(made); t = t.tz_localize('Asia/Kolkata') if t.tzinfo is None else t
    g = t.tz_convert(GOLD_CLOCK); return g.normalize() + pd.Timedelta(hours=GOLD_SQUARE[0], minutes=GOLD_SQUARE[1])
SQUARE_OFF = (15, 15)                                             # options and intraday are closed by 15:15 IST
LAST_ENTRY = '15:00'                                              # and no new options trade after 15:00 IST
LAST_ENTRY_BY = {} if holdbacks.off() else dict(intraday='14:00')                           # stock intraday: the backtest of 999 trades lost money after 14:00 in every month (profit factor 0.45), so the last entry is 14:00
def last_entry(section): return LAST_ENTRY_BY.get(section, LAST_ENTRY)
# ---- your daily rule (18 Nov 2026): at most 2 trades a day, and only high quality (A+, score 8 or more). Strict: even an A+ waits for tomorrow unless APLUS_OVERFLOW=on.
# The same numbers drive the backtest ("With your rules") through the repo variables MAX_TRADES_PER_DAY, MIN_SCORE and APLUS_OVERFLOW.
def day_rules(env=None):
    e = env if env is not None else os.environ
    def num(k, d):
        try: return int(float(str(e.get(k, '') or '').strip())) if str(e.get(k, '') or '').strip() else d
        except ValueError: return d
    ov = str(e.get('APLUS_OVERFLOW', '') or '').strip().lower() in ('on', 'true', 'yes', '1')
    return dict(max_day=max(0, num('MAX_TRADES_PER_DAY', 2)), min_score=num('MIN_SCORE', 8), overflow=ov)

def trade_day(section, ts):
    """The trading day a trade belongs to: the IST date for NSE sections, the UTC+2 session day for the gold sections (a gold session runs past midnight IST)."""
    t = pd.Timestamp(ts)
    if t.tzinfo is None: t = t.tz_localize('Asia/Kolkata')
    return (t.tz_convert(GOLD_CLOCK) if str(section).startswith('gold') else t.tz_convert('Asia/Kolkata')).date()

def limit_items(items, taken, section, now, holding=(), rules=None):
    """Mark every TRIGGERED setup that may NOT be taken as 'TRIGGERED (not taken: reason)' (the pages show these as 'not taken'; they stay listed, nothing vanishes).
    taken: the signals already opened (any ledger that shares the limit). Setups are ranked by score, so when several trigger together the best ones use the free slots;
    over time it is first come first served. Setups already opened (id in `taken`), and ones blocked because that stock/side is already a tracked trade, do not use a slot."""
    r = rules or day_rules(); day = trade_day(section, now); known = {s['id'] for s in taken}
    n = sum(1 for s in taken if trade_day(s['section'], s['created']) == day)
    hold = set(holding); todo = [it for it in items if it.get('status') == 'TRIGGERED' and key(section, it) not in known and (it['symbol'], it['direction']) not in hold]
    for it in sorted(todo, key=lambda x: -(x.get('score') or 0)):
        sc_ = it.get('score') or 0; aplus = sc_ >= r['min_score']
        if sc_ < r['min_score']: it['status'] = f"TRIGGERED (not taken: score {sc_}/10, only {r['min_score']}+ is taken)"
        elif n >= r['max_day'] and not (r['overflow'] and aplus): it['status'] = f"TRIGGERED (not taken: {n} trades already taken today, your limit is {r['max_day']} a day)"
        else: n += 1
    return items

REASONS = {'BROKEN': 'Zone broken: price closed through the zone, so the setup is cancelled.',
           'EXTENDED': 'The trigger came after price had already run more than 1 ATR from the zone: no chase, no entry.',
           'FAR': 'Price moved away from the zone without a trigger.',
           'STALE': 'The structure became too old.',
           'WIDE': 'The zone became too wide for a sensible stop.',
           'NO_BIAS': 'The 15m bias turned against the trade.',
           'SCORE': 'The score fell below the minimum.',
           'WEEKLY': 'The weekly trend is no longer up (your weekly location filter).',
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

def daily_swings(bars, idx):
    """Daily lows and highs built from the candles being walked (1H for swing, daily for positional): {date: (low, high)} in date order."""
    try:
        d = pd.DataFrame({'Low': bars.Low.values.astype(float), 'High': bars.High.values.astype(float)}, index=[t.date() for t in idx])
        g = d.groupby(level=0).agg({'Low': 'min', 'High': 'max'}); return list(g.itertuples(name=None))
    except Exception: return []

def trail_level(days, today, since, long=True):
    """Your swing trail after T2: the latest confirmed daily higher low (a daily low with a higher low on each side, all three days
    finished before `today`), formed after `since` (the trigger day). Mirrored with highs for shorts. None if there is none yet."""
    done = [x for x in days if x[0] < today]
    for i in range(len(done) - 2, 0, -1):
        d, lo, hi = done[i]
        if d <= since: break
        if long and lo < done[i - 1][1] and lo <= done[i + 1][1]: return float(lo)
        if not long and hi > done[i - 1][2] and hi >= done[i + 1][2]: return float(hi)
    return None

def walk(sig, bars, now):
    """Replay the closed candles since the last check. The stop is checked before the targets inside a candle (the cautious assumption).
    Swing-like trades trail after T2 below each new confirmed daily higher low (your playbook: 'protect behind the new daily higher low,
    then trail by daily structure'); before 17 Nov 2026 the alert said so but the stop stayed at entry."""
    out = []; long = sig['direction'] == 'long'
    ladder = sorted([('T1', sig['t1']), ('T2', sig['t2']), ('T3', sig['t3'])], key=lambda x: x[1], reverse=not long)
    start = pd.Timestamp(sig['checked_to'])
    if bars is not None and len(bars):
        idx = bars.index if bars.index.tz is not None or start.tzinfo is None else bars.index.tz_localize('Asia/Kolkata')
        st = start if (start.tzinfo is not None) == (idx.tz is not None) else (start.tz_localize('Asia/Kolkata') if start.tzinfo is None else start.tz_convert(None))
        trails = sig['section'] in SWINGLIKE; days = daily_swings(bars, idx) if trails else []; made_day = pd.Timestamp(sig['created']).date(); day_seen = None
        for ts, row in zip(idx, bars.itertuples()):
            if ts <= st: continue
            if trails and len(sig['hits']) >= 2 and ts.date() != day_seen:                    # once per new day, before that day's candles
                day_seen = ts.date(); lvl = trail_level(days, day_seen, made_day, long)
                if lvl is not None and ((long and lvl > sig['stop']) or (not long and lvl < sig['stop'])):
                    sig['stop'] = round(lvl, 2); out.append(_event(sig, ts, 'trail', f"Stop trailed to {sig['stop']}: below the new daily higher low." if long else f"Stop trailed to {sig['stop']}: above the new daily lower high."))
            hi, lo = float(row.High), float(row.Low)
            sig['best'] = max(sig['best'], hi) if long else min(sig['best'], lo); sig['worst'] = min(sig['worst'], lo) if long else max(sig['worst'], hi)
            if (long and lo <= sig['stop']) or (not long and hi >= sig['stop']):
                trail = bool(sig['hits']); out.append(_close(sig, ts, sig['stop'], 'TRAIL' if trail else 'SL', ('Trailing stop' if trail else 'Stop-loss') + f" {sig['stop']} hit.")); break
            for name, lvl in ladder:
                if name in sig['hits']: continue
                if (long and hi >= lvl) or (not long and lo <= lvl):
                    sig['hits'][name] = pd.Timestamp(ts).isoformat(timespec='minutes'); n = len(sig['hits'])
                    if n == 1 and sig['section'] in SWINGLIKE:        # your rules: no breakeven just because +1R was reached
                        sig['booked'].append((0.5, lvl)); out.append(_event(sig, ts, name.lower(), f"{name} {lvl} hit ({_r(sig, lvl):+.1f}R): book half. Keep the original stop: no early breakeven."))
                    elif n == 2 and sig['section'] in SWINGLIKE:
                        sig['booked'].append((0.25, lvl)); sig['stop'] = sig['entry']; out.append(_event(sig, ts, name.lower(), f"{name} {lvl} hit ({_r(sig, lvl):+.1f}R): book a quarter, protect at entry {sig['entry']} and trail behind each new daily higher low."))
                    elif n == 1: sig['booked'].append((0.5, lvl)); sig['stop'] = sig['entry']; out.append(_event(sig, ts, name.lower(), f"{name} {lvl} hit ({_r(sig, lvl):+.1f}R): book half, move the stop to entry {sig['entry']}."))
                    elif n == 2: sig['booked'].append((0.25, lvl)); sig['stop'] = ladder[0][1]; out.append(_event(sig, ts, name.lower(), f"{name} {lvl} hit ({_r(sig, lvl):+.1f}R): book a quarter, move the stop to {ladder[0][1]}."))
                    else: out.append(_close(sig, ts, lvl, 'TARGET', f"{name} {lvl} hit: final target reached.")); break
                else: break                                       # targets are reached in price order
            if sig['status'] == 'CLOSED': break
            sig['last'] = round(float(row.Close), 2); sig['r_now'] = _r(sig, sig['last']); sig['checked_to'] = pd.Timestamp(ts).isoformat()
    if sig['status'] == 'ACTIVE':
        made = pd.Timestamp(sig['created'])
        if sig['section'] == 'gold_intraday':
            cut = gold_square_off(made); nw = pd.Timestamp(now); nw = nw.tz_localize('Asia/Kolkata') if nw.tzinfo is None else nw
            if nw >= cut: out.append(_close(sig, now, sig['last'], 'EXPIRED', f"Squared off at {sig['last']} (end of the New York session, 02:00 IST)."))
        elif sig['section'] in ('options', 'intraday'):
            cut = made.normalize() + pd.Timedelta(hours=SQUARE_OFF[0], minutes=SQUARE_OFF[1])
            if now >= (cut if cut.tzinfo is not None else cut.tz_localize('Asia/Kolkata')): out.append(_close(sig, now, sig['last'], 'EXPIRED', f"Squared off at {sig['last']} (15:15 rule)."))
        else:
            life = POSITIONAL_EXPIRY_DAYS if sig['section'] in ('positional', 'gold_positional') else SWING_EXPIRY_DAYS
            if (now - (made if made.tzinfo is not None else made.tz_localize('Asia/Kolkata'))).days > life:
                out.append(_close(sig, now, sig['last'], 'EXPIRED', f'Closed after {life} days without reaching T3.'))
    return out

def update(led, section, items, states, bars, now, can_open=True, limit=True, others=()):
    """items: setups from this run. states: {(symbol, direction): state or None} for everything scanned.
    bars: {symbol: closed candles to follow open trades}. Returns the new lifecycle events (for phone alerts)."""
    late = lambda s: s['section'] in ('options', 'intraday') and pd.Timestamp(s['created']).strftime('%H:%M') >= last_entry(s['section'])
    led['signals'] = [s for s in led['signals'] if not (s['status'] == 'ACTIVE' and late(s))]   # no new trades after 15:00
    events = []; known = {s['id'] for s in led['signals']}
    for k in [k for k in led['watch'] if k in known]: del led['watch'][k]                                   # a setup that is already a trade lives in the trades list only:
    seen_ids = set()                                                                                       # never in the watch or dropped lists (this also heals old files);
    led['dropped'] = [d for d in reversed(led['dropped']) if d.get('id') not in known and not (d.get('id') in seen_ids or seen_ids.add(d.get('id')))][::-1]    # one entry per setup, the latest
    for sig in led['signals']:
        if sig['status'] == 'ACTIVE': events += walk(sig, bars.get(sig['symbol']), now)
    holding = {(s['symbol'], s['direction']) for s in led['signals'] if s['status'] == 'ACTIVE'}       # one open tracked trade per stock and side
    if limit: limit_items(items, list(led['signals']) + list(others), section, now, holding)      # others: the signals of the other segments that share the daily limit                                  # your daily rule: 2 a day, A+ only
    current = {key(section, it): it for it in items}
    for k, it in current.items():
        frame = bars.get(it['symbol']); ts = frame.index[-1] if frame is not None and len(frame) else now
        if section in ('options', 'intraday') and pd.Timestamp(ts).strftime('%H:%M') >= last_entry(section): can_open = False
        if it['status'] == 'TRIGGERED' and k not in known and can_open:
            if (it['symbol'], it['direction']) in holding: continue                                         # a new structure on a stock that is already a tracked trade:
                                                                                                           # not a second position (SANSERA had an open trade and a fresh setup)
            holding.add((it['symbol'], it['direction']))
            sig = new_signal(section, it, ts); led['signals'].append(sig); events.append(dict(sig['events'][0], id=sig['id'], symbol=sig['symbol'], section=section, label=sig['label'])); led['watch'].pop(k, None)
            led['dropped'] = [d for d in led['dropped'] if d.get('id') != k]                               # it was dropped earlier but came back and triggered: it is a trade now
        elif not it['status'].startswith('TRIGGER'):
            if k in known: continue                                                                        # already a trade (even if the trigger candle has passed): not a watch item again
            led['dropped'] = [d for d in led['dropped'] if d.get('id') != k]                               # back in play: no longer 'dropped'
            w = led['watch'].get(k) or dict(first_seen=now.isoformat(timespec='minutes'))
            w.update(id=k, section=section, symbol=it['symbol'], direction=it['direction'], label=it.get('label'), status=it['status'], grade=it['grade'], score=it['score'], entry=it['entry'], sl=it['sl'], t1=it['t1'],
                     zone_bot=it['zone_bot'], zone_top=it['zone_top'], last_seen=now.isoformat(timespec='minutes')); led['watch'][k] = w
    for k in list(led['watch']):
        if k in current or k in known: continue
        w = led['watch'].pop(k); st = states.get((w['symbol'], w['direction']), 'GONE')
        if st in ('GONE', 'OK'): continue                           # not scanned this run (data missing), or still a valid setup that was only ranked out or
                                                                     # filtered after the scan: no 'dropped' entry with a wrong reason (it said 'the structure is no longer there')
        w.update(dropped=now.isoformat(timespec='minutes'), reason=REASONS.get(st, REASONS[None]), state=st)
        led['dropped'] = [d for d in led['dropped'] if d.get('id') != k] + [w]                             # one dropped entry per setup, the latest
    cut = now - pd.Timedelta(days=KEEP_DAYS.get(section, 30))
    led['signals'] = [s for s in led['signals'] if s['status'] == 'ACTIVE' or pd.Timestamp(s.get('closed') or s['created']) >= (cut if pd.Timestamp(s.get('closed') or s['created']).tzinfo is not None else cut.tz_localize(None))]
    led['dropped'] = [d for d in led['dropped'] if pd.Timestamp(d['dropped']) >= cut][-200:]
    return events
