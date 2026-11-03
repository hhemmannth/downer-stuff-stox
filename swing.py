"""Swing engine, built on your swing playbook (long only):

  Weekly  location      trend up, price near support
  1D      structure     liquidity sweep -> CHoCH -> BOS with displacement -> FVG + OB -> fib 0.618-0.705 + key level
  1H      confirmation  pullback into the daily zone -> rejection -> close above the 9 EMA on >= 1.5x volume
  15m     entry         CHoCH + BOS + FVG inside the zone -> controlled retest -> close above the 9 EMA on >= 1.5x volume

Every setup gets a stage, so you see where it is in the playbook:
  1 CHoCH          alert only, wait for the BOS
  2 BOS            zone marked, set an alert and wait for the pullback
  3 In zone        price is in the daily zone, wait for the 1H
  4 1H confirmed   wait for the 15m precision entry (no chasing the big candle)
  5 Entry          the 15m trigger fired: TRIGGERED

Plan: stop below the daily OB with a buffer, T1 = 1R (partial), T2 = 2R, T3 = 3R, trail by daily structure.
Scorecard: Structure 0-2, Zone 0-2, Confirmation 0-3 (1H), Context 0-3 (key level, fib 0.618, MTF EMA; futures OI you check).
"""
import math
import numpy as np, pandas as pd

H = None                          # helper module (strategy_scanner), bound at import time with bind()
def bind(mod):
    global H; H = mod

CFG = dict(pivot=3, zz=0.8, atr_n=14, lookback=150, disp_body_atr=1.0, fvg_min_atr=0.2, stack_gap_atr=0.5, sl_buffer_atr=0.25,
           max_bos_age=60, max_zone_atr=3.5, max_zone_pct=10.0, alert_atr=4.0, choch_age=15,
           rvol_min=1.5, bos_rvol_good=1.5, confirm_max_age=21, entry_fresh=8, entry_chase_atr=0.5,
           min_room_r=2.0, wide_stop_pct=8.0, wide_stop_atr=2.5, results_hold_days=14)
STAGES = {1: 'DEVELOPING (CHoCH, wait for BOS)', 2: 'SET ALERT (wait for pullback)', 3: 'IN ZONE (wait for 1H)', 4: '1H CONFIRMED (wait for 15m entry)', 5: 'TRIGGERED'}
STAGE_SHORT = {1: 'CHoCH', 2: 'BOS', 3: 'In zone', 4: '1H confirmed', 5: 'Entry'}

# ------------------------------------------------------------------ helpers
def _nan(x): return x is None or (isinstance(x, float) and math.isnan(x))

def _rvol(idx, v, t, n=20, slot=False):
    base = H.slot_volumes(idx, v, t) if slot and isinstance(idx, pd.DatetimeIndex) else None
    if base is None: base = v[max(0, t - n):t]
    m = float(np.mean(base)) if len(base) else 0.0
    return float(v[t] / m) if m > 0 else float('nan')

def weekly_location(daily):
    """Weekly: trend up (close above a rising weekly 9 EMA) and how far price is from it, in weekly ATRs."""
    w = daily.resample('W-FRI').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
    if len(w) < 12: return dict(up=None, text='Not enough weekly history.')
    e = H.ema(w.Close, 9); a = H.atr(w, 10).iloc[-1]; up = bool(w.Close.iloc[-1] >= e.iloc[-1] and e.iloc[-1] >= e.iloc[-3])
    dist = float((w.Close.iloc[-1] - e.iloc[-1]) / a) if a and not math.isnan(a) else None
    near = dist is not None and dist <= 1.5
    txt = ('Weekly trend up' if up else 'Weekly trend not up') + (f', price {dist:.1f} weekly ATR above the 9 EMA' if dist is not None and dist >= 0 else ', price below the weekly 9 EMA' if dist is not None else '') + ('' if not up else ' (near support)' if near else ' (extended)')
    return dict(up=up, near=bool(near), dist=dist, text=txt)

