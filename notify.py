#!/usr/bin/env python3
"""DownerStuffScreener phone notifications through ntfy (https://ntfy.sh) for the three sections.

Two kinds of push:
  1. ALERT   a setup reached TRIGGER (score >= NTFY_MIN_SCORE). Once per setup per day.
  2. UPDATE  a section finished a fresh scan. Once per scan. Say what changed in one line.

Env vars:
  NTFY_TOPIC       required. A long random topic name. Anyone who knows it can read the pushes.
  NTFY_MIN_SCORE   default 6 (grade A and above)
  NTFY_STATUSES    default TRIGGER (matches TRIGGERED and TRIGGER (check volume)). Add WATCH to get those too.
  NTFY_EVENTS      default on. Push trade-lifecycle events (T1/T2/T3 hit, stop or trailing stop hit, expiry) for triggered signals.
  NTFY_UPDATES     default swing.  swing = only the hourly swing scans, all = every fresh scan (about 150 pushes a day at a 5-minute rhythm), off = none.
  PAGE_URL         optional, opens when you tap the push
  NTFY_URL         default https://ntfy.sh
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID   optional: the same pushes as Telegram messages with an "Open" button.
                   TELEGRAM_CHAT_ID can hold several ids separated by commas. Either channel alone is enough.
No Priority header is sent: some iOS installs of the ntfy app do not show pushes that carry one."""
import argparse, datetime, html, json, os, sys, urllib.error, urllib.request

SECTIONS = [('swing', 'Swing'), ('options', 'Nifty options'), ('intraday', 'Intraday')]
FRESH_MINUTES = 20

def ist_now(): return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
def fmt(v): return '-' if v is None else f'{v + 1e-9:,.1f}'

EMOJI = {'star': '⭐', 'chart_with_upwards_trend': '📈', 'chart_with_downwards_trend': '📉', 'white_check_mark': '✅', 'trophy': '🏆', 'x': '❌', 'lock': '🔒',
         'hourglass': '⏳', 'arrows_counterclockwise': '🔄', 'rotating_light': '🚨', 'bell': '🔔'}

def telegram_ready(): return bool(os.environ.get('TELEGRAM_BOT_TOKEN', '').strip() and os.environ.get('TELEGRAM_CHAT_ID', '').strip())

TELEGRAM_HINTS = {404: 'bot token is wrong (check TELEGRAM_BOT_TOKEN: only the token from @BotFather, like 123456789:AAH..., no "bot" in front, no quotes or spaces)',
                  400: 'chat not found (check TELEGRAM_CHAT_ID, and send your bot a message first)', 401: 'bot token was revoked: get a new one from @BotFather',
                  403: 'the bot cannot message this chat (you blocked it, or it is not in the group)'}

def telegram(title, body, tags, click):
    """One Telegram message per chat id: bold title, the body, and an Open button that goes straight to the trade."""
    token = os.environ['TELEGRAM_BOT_TOKEN'].strip().strip('"\'').strip()
    if token.lower().startswith('bot') and token[3:4].isdigit(): token = token[3:]          # pasted with the "bot" from the URL in front
    api = os.environ.get('TELEGRAM_API', 'https://api.telegram.org').rstrip('/')
    icon = ''.join(EMOJI.get(t, '') for t in str(tags).split(','))
    text = (f'{icon} ' if icon else '') + f'<b>{html.escape(title)}</b>\n{html.escape(body)}'
    msg = dict(text=text[:4000], parse_mode='HTML', disable_web_page_preview=True)
    if click and click.startswith('https://'): msg['reply_markup'] = {'inline_keyboard': [[{'text': 'Open in DownerStuff', 'url': click}]]}
    for chat in [c.strip() for c in os.environ['TELEGRAM_CHAT_ID'].split(',') if c.strip()]:
        req = urllib.request.Request(f'{api}/bot{token}/sendMessage', data=json.dumps(dict(msg, chat_id=chat)).encode(), headers={'Content-Type': 'application/json'}, method='POST')
        try: urllib.request.urlopen(req, timeout=20).read()
        except urllib.error.HTTPError as ex: raise RuntimeError(f'HTTP {ex.code}: ' + TELEGRAM_HINTS.get(ex.code, ex.reason)) from None

