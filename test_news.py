"""News and events tests, no internet needed. Run: python test_news.py"""
import datetime as dt, json, sys
import newsfeed as nf
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
RSS = '''<?xml version="1.0"?><rss><channel>
<item><title>RBI keeps repo rate unchanged, Nifty surges - Economic Times</title><link>https://example.com/a</link><pubDate>Wed, 21 Oct 2026 04:30:00 GMT</pubDate><source url="https://et.com">Economic Times</source></item>
<item><title>Crude oil slides as OPEC output rises - Reuters</title><link>https://example.com/b</link><pubDate>Wed, 21 Oct 2026 03:00:00 GMT</pubDate><source>Reuters</source></item>
<item><title>RBI keeps repo rate unchanged, Nifty surges - Mint</title><link>https://example.com/c</link><pubDate>Wed, 21 Oct 2026 04:31:00 GMT</pubDate><source>Mint</source></item>
<item><title></title><link>https://example.com/empty</link></item></channel></rss>'''
items = nf.parse_rss(RSS)
check('RSS items are parsed, empty titles skipped, source split from the title', len(items) == 3 and items[0]['source'] == 'Economic Times' and not items[0]['title'].endswith('Times'), str(items[0]))
check('publication time is converted to IST', items[0]['published'] == '2026-10-21T10:00+05:30', str(items[0]['published']))
check('topics: RBI and results are recognised', 'RBI' in nf.tag_topics('RBI keeps repo rate unchanged') and 'Results' in nf.tag_topics('Infosys Q2 profit rises') and 'Crude' in nf.tag_topics('Brent crude slips'))
check('impact: RBI or a big move words are high, a routine item is not', nf.impact('RBI keeps repo rate', ['RBI']) == 'high' and nf.impact('Nifty surges to a record', []) == 'high' and nf.impact('Company opens new office', []) == 'normal')
now = dt.datetime(2026, 10, 21, 11, 0, tzinfo=nf.greeks.IST)
news = nf.build_news(now, ['BHEL', 'CUPID'], fetch=lambda url: RSS)
check('headlines are de-duplicated across sources and feeds', len([h for h in news['headlines'] if h['title'].startswith('RBI keeps')]) == 1 and len(news['headlines']) == 2, str(len(news['headlines'])))
check('per-symbol news is attached', set(news['by_symbol']) == {'BHEL', 'CUPID'} and news['ok'])
def boom(url): raise OSError('blocked')
nb = nf.build_news(now, ['BHEL'], fetch=boom); check('every feed failing gives an empty but valid result (no crash)', nb['headlines'] == [] and nb['by_symbol'] == {} and nb['ok'] is False)
cfg = json.load(open('events.json')); ev = nf.upcoming(now, cfg, results={'BHEL': '2026-10-23'}, horizon=24)
titles = [e['title'] for e in ev]
check('weekly expiry on Tue 27 Oct and US Fed on 28 Oct are listed', any(e['date'] == '2026-10-27' and 'weekly expiry' in e['title'] for e in ev) and any(e['date'] == '2026-10-28' and 'Fed' in e['title'] for e in ev), str(titles[:6]))
check('expiry moves to Monday 9 Nov because Tuesday 10 Nov is a holiday', any(e['date'] == '2026-11-09' and 'weekly expiry' in e['title'] for e in ev) and not any(e['date'] == '2026-11-10' and 'expiry' in e['title'] for e in ev))
check('holiday and Muhurat trading appear', any(e['type'] == 'holiday' and e['date'] == '2026-11-10' for e in ev) and any('Muhurat' in e['title'] for e in ev))
check('results date of your setup is flagged high impact', any(e['title'] == 'BHEL: results' and e['impact'] == 'high' and e['days'] == 2 for e in ev))
check('events are sorted by date', [e['date'] for e in ev] == sorted(e['date'] for e in ev))
fl = nf.risk_flags(nf.upcoming(dt.datetime(2026, 10, 27, 10, 0, tzinfo=nf.greeks.IST), cfg, horizon=3)); check('expiry morning flags: no option buys after lunch', any('expiry today' in f for f in fl), str(fl))
fl = nf.risk_flags(nf.upcoming(dt.datetime(2026, 10, 28, 10, 0, tzinfo=nf.greeks.IST), cfg, horizon=3)); check('Fed day flags volatility', any('Fed' in f and 'today' in f for f in fl), str(fl))
fl = nf.risk_flags(nf.upcoming(dt.datetime(2026, 11, 9, 10, 0, tzinfo=nf.greeks.IST), cfg, horizon=3)); check('day before a holiday warns about overnight gaps', any('holiday' in f.lower() and 'tomorrow' in f for f in fl), str(fl))
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