def chochs(df, cfg):
    """Recent daily CHoCHs (first close above a lower high after lower highs and lower lows) whose base still holds."""
    N = len(df); h, l, c = df.High.values, df.Low.values, df.Close.values; n = cfg['pivot']; ph, pl, known = H.pivots(df, cfg); out = []
    for ci in range(N - 1, max(n * 3, N - cfg['lookback']) - 1, -1):
        phs = [i for i in ph if known[i] <= ci - 1]; pls = [i for i in pl if known[i] <= ci - 1]
        if len(phs) < 2 or len(pls) < 2: continue
        lh = phs[-1]
        if not (h[lh] < h[phs[-2]] and l[pls[-1]] < l[pls[-2]]): continue
        if not c[ci] > h[lh] or np.any(c[lh + 1:ci] > h[lh]): continue
        base = l[pls[-1]]
        if np.any(l[ci:] < base): continue
        prior = l[pls[-2]]; seg = range(pls[-2] + 1, ci)
        sweep = next((j for j in seg if l[j] < prior and c[j] > prior), None)              # wick below the prior swing low, close back above
        out.append(dict(ci=ci, level=float(h[lh]), base=float(base), prior_low=float(prior), sweep_i=sweep, sweep_low=float(l[sweep]) if sweep is not None else None))
    return out

def resistance_above(df, level, lookback=250, n=3):
    """Nearest older daily swing high above `level`: the overhead supply your 2R rule looks at."""
    d = df.tail(lookback); ph, _ = H.swing_points(d, n); highs = sorted(float(d.High.values[i]) for i in ph if d.High.values[i] > level * 1.002)
    return highs[0] if highs else None

# ------------------------------------------------------------------ 1H confirmation
def confirm_1h(h1, s, buf, since):
    """Pullback into the daily zone on the 1H, a rejection candle, then a 1H close back above the 9 EMA on >= 1.5x
    volume (compared with the same hour on earlier days). Returns the parts and the bar where it confirmed."""
    res = dict(touched=False, rejection=0, reclaim=0, rvol_ok=0, rvol=float('nan'), pullback_low=float('nan'), t_touch=None, t_confirm=None, broken=False, confirm_age=None)
    if h1 is None or len(h1) < 10: return res
    h1 = h1[h1.index > since] if since is not None else h1
    if len(h1) < 2: return res
    full = h1; e = H.ema(full.Close, 9).values; o, hi, lo, c, v = (full[k].values for k in ('Open', 'High', 'Low', 'Close', 'Volume'))
    zb, zt = s['zone_bot'], s['zone_top']; touch = [i for i in range(len(full)) if lo[i] <= zt and lo[i] >= zb - 2 * buf]
    if not touch: return res
    t0 = touch[0]; res.update(touched=True, t_touch=str(full.index[t0])[:16], pullback_low=float(lo[t0:].min()))
    if np.any(c[t0:] < zb - buf): res['broken'] = True; return res
    for i in touch:
        rg = hi[i] - lo[i]; body = abs(c[i] - o[i]) + 1e-9; lw = min(o[i], c[i]) - lo[i]
        if rg > 0 and c[i] >= lo[i] + 0.6 * rg and lw >= 0.5 * body: res['rejection'] = 1
    for t in range(len(full) - 1, max(t0, 1) - 1, -1):
        if c[t] > e[t] and c[t - 1] <= e[t - 1]:
            rv = _rvol(full.index, v, t, slot=True); res.update(reclaim=1, rvol=rv, rvol_ok=int(not math.isnan(rv) and rv >= CFG['rvol_min']), t_confirm=str(full.index[t])[:16], confirm_age=len(full) - 1 - t, i_confirm=t)
            break
    return res

