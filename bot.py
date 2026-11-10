#!/usr/bin/env python3
"""Two-way Telegram bot (item 18): ask the scanner from your phone.

  /setups          today's swing shortlist and any triggered options or intraday setups
  /why SYMBOL      why a stock is or is not on the swing list (where the scan stopped)
  /size SYMBOL     position size for a listed setup from your capital and risk per trade
  /open            tracked trades that are open, with R and the stop
  /status          is the 5-minute loop alive, when each section last updated, which data source
  /brief  /recap   the morning brief or the day recap, now
  /help

It answers only the chat ids in TELEGRAM_CHAT_ID. The free setup has no server waiting for messages, so the bot reads new messages
whenever a scan runs: every 5 minutes in market hours (the market loop), and with each manual or scheduled scan otherwise.
/size uses the repo variables ACCOUNT_CAPITAL (rupees) and RISK_PCT (default 0.5; A+ setups use RISK_PCT_APLUS, default 0.75).

  python bot.py --dir pub/data --state pub/state/bot.json"""
import argparse, datetime as dt, html, json, math, os, sys, urllib.request

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
HELP = ('Commands:\n/setups: today\'s shortlist\n/why SYMBOL: why a stock is or is not listed\n/size SYMBOL: position size for a listed setup\n/open: open tracked trades\n'
        '/status: is the scanner alive\n/brief: morning brief now\n/recap: day recap now\n\nI read messages when a scan runs: every 5 minutes in market hours.')

def _read(d, name):
    try: return json.load(open(os.path.join(d, name + '.json')))
    except Exception: return {}

