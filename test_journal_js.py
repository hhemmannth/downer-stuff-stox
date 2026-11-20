"""Audit tests (18-19 Nov 2026): the journal's maths in site/js/pnl.js + site/js/journal.js, run in Node with a stub page, against values worked
out by hand. Part 1: per-trade P&L. Part 2 (19 Nov 2026): realized P&L dated by the EXIT, daily/weekly loss limits, partial exits, unknown exit
dates, the schema-2 migration, and the shared engine giving Trade Insight the same answer. Skipped (not failed) when Node is not installed.
Run: python test_journal_js.py"""
import json, os, shutil, subprocess, sys, tempfile
fails = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info else ''))
    if not cond: fails.append(name)
node = shutil.which('node')
if not node: print('SKIP node not installed: journal maths not checked here\nALL PASSED'); sys.exit(0)
HERE = os.path.dirname(os.path.abspath(__file__)); JS = os.path.join(HERE, 'site', 'js')
BOOT = r"""
const fs = require('fs'), vm = require('vm');
const mem = {};
const ctx = { App: { pages: {}, binds: {}, ui: {} }, store: { get: (k, d) => (k in mem ? mem[k] : d), set: (k, v) => { mem[k] = v; } }, todayIST: () => TODAY, pct: x => (100 * x).toFixed(2) + '%', inr: x => 'Rs ' + Math.round(x),
  console, Date, Math, JSON, setTimeout, clearTimeout, document: { addEventListener() {} } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2] + '/pnl.js', 'utf8'), ctx);          // loaded first, exactly as index.html does
vm.runInContext(fs.readFileSync(process.argv[2] + '/journal.js', 'utf8'), ctx);
const JR = ctx.App.journal, PnL = ctx.PnL;
const T = o => Object.assign({ d: '2026-11-18', tm: '10:00', cat: 'Swing', dir: 'Long', qty: null, cap: null, entry: null, sl: null, tgt: null, exit: null, chg: null, ovr: null, xd: '', xtm: '', parts: null }, o);
const use = (trades, cap) => { const J = { id: 'j1', name: 't', schema: 2, set: { ...JR.SET0, capital: cap || 200000 }, trades: trades.map(T) }; JR.E.list = [J]; JR.E.cur = 'j1'; return JR.riskStatus(); };
"""
def run(body, today='2026-11-18'):
    d = tempfile.mkdtemp(); h = os.path.join(d, 'h.js'); open(h, 'w').write(f"const TODAY = '{today}';\n" + BOOT + body)
    p = subprocess.run([node, h, JS], capture_output=True, text=True, timeout=60)
    if p.returncode != 0: return None, p.stderr[-400:]
    return json.loads(p.stdout.strip().splitlines()[-1]), ''