# ------------------------------------------------------------------ 15m precision entry
def entry_15m(m15, s, since, daily_atr):
    """Inside the daily zone on the 15m: CHoCH + BOS + FVG, a controlled retest of that FVG, then a 15m close above the 9 EMA
    on >= 1.5x volume. Returns the entry if it fired."""
    out = dict(found=False, choch=None, bos=None, fvg=None, retest=None, trigger=None, entry=None, rvol=float('nan'), age=None, note='')
    if m15 is None or len(m15) < 15: out['note'] = 'No 15m data: check the 15m chart yourself.'; return out
    w = m15[m15.index >= since] if since is not None else m15
    start = max(0, len(m15) - len(w) - 12)                 # a little context before the pullback for the swing points
    f = m15.iloc[start:]
    if len(f) < 15: out['note'] = 'Not enough 15m candles since the pullback yet.'; return out
    cfg = dict(H.CFG_I, pivot=2, zz=0.8, lookback=len(f), min_bars=15, disp_body_atr=0.8)
    cands = [z for z in H.find_structures(f, cfg) if z['zone_top'] >= s['zone_bot'] - 0.5 * daily_atr and z['zone_bot'] <= s['zone_top'] + 0.5 * daily_atr]
    if not cands: out['note'] = 'No 15m CHoCH + BOS inside the daily zone yet.'; return out
    z = cands[0]; o, hi, lo, c, v = (f[k].values for k in ('Open', 'High', 'Low', 'Close', 'Volume')); e = H.ema(f.Close, 9).values; b = z['bos_i']
    zt = z['fvg_high'] if not _nan(z['fvg_high']) else z['zone_top']; zb = z['zone_bot']
    out.update(found=True, choch=dict(level=float(z['choch_level']), at=str(f.index[z['choch_i']])[:16]), bos=dict(level=float(z['bos_level']), at=str(f.index[b])[:16]),
               fvg=dict(low=float(z['fvg_low']) if not _nan(z['fvg_low']) else None, high=float(z['fvg_high']) if not _nan(z['fvg_high']) else None), ob=dict(low=float(z['ob_low']) if not _nan(z['ob_low']) else None, high=float(z['ob_high']) if not _nan(z['ob_high']) else None),
               zone=dict(low=float(zb), high=float(zt)))
    rt = next((j for j in range(b + 1, len(f)) if lo[j] <= zt and c[j] >= zb), None)
    if rt is None: out['note'] = '15m structure is there: wait for a controlled retest of the 15m FVG.'; return out
    if np.any(c[rt:] < zb - 0.1 * daily_atr): out['note'] = 'The 15m zone failed: wait for a new 15m structure.'; out['found'] = False; return out
    out['retest'] = str(f.index[rt])[:16]
    for t in range(rt, len(f)):
        if c[t] > e[t] and (t == rt or c[t - 1] <= e[t - 1] or lo[t] <= zt):
            rv = _rvol(f.index, v, t, slot=True)
            if not math.isnan(rv) and rv >= CFG['rvol_min']:
                out.update(trigger=str(f.index[t])[:16], entry=float(c[t]), rvol=rv, age=len(f) - 1 - t, i_trigger=t); return out
    out['note'] = 'Retest done: waiting for a 15m close above the 9 EMA on at least 1.5x volume.'
    return out

