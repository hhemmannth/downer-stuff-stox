"""Open-interest analysis for the Nifty option chain.

Auto mode asks NSE for the chain. NSE often blocks cloud servers, so this is best effort: when it fails the page
shows an 'OI unavailable' note and lets you type the call wall, put wall and PCR yourself. Nothing breaks either way."""
import http.cookiejar
import json
import urllib.request

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'

def fetch_nse_chain(symbol='NIFTY', timeout=20, opener=None):
    """Return the raw option-chain JSON from NSE, or raise."""
    if opener is None:
        jar = http.cookiejar.CookieJar(); opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    hdr = {'User-Agent': UA, 'Accept': 'application/json,text/plain,*/*', 'Accept-Language': 'en-US,en;q=0.9', 'Referer': 'https://www.nseindia.com/option-chain'}
    try: opener.open(urllib.request.Request('https://www.nseindia.com/option-chain', headers=hdr), timeout=timeout).read()
    except Exception: pass                                            # only needed to collect cookies
    raw = opener.open(urllib.request.Request(f'https://www.nseindia.com/api/option-chain-indices?symbol={symbol}', headers=hdr), timeout=timeout).read()
    js = json.loads(raw.decode('utf-8'))
    if not js.get('records', {}).get('data'): raise ValueError('empty option chain')
    return js

def analyse_chain(js, expiry=None, near=1500):
    """Summarise one expiry: walls, PCR, build-up and max pain. near = how far from spot (points) to look for walls."""
    rec = js['records']; spot = rec.get('underlyingValue'); expiry = expiry or rec['expiryDates'][0]
    rows = [d for d in rec['data'] if d.get('expiryDate') == expiry]
    if not rows: raise ValueError('expiry not in chain')
    ce = {d['strikePrice']: d['CE'] for d in rows if 'CE' in d}; pe = {d['strikePrice']: d['PE'] for d in rows if 'PE' in d}
    strikes = sorted(set(ce) | set(pe)); near_s = [k for k in strikes if spot is None or abs(k - spot) <= near] or strikes
    oi = lambda side, k: (side.get(k) or {}).get('openInterest', 0) or 0
    chg = lambda side, k: (side.get(k) or {}).get('changeinOpenInterest', 0) or 0
    call_wall = max(near_s, key=lambda k: oi(ce, k)); put_wall = max(near_s, key=lambda k: oi(pe, k))
    tot_c = sum(oi(ce, k) for k in strikes); tot_p = sum(oi(pe, k) for k in strikes)
    pain = {k: sum(max(k - s, 0) * oi(ce, s) + max(s - k, 0) * oi(pe, s) for s in strikes) for k in near_s}
    top = lambda side: [dict(strike=k, oi=oi(side, k), change=chg(side, k)) for k in sorted(near_s, key=lambda k: -oi(side, k))[:3]]
    return dict(source='NSE', expiry=expiry, spot=spot, timestamp=rec.get('timestamp'), call_wall=call_wall, put_wall=put_wall, call_wall_oi=oi(ce, call_wall), put_wall_oi=oi(pe, put_wall),
                pcr=round(tot_p / tot_c, 2) if tot_c else None, max_pain=min(pain, key=pain.get), top_calls=top(ce), top_puts=top(pe),
                call_buildup=max(near_s, key=lambda k: chg(ce, k)), put_buildup=max(near_s, key=lambda k: chg(pe, k)))

def alignment(side, entry, sl, t1, oi):
    """Does open interest agree with the trade? side 'long' = CALL, 'short' = PUT. All levels are index points.
    CALL: a put wall at or below price is support, and the call wall should sit beyond the first target.
    PUT : a call wall at or above price is resistance, and the put wall should sit beyond the first target."""
    if not oi or oi.get('call_wall') is None or oi.get('put_wall') is None:
        return dict(aligned=False, verdict='unknown', notes=['OI not available: check the option chain yourself.'])
    cw, pw, pcr = oi['call_wall'], oi['put_wall'], oi.get('pcr'); notes = []; good = 0; bad = 0
    if side == 'long':
        if pw <= entry: good += 1; notes.append(f'Put wall {pw:,.0f} is below price: writers defend that level, so it acts as support.')
        else: bad += 1; notes.append(f'Put wall {pw:,.0f} is above price: support is thin below you.')
        if cw >= t1: good += 1; notes.append(f'Call wall {cw:,.0f} sits at or beyond T1 {t1:,.0f}: the first target is not capped.')
        elif cw > entry: bad += 1; notes.append(f'Call wall {cw:,.0f} sits before T1 {t1:,.0f}: expect resistance and take profit there.')
        if pcr is not None and pcr >= 1.1: good += 1; notes.append(f'PCR {pcr:.2f} leans bullish (more put OI than call OI).')
        elif pcr is not None and pcr <= 0.8: bad += 1; notes.append(f'PCR {pcr:.2f} leans bearish.')
    else:
        if cw >= entry: good += 1; notes.append(f'Call wall {cw:,.0f} is above price: writers defend it, so it acts as resistance.')
        else: bad += 1; notes.append(f'Call wall {cw:,.0f} is below price: resistance is thin above you.')
        if pw <= t1: good += 1; notes.append(f'Put wall {pw:,.0f} sits at or beyond T1 {t1:,.0f}: the first target is not capped.')
        elif pw < entry: bad += 1; notes.append(f'Put wall {pw:,.0f} sits before T1 {t1:,.0f}: expect support there and take profit.')
        if pcr is not None and pcr <= 0.9: good += 1; notes.append(f'PCR {pcr:.2f} leans bearish (more call OI than put OI).')
        elif pcr is not None and pcr >= 1.2: bad += 1; notes.append(f'PCR {pcr:.2f} leans bullish.')
    verdict = 'supports' if good >= 2 and bad == 0 else 'against' if bad >= 2 or (bad > good) else 'mixed'
    return dict(aligned=verdict == 'supports', verdict=verdict, notes=notes)