def post(base, topic, title, body, tags, click):
    """Send to every configured channel (ntfy and/or Telegram). Fails only if every channel failed."""
    ok, errs = 0, []
    if topic:
        headers = {'Title': title.encode('ascii', 'ignore').decode(), 'Tags': tags}
        if click: headers['Click'] = click
        try: urllib.request.urlopen(urllib.request.Request(f'{base}/{topic}', data=body.encode('utf-8'), headers=headers, method='POST'), timeout=20).read(); ok += 1
        except Exception as ex: errs.append(f'ntfy: {ex}')
    if telegram_ready():
        try: telegram(title, body, tags, click); ok += 1
        except Exception as ex: errs.append(f'telegram: {ex}')
    if not ok: raise RuntimeError('; '.join(errs) or 'no channel configured')
    if errs: print('  ' + '; '.join(errs), file=sys.stderr)
    return [c for c, on in (('ntfy', bool(topic)), ('Telegram', telegram_ready())) if on and not any(e.startswith(c.lower()) for e in errs)]

from urllib.parse import quote
def deep(click, **q):
    """A link that opens the exact trade inside the app (one-page app: index.html#/trade?...)."""
    if not click: return click
    return click.rstrip('/') + '/#/trade?' + '&'.join(f'{k}={quote(str(v), safe="")}' for k, v in q.items())

def alert_body(s):
    return '\n'.join([f"Zone {fmt(s['zone_bot'])}-{fmt(s['zone_top'])}   Entry {fmt(s['entry'])}   SL {fmt(s['sl'])}", f"T1 {fmt(s['t1'])} ({fmt(s.get('r_t1'))}R)   T2 {fmt(s['t2'])}   T3 {fmt(s['t3'])}",
                      'Ticks: ' + (', '.join(s['ticks']) or 'none'), ' / '.join(s['notes'][:2]) or 'Check the chart before trading.'])

def send_alert(base, topic, s, section, click):
    what = s.get('label', s['direction'].upper())
    post(base, topic, f"{section}: {s['status'].split(' ')[0]} {s['grade']} {s['symbol']} {what} ({s['score']}/10)", alert_body(s),
         ('star,' if s['grade'] == 'A+' else '') + ('chart_with_upwards_trend' if s['direction'] == 'long' else 'chart_with_downwards_trend'), click)

def fresh(data, now):
    try: t = datetime.datetime.fromisoformat(data['generated_at'])
    except Exception: return False
    return 0 <= (now - t).total_seconds() / 60 <= FRESH_MINUTES