# ---------------------------------------------------------------- part 1: per-trade maths (unchanged expectations; exit dates added)
o, err = run(r"""
const J = { set: { ...JR.SET0, capital: 200000 }, trades: [] };
J.trades = [T({ inst: 'LONGWIN', qty: 100, entry: 500, sl: 480, exit: 540, chg: 120, tgt: 560, xd: '2026-11-18' }), T({ inst: 'SHORTLOSS', dir: 'Short', qty: 50, entry: 200, sl: 210, exit: 212, chg: 30, xd: '2026-11-18' }),
  T({ inst: 'CAPQTY', cap: 10000, entry: 333, sl: 320, exit: 333, xd: '2026-11-18' }), T({ inst: 'OPEN', qty: 10, entry: 100, sl: 95 }), T({ inst: 'OVR', qty: 10, entry: 100, sl: 95, exit: 120, ovr: 150, xd: '2026-11-18' }),
  T({ inst: 'NODATE', d: '', qty: 1, entry: 1, sl: 0.5, exit: 2 }), T({ inst: 'ZERO', qty: 0, entry: 100, sl: 100, exit: 101, xd: '2026-11-18' }), T({ inst: 'SHORTWIN', dir: 'Short', qty: 65, entry: 150, sl: 160, exit: 130, chg: 50, xd: '2026-11-18' })];
JR.E.list = [Object.assign({ id: 'j1', name: 't' }, J)]; JR.E.cur = 'j1';
const S = JR.sizeFor(500, 480, 'A+'), S2 = JR.sizeFor(500, 480, 'A');
console.log(JSON.stringify({ rows: JR.enrich(J).map(t => ({ inst: t.inst, q: t.q, gross: t.gross, net: t.net, risk: t.risk, r: t.r, res: t.res, closed: t.closed, prr: t.prr, didx: t.didx })), size: S, size2: S2 }));
""")
if o is None: check('journal.js and pnl.js load in Node with a stub page', False, err); print(f'\n{len(fails)} FAILED'); sys.exit(1)
R = {x['inst']: x for x in o['rows']}
close = lambda a, b, tol=1e-9: a is not None and abs(a - b) < tol
check('journal.js and pnl.js load in Node with a stub page (pnl.js first, as in index.html)', True)
check('long: gross = (540 - 500) x 100 = 4,000; net = 4,000 - 120 charges = 3,880', R['LONGWIN']['gross'] == 4000 and R['LONGWIN']['net'] == 3880)
check('long: risk = |500 - 480| x 100 = 2,000; R = 3,880 / 2,000 = 1.94 (after charges)', R['LONGWIN']['risk'] == 2000 and close(R['LONGWIN']['r'], 1.94))
check('long: planned reward/risk to the target = (560 - 500) / 20 = 3.0', close(R['LONGWIN']['prr'], 3.0))
check('short loss: gross = (212 - 200) x 50 x -1 = -600; net -630; R = -630 / 500 = -1.26', R['SHORTLOSS']['gross'] == -600 and R['SHORTLOSS']['net'] == -630 and close(R['SHORTLOSS']['r'], -1.26) and R['SHORTLOSS']['res'] == 'Loss')
check('short win (options lot 65): gross = (150 - 130) x 65 = 1,300; net 1,250; R = 1,250 / 650 = 1.923', R['SHORTWIN']['gross'] == 1300 and R['SHORTWIN']['net'] == 1250 and close(R['SHORTWIN']['r'], 1250 / 650))
check('quantity from capital: floor(10,000 / 333) = 30; flat exit = 0 and breakeven', R['CAPQTY']['q'] == 30 and R['CAPQTY']['net'] == 0 and R['CAPQTY']['res'] == 'BE')
check('an open trade has no P&L yet (null, not 0)', R['OPEN']['closed'] is False and R['OPEN']['net'] is None and R['OPEN']['risk'] == 50)
check('a manual net override replaces the computed net: 150, R = 150 / 50 = 3', R['OVR']['net'] == 150 and close(R['OVR']['r'], 3.0))
check('zero quantity and a zero-width stop: no P&L and no R (no division by zero)', R['ZERO']['net'] is None and R['ZERO']['r'] is None)
check('a trade without a valid entry date is left out of the statistics', 'NODATE' not in R)
check('trade number of the day counts every style (your 2-a-day rule)', sorted(x['didx'] for x in o['rows']) == list(range(1, 8)))
check('position size: A+ risks 0.75% of 2,00,000 = 1,500; qty = floor(1,500 / 20) = 75', close(o['size']['risk'], 1500) and o['size']['qty'] == 75)
check('position size: A risks 0.5% = 1,000; qty = 50', close(o['size2']['risk'], 1000) and o['size2']['qty'] == 50)

