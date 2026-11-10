#!/usr/bin/env python3
"""Angel One tradebook import (item 21), experimental.

  python tradebook.py [--force]

After the close, reads today's fills from Angel One (SmartAPI getTradeBook), signs in as the scanner user and saves the new fills
into your broker_fills table. Nothing is written into your journal: the app's Journal page shows the fills, groups them into trades
and lets you import each one (adding your stop and grade) or dismiss it.

Limits: the tradebook only covers the current day, it has no brokerage or taxes (the Charges field stays yours to fill), and I could not
confirm whether Angel One lets this endpoint run without a registered static IP. If it refuses, the run says so and alerts your phone."""
import argparse, datetime as dt, hashlib, json, os, sys
IST = dt.timezone(dt.timedelta(hours=5, minutes=30)); PATH = '/rest/secure/angelbroking/order/v1/getTradeBook'

def _f(x, d=0.0):
    try: return float(x)
    except (TypeError, ValueError): return d

def normalise(rows, day, user_id=None):
    """Angel One fills -> broker_fills rows. `day` is the IST date the tradebook belongs to (the API only returns today)."""
    out = []
    for r in rows or []:
        side = str(r.get('transactiontype') or '').upper()
        if side not in ('BUY', 'SELL'): continue
        qty, price = _f(r.get('fillsize') or r.get('tradedquantity')), _f(r.get('fillprice') or r.get('tradeprice'))
        if qty <= 0 or price <= 0: continue
        t = str(r.get('filltime') or '').strip() or '00:00:00'
        if len(t) == 5: t += ':00'
        oid, fid = str(r.get('orderid') or ''), str(r.get('fillid') or '')
        key = f'{oid}-{fid}' if oid and fid else hashlib.sha1(json.dumps(r, sort_keys=True, default=str).encode()).hexdigest()[:20]
        out.append(dict(fill_id=f'ao-{day}-{key}', user_id=user_id, source='angelone', symbol=str(r.get('tradingsymbol') or '').strip(), exchange=r.get('exchange'), product=str(r.get('producttype') or '').upper() or None,
                        instrument=str(r.get('instrumenttype') or '').upper() or None, side=side, qty=qty, price=price, lot=_f(r.get('marketlot')) or None, option_type=(str(r.get('optiontype') or '').upper() or None),
                        strike=_f(r.get('strikeprice')) or None, expiry=r.get('expirydate') or None, filled_at=f'{day}T{t}+05:30', raw=r))
    return [x for x in out if x['symbol']]

def fetch(angel):
    data = angel.call(PATH, None, gap=1.1, method='GET')
    return data if isinstance(data, list) else []

def notify_msg(title, body, tags='bar_chart', link=''):
    import notify
    topic = os.environ.get('NTFY_TOPIC', '').strip()
    if not topic and not notify.telegram_ready(): return
    page = os.environ.get('PAGE_URL', '').strip().rstrip('/')
    try: notify.post(os.environ.get('NTFY_URL', 'https://ntfy.sh').rstrip('/'), topic, title, body, tags, (page + link) if page and link else '')
    except Exception as ex: print(f'could not send the message: {ex}', file=sys.stderr)

def run(angel, supa, now=None):
    now = now or dt.datetime.now(IST); day = now.strftime('%Y-%m-%d')
    rows = fetch(angel); supa.login()
    owner = (supa.select('journal_state', 'select=user_id&limit=1') or [{}])[0].get('user_id')
    if not owner: raise RuntimeError('could not find your journal row: has supabase/setup.sql been run, and is the scanner email in it correct?')
    fills = normalise(rows, day, owner); new = supa.insert_ignore('broker_fills', fills, 'fill_id') if fills else []
    return dict(day=day, fills=len(fills), new=len(new))

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--force', action='store_true'); a = ap.parse_args(argv); now = dt.datetime.now(IST)
    import loop
    if not a.force and not loop.trading_day(now.date()): print(f'tradebook: {now.date()} is not a trading day'); return 0
    import datasource; from supa import Supa
    angel, supa = datasource.Angel(), Supa()
    if not angel.configured: print('tradebook: Angel One is not set up (ANGEL_ secrets missing)'); return 0
    if not supa.configured: print('tradebook: the scanner user is not set up (SUPABASE_BOT_EMAIL / SUPABASE_BOT_PASSWORD secrets missing)'); return 0
    try: r = run(angel, supa, now)
    except Exception as ex:
        msg = str(ex); hint = ' Angel One may require a registered static IP for order-book data: tell me and I will look at alternatives.' if 'ip' in msg.lower() else ''
        print(f'tradebook failed: {msg}', file=sys.stderr); notify_msg('Tradebook import failed', msg[:250] + hint, 'warning', '/#/health'); return 1
    print(f"tradebook: {r['fills']} fills from Angel One today, {r['new']} new")
    if r['new']: notify_msg(f"Angel One: {r['new']} new fill{'s' if r['new'] > 1 else ''}", 'Open Journal to import them as trades (add your stop and grade) or dismiss them.', 'bar_chart', '/#/journal')
    return 0

if __name__ == '__main__':
    sys.exit(main())