# ------------------------------------------------------------------ the full analysis
def analyse(daily, h1=None, m15=None, weekly=None, levels=(), cfg=None):
    """One stock, long only. Returns a result dict with stage, status, scorecard, checklist and plan, or dict(state=...) when there is nothing."""
    cfg = cfg or CFG; base = H.CFG
    d = daily.dropna(subset=['Open', 'High', 'Low', 'Close'])
    if len(d) < base['min_bars']: return None
    N = len(d); a = float(H.atr(d, base['atr_n']).iloc[-1]); px = float(d.Close.iloc[-1]); buf = cfg['sl_buffer_atr'] * a
    weekly = weekly or weekly_location(d)
    scfg = dict(base, lookback=cfg['lookback'], zz=cfg['zz']); cands = H.find_structures(d, scfg)
    chosen = None
    for s in cands:
        st = H.zone_state(d, s, dict(base, max_bos_age=cfg['max_bos_age'], max_zone_atr=cfg['max_zone_atr'], max_zone_pct=cfg['max_zone_pct']), px)
        if st in ('IN_ZONE', 'APPROACH'): chosen = (s, st); break
        if st == 'FAR' and chosen is None and px - s['zone_top'] <= cfg['alert_atr'] * a and N - 1 - s['bos_i'] <= 20: chosen = (s, 'ALERT')
    ch_list = chochs(d, scfg)
    if chosen is None:
        pend = [x for x in ch_list if N - 1 - x['ci'] <= cfg['choch_age'] and not any(s['choch_i'] == x['ci'] for s in cands)]
        if not pend:
            st = H.zone_state(d, cands[0], dict(base, max_bos_age=cfg['max_bos_age']), px) if cands else None
            return dict(state=st, score=0, grade='skip')
        x = pend[0]
        return _result(d, dict(stage=1, choch=x, s=None, weekly=weekly, a=a, px=px, cfg=cfg, levels=levels))
    s, st = chosen; x = next((y for y in ch_list if y['ci'] == s['choch_i']), None)
    ctx = dict(stage=2, choch=x, s=s, weekly=weekly, a=a, px=px, cfg=cfg, levels=levels, zone_state=st)
    bos_v = d.Volume.values; ctx['bos_rvol'] = _rvol(d.index, bos_v, s['bos_i'])
    since = d.index[s['bos_i']] + pd.Timedelta(days=1)
    if st == 'IN_ZONE' or (h1 is not None and len(h1)):
        cf = confirm_1h(h1, s, buf, since.tz_localize(h1.index.tz) if h1 is not None and h1.index.tz is not None and since.tzinfo is None else since) if h1 is not None else None
        ctx['cf'] = cf
        if cf and cf['broken']: return dict(state='BROKEN', score=0, grade='skip')
        if st == 'IN_ZONE' or (cf and cf['touched']): ctx['stage'] = 3
        if cf and cf['reclaim'] and (cf['rejection'] or cf['rvol_ok']) and (cf['confirm_age'] or 0) <= cfg['confirm_max_age']: ctx['stage'] = 4
        if ctx['stage'] >= 4 and m15 is not None:
            t_since = pd.Timestamp(cf['t_touch'])
            if m15.index.tz is not None and t_since.tzinfo is None: t_since = t_since.tz_localize(m15.index.tz)
            en = entry_15m(m15, s, t_since, a); ctx['m15'] = en
            if en['entry'] is not None:
                last = float(m15.Close.iloc[-1])
                if en['age'] <= cfg['entry_fresh'] and last - en['entry'] <= cfg['entry_chase_atr'] * a: ctx['stage'] = 5
                elif last - en['entry'] > cfg['entry_chase_atr'] * a: en['note'] = 'The 15m entry fired but price has run away from it: no chasing, wait for the next retest.'
                else: en['note'] = f"The 15m entry fired {en['age']} candles ago: if you missed it, wait for the next retest."
    return _result(d, ctx)