# ---------------------------------------------------------------- part 2: realized P&L by EXIT date and the loss limits
# Today is Wed 18 Nov 2026 (IST). The NSE week is Mon 16 to Fri 20 Nov. Capital 2,00,000; your limits: day 1% (2,000), week 2% (4,000), month 5%.
pick = "const pick = r => ({ day: r.day, week: r.week, month: r.month, rs: r.realizedRs, use: r.use, level: r.level, msgs: r.msgs.map(m => m[0] + ': ' + m[1]), unknown: r.unknownExit, unreal: r.unrealized });"
o, err = run(pick + r"""
const out = {
  A: pick(use([{ inst: 'SWING', d: '2026-11-10', qty: 100, entry: 500, sl: 470, exit: 470, xd: '2026-11-18', xtm: '11:05' }])),
  same: pick(use([{ inst: 'INTRA', cat: 'Intraday', d: '2026-11-18', qty: 50, entry: 200, sl: 180, exit: 180, xd: '2026-11-18' }])),
  wk: pick(use([{ inst: 'LASTWEEK', d: '2026-11-04', qty: 100, entry: 500, sl: 480, exit: 480, xd: '2026-11-13' }])),
  sun: pick(use([{ inst: 'SUN', d: '2026-11-09', qty: 100, entry: 500, sl: 480, exit: 490, xd: '2026-11-15' }])),
  mon: pick(use([{ inst: 'MON', d: '2026-11-09', qty: 100, entry: 500, sl: 480, exit: 490, xd: '2026-11-16' }])),
  parts: pick(use([{ inst: 'PARTS', d: '2026-11-12', qty: 100, entry: 500, sl: 480, exit: 490, xd: '2026-11-18', chg: 20, parts: [{ d: '2026-11-17', tm: '10:00', qty: 50, px: 520, chg: 30 }] }])),
  multi: pick(use([{ inst: 'A', d: '2026-11-18', qty: 10, entry: 100, sl: 90, exit: 80, xd: '2026-11-18' }, { inst: 'B', dir: 'Short', d: '2026-11-17', qty: 20, entry: 50, sl: 55, exit: 60, xd: '2026-11-18' }, { inst: 'C', d: '2026-11-18', qty: 5, entry: 100, sl: 95, exit: 120, xd: '2026-11-18' }])),
  open: pick(use([{ inst: 'OPENLOSS', d: '2026-11-17', qty: 100, entry: 500, sl: 485 }])),        // open risk 1,500 = 0.75%, inside your 2% cap
  unk: pick(use([{ inst: 'LEGACY', d: '2026-11-17', qty: 100, entry: 500, sl: 470, exit: 470 }])),
};
const t = { inst: 'X', d: '2026-11-12', qty: 100, entry: 500, sl: 480, exit: 490, xd: '2026-11-18', chg: 20, parts: [{ d: '2026-11-17', qty: 50, px: 520, chg: 30 }] };
out.legs = PnL.legs(T(t), 100); out.tot = PnL.totals(T(t), 100);
out.problems = [JR.exitProblem(T({ d: '2026-11-18', qty: 1, entry: 1, exit: 2 })), JR.exitProblem(T({ d: '2026-11-18', qty: 1, entry: 1, exit: 2, xd: '2026-11-17' })),
  JR.exitProblem(T({ d: '2026-11-10', qty: 10, entry: 1, exit: 2, xd: '2026-11-18', parts: [{ d: '2026-11-11', qty: 11, px: 2 }] })), JR.exitProblem(T({ d: '2026-11-10', qty: 10, entry: 1, exit: 2, xd: '2026-11-18' }))];
out.weeks = ['2026-11-15', '2026-11-16', '2026-11-20', '2026-11-22', '2026-11-23', '2027-01-01'].map(PnL.weekStart);
console.log(JSON.stringify(out));
""")
if o is None: check('loss-limit scenarios run', False, err); print(f'\n{len(fails)} FAILED'); sys.exit(1)
A = o['A']
check('EXAMPLE A: a swing opened 10 Nov and closed today (18 Nov) for -3,000 is in TODAY\'s realized P&L: -3,000 = -1.50% of capital', A['rs']['day'] == -3000 and close(A['day'], -0.015), str(A['rs']))
check('EXAMPLE A: the same loss is in THIS WEEK (Mon 16 to Fri 20 Nov): -3,000 = -1.50%', A['rs']['week'] == -3000 and close(A['week'], -0.015))
check('EXAMPLE A: daily limit 2,000 -> used 150%, nothing left, status red; the banner says the day is over', close(A['use']['day']['use'], 1.5) and A['use']['day']['remainingRs'] == 0 and A['use']['day']['status'] == 'bad' and A['level'] == 'bad' and any('Day is over' in m for m in A['msgs']), str(A['use']['day']))
check('EXAMPLE A: weekly limit 4,000 -> used 75%, 1,000 left, amber', close(A['use']['week']['use'], 0.75) and close(A['use']['week']['remainingRs'], 1000) and A['use']['week']['status'] == 'warn', str(A['use']['week']))
check('same-day closed trade (intraday): -1,000 today and this week', o['same']['rs']['day'] == -1000 and o['same']['rs']['week'] == -1000)
check('closed in a DIFFERENT week (Fri 13 Nov): not today, not this week, but this month (-2,000)', o['wk']['rs']['day'] == 0 and o['wk']['rs']['week'] == 0 and o['wk']['rs']['month'] == -2000)
check('week boundary (IST, Monday start): exit on Sun 15 Nov belongs to last week, exit on Mon 16 Nov to this week', o['sun']['rs']['week'] == 0 and o['mon']['rs']['week'] == -1000)
check('week starts: Sun 15 Nov -> Mon 9 Nov; Mon 16 and Fri 20 -> 16 Nov; Sun 22 -> 16 Nov; Mon 23 -> 23 Nov; Fri 1 Jan 2027 -> Mon 28 Dec 2026', o['weeks'] == ['2026-11-09', '2026-11-16', '2026-11-16', '2026-11-16', '2026-11-23', '2026-12-28'], str(o['weeks']))
P = o['parts']
check('partial exits across days: 50 @ 520 on 17 Nov = +1,000 - 30 = +970 (yesterday); the rest 50 @ 490 today = -500 - 20 = -520 (today)', P['rs']['day'] == -520 and P['rs']['week'] == 450, str(P['rs']))
check('partial exits: two legs on their own dates, total +450, nothing counted twice', [(l['d'], l['qty'], l['net']) for l in o['legs']] == [('2026-11-17', 50, 970), ('2026-11-18', 50, -520)] and o['tot']['net'] == 450, str(o['legs']))
check('several instruments, long and short: A -200, B (short) -200, C +100 = -300 today', o['multi']['rs']['day'] == -300, str(o['multi']['rs']))
check('an open position is NOT realized: day and week stay 0, green; its unrealized P&L is kept apart (no live price in this test: none)', o['open']['rs']['day'] == 0 and o['open']['rs']['week'] == 0 and o['open']['level'] == 'ok' and not o['open']['unreal'])
U = o['unk']
check('a closed trade with NO exit date is never put on a day: today 0 (not guessed from entry or today)', U['rs']['day'] == 0 and U['rs']['week'] == 0 and U['unknown'] == 1)
check('... and the banner warns that its P&L is outside the limits until the exit date is added (amber, not green)', U['level'] == 'warn' and any('no exit date' in m for m in U['msgs']), str(U['msgs']))
pr = o['problems']
check('saving: a closed trade needs its exit date; an exit before the entry and partials larger than the position are refused; a valid one saves', 'exit date' in pr[0] and 'before the entry' in pr[1] and 'more than the position' in pr[2] and pr[3] == '', str(pr))

