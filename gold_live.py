#!/usr/bin/env python3
"""Live XAUUSD gold scanner: the same engines as the gold backtests, run on fresh candles every 5 minutes through every gold session.

  intraday    5m structure and trigger with the 15m CHoCH bias, long and short, every 5 minutes; no new entry 00:30-04:00 IST, closed by 02:00 IST
  swing       daily structure, 1H confirmation, long and short (shorts on the mirrored chart), checked every hour
  positional  weekly structure, daily trigger, long and short, checked every hour

Only A+ setups (score 8 to 10) are listed and taken. A setup that TRIGGERS becomes a tracked signal (signals.py: the same trade rules as
the backtest), at most GOLD_MAX_OPEN open at once (2 = your 2% open-risk cap at 0.75% a trade), and past 2 trades a day only A+ (always
true here, since only A+ is taken). It NEVER places orders: you get an alert with entry, stop, targets and lots, and you decide.
Data: Yahoo GC=F (COMEX gold futures), the closest free intraday feed; it can lag the live market by a few minutes.

  python gold_live.py --out pub/data --state pub/state [--styles intraday,swing,positional]"""
import argparse, datetime as dt, json, math, os, sys
import numpy as np, pandas as pd
import backtest as bt, backtest_tf as tf, signals, strategy_scanner as sc

IST = 'Asia/Kolkata'; GOLD_TZ = tf.GOLD_TZ; LABEL = tf.GOLD_LABEL; STYLES = ('intraday', 'swing', 'positional')
SECTION = {k: 'gold_' + k for k in STYLES}
TITLE = {'intraday': 'Gold intraday', 'swing': 'Gold swing', 'positional': 'Gold positional'}

def env_int(name, default):
    try: return int(float(os.environ.get(name, '') or default))
    except ValueError: return default

def market_open(now):
    """Gold trades from Sunday 22:00 UTC (23:00 in the northern winter) to Friday 22:00 UTC, with a short daily break. Weekends are closed."""
    import watchdog; return watchdog.gold_market_open(pd.Timestamp(now).to_pydatetime())

def session_name(now):
    """Which session it is, in IST terms (summer hours; in winter London and New York start about an hour later)."""
    t = pd.Timestamp(now).tz_convert(IST); m = t.hour * 60 + t.minute
    if 12 * 60 + 30 <= m < 17 * 60 + 30: return 'London'
    if 17 * 60 + 30 <= m < 21 * 60 + 30: return 'London + New York'
    if m >= 21 * 60 + 30 or m < 2 * 60 + 30: return 'New York'
    return 'Asia'

def entry_window(now, session=None):
    """True when a new gold intraday trade may open (the backtest uses the same window)."""
    S = session or tf.gold_session(); g = pd.Timestamp(now).tz_convert(S['tz']); m = g.hour * 60 + g.minute
    return S['first'] <= m <= S['last']

def _lv(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 2)

def item(style, side, r, entry, sl, t1, t2, t3, status, extra=None):
    """One setup in the shape the page, the tracker and the alerts read."""
    risk = abs(entry - sl)
    it = dict(symbol=LABEL, section=SECTION[style], style=style, direction=side, label=side.upper(), grade=r['grade'], score=int(r['score']), status=status,
              entry=_lv(entry), sl=_lv(sl), t1=_lv(t1), t2=_lv(t2), t3=_lv(t3), risk_usd=round(risk, 2), zone_bot=_lv(r.get('zone_bot')), zone_top=_lv(r.get('zone_top')),
              structure=int(r.get('structure') or 0), zone_q=int(r.get('zone_q') or 0), confirm=int(r.get('confirm') or 0), context=int(r.get('context') or 0),
              bos_date=str(r.get('bos_date') or '')[:16], stage=r.get('stage'))
    if extra: it.update(extra)
    return it

# ------------------------------------------------------------------ the three styles
def scan_intraday(f5, f15, now, min_score):
    """f5, f15: 5m and 15m gold candles (closed bars only). Returns (items, states)."""
    S = tf.gold_session(); a5, a15 = tf._aware(f5, S['tz']), tf._aware(f15, S['tz']); items, states = [], {}
    if len(a5) < sc.CFG_I['min_bars'] or len(a15) < 3: return items, states
    w5, w15 = a5.tail(375), a15.tail(250); lv = sc.prev_day_levels(w5)
    for side in ('long', 'short'):
        try: r = sc.scan_intraday(w5, w15, side, sc.CFG_I, lv, section='intraday')
        except Exception as ex: print(f'  intraday {side}: {ex}', file=sys.stderr); continue
        states[(LABEL, side)] = sc.state_of(r, min_score)
        if not r or 'zone_bot' not in r or 'entry' not in r or r['score'] < min_score: continue
        long = side == 'long'; entry, sl = sc.r05(r['entry']), sc.r05(r['sl']); risk = (entry - sl) if long else (sl - entry)
        if risk <= 0: continue
        t1, t2, t3 = sc.r05(r['t1']), sc.r05(r['t2']), sc.r05(r['t3'])
        if (long and t1 <= entry) or (not long and t1 >= entry): t1 = sc.r05(entry + risk if long else entry - risk)
        status = r['status'] if entry_window(now) or not r['status'].startswith('TRIGGER') else 'TRIGGERED (outside the entry window)'
        items.append(item('intraday', side, r, entry, sl, t1, t2, t3, status, dict(tf_structure='5m', ticks=[t for t in r['ticks'].split(', ') if t and t != '-'])))
    return items, states

