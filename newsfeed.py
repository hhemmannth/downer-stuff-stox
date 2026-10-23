"""News headlines and the events calendar for the News page. Standard library only.
Headlines come from Google News RSS (India edition) because it is open and stable; each failed feed is skipped, never fatal."""
import datetime as dt
import email.utils
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import greeks

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
MARKET_QUERIES = [('Market', 'Nifty OR Sensex OR "Indian stock market"', 1), ('RBI and rates', 'RBI OR "repo rate" OR "bond yield" India', 2), ('FII / DII', 'FII OR FPI OR DII flows India equities', 2),
                  ('Global', '"Wall Street" OR "US Fed" OR "crude oil" OR "Brent" markets', 1), ('Rupee', 'rupee dollar exchange rate India', 2)]
TOPICS = {'RBI': r'\brbi\b|repo rate|monetary policy|\bmpc\b|bond yield|liquidity', 'Fed / Global': r'\bfed\b|fomc|powell|warsh|wall street|treasury yield|dollar index|nasdaq|dow jones|china',
          'Crude': r'crude|brent|opec|oil price', 'Flows': r'\bfii\b|\bfpi\b|\bdii\b|foreign investors|institutional', 'Results': r'results|earnings|q[1-4]\b|profit|net loss|board meeting|dividend',
          'Policy': r'budget|\bgst\b|\bsebi\b|tax|tariff|policy|regulat', 'Rupee': r'rupee|forex', 'Sector': r'bank|\bit\b|pharma|auto|realty|metal|fmcg|energy|power|infra'}
HIGH_WORDS = r'crash|plunge|surge|rally|record|slump|tumble|soar|rate hike|rate cut|ban|probe|fraud|downgrade|upgrade|default|war|ceasefire|tariff'