# ---------------------------------------------------------------- part 3: migration (schema 2), persistence and Trade Insight consistency
# Migration through the real local load path: an old (schema 1) journal in storage, then load.
o3, err3 = run(r"""
const old = { journals: [{ id: 'jx', name: 'mine', updated: 1, set: { capital: 200000 }, trades: [
  { id: 't1', d: '2026-11-03', inst: 'OLDSWING', cat: 'Swing', dir: 'Long', qty: 10, entry: 100, sl: 90, exit: 95, note: 'keep me' },
  { id: 't2', d: '2026-11-18', inst: 'OPEN', cat: 'Swing', dir: 'Long', qty: 10, entry: 100, sl: 90 } ] }], cur: 'jx' };
const before = JSON.stringify(old.journals[0]);
mem['tji_journals_v1'] = JSON.parse(JSON.stringify(old.journals)); mem['tji_last_v1'] = 'jx';
let loaded = 'no load()';
try { JR.loadLocal(); loaded = 'ok'; } catch (e) { loaded = 'error ' + e.message; }
const J = JR.E.list.find(j => j.id === 'jx');
const bk = mem[JR.backupKey('jx')];
console.log(JSON.stringify({ loaded, found: !!J, schema: J && J.schema, t1: J && J.trades.find(t => t.id === 't1'), t2: J && J.trades.find(t => t.id === 't2'), backupSame: bk ? JSON.stringify(bk.journal) === before : null, backupAt: bk && bk.at,
  n: J && J.trades.length, rs: J ? (JR.E.cur = 'jx', JR.riskStatus().unknownExit) : null }));
""")
if o3 is None: check('migration runs through the normal load path', False, err3)
else:
    t1 = o3.get('t1') or {}
    check('migration: an old journal loads, is marked schema 2, and keeps every trade and field (nothing deleted)', o3['found'] and o3['schema'] == 2 and o3['n'] == 2 and t1.get('note') == 'keep me' and t1.get('exit') == 95, json.dumps(o3)[:300])
    check('migration: a byte-for-byte copy of the journal as it was is saved first (backup before the schema change)', o3['backupSame'] is True and bool(o3['backupAt']), str(o3.get('backupSame')))
    check('migration: an old closed trade gets NO invented exit date: xd stays empty and it is flagged xd_unknown', t1.get('xd') == '' and t1.get('xd_unknown') is True)
    check('migration: an open trade is not flagged (nothing to date yet)', not (o3.get('t2') or {}).get('xd_unknown'))
    check('migration: the risk banner counts 1 trade with an unknown exit date', o3['rs'] == 1)