def _swing_one(daily, h1, side, K, min_score):
    import swing
    d, h = (daily, h1) if side == 'long' else (sc.invert(daily, K), sc.invert(h1, K))
    rr = swing.analyse(d.tail(250), h)
    if not rr or rr.get('stage', 0) < 2 or rr['score'] < min_score or rr.get('sl') is None: return None, (None if not rr else rr.get('stage'))
    entry = float(h.Close.iloc[-1]); sl = float(rr['sl']); risk = entry - sl
    if risk <= 0: return None, rr.get('stage')
    fresh = rr.get('stage', 0) >= 4 and (rr.get('cf') or {}).get('confirm_age') == 0
    chase = entry - rr['zone_top'] > swing.CFG['entry_chase_atr'] * rr['atr'] * 3
    held = (['weekly trend against'] if rr['weekly'].get('up') is False else []) + (['room under 2R'] if rr.get('room_r') is not None and rr['room_r'] < swing.CFG['min_room_r'] else [])
    status = ('TRIGGERED' if not held and not chase else 'HELD BACK (' + ', '.join(held or ['price ran away from the zone']) + ')') if fresh else \
             {2: 'SET ALERT (wait for the pullback)', 3: 'IN ZONE (wait for the 1H)'}.get(rr['stage'], 'WATCH (1H confirmed earlier)')
    m = (lambda x: K - x) if side == 'short' else (lambda x: x)
    zb, zt = (rr['zone_bot'], rr['zone_top']) if side == 'long' else (K - rr['zone_top'], K - rr['zone_bot'])
    r = dict(rr, zone_bot=zb, zone_top=zt, bos_date=rr.get('bos_date'))
    return item('swing', side, r, m(entry), m(sl), m(entry + risk), m(entry + 2 * risk), m(entry + 3 * risk), status,
                dict(tf_structure='1D', held=held, weekly=('down' if side == 'short' else 'up') if rr['weekly'].get('up') else 'against', room_r=_lv(rr.get('room_r')))), rr.get('stage')

def scan_swing(daily, h1, min_score):
    """daily: gold daily candles (finished sessions), h1: 1H candles (closed). Long and short."""
    items, states = [], {}
    if daily is None or h1 is None or len(daily) < sc.CFG['min_bars'] + 5 or len(h1) < 20: return items, states
    h1 = h1[h1.index >= h1.index[-1] - pd.Timedelta(days=92)]; K = tf.mirror_k(daily, h1)
    for side in ('long', 'short'):
        try: it, stage = _swing_one(daily, h1, side, K, min_score)
        except Exception as ex: print(f'  swing {side}: {ex}', file=sys.stderr); continue
        states[(LABEL, side)] = None if it is None else 'IN_ZONE'
        if it: items.append(it)
    return items, states

def scan_positional(daily, min_score):
    """Weekly structure, daily trigger (the positional backtest's engine), long and short."""
    items, states = [], {}; cfg = tf.CFG_GP
    if daily is None or len(daily) < cfg['min_bars'] * 5 + 30: return items, states
    d = daily.dropna(subset=['Open', 'High', 'Low', 'Close']); K = tf.mirror_k(d)
    for side in ('long', 'short'):
        dd = d if side == 'long' else sc.invert(d, K); W = tf._weekly(dd)
        try: r = sc.detect(W.iloc[-cfg['lookback']:], dd.tail(240), cfg, None if side == 'long' else K, 'swing')
        except Exception as ex: print(f'  positional {side}: {ex}', file=sys.stderr); continue
        states[(LABEL, side)] = sc.state_of(r, min_score)
        if not r or 'zone_bot' not in r or 'entry' not in r or r['score'] < min_score: continue
        entry, sl = float(r['entry']), float(r['sl']); risk = entry - sl
        if risk <= 0: continue
        if side == 'short': r = sc.unflip(dict(r), K)
        m = (lambda x: K - x) if side == 'short' else (lambda x: x); e0 = m(entry)
        items.append(item('positional', side, r, e0, m(sl), m(entry + risk), m(entry + 2 * risk), m(entry + 3 * risk), r['status'], dict(tf_structure='1W')))
    return items, states

