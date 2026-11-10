"""Broker fills -> proposed trades (site/js/fills.js), run with node. Run: python test_fills.py"""
import json, shutil, subprocess, sys
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
if not shutil.which('node'): print('node is not installed: skipped'); raise SystemExit(0)
JS = r"""
const F = require('./site/js/fills.js');
const f = (id, sym, side, qty, price, t, extra) => Object.assign({ fill_id: id, symbol: sym, product: 'INTRADAY', side, qty, price, filled_at: '2026-11-11T' + t + '+05:30' }, extra || {});
const out = {};
let p = F.propose([f('a1', 'RELIANCE-EQ', 'BUY', 60, 1300), f('a2', 'RELIANCE-EQ', 'BUY', 40, 1305), f('a3', 'RELIANCE-EQ', 'SELL', 100, 1312, '11:20:00')].map((x, i) => i < 2 ? Object.assign(x, { filled_at: '2026-11-11T09:4' + i + ':00+05:30' }) : x), []);
out.avg = p;
out.short = F.propose([f('s1', 'TCS-EQ', 'SELL', 50, 3900, '10:00:00'), f('s2', 'TCS-EQ', 'BUY', 50, 3880, '10:40:00')], []);
out.open = F.propose([f('d1', 'PBK-EQ', 'BUY', 100, 1070, '15:16:30', { product: 'DELIVERY' })], []);
out.partial = F.propose([f('p1', 'INFY-EQ', 'BUY', 100, 1500, '09:30:00'), f('p2', 'INFY-EQ', 'SELL', 40, 1510, '10:30:00')], []);
out.two = F.propose([f('t1', 'SBIN-EQ', 'BUY', 100, 800, '09:30:00'), f('t2', 'SBIN-EQ', 'SELL', 100, 805, '10:00:00'), f('t3', 'SBIN-EQ', 'BUY', 100, 802, '11:00:00'), f('t4', 'SBIN-EQ', 'SELL', 100, 797, '12:00:00')], []);
out.flip = F.propose([f('x1', 'ITC-EQ', 'BUY', 100, 400, '09:30:00'), f('x2', 'ITC-EQ', 'SELL', 150, 402, '10:00:00'), f('x3', 'ITC-EQ', 'BUY', 50, 399, '10:30:00')], []);
out.opt = F.propose([f('o1', 'NIFTY10NOV2624400CE', 'BUY', 65, 120.5, '10:05:00', { option_type: 'CE', instrument: 'OPTIDX', lot: 65 }), f('o2', 'NIFTY10NOV2624400CE', 'SELL', 65, 150, '10:50:00', { option_type: 'CE', instrument: 'OPTIDX' })], []);
const mine = [{ id: 'tr1', inst: 'PBK', dir: 'Long', entry: 1070, exit: null, closed: false }];
out.sellHold = F.propose([f('h1', 'PBK-EQ', 'SELL', 100, 1137, '10:15:00', { product: 'DELIVERY' })], mine);
out.orphan = F.propose([f('h2', 'ZZZ-EQ', 'SELL', 10, 100, '10:15:00', { product: 'DELIVERY' })], mine);
out.mixed = F.propose([f('m1', 'A-EQ', 'BUY', 1, 10, '09:30:00'), f('m2', 'B-EQ', 'BUY', 1, 20, '09:31:00')], []);
const sp = F.split(p, [{ note: 'my trade BR:a1 | from Angel One' }, { note: 'unrelated' }]); out.split = { pending: sp.pending.length, done: sp.done.length };
out.split2 = (() => { const s = F.split(p, [{ note: '' }]); return { pending: s.pending.length, done: s.done.length }; })();
out.prefill = F.prefill(p[0]); out.ist = F.ist('2026-11-11T09:45:12+05:30'); out.ist2 = F.ist('2026-11-10T23:50:00Z');
console.log(JSON.stringify(out));
"""
r = subprocess.run(['node', '-e', JS], capture_output=True, text=True, cwd=__import__('os').path.dirname(__import__('os').path.abspath(__file__)))
if r.returncode: print(r.stderr); raise SystemExit(1)
o = json.loads(r.stdout)
a = o['avg'][0]
check('avg: three fills (buy 60 + buy 40, sell 100) become ONE round trip: Long, qty 100, entry = the weighted average 1302 (not two trades)', len(o['avg']) == 1 and a['dir'] == 'Long' and a['qty'] == 100 and a['entry'] == 1302 and a['closed'] and a['exit'] == 1312 and a['cat'] == 'Intraday', json.dumps(a)[:200])
check('avg: the trade is dated by its first fill in IST, exit time by its last', a['d'] == '2026-11-11' and a['tm'] == '09:40' and a['xtm'] == '11:20' and a['inst'] == 'RELIANCE')
s = o['short'][0]; check('short: sell first then buy back is a Short, entry 3900, exit 3880', s['dir'] == 'Short' and s['entry'] == 3900 and s['exit'] == 3880 and s['closed'])
d = o['open'][0]; check('delivery buy with no sale is an open swing trade (no exit)', d['cat'] == 'Swing' and d['dir'] == 'Long' and d['exit'] is None and not d['closed'] and d['inst'] == 'PBK')
pa = o['partial'][0]; check('partly closed position is flagged partial, so it is not imported as if it were finished', pa['partial'] and not pa['closed'] and pa['qty'] == 100 and pa['exit'] is None)
check('two separate round trips in one symbol stay two trades', len(o['two']) == 2 and sorted(t['entry'] for t in o['two']) == [800, 802] and all(t['closed'] for t in o['two']))
fl = sorted(o['flip'], key=lambda t: t['at']); check('flipping from long to short in one fill closes the long and opens a short with the remainder', len(fl) == 2 and fl[0]['dir'] == 'Long' and fl[0]['closed'] and fl[0]['exit'] == 402 and fl[1]['dir'] == 'Short' and fl[1]['qty'] == 50, json.dumps([(t['dir'], t['qty'], t['closed']) for t in fl]))
op = o['opt'][0]; check('options: kept as Options with the full contract name and the lot', op['cat'] == 'Options' and op['inst'] == 'NIFTY10NOV2624400CE' and op['qty'] == 65 and op['entry'] == 120.5 and op['exit'] == 150)
sh = o['sellHold'][0]; check('selling a holding bought earlier closes your open journal trade (one click), at the sale price', sh['kind'] == 'close' and sh['tradeId'] == 'tr1' and sh['exit'] == 1137 and sh['qty'] == 100)
check('selling something not in your journal is an orphan: dismiss only, never a made-up Short', o['orphan'][0]['kind'] == 'orphan')
check('different symbols are never mixed', len(o['mixed']) == 2)
check('split: a trade whose note carries BR:<first fill id> is already imported', o['split'] == {'pending': 0, 'done': 1} and o['split2'] == {'pending': 1, 'done': 0})
pf = o['prefill']; check('prefill: fills the journal form with entry, exit, quantity, category and a BR: marker for matching later', pf['inst'] == 'RELIANCE' and pf['entry'] == 1302 and pf['exit'] == 1312 and pf['qty'] == 100 and pf['cat'] == 'Intraday' and pf['note'].startswith('BR:a1') and pf['tf'] == '5 MINS')
check('time: converted to IST, including across midnight UTC', o['ist'] == {'d': '2026-11-11', 'tm': '09:45'} and o['ist2'] == {'d': '2026-11-11', 'tm': '05:20'})
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED'); raise SystemExit(1 if fails else 0)