# Trade Insight consistency: pnl.js is self-contained (no App, no DOM), so the same file gives Trade Insight identical numbers.
o4, err4 = run(r"""
const iso = { console }; vm.createContext(iso); vm.runInContext(fs.readFileSync(process.argv[2] + '/pnl.js', 'utf8'), iso);
const t = T({ inst: 'X', d: '2026-11-12', qty: 100, entry: 500, sl: 480, exit: 490, xd: '2026-11-18', chg: 20, parts: [{ d: '2026-11-17', qty: 50, px: 520, chg: 30 }] });
const a = iso.PnL.totals(t, 100), b = PnL.totals(t, 100);
const J = { set: { ...JR.SET0 }, trades: [t] }; const e = JR.enrich(J)[0];
console.log(JSON.stringify({ standalone: !!iso.PnL, same: JSON.stringify(a) === JSON.stringify(b), journalNet: e.net, engineNet: a.net, exported: typeof module === 'object' }));
""")
if o4 is None: check('pnl.js runs on its own (no App, no page)', False, err4)
else:
    check('Trade Insight consistency: pnl.js runs on its own with no App and no page, so it can be dropped into Trade Insight unchanged', o4['standalone'] is True)
    check('Trade Insight consistency: the standalone engine and the journal give the identical result (+450 for the partial-exit trade)', o4['same'] is True and o4['journalNet'] == o4['engineNet'] == 450, json.dumps(o4))
# ---------------------------------------------------------------- part 5 (19 Nov 2026): hiding alerts
o5, err5 = run(r"""
const old = n => Array.from({ length: n }, (_, i) => T({ id: 'o' + i, inst: 'OLD' + i, d: '2026-11-10', qty: 10, entry: 100, sl: 95, exit: 90 }));      // closed, no exit date
const seen = x => ({ shown: x.shown.map(m => m[2]), level: x.level, levelShown: x.levelShown, hidden: x.hiddenN, ack: x.ackN, day: x.day, unknown: x.unknownExit, use: x.use.day.pnlRs });
const out = {};
let J = { id: 'j1', name: 't', schema: 2, set: { ...JR.SET0, capital: 200000 }, trades: old(3).concat([T({ id: 'big', inst: 'BIG', d: '2026-11-18', qty: 100, entry: 500, sl: 480, exit: 470, xd: '2026-11-18' })]) };
JR.E.list = [J]; JR.E.cur = 'j1'; JR.persist = () => {}; ctx.App.render = () => {};
out.base = seen(JR.riskStatus());
JR.ignoreAlert('xd'); out.afterXd = seen(JR.riskStatus());                                   // old trades accepted: day alert stays
JR.ignoreAlert('hide', 'day'); out.afterHide = seen(JR.riskStatus());                         // hard stop hidden for today
JR.ignoreAlert('mute', 'day'); out.muteHard = JR.J().ign.mute.day === true;                  // a hard stop can never be muted for good
out.nextDay = null;
J.trades.push(T({ id: 'new', inst: 'NEWONE', d: '2026-11-18', qty: 1, entry: 10, sl: 9, exit: 11 })); out.newUnknown = seen(JR.riskStatus());   // a NEW trade with no exit date still alerts
JR.ignoreAlert('restore'); out.restored = seen(JR.riskStatus());
JR.ignoreAlert('all'); out.allHidden = seen(JR.riskStatus());
console.log(JSON.stringify(out));
""")
if o5 is None: check('hide-alert harness runs', False, err5)
else:
    check('hide alerts: before hiding, the no-exit-date alert and the day-loss alert both show', 'noexit' in o5['base']['shown'] and 'day' in o5['base']['shown'], json.dumps(o5['base']['shown']))
    check('ignore old trades: the no-exit-date alert goes, the loss-limit alert stays (hiding one kind never hides another)', 'noexit' not in o5['afterXd']['shown'] and 'day' in o5['afterXd']['shown'] and o5['afterXd']['ack'] == 3)
    check('ignored trades are NOT given a date: they still count as unknown and still stay out of the day limit', o5['afterXd']['unknown'] == 3 and o5['afterXd']['use'] == o5['base']['use'])
    check('hide today: a reached loss limit can be hidden for today, the banner level drops, but the true level and the maths do not change', 'day' not in o5['afterHide']['shown'] and o5['afterHide']['level'] == 'bad' and o5['afterHide']['hidden'] == 1 and o5['afterHide']['day'] == o5['base']['day'])
    check('a hard stop (loss limit) can only be hidden for today, never muted for good', o5['muteHard'] is False)
    check('a NEW closed trade without an exit date still alerts after old ones were ignored', 'noexit' in o5['newUnknown']['shown'])
    check('show again restores every hidden alert and clears the accepted trades', o5['restored']['hidden'] == 0 and o5['restored']['ack'] == 0 and 'day' in o5['restored']['shown'])
    check('hide all today hides everything currently shown', o5['allHidden']['shown'] == [] and o5['allHidden']['hidden'] >= 2)