def _result(d, ctx):
    cfg = ctx['cfg']; a, px, s, x, stage, weekly = ctx['a'], ctx['px'], ctx['s'], ctx['choch'], ctx['stage'], ctx['weekly']; base = H.CFG
    cf = ctx.get('cf') or {}; m = ctx.get('m15') or {}; ticks = []
    ema21 = float(H.ema(d.Close, 21).iloc[-1]); n = len(d)
    if s is None:                                   # stage 1: CHoCH only
        zb = zt = None; structure = 1; zone_q = 0
        entry = sl = t1 = t2 = t3 = None; risk = None
    else:
        structure = 2; zone_q = int(s['zone_q']); zb, zt = s['zone_bot'], s['zone_top']
        lv = list(ctx.get('levels') or [])
        if H.round_in_zone(zb, zt) or (zb - .25 * a <= s['bos_level'] <= zt + .25 * a) or (x and zb - .25 * a <= x['level'] <= zt + .25 * a) or any(zb - .25 * a <= y <= zt + .25 * a for y in lv): ticks.append('Key level')
        if min(s['fib_hi'], zt) >= max(s['fib_lo'], zb): ticks.append('Fib 0.618')
    h_ok = cf.get('reclaim') == 1 if stage >= 3 else True
    if px >= ema21 - .5 * a and weekly.get('up') and h_ok: ticks.append('MTF EMA')
    conf = int(cf.get('rejection', 0) + cf.get('reclaim', 0) + cf.get('rvol_ok', 0)) if stage >= 3 else 0
    context = min(3, len(ticks)); score = structure + zone_q + conf + context
    # ---- plan
    plan = {}; room = None; res_lvl = None
    if s is not None:
        ob = s['ob_low'] if not _nan(s['ob_low']) else zb
        pull = cf.get('pullback_low', float('nan'))
        sl = min(ob, zb, pull if not _nan(pull) else ob) - cfg['sl_buffer_atr'] * a
        if stage == 5: entry = m['entry']
        elif stage == 4 and m.get('fvg') and m['fvg'].get('high'): entry = m['fvg']['high']
        else: entry = zt - .25 * (zt - zb)
        risk = entry - sl
        if risk > 0:
            t1, t2, t3 = entry + risk, entry + 2 * risk, entry + 3 * risk
            res_lvl = resistance_above(d, s['leg_high']); res_ref = res_lvl if res_lvl else None
            room = ((res_ref - entry) / risk) if res_ref else None
            plan = dict(entry=entry, sl=sl, t1=t1, t2=t2, t3=t3, risk_pct=100 * risk / entry, r_t1=1.0, prior_high=float(s['leg_high']), resistance=res_lvl, room_r=room,
                        risk_atr=risk / a if a else None)
    # ---- status and hold-backs
    status = STAGES[stage]; holds = []
    if stage == 5 and weekly.get('up') is False: holds.append('weekly trend against')
    if stage == 5 and room is not None and room < cfg['min_room_r']: holds.append(f'room < {cfg["min_room_r"]:.0f}R')
    if holds: status = f'WATCH ({holds[0]})'
    notes = []
    if plan and (plan['risk_pct'] > cfg['wide_stop_pct'] or (plan['risk_atr'] or 0) > cfg['wide_stop_atr']): notes.append('wide structural stop: reduce size or skip, never widen it')
    if room is not None and room < cfg['min_room_r']: notes.append(f'overhead resistance at {res_lvl:,.2f} is only {room:.1f}R away (your rule: target at least 2R)')
    if plan and plan['prior_high'] < plan['t1']: notes.append(f"the prior high {plan['prior_high']:,.2f} sits before T1: expect selling there")
    if weekly.get('up') is False: notes.append('weekly trend is not up: lower conviction')
    if s is not None and ctx.get('bos_rvol') is not None and not math.isnan(ctx['bos_rvol']) and ctx['bos_rvol'] < 1.2: notes.append(f"the BOS candle had only {ctx['bos_rvol']:.1f}x volume")
    out = dict(stage=stage, stage_label=STAGE_SHORT[stage], status=status, holds=holds, structure=structure, zone_q=zone_q, confirm=conf, context=context, score=score, grade=H.grade(score),
               ticks=', '.join(ticks) or '-', notes='; '.join(notes), price=px, atr=a, weekly=weekly, rvol=cf.get('rvol', float('nan')),
               choch_level=x['level'] if x else float('nan'), choch_date=str(d.index[x['ci']])[:16] if x else '', sweep=bool(x and x['sweep_i'] is not None),
               sweep_low=x['sweep_low'] if x else None, sweep_level=x['prior_low'] if x else None, sweep_date=str(d.index[x['sweep_i']])[:10] if x and x['sweep_i'] is not None else None,
               state=ctx.get('zone_state', 'CHOCH'), cf=cf, m15=m, bos_rvol=ctx.get('bos_rvol'), **plan)
    if s is not None:
        out.update(bos_level=s['bos_level'], bos_date=str(d.index[s['bos_i']])[:16], leg=s.get('leg', 1), zone_bot=zb, zone_top=zt, ob_low=s['ob_low'], ob_high=s['ob_high'], fvg_low=s['fvg_low'], fvg_high=s['fvg_high'],
                   fib_lo=s['fib_lo'], fib_hi=s['fib_hi'], leg_low=s['leg_low'], leg_high=s['leg_high'], pullback_low=cf.get('pullback_low', float('nan')), rejection=cf.get('rejection', 0), reclaim=cf.get('reclaim', 0), rvol_ok=cf.get('rvol_ok', 0))
    else:
        out.update(bos_level=float('nan'), bos_date=str(d.index[x['ci']])[:16], zone_bot=float('nan'), zone_top=float('nan'))
    return out

