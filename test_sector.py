"""Sector-index confirmation tests. Run: python test_sector.py"""
import datetime as dt, sys
import numpy as np, pandas as pd
import sector_index as si
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
g = lambda s, i=None: si.index_for(s, i)
check('private banks map to Bank Nifty, PSU banks to PSU Bank', g('HDFCBANK', 'Financial Services')['name'] == 'NIFTY BANK' and g('SBIN', 'Financial Services')['name'] == 'NIFTY PSU BANK')
check('non-bank financials map to Nifty Financial Services', g('BAJFINANCE', 'Financial Services')['name'] == 'NIFTY FIN SERVICE')
check('industries map to their index: IT, auto, pharma, FMCG, metal, realty, energy, media, infra', [g('X', i)['name'] for i in ('Information Technology', 'Automobile and Auto Components', 'Healthcare', 'Fast Moving Consumer Goods', 'Metals & Mining', 'Realty', 'Oil Gas & Consumable Fuels', 'Media Entertainment & Publication', 'Construction')] ==
      ['NIFTY IT', 'NIFTY AUTO', 'NIFTY PHARMA', 'NIFTY FMCG', 'NIFTY METAL', 'NIFTY REALTY', 'NIFTY ENERGY', 'NIFTY MEDIA', 'NIFTY INFRA'])
check('industries with no index of their own use an industry basket', g('X', 'Capital Goods')['ticker'] is None and g('X', 'Construction Materials')['source'] == 'basket' and g('X', 'Chemicals')['name'] == 'Chemicals basket')
check('no industry info at all falls back to Nifty 50', g('X')['ticker'] == '^NSEI')
idx = pd.bdate_range('2026-06-01', periods=120)
up = pd.Series(np.linspace(100, 130, 120), index=idx); dn = pd.Series(np.linspace(130, 100, 120), index=idx); flat = pd.Series(100 + np.sin(np.arange(120) / 3.0), index=idx)
check('rising index is strong', si.evaluate(up)['state'] == 'strong')
e = si.evaluate(dn); check('falling index is falling, with the reasons', e['state'] == 'falling' and len(e['reasons']) >= 2, str(e['reasons']))
check('a sideways index holding its average is ok (not falling)', si.evaluate(flat)['state'] in ('ok', 'strong'), si.evaluate(flat)['state'])
e = si.evaluate(up, today=-1.4); check('a strong index that is down 1.4% today counts as falling', e['state'] == 'falling' and any('today' in r for r in e['reasons']))
check('down 3% in five days counts as falling', si.evaluate(pd.concat([up.iloc[:-5], up.iloc[-5:] * 0.95]))['state'] == 'falling')
check('too little data: unknown, no crash', si.evaluate(up.iloc[:10])['state'] == 'unknown')
fr = {f'S{i}': pd.DataFrame({'Close': np.linspace(100, 100 + 10 * (i + 1), 120)}, index=idx) for i in range(4)}
b = si.basket(fr, list(fr)); check('basket is the equal-weight average of rebased closes', b is not None and abs(b.iloc[0] - 1.0) < 1e-9 and b.iloc[-1] > 1.0)
check('basket needs at least 3 stocks', si.basket(fr, ['S0', 'S1']) is None)
now = pd.Timestamp('2026-10-21 12:30', tz='Asia/Kolkata'); daily = pd.DataFrame({'Close': np.r_[np.linspace(100, 130, 119), 130]}, index=pd.bdate_range(end='2026-10-20', periods=120))
h1 = pd.DataFrame({'Close': [128.0, 127.5]}, index=pd.DatetimeIndex(['2026-10-21 10:15', '2026-10-21 11:15']).tz_localize('Asia/Kolkata'))
check('today move comes from the latest 1H close vs the previous daily close', abs(si.today_pct(h1, daily, now) - (100 * (127.5 / 130 - 1))) < 1e-9 and si.today_pct(h1.iloc[:0], daily, now) is None)
inds = {'AAA': 'Information Technology', 'BBB': 'Information Technology', 'C1': 'Capital Goods', 'C2': 'Capital Goods', 'C3': 'Capital Goods', 'C4': 'Capital Goods'}
dly = {'C1': fr['S0'], 'C2': fr['S1'], 'C3': fr['S2'], 'C4': fr['S3']}
calls = []
res = si.confirm(['AAA', 'BBB', 'C1'], dly, inds, lambda t: (calls.append(('d', t)), {'^CNXIT': dn.to_frame('Close')})[1], lambda t: {}, now)
check('stocks of one industry share one index lookup', calls == [('d', ['^CNXIT'])] and res['AAA'] is res['BBB'])
check('official index data is used when Yahoo returns it', res['AAA']['source'] == 'official' and res['AAA']['sector_index'] == 'NIFTY IT' and res['AAA']['state'] == 'falling')
check('basket is used for an industry with no index', res['C1']['source'] == 'basket' and 'Capital Goods basket' in res['C1']['sector_index'] and res['C1']['state'] in ('ok', 'strong'), str(res['C1']['sector_index']))
res2 = si.confirm(['AAA'], dly, {'AAA': 'Information Technology', 'Z1': 'Information Technology'}, lambda t: {}, lambda t: {}, now)
check('official index missing and no basket possible: unknown, never a crash', res2['AAA']['state'] == 'unknown')
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
