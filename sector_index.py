"""Sector-index confirmation for swing longs: if the whole index a stock belongs to is falling, the stock cannot sustain.

Each stock is mapped to its NSE index (Bank Nifty, Nifty IT, Auto, Pharma, FMCG, Metal, Realty, Energy, Media, PSU Bank, Financial Services, Infra)
from the Nifty 500 industry column, with a list of banks for the bank indices. Industries with no index of their own, or an index Yahoo does not
return, fall back to an equal-weight basket of the Nifty 500 stocks in the same industry, built from the data the scan already has."""
import re
import numpy as np
import pandas as pd

OFFICIAL = {'bank': ('NIFTY BANK', '^NSEBANK'), 'psubank': ('NIFTY PSU BANK', '^CNXPSUBANK'), 'fin': ('NIFTY FIN SERVICE', '^CNXFIN'), 'it': ('NIFTY IT', '^CNXIT'), 'auto': ('NIFTY AUTO', '^CNXAUTO'),
            'pharma': ('NIFTY PHARMA', '^CNXPHARMA'), 'fmcg': ('NIFTY FMCG', '^CNXFMCG'), 'metal': ('NIFTY METAL', '^CNXMETAL'), 'realty': ('NIFTY REALTY', '^CNXREALTY'),
            'energy': ('NIFTY ENERGY', '^CNXENERGY'), 'media': ('NIFTY MEDIA', '^CNXMEDIA'), 'infra': ('NIFTY INFRA', '^CNXINFRA'), 'nifty': ('NIFTY 50', '^NSEI')}
PSU_BANKS = {'SBIN', 'BANKBARODA', 'PNB', 'CANBK', 'UNIONBANK', 'INDIANB', 'BANKINDIA', 'IOB', 'UCOBANK', 'CENTRALBK', 'MAHABANK', 'PSB'}
BANKS = {'HDFCBANK', 'ICICIBANK', 'AXISBANK', 'KOTAKBANK', 'INDUSINDBK', 'FEDERALBNK', 'IDFCFIRSTB', 'AUBANK', 'BANDHANBNK', 'YESBANK', 'RBLBANK', 'IDBI', 'CUB', 'KARURVYSYA', 'DCBBANK', 'TMB',
         'SOUTHBANK', 'JKBANK', 'CSBBANK', 'UJJIVANSFB', 'EQUITASBNK', 'ESAFSFB', 'CAPITALSFB', 'SURYODAY', 'UTKARSHBNK', 'DHANBANK', 'KTKBANK', 'NAINITAL'}
RULES = [(r'information tech', 'it'), (r'automobile|auto comp', 'auto'), (r'fast moving|fmcg', 'fmcg'), (r'health|pharma', 'pharma'), (r'metal|mining', 'metal'), (r'realty|real estate', 'realty'),
         (r'oil|gas|fuel|power|energy', 'energy'), (r'media', 'media'), (r'^construction$|infrastructure', 'infra'), (r'financial', 'fin')]

def index_for(symbol, industry=None):
    """Return dict(name, ticker, source, industry). ticker None means an equal-weight industry basket."""
    s = str(symbol).upper().replace('.NS', '')
    key = 'psubank' if s in PSU_BANKS else 'bank' if s in BANKS else None
    if key is None and industry:
        low = industry.lower()
        for rx, k in RULES:
            if re.search(rx, low): key = k; break
    if key: name, tk = OFFICIAL[key]; return dict(name=name, ticker=tk, source='official', industry=industry)
    if industry: return dict(name=f'{industry} basket', ticker=None, source='basket', industry=industry)
    name, tk = OFFICIAL['nifty']; return dict(name=name, ticker=tk, source='official', industry=None)

def basket(frames, symbols, n=120):
    """Equal-weight index of the stocks: every close divided by its first close in the window, then averaged."""
    cols = []
    for s in symbols:
        f = frames.get(s)
        if f is not None and len(f) >= 60:
            c = f.Close.tail(n); cols.append(c / c.iloc[0])
    return pd.concat(cols, axis=1).mean(axis=1).dropna() if len(cols) >= 3 else None

def today_pct(h1, daily, now):
    """How far the index is from the previous close right now, from its latest closed 1H candle."""
    if h1 is None or not len(h1) or daily is None or not len(daily): return None
    last = h1.index[-1]
    if last.date() != now.date(): return None
    prev = daily[[d.date() < now.date() for d in daily.index]]
    return float(100 * (h1.Close.iloc[-1] / prev.Close.iloc[-1] - 1)) if len(prev) else None

def evaluate(close, today=None):
    """Falling = closed more than half an ATR under its 21 EMA, or under both the 9 EMA and a falling 21 EMA, or down 3% in 5 days, or down 1% today."""
    c = close.dropna()
    if len(c) < 30: return dict(state='unknown', reasons=['not enough index data'])
    e9, e21 = c.ewm(span=9, adjust=False).mean(), c.ewm(span=21, adjust=False).mean(); atr = float(c.diff().abs().rolling(14).mean().iloc[-1]); last = float(c.iloc[-1])
    ret5 = float(100 * (last / c.iloc[-6] - 1)); slope = float(e21.iloc[-1] - e21.iloc[-4]); reasons = []
    if last < e21.iloc[-1] - 0.5 * atr: reasons.append('closed more than half an ATR below its 21 EMA')
    if last < e9.iloc[-1] and slope < 0: reasons.append('below its 9 EMA while the 21 EMA is falling')
    if ret5 <= -3.0: reasons.append(f'down {abs(ret5):.1f}% in 5 days')
    if today is not None and today <= -1.0: reasons.append(f'down {abs(today):.1f}% today')
    state = 'falling' if reasons else 'strong' if (last > e21.iloc[-1] and e9.iloc[-1] > e21.iloc[-1] and slope > 0) else 'ok'
    if not reasons: reasons = ['above its 21 EMA with a rising 9 EMA' if state == 'strong' else 'holding its 21 EMA, no breakdown']
    return dict(state=state, reasons=reasons, ema9=round(float(e9.iloc[-1]), 2), ema21=round(float(e21.iloc[-1]), 2), close=round(last, 2), ret5=round(ret5, 2), today=None if today is None else round(today, 2))

def confirm(symbols, daily, industries, fetch_daily, fetch_hourly, now):
    """symbols: stocks with a setup. fetch_daily/fetch_hourly: callables(list of tickers) -> {ticker: frame}. Returns {symbol: check dict}."""
    plan = {s: index_for(s, industries.get(s)) for s in symbols}; tickers = sorted({p['ticker'] for p in plan.values() if p['ticker']})
    d_idx = fetch_daily(tickers) if tickers else {}; h_idx = fetch_hourly(tickers) if tickers else {}; done = {}; out = {}
    for s, p in plan.items():
        key = p['ticker'] or p['name']
        if key not in done:
            close, source, name, today = None, p['source'], p['name'], None
            if p['ticker'] and p['ticker'] in d_idx and len(d_idx[p['ticker']]) >= 30: close = d_idx[p['ticker']].Close; today = today_pct(h_idx.get(p['ticker']), d_idx[p['ticker']], now)
            elif p['industry']:
                members = [x for x, i in industries.items() if i == p['industry']]; close = basket(daily, members); source = 'basket'; name = f"{p['industry']} basket (equal-weight, {len(members)} stocks)"
            ev = evaluate(close, today) if close is not None else dict(state='unknown', reasons=['index data unavailable'])
            done[key] = dict(sector_index=name, source=source, **ev)
        out[s] = done[key]
    return out