# ------------------------------------------------------------------ checklist and explanation (what the trade page shows)
def _f(v, dd=2):
    return '-' if v is None or (isinstance(v, float) and math.isnan(v)) else f'{v:,.{dd}f}'

def checklist(r, extra):
    """The playbook steps, each ticked from the data (True / False) or left for you to check (None)."""
    st = r['stage']; cf = r.get('cf') or {}; m = r.get('m15') or {}; wk = r.get('weekly') or {}; out = []
    add = lambda tf, t, ok, x: out.append(dict(tf=tf, title=t, ok=ok, text=x))
    add('Weekly', 'Trend up, price near support', wk.get('up'), wk.get('text', ''))
    add('1D', 'Liquidity sweep', True if r.get('sweep') else None, f"Price wicked below the swing low {_f(r.get('sweep_level'))} to {_f(r.get('sweep_low'))} on {r.get('sweep_date')} and closed back above it." if r.get('sweep') else 'No clear sweep of the prior swing low before the CHoCH. Not required, but a sweep makes the setup cleaner.')
    add('1D', 'CHoCH', True, f"A daily close broke above the last lower high {_f(r.get('choch_level'))} on {str(r.get('choch_date'))[:10]}. An alert, not an entry.")
    bos_txt = (f"A displacement candle closed above {_f(r.get('bos_level'))} on {str(r.get('bos_date'))[:10]}" + (f" on {r['bos_rvol']:.1f}x volume" if r.get('bos_rvol') and not math.isnan(r['bos_rvol']) else '') + '. CHoCH + BOS = Structure 2 of 2.') if st >= 2 else 'Waiting for a BOS: a strong daily candle closing above the swing high.'
    add('1D', 'BOS with displacement', st >= 2, bos_txt)
    if st >= 2:
        z = []
        if not _nan(r.get('fvg_low')): z.append(f"FVG {_f(r['fvg_low'])} to {_f(r['fvg_high'])}")
        if not _nan(r.get('ob_low')): z.append(f"OB {_f(r['ob_low'])} to {_f(r['ob_high'])}")
        add('1D', 'FVG + OB marked', True, ', '.join(z) + (': they overlap, Zone 2 of 2.' if r['zone_q'] == 2 else ': Zone 1 of 2.'))
        tk = r['ticks']
        add('1D', 'Fib 0.618 to 0.705 and key level', ('Fib 0.618' in tk) or ('Key level' in tk), f"Fib zone {_f(r.get('fib_lo'))} to {_f(r.get('fib_hi'))}" + (' sits inside the zone' if 'Fib 0.618' in tk else ' is outside the zone') + ('; a key level is in the zone.' if 'Key level' in tk else '; no key level in the zone.'))
    if st >= 2:
        add('1H', 'Pullback and rejection', bool(cf.get('touched') and cf.get('rejection')) if st >= 3 else False,
            (f"Price pulled back into the zone on the 1H ({cf.get('t_touch')}), low {_f(cf.get('pullback_low'))}" + (', with a rejection candle.' if cf.get('rejection') else ', no clean rejection candle yet.')) if cf.get('touched') else 'Waiting for price to pull back into the daily zone. Set an alert at the zone top.')
        add('1H', 'Close above 9 EMA on 1.5x volume', bool(cf.get('reclaim') and cf.get('rvol_ok')) if st >= 3 else False,
            (f"1H close above the 9 EMA at {cf.get('t_confirm')}" + (f" on {cf['rvol']:.1f}x volume (same hour on earlier days)." if not _nan(cf.get('rvol')) else '.') + ('' if cf.get('rvol_ok') else ' Volume is below 1.5x.')) if cf.get('reclaim') else 'No 1H close above the 9 EMA yet.')
        add('1H', 'Futures OI long buildup', None, 'Check it yourself: price up with open interest up.')
        res = extra.get('results') or {}
        add('Risk', 'No results inside the hold', (res.get('days') is None or res['days'] > CFG['results_hold_days']) if res else None,
            f"Results on {res['date']} ({res['days']} days)." if res.get('date') else 'Results date not found: check the NSE announcement before holding.')
        ix = extra.get('index_check') or {}
        if ix: add('Risk', 'Sector index not falling', ix.get('state') != 'falling' if ix.get('state') != 'unknown' else None, ix.get('reason') or ix.get('text') or ix.get('state', ''))
        add('15m', 'CHoCH + BOS + FVG in the zone', bool(m.get('found')) if st >= 4 else False,
            (f"15m CHoCH at {_f(m['choch']['level'])} ({m['choch']['at'][11:]}), BOS at {_f(m['bos']['level'])} ({m['bos']['at'][11:]})" + (f", FVG {_f(m['fvg']['low'])} to {_f(m['fvg']['high'])}." if m.get('fvg') and m['fvg'].get('low') else '.')) if m.get('found') else (m.get('note') or 'After the 1H confirms, drop to the 15m.'))
        add('15m', 'Retest + close above 9 EMA on 1.5x volume', st == 5 or (m.get('entry') is not None),
            f"Retest at {m.get('retest')}, trigger close {_f(m.get('entry'))} at {m.get('trigger')} on {m['rvol']:.1f}x volume. Enter here." if m.get('entry') is not None else (m.get('note') or 'Wait for the controlled retest.'))
        if r.get('room_r') is not None or r.get('resistance') is None:
            add('Plan', 'Room to resistance at least 2R', True if r.get('resistance') is None else (None if r.get('room_r') is None else r['room_r'] >= CFG['min_room_r']),
                'No older swing high above: open room.' if r.get('resistance') is None else f"Nearest overhead swing high {_f(r['resistance'])} is {r['room_r']:.1f}R away.")
    return out

