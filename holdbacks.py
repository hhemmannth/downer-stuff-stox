"""Hold-backs by segment (18 Nov 2026). A setup that fails one stays on the list as WATCH with the reason; it is never opened as a tracked trade and the
backtest marks it 'held' and does not count it. One table for every segment, so the live scan and the backtest cannot disagree.

Where each number comes from (your published backtests, A+ only, FY from 1 April 2026; all in-sample, one market phase):
  swing            287 trades   stop under 7% of price lost, zone below 2/2 lost, 1H volume under 2x lost, Mixed / transitioning market lost (PF 0.38)   [swing.CFG, in swing.py]
  intraday (stock) 999 trades   no entry from 14:00 (PF 0.45), stop under 0.5% of price (PF 0.53)                                                           [here and signals.LAST_ENTRY_BY]
  options           24 trades   zone below 2/2: PF 0.25, against 1.01 for 2/2 (thin evidence)
  gold intraday     48 trades   zone below 2/2: PF 0.35, against 1.28 for 2/2
  positional        33 trades   zone below 2/2 and the Mixed market (0 of 10 won): applied for consistency; the segment still loses money
  gold swing / gold positional: 2 and 0 trades, so no evidence of its own: the swing engine's zone 2/2 and 1H volume 2x rules are applied (swing.GOLD_HB), the 7% stop rule is not (gold stops are in dollars)
HOLDBACKS=off (repo variable) switches every hold-back off, live and in the backtests."""
import os

def off(env=None):
    return str((env if env is not None else os.environ).get('HOLDBACKS', '') or '').strip().lower() in ('off', 'false', 'no', '0')

RULES = dict(
    intraday=dict(min_stop_pct=0.5),
    options=dict(min_zone_q=2),
    gold_intraday=dict(min_zone_q=2),
    positional=dict(min_zone_q=2, regimes=('Mixed / transitioning',)),
    gold_positional=dict(min_zone_q=2),
)

def reasons(segment, zone_q=None, risk_pct=None, regime=None):
    """[(short label for the backtest, sentence for the page)] for one setup. Missing facts never hold a setup back."""
    r = RULES.get(segment) or {}; out = []
    if off(): return out
    if r.get('min_zone_q') and zone_q is not None and zone_q < r['min_zone_q']: out.append(('weak zone', f"weak zone ({zone_q}/2): the backtest lost money on zones below {r['min_zone_q']}/2"))
    if r.get('min_stop_pct') and risk_pct is not None and risk_pct < r['min_stop_pct']: out.append((f"stop under {r['min_stop_pct']:g}%", f"stop only {risk_pct:.2f}% of price: inside the noise (the backtest lost money with stops under {r['min_stop_pct']:g}%)"))
    if r.get('regimes') and regime in r['regimes']: out.append(('mixed market regime', f'market regime "{regime}": the backtest lost money in it'))
    return out

def hold_items(items, segment, regime=None):
    """Live: every TRIGGERED setup that fails a hold-back becomes WATCH (reason) with a note. Other statuses are untouched."""
    for it in items:
        if it.get('status') != 'TRIGGERED': continue
        rs = reasons(segment, it.get('zone_q'), it.get('risk_pct'), regime)
        if not rs: continue
        it['status'] = f'WATCH ({rs[0][1]})'
        n = it.get('notes'); add = '; '.join(x[1] for x in rs)
        if isinstance(n, list): it['notes'] = n + [add]
        else: it['notes'] = ((n + '; ') if n else '') + add
    return items