# ------------------------------------------------------------------ tracking, your daily rule and alerts
def ledger_path(out, style): return os.path.join(out, f'signals_{SECTION[style]}.json')

def today_count(out, now):
    """Gold trades opened today (gold session day) and gold trades open now, across the three styles."""
    day = bt.session_day(now, GOLD_TZ); n_day = n_open = 0
    for st in STYLES:
        for s in signals.load(ledger_path(out, st))['signals']:
            if s['status'] == 'ACTIVE': n_open += 1
            if bt.session_day(pd.Timestamp(s['created']), GOLD_TZ) == day: n_day += 1
    return n_day, n_open

def apply_rules(items, out, now, max_open, max_day):
    """Your rules before a trigger is taken: at most max_open gold trades open at once, and past max_day a day only A+."""
    n_day, n_open = today_count(out, now); known = set()
    for st in STYLES: known |= {s['id'] for s in signals.load(ledger_path(out, st))['signals']}
    for it in items:
        if it['status'] != 'TRIGGERED' or signals.key(it['section'], it) in known: continue
        if n_open >= max_open: it['status'] = f'TRIGGERED (not taken: {n_open} gold trades already open, your limit is {max_open})'; continue
        if n_day >= max_day and it['grade'] != 'A+': it['status'] = f'TRIGGERED (not taken: {n_day} trades today and this is not A+)'; continue
        n_open += 1; n_day += 1
    return items

def lots_text(risk_usd):
    """Lots for the gold account in the repo variables (GOLD_ACCOUNT in dollars, GOLD_RISK_PCT for A+, default 0.75%)."""
    try: acct = float(os.environ.get('GOLD_ACCOUNT', '') or 0); rp = float(os.environ.get('GOLD_RISK_PCT', '') or 0.75)
    except ValueError: acct, rp = 0.0, 0.75
    per = f'0.01 lot risks ${risk_usd:.2f}'
    if acct <= 0 or risk_usd <= 0: return per
    lots = math.floor(acct * rp / 100 / (risk_usd * 100) * 100) / 100
    return f'{lots:.2f} lots for {rp}% of ${acct:,.0f} ({per})' if lots >= 0.01 else f'stop too wide for {rp}% of ${acct:,.0f}: even 0.01 lot risks more ({per})'

def send(title, body, tags, click, sent):
    import notify
    topic = os.environ.get('NTFY_TOPIC', '').strip()
    if not topic and not notify.telegram_ready(): return False
    try: notify.post(os.environ.get('NTFY_URL', 'https://ntfy.sh').rstrip('/'), topic, title, body, tags, click); sent.append(title); return True
    except Exception as ex: print(f'  gold alert failed: {ex}', file=sys.stderr); return False

def alerts(out, state_path, now):
    """One push per new gold trade (entry, stop, targets, lots) and per step of a tracked trade (T1, T2, T3, stop, square-off). Never twice."""
    try: st = json.load(open(state_path))
    except Exception: st = {}
    seen = st.get('sent', {}); click = os.environ.get('PAGE_URL', '').strip().rstrip('/'); link = (click + '/#/gold') if click else ''; sent = []
    icon = {'trigger': 'star', 't1': 'white_check_mark', 't2': 'white_check_mark', 'target': 'trophy', 'sl': 'x', 'trail': 'lock', 'expired': 'hourglass'}
    for style in STYLES:
        for sig in signals.load(ledger_path(out, style))['signals']:
            for ev in sig.get('events', []):
                k = f"{sig['id']}|{ev['kind']}|{ev['t']}"
                if k in seen: continue
                if (pd.Timestamp(now) - pd.Timestamp(ev['t'])).total_seconds() > 6 * 3600: seen[k] = ev['t'][:10]; continue      # old news: mark, do not send
                it = sig.get('item') or {}
                if ev['kind'] == 'trigger':
                    title = f"{TITLE[style]}: {sig['label']} XAUUSD, A+ {sig['score']}/10"
                    body = '\n'.join([f"Entry {sig['entry']}   Stop {sig['sl']}   (stop ${it.get('risk_usd', abs(sig['entry'] - sig['sl'])):.2f} an ounce)", f"T1 {sig['t1']}   T2 {sig['t2']}   T3 {sig['t3']}",
                                      lots_text(float(it.get('risk_usd') or abs(sig['entry'] - sig['sl']))), 'Prices are COMEX gold futures (GC=F): check them against your XAUUSD chart. You place the order.'])
                else: title, body = f"{TITLE[style]}: XAUUSD {sig['label']} {ev['kind'].upper()}", ev['text']
                send(title, body, icon.get(ev['kind'], 'bell'), link, sent); seen[k] = ev['t'][:10]
    cut = (pd.Timestamp(now) - pd.Timedelta(days=10)).strftime('%Y-%m-%d'); st['sent'] = {k: v for k, v in seen.items() if v >= cut}
    os.makedirs(os.path.dirname(state_path) or '.', exist_ok=True); json.dump(st, open(state_path, 'w')); return sent