def plan_text(r):
    if r['stage'] < 2 or r.get('entry') is None: return None
    risk = r['entry'] - r['sl']
    return dict(
        execution=[('Entry ' + _f(r['entry']) + (' (15m trigger close).' if r['stage'] == 5 else ' planned: enter only after the 1H confirms and the 15m triggers.')),
                   f"Stop-loss {_f(r['sl'])}: below the daily OB with a 0.25 ATR buffer ({_f(risk)} points, {r['risk_pct']:.1f}%). Place it as a GTT/SL order right away.",
                   'Size from the stop: quantity = risk in rupees / stop distance. Never widen the stop to fit a bigger size.',
                   f"T1 {_f(r['t1'])} (1R): take a partial. T2 {_f(r['t2'])} (2R). T3 {_f(r['t3'])} (3R)."],
        trail=['At T1 (+1R): book part, keep the original stop. No early breakeven.', 'At T2 (+2R): protect behind the new daily higher low.',
               'Then trail by daily structure (below each new higher low), never by a fixed amount.', 'Exit before the results date if it falls inside the hold.',
               'If the daily closes back below the zone, exit: the structure has failed.'],
        marks=[dict(at='t1', label='T1 1R'), dict(at='t2', label='T2 2R'), dict(at='t3', label='T3 3R')])