def update_text(key, data):
    t = datetime.datetime.fromisoformat(data['generated_at']).strftime('%H:%M'); st = data.get('setups', [])
    trig = sum(s['status'].startswith('TRIGGER') for s in st); zone = sum(s['status'].startswith('WATCH') for s in st); near = len(st) - trig - zone
    line = f"{t} IST. " + (f"{data['scanned']}/{data['universe']} scanned. " if key != 'options' else '')
    line += f"{len(st)} setups: {trig} triggered, {zone} in zone, {near} near zone." if st else 'No setups right now.'
    if key == 'options' and data.get('snapshot'):
        p = data['snapshot']; line += f" Nifty {fmt(p.get('spot'))}, 15m bias " + ('up.' if p.get('bias_up') else 'down.' if p.get('bias_down') else 'none.')
    if st: b = max(st, key=lambda s: s['score']); line += f" Best: {b['symbol']} {b.get('label', b['direction'].upper())} {b['score']}/10."
    return line

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='_site/data'); ap.add_argument('--state', default='.state/notified.json')
    ap.add_argument('--test', action='store_true', help='send one test push and exit'); a = ap.parse_args()
    topic = os.environ.get('NTFY_TOPIC', '').strip(); click = os.environ.get('PAGE_URL', '').strip(); base = os.environ.get('NTFY_URL', 'https://ntfy.sh').rstrip('/')
    if not topic and not telegram_ready(): print('Neither NTFY_TOPIC nor TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID is set, skipping alerts.'); return 1 if a.test else 0
    if a.test:
        try:
            sent = post(base, topic, 'DownerStuffScreener: test', 'If you see this, pushes work. You will get one when a setup triggers (score 6 or more) and when a scan finishes.', 'white_check_mark', click)
            missed = [c for c, on in (('ntfy', bool(topic)), ('Telegram', telegram_ready())) if on and c not in sent]
            print('test alert sent to ' + ' and '.join(sent) + (f" (FAILED: {', '.join(missed)}: see the error above)" if missed else '')); return 1 if missed else 0
        except Exception as ex: print(f'test alert failed: {ex}', file=sys.stderr); return 1
    min_score = int(os.environ.get('NTFY_MIN_SCORE', '6') or 6); updates = os.environ.get('NTFY_UPDATES', 'swing').strip().lower() or 'swing'
    statuses = tuple(x.strip().upper() for x in os.environ.get('NTFY_STATUSES', 'TRIGGER').split(',') if x.strip()); now = ist_now(); today = now.strftime('%Y-%m-%d')
    try: state = json.load(open(a.state))
    except Exception: state = {}
    if state.get('date') != today: state = {'date': today, 'sent': [], 'updated': {}}
    state.setdefault('updated', {}); sent = ups = 0
    for key, title in SECTIONS:
        try: data = json.load(open(os.path.join(a.dir, key + '.json')))
        except Exception: continue
        for s in data.get('setups', []):
            k = f"{key}|{s['symbol']}|{s['direction']}|{s['bos_date']}|{s['status'].split(' ')[0]}"
            if s['score'] < min_score or not s['status'].upper().startswith(statuses) or k in state['sent']: continue
            try: send_alert(base, topic, s, title, deep(click, s=key, id=f"{s['symbol']}|{s['direction']}")); state['sent'].append(k); sent += 1
            except Exception as ex: print(f"  could not send {s['symbol']}: {ex}", file=sys.stderr)
        if updates == 'off' or (updates == 'swing' and key != 'swing') or state['updated'].get(key) == data.get('generated_at') or not fresh(data, datetime.datetime.now(datetime.timezone.utc)): continue
        try: post(base, topic, f'DownerStuffScreener: {title} scan updated', update_text(key, data), 'arrows_counterclockwise', click); state['updated'][key] = data['generated_at']; ups += 1
        except Exception as ex: print(f'  could not send update for {key}: {ex}', file=sys.stderr)
    evs = 0
    if os.environ.get('NTFY_EVENTS', 'on').strip().lower() != 'off':
        names = dict(SECTIONS); icon = {'t1': 'white_check_mark', 't2': 'white_check_mark', 'target': 'trophy', 'sl': 'x', 'trail': 'lock', 'expired': 'hourglass'}
        for key, title in SECTIONS:
            try: led = json.load(open(os.path.join(a.dir, f'signals_{key}.json')))
            except Exception: continue
            for sig in led.get('signals', []):
                for ev in sig.get('events', []):
                    k = f"ev|{sig['id']}|{ev['kind']}|{ev['t']}"
                    if ev['kind'] == 'trigger' or k in state['sent'] or ev['t'][:10] != today: continue
                    what = sig.get('instrument') or f"{sig['symbol']} {sig.get('label', '')}"
                    try: post(base, topic, f"{title}: {what} {ev['kind'].upper()}", ev['text'], icon.get(ev['kind'], 'bell'), deep(click, s=key, sig=sig['id'])); state['sent'].append(k); evs += 1
                    except Exception as ex: print(f'  could not send event: {ex}', file=sys.stderr)
    os.makedirs(os.path.dirname(a.state) or '.', exist_ok=True); json.dump(state, open(a.state, 'w')); print(f'alerts sent: {sent}, updates sent: {ups}, trade events sent: {evs}'); return 0

if __name__ == '__main__':
    sys.exit(main())
