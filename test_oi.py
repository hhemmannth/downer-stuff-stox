"""OI tests with a made-up NSE chain. Run: python test_oi.py"""
import sys
import oi
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
def chain(spot=22700):
    data = []
    for k in range(22000, 23500, 50):
        ce = 1000 + (200000 if k == 22900 else 0) + (50000 if k == 22800 else 0) + max(0, 22800 - k) * -0 ; pe = 1000 + (260000 if k == 22500 else 0) + (60000 if k == 22600 else 0)
        data.append(dict(strikePrice=k, expiryDate='27-Oct-2026', CE=dict(openInterest=ce, changeinOpenInterest=(90000 if k == 22800 else 100)), PE=dict(openInterest=pe, changeinOpenInterest=(80000 if k == 22600 else 100))))
    data.append(dict(strikePrice=22700, expiryDate='03-Nov-2026', CE=dict(openInterest=5, changeinOpenInterest=0), PE=dict(openInterest=5, changeinOpenInterest=0)))
    return dict(records=dict(underlyingValue=spot, timestamp='21-Oct-2026 11:00:00', expiryDates=['27-Oct-2026', '03-Nov-2026'], data=data))
a = oi.analyse_chain(chain())
check('walls: biggest call OI 22,900 and biggest put OI 22,500', a['call_wall'] == 22900 and a['put_wall'] == 22500, f"{a['call_wall']} {a['put_wall']}")
check('nearest expiry is used and the other expiry is ignored', a['expiry'] == '27-Oct-2026' and a['spot'] == 22700)
check('PCR is total put OI over total call OI', a['pcr'] is not None and a['pcr'] > 1.0, str(a['pcr']))
check('build-up strikes use the change in OI', a['call_buildup'] == 22800 and a['put_buildup'] == 22600)
check('top three walls are listed biggest first', a['top_calls'][0]['strike'] == 22900 and a['top_puts'][0]['strike'] == 22500 and len(a['top_calls']) == 3)
check('max pain is a strike between the walls', 22500 <= a['max_pain'] <= 22900, str(a['max_pain']))
w = oi.alignment('long', 22700, 22660, 22780, dict(call_wall=22900, put_wall=22600, pcr=1.2))
check('CALL with put wall below, call wall beyond T1 and bullish PCR: supports', w['verdict'] == 'supports' and w['aligned'], str(w['notes']))
w = oi.alignment('long', 22700, 22660, 22780, dict(call_wall=22740, put_wall=22600, pcr=1.0))
check('CALL with the call wall before T1: not supportive', not w['aligned'] and any('before T1' in n for n in w['notes']))
w = oi.alignment('short', 22700, 22740, 22620, dict(call_wall=22800, put_wall=22500, pcr=0.8))
check('PUT with call wall above, put wall beyond T1 and bearish PCR: supports', w['verdict'] == 'supports', str(w['notes']))
w = oi.alignment('short', 22700, 22740, 22620, dict(call_wall=22650, put_wall=22660, pcr=1.3))
check('PUT against the walls: against', w['verdict'] == 'against', w['verdict'])
check('no OI data: unknown, no crash, tells you to check manually', oi.alignment('long', 1, 1, 2, None)['verdict'] == 'unknown' and 'check' in oi.alignment('long', 1, 1, 2, {})['notes'][0].lower())
class Boom:
    def open(self, *a, **k): raise OSError('blocked')
try: oi.fetch_nse_chain(opener=Boom()); ok = False
except Exception: ok = True
check('a blocked NSE request raises (the caller falls back to manual OI)', ok)
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}'); sys.exit(1 if fails else 0)