def _ago(iso, now):
    try: m = int((now - dt.datetime.fromisoformat(iso).astimezone(IST)).total_seconds() // 60)
    except Exception: return 'unknown'
    return 'just now' if m < 1 else f'{m} min ago' if m < 90 else f'{m // 60} h ago' if m < 48 * 60 else f'{m // 1440} d ago'

def cmd_setups(d):
    import digest
    D = digest.load(d); L = ['Swing shortlist:'] + (['• ' + digest.setup_line(s) for s in digest.shortlist(D['swing'])] or ['• nothing in its zone right now'])
    for key, name in (('options', 'Nifty options'), ('intraday', 'Intraday')):
        trig = [s for s in (D[key] or {}).get('setups', []) if str(s.get('status', '')).upper().startswith('TRIGGER')]
        if trig: L += ['', f'{name} triggered:'] + [f"• {s.get('symbol')} {s.get('label', '')} · {s.get('grade')} {s.get('score')}/10 · entry {s.get('entry')} · stop {s.get('sl')}" for s in trig[:5]]
    return '\n'.join(L)

def cmd_why(d, sym):
    if not sym: return 'Send it like this: /why COFORGE'
    rows = (_read(d, 'explain').get('rows') or {}); r = rows.get(sym.upper())
    if not r: return f'{sym.upper()} is not in the last swing scan (it may not be in the Nifty 500, or the symbol is spelled differently on NSE).'
    stage, kind, text = r[0], r[1], r[2]; extra = f"\nScore {r[3]}/10" if len(r) > 3 and r[3] is not None else ''
    return f"{sym.upper()}: {text}{extra}"

def cmd_size(d, sym, env):
    if not sym: return 'Send it like this: /size PBK'
    it = next((s for s in _read(d, 'swing').get('setups', []) if s.get('symbol') == sym.upper()), None)
    if not it or not it.get('entry') or not it.get('sl'): return f'{sym.upper()} is not a listed swing setup with a plan right now. Try /setups.'
    per = abs(it['entry'] - it['sl']); head = f"{it['symbol']} · {it.get('grade')} {it.get('score')}/10\nEntry {it['entry']:,.2f} · stop {it['sl']:,.2f} · risk per share ₹{per:,.2f} ({100 * per / it['entry']:.1f}%)"
    try: cap = float(env.get('ACCOUNT_CAPITAL', '') or 0)
    except ValueError: cap = 0
    if cap <= 0: return head + '\n\nSet the repo variable ACCOUNT_CAPITAL (rupees) and I will work out the quantity. Formula: quantity = capital x risk % ÷ risk per share.'
    try: rp = float(env.get('RISK_PCT_APLUS', '') or 0.75) if it.get('grade') == 'A+' else float(env.get('RISK_PCT', '') or 0.5)
    except ValueError: rp = 0.5
    risk = cap * rp / 100; qty = math.floor(risk / per) if per > 0 else 0
    return head + f"\n\nRisk {rp:g}% of ₹{cap:,.0f} = ₹{risk:,.0f}\nQuantity {qty:,} shares (₹{qty * it['entry']:,.0f}, {100 * qty * it['entry'] / cap:.0f}% of capital)\nT1 {it.get('t1'):,.2f} · T2 {it.get('t2'):,.2f}" + ('\nNote: ' + it['notes'] if it.get('notes') else '')

def cmd_open(d):
    import digest
    act = digest.active(digest.load(d)['led'])
    return 'Open tracked trades:\n' + '\n'.join(f"• {s.get('instrument') or s['symbol']} ({k}): {s.get('r_now', 0):+.2f}R · entry {s.get('entry')} · stop {s.get('stop')}" for k, s in act) if act else 'No tracked trade is open.'

def cmd_status(d, now):
    hb = _read(os.path.join(d, 'health'), 'loop'); L = []
    if hb.get('last_tick'): L.append(f"Market loop: {hb.get('state', 'unknown')}, last tick {_ago(hb['last_tick'], now)}, last scan took {hb.get('last_scan_s', '-')}s, publish {hb.get('publish', '-')}")
    else: L.append('Market loop: no heartbeat yet today')
    for key, name in (('swing', 'Swing'), ('options', 'Nifty options'), ('intraday', 'Intraday'), ('market', 'Market')):
        g = _read(d, key).get('generated_at'); L.append(f"{name}: {_ago(g, now) if g else 'no data'}")
    src = next((r['data'] for r in (_read(os.path.join(d, 'health'), n) for n in ('live', 'swing', 'all')) if r.get('data')), None)
    if src: L.append(f"Data: {src.get('primary')}" + ('' if (src.get('angel') or {}).get('ok') or not (src.get('angel') or {}).get('configured') else f" (Angel One not working: {src['angel'].get('error')})"))
    return '\n'.join(L)

def answer(text, d, env, now):
    parts = text.strip().split(); c = parts[0].lower().split('@')[0] if parts else ''; arg = parts[1] if len(parts) > 1 else ''
    if c in ('/start', '/help'): return HELP
    if c == '/setups': return cmd_setups(d)
    if c == '/why': return cmd_why(d, arg)
    if c == '/size': return cmd_size(d, arg, env)
    if c == '/open': return cmd_open(d)
    if c == '/status': return cmd_status(d, now)
    if c in ('/brief', '/recap'):
        import digest
        t, b, _ = (digest.morning_text if c == '/brief' else digest.evening_text)(digest.load(d), now); return t + '\n\n' + b
    return "I did not understand that. " + HELP

def _api(method, payload, env):
    api = env.get('TELEGRAM_API', 'https://api.telegram.org').rstrip('/'); tok = env['TELEGRAM_BOT_TOKEN'].strip().strip('"\'')
    if tok.lower().startswith('bot') and tok[3:4].isdigit(): tok = tok[3:]
    req = urllib.request.Request(f'{api}/bot{tok}/{method}', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    return json.loads(urllib.request.urlopen(req, timeout=25).read() or b'{}')

def poll(d, state_path, env=None, now=None):
    """Read new messages, answer the ones from your chat ids, remember where we got to. Returns how many were answered."""
    env = env if env is not None else os.environ; now = now or dt.datetime.now(IST)
    if not (env.get('TELEGRAM_BOT_TOKEN', '').strip() and env.get('TELEGRAM_CHAT_ID', '').strip()): return 0
    allowed = {c.strip() for c in env['TELEGRAM_CHAT_ID'].split(',') if c.strip()}
    try: st = json.load(open(state_path))
    except Exception: st = {}
    res = _api('getUpdates', dict(offset=int(st.get('offset', 0)), timeout=0, allowed_updates=['message']), env).get('result', []); n = 0
    for u in res:
        st['offset'] = max(int(st.get('offset', 0)), int(u.get('update_id', 0)) + 1); m = u.get('message') or {}; chat = str((m.get('chat') or {}).get('id', '')); text = m.get('text') or ''
        if chat not in allowed or not text.startswith('/'): continue
        if now.timestamp() - float(m.get('date', now.timestamp())) > 6 * 3600: continue           # a question from yesterday is no longer worth answering
        try: reply = answer(text, d, env, now)
        except Exception as ex: reply = f'Something went wrong answering that: {ex}'
        try: _api('sendMessage', dict(chat_id=chat, text=html.escape(reply)[:4000], parse_mode='HTML', disable_web_page_preview=True), env); n += 1
        except Exception as ex: print(f'  bot reply failed: {ex}', file=sys.stderr)
    os.makedirs(os.path.dirname(state_path) or '.', exist_ok=True); json.dump(st, open(state_path, 'w'))
    return n

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='pub/data'); ap.add_argument('--state', default='pub/state/bot.json'); a = ap.parse_args(argv)
    try: print(f'bot: answered {poll(a.dir, a.state)} message(s)')
    except Exception as ex: print(f'bot: could not read messages ({ex})', file=sys.stderr)
    return 0

if __name__ == '__main__':
    sys.exit(main())