# hidden for today only: the next day the alert is back
o6, err6 = run(r"""
let J = { id: 'j1', name: 't', schema: 2, set: { ...JR.SET0, capital: 200000 }, trades: [T({ id: 'big', inst: 'BIG', d: '2026-11-18', qty: 100, entry: 500, sl: 480, exit: 470, xd: '2026-11-18' })] };
JR.E.list = [J]; JR.E.cur = 'j1'; JR.persist = () => {}; ctx.App.render = () => {};
JR.ignoreAlert('hide', 'day'); const a = JR.riskStatus().shown.some(m => m[2] === 'day'); J.ign.snooze.day = '2026-11-17'; const b = JR.riskStatus().shown.some(m => m[2] === 'day');
console.log(JSON.stringify({ a, b }));
""")
if o6 is None: check('snooze-expiry harness runs', False, err6)
else: check('hidden for today only: an alert hidden yesterday is shown again today', o6['a'] is False and o6['b'] is True, json.dumps(o6))
o7, err7 = run(r"""
const T0 = id => T({ id, inst: id, d: '2026-11-10', qty: 10, entry: 100, sl: 95, exit: 90 });
let J = { id: 'j1', name: 't', schema: 2, set: { ...JR.SET0, capital: 200000 }, trades: [T0('a'), T0('b')] };
JR.E.list = [J]; JR.E.cur = 'j1'; JR.persist = () => {}; ctx.App.render = () => {};
const out = {}; out.base = JR.riskStatus().shown.map(m => m[2]);
JR.ignoreAlert('mute', 'noexit'); J.trades.push(T0('c')); out.mutedFuture = JR.riskStatus().shown.map(m => m[2]);      // always ignore covers trades added later too
JR.ignoreAlert('restore'); out.restored = JR.riskStatus().shown.map(m => m[2]);
JR.ignoreAlert('off'); const off = JR.riskStatus(); out.off = { bannerOff: off.bannerOff, still: off.msgs.length };       // banner off: alerts still computed for the Dashboard card
JR.ignoreAlert('on'); out.on = JR.riskStatus().bannerOff;
console.log(JSON.stringify(out));
""")
if o7 is None: check('banner-off harness runs', False, err7)
else:
    check('"Always ignore" on the no-exit-date alert also covers closed trades added later', 'noexit' in o7['base'] and 'noexit' not in o7['mutedFuture'])
    check('restore brings the no-exit-date alert back', 'noexit' in o7['restored'])
    check('banner off: the page banner is switched off but the Dashboard still has every alert computed; on reverses it', o7['off']['bannerOff'] is True and o7['off']['still'] >= 1 and o7['on'] is False, json.dumps(o7['off']))
core_src = open(os.path.join(JS, 'core.js')).read()
check('banner has the hide buttons and a "show them again" link, and the pop-up only fires for alerts that are shown', 'App.riskAct' in core_src and 'Show them again' in core_src and 'notifyRisk(alerts)' in core_src)
pnl_src = open(os.path.join(JS, 'pnl.js')).read(); jr_src = open(os.path.join(JS, 'journal.js')).read(); idx = open(os.path.join(HERE, 'site', 'index.html')).read()
check('one source of truth: journal.js uses PnL for net, day, week and month and no longer sums P&L by the entry date', 'PnL.totals(' in jr_src and 'PnL.realized(T, d => d === td)' in jr_src and 'closed.filter(t => t.d === td)' not in jr_src)
check('index.html loads pnl.js before journal.js', 0 <= idx.find('js/pnl.js') < idx.find('js/journal.js'))
print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: ' + '; '.join(fails))
sys.exit(1 if fails else 0)