# ------------------------------------------------------------------ one run
def fetch_frames(styles, now, sym, fetch=None):
    fr = {}
    if 'intraday' in styles: fr['f5'], fr['f15'] = tf.gold_intraday(sym, '5d', '5m', now, fetch), tf.gold_intraday(sym, '30d', '15m', now, fetch)
    if 'swing' in styles: fr['h1'] = tf.gold_intraday(sym, '180d', '1h', now, fetch)
    if 'swing' in styles or 'positional' in styles: fr['daily'] = tf.gold_daily(sym, '5y', now, fetch)
    return fr

def run(out, state_dir, styles=STYLES, now=None, fetch=None):
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz=IST); now = now.tz_localize(IST) if now.tzinfo is None else now.tz_convert(IST)
    os.makedirs(out, exist_ok=True); rules = bt.rules_from_env(); ms = rules['min_score']; sym = tf.gold_symbol()
    max_open, max_day = env_int('GOLD_MAX_OPEN', 2), env_int('MAX_TRADES_PER_DAY', 2)
    fr = fetch_frames(styles, now, sym, fetch); prev = sc.read_json(out, 'gold.json', {}) or {}; doc = dict(prev); doc['styles'] = dict(prev.get('styles') or {})
    is_open = market_open(now); tracked = 0
    for style in styles:
        try:
            if style == 'intraday': items, states = scan_intraday(fr.get('f5'), fr.get('f15'), now, ms) if fr.get('f5') is not None and fr.get('f15') is not None else ([], {})
            elif style == 'swing': items, states = scan_swing(fr.get('daily'), fr.get('h1'), ms)
            else: items, states = scan_positional(fr.get('daily'), ms)
        except Exception as ex: print(f'gold {style} failed: {ex}', file=sys.stderr); doc['styles'][style] = dict(error=str(ex)[:200], scanned_at=now.isoformat(timespec='seconds')); continue
        items = apply_rules(items, out, now, max_open, max_day)
        bars = {LABEL: fr.get('f5') if style == 'intraday' else fr.get('h1') if style == 'swing' and fr.get('h1') is not None else fr.get('daily')}
        if style == 'positional' and bars[LABEL] is not None:
            b = bars[LABEL].copy(); b.index = pd.DatetimeIndex(b.index).tz_localize(IST) + pd.Timedelta(hours=15, minutes=30); bars[LABEL] = b      # daily candles, followed at their close
        led = signals.load(ledger_path(out, style)); signals.update(led, SECTION[style], items, states, bars, now, is_open); signals.save(ledger_path(out, style), led, now)
        tracked += sum(1 for s in led['signals'] if s['status'] == 'ACTIVE')
        doc['styles'][style] = dict(setups=items, scanned_at=now.isoformat(timespec='seconds'))
    last = None
    for k in ('f5', 'h1', 'daily'):
        f = fr.get(k)
        if f is not None and len(f): last = float(f.Close.iloc[-1]); break
    n_day, n_open = today_count(out, now)
    doc.update(generated_at=now.isoformat(timespec='seconds'), source=sym, price=last if last is not None else prev.get('price'), market_open=is_open, session=session_name(now) if is_open else 'closed',
               entry_window=entry_window(now), trades_today=n_day, open_now=n_open, max_open=max_open, max_day=max_day, min_score=ms, sessions=os.environ.get('GOLD_SESSIONS', 'all') or 'all')
    sc.write_json(out, 'gold.json', doc)
    sent = alerts(out, os.path.join(state_dir, 'gold_notified.json'), now)
    print(f"gold {now:%Y-%m-%d %H:%M} IST: {', '.join(f'{s} {len(doc['styles'].get(s, {}).get('setups', []))}' for s in styles)} A+ setups, {n_open} open, {n_day} today, {len(sent)} alerts")
    return doc

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='pub/data'); ap.add_argument('--state', default='pub/state'); ap.add_argument('--styles', default=','.join(STYLES))
    a = ap.parse_args(argv); styles = tuple(s for s in a.styles.split(',') if s in STYLES)
    try: run(a.out, a.state, styles); return 0
    except Exception as ex: print(f'gold scan failed: {ex}', file=sys.stderr); return 1

if __name__ == '__main__':
    sys.exit(main())