def fetch_url(url, timeout=15):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/rss+xml,application/xml,text/xml,*/*'}), timeout=timeout).read().decode('utf-8', 'replace')

def gnews_url(query, days=1):
    return 'https://news.google.com/rss/search?q=' + urllib.parse.quote(f'{query} when:{days}d') + '&hl=en-IN&gl=IN&ceid=IN:en'

def parse_rss(xml_text, limit=40):
    items = []; root = ET.fromstring(xml_text)
    for it in root.iter('item'):
        title = (it.findtext('title') or '').strip(); link = (it.findtext('link') or '').strip()
        if not title or not link: continue
        src = (it.findtext('source') or '').strip()
        if not src and ' - ' in title: title, src = title.rsplit(' - ', 1)
        elif src and title.endswith(' - ' + src): title = title[:-len(src) - 3]
        pub = it.findtext('pubDate')
        try: when = email.utils.parsedate_to_datetime(pub).astimezone(greeks.IST).isoformat(timespec='minutes') if pub else None
        except Exception: when = None
        items.append(dict(title=title.strip(), link=link, source=src.strip(), published=when))
        if len(items) >= limit: break
    return items

def tag_topics(title):
    t = title.lower(); return [k for k, rx in TOPICS.items() if re.search(rx, t)]

def impact(title, topics):
    return 'high' if re.search(HIGH_WORDS, title.lower()) or {'RBI', 'Fed / Global'} & set(topics) else 'normal'

def _norm(t): return re.sub(r'[^a-z0-9]+', ' ', t.lower()).strip()

def _collect(queries, fetch, per_feed=15):
    out, seen = [], set()
    for label, q, days in queries:
        try: items = parse_rss(fetch(gnews_url(q, days)), per_feed)
        except Exception: continue
        for it in items:
            key = _norm(it['title'])[:80]
            if key in seen: continue
            seen.add(key); tp = tag_topics(it['title']); it.update(group=label, topics=tp, impact=impact(it['title'], tp)); out.append(it)
    out.sort(key=lambda x: x.get('published') or '', reverse=True); return out

def build_news(now, symbols, fetch=None, max_headlines=60):
    """Market headlines plus the latest items for each symbol that currently has a setup."""
    fetch = fetch or fetch_url; heads = _collect(MARKET_QUERIES, fetch)[:max_headlines]; by = {}
    for s in symbols[:15]:
        items = _collect([(s, f'{s} NSE share OR stock', 7)], fetch, per_feed=8)[:5]
        if items: by[s] = items
    return dict(generated_at=now.isoformat(timespec='seconds'), headlines=heads, by_symbol=by, feeds=len(MARKET_QUERIES) + len(symbols[:15]), ok=bool(heads or by))

def load_events(path='events.json'):
    try: return json.load(open(path, encoding='utf-8'))
    except Exception: return dict(holidays=[], events=[])

def _last_tuesday(y, m, hol):
    d = dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)
    while d.weekday() != 1: d -= dt.timedelta(days=1)
    while d.weekday() >= 5 or d in hol: d -= dt.timedelta(days=1)
    return d

def upcoming(now, cfg, results=None, horizon=24):
    """Everything in the next `horizon` days: expiries, holidays, macro events and results dates of your setups."""
    today = now.date(); end = today + dt.timedelta(days=horizon); hol = {dt.date.fromisoformat(h['date']): h['name'] for h in cfg.get('holidays', [])}; ev = []
    add = lambda d, title, typ, imp, note='', time='': ev.append(dict(date=d.isoformat(), time=time, title=title, type=typ, impact=imp, note=note, days=(d - today).days)) if today <= d <= end else None
    d = today
    while d <= end:
        if d.weekday() < 5 and d in hol: add(d, f'NSE holiday: {hol[d]}', 'holiday', 'high', 'Markets closed. Do not carry leveraged positions into a long weekend without a reason.')
        d += dt.timedelta(days=1)
    seen = set(); e = greeks.weekly_expiry(now, list(hol))
    while e <= end:
        if e not in seen:
            seen.add(e); mon = _last_tuesday(e.year, e.month, set(hol)); add(e, 'Nifty weekly expiry' + (' (also monthly expiry)' if e == mon else ''), 'expiry', 'high' if (e - today).days <= 1 else 'medium',
                                                              'Skip new option buys after lunch. Gamma and theta are extreme on expiry day.' if (e - today).days == 0 else '')
        e = greeks.weekly_expiry(dt.datetime.combine(e + dt.timedelta(days=1), dt.time(9, 0), tzinfo=greeks.IST), list(hol))
    for x in cfg.get('events', []):
        try: add(dt.date.fromisoformat(x['date']), x['title'], x.get('type', 'event'), x.get('impact', 'medium'), x.get('note', ''), x.get('time', ''))
        except Exception: continue
    for sym, d in (results or {}).items():
        try: add(dt.date.fromisoformat(d), f'{sym}: results', 'results', 'high', 'You have a setup in this stock. Exit or cut size before the announcement (your no-event-risk rule).')
        except Exception: continue
    ev.sort(key=lambda x: (x['date'], x['time'] or '')); return ev

def risk_flags(events):
    out = []
    for x in events:
        if x['days'] == 0 and x['type'] == 'expiry': out.append('Nifty weekly expiry today: no option buys after lunch, size down.')
        elif x['days'] == 0 and x['type'] == 'results': out.append(x['title'] + ' today.')
        elif x['days'] <= 1 and x['type'] == 'holiday': out.append(x['title'] + ('. Closed tomorrow: avoid overnight gap risk in leveraged positions.' if x['days'] == 1 else '. Closed today.'))
        elif x['days'] <= 1 and x['impact'] == 'high' and x['type'] in ('global', 'india'): out.append(f"{x['title']} {'today' if x['days'] == 0 else 'tomorrow'}" + (f" ({x['time']} IST)" if x['time'] else '') + ': expect volatility, prefer smaller size.')
        elif x['days'] <= 2 and x['type'] == 'results': out.append(x['title'] + f" in {x['days']} day(s): review your open trade.")
    return out
