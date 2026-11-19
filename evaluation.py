"""Which backtest trades are evidence for the frozen rules, and which are not (18 Nov 2026).

What happened before: the 18 Nov 2026 hold-backs (stop under 7%, zone under 2/2, 1H volume under 2x, Mixed regime; intraday after 14:00 and
stops under 0.5%; options and gold zone 2/2) were chosen by looking at the results of the A+ trades from 1 Apr to 18 Nov 2026, and the same
trades were then scored with those hold-backs, and the 'first 60% / last 40%' split sat inside that same window. So:
  - the trades were not selected before their outcomes were known;
  - the same trades shaped the rules AND scored them;
  - the 'held in both halves' check is not independent (both halves were used to choose the rules).
That window is therefore labelled DEVELOPMENT (in-sample) here, and no result from it is presented as validation.

Chronological windows, fixed on 18 Nov 2026 before any validation run (never moved after seeing a result):
  validation      VALIDATION_FROM (default 1 Apr 2025) up to 31 Mar 2026: before the development window. These trades were not used to
                  choose the hold-backs, but they are NOT untouched: the 11 Nov 2026 full swing backtest (about two years, raw rules,
                  -0.03R a trade after costs) already showed this period. So it is independent of the hold-back choice only; the one truly
                  untouched evidence is out of sample (after the freeze). Swing and positional replay it when history allows; intraday and
                  options cannot (60 days).
  development     1 Apr 2026 to the freeze of the strategy version (18 Nov 2026): where the hold-backs were chosen. In-sample.
  out_of_sample   after the freeze: trades the frozen version could not have been fitted to. Grows every week (and through paper trading).
Walk-forward: the frozen rules are scored in consecutive 3-month windows across everything replayed, with no re-fitting (re-fitting a filter
per window would be optimising the strategy, which you ruled out). It shows whether the result is stable, not a better rule.
The hold-back check that matters is in the validation and out-of-sample windows: if the held-back trades did as well there as the taken ones,
the hold-backs were fitted to noise."""
import os
import pandas as pd

DEV_FROM = '2026-04-01'
FIT_END = '2026-11-18'          # the hold-backs were chosen on trades up to this day

def validation_from(env=None):
    v = str((env if env is not None else os.environ).get('BACKTEST_VALIDATION_FROM', '') or '').strip()
    try: return str(pd.Timestamp(v).date()) if v else '2025-04-01'
    except Exception: return '2025-04-01'

def freeze_at():
    try:
        import strategy_config; L = strategy_config.latest(); return (L['version'], str(L['frozen_at'])[:16].replace('T', ' ')) if L else (None, None)
    except Exception: return (None, None)

def window_of(entry_t, val_from=None, frozen=None):
    t = str(entry_t or '')[:16]; vf = val_from or validation_from(); fz = frozen or (freeze_at()[1] or FIT_END)
    if t < vf: return 'before_validation'
    if t < DEV_FROM: return 'validation'
    if t < fz: return 'development'
    return 'out_of_sample'

LABEL = dict(validation='Validation (before the hold-back window; seen once with the raw rules on 11 Nov 2026, so independent of the hold-backs only)', development='Development: in-sample (the hold-backs were chosen on these trades)',
             out_of_sample='Out of sample (after the rules were frozen)', before_validation='Before the validation window (not used)')
INDEPENDENT = dict(validation=True, development=False, out_of_sample=True, before_validation=False)       # of the hold-back choice
UNTOUCHED = dict(validation=False, development=False, out_of_sample=True, before_validation=False)        # never seen in any result before the freeze

def _st(rs):
    import backtest as bt; s = bt.stats(rs); return {k: s[k] for k in ('n', 'win', 'avg', 'pf', 'max_dd')}

def split(trades, min_score=8, val_from=None):
    """Stats per window on the trades the rules TOOK (closed, not held), plus the held-back trades in each window."""
    vf = val_from or validation_from(); ver, fz = freeze_at(); fz = fz or FIT_END; out = {}
    for w in ('validation', 'development', 'out_of_sample'):
        T = [t for t in trades if t.get('closed') and (t.get('score') or 0) >= min_score and window_of(t.get('entry_t'), vf, fz) == w]
        taken = [t['r_net'] for t in T if not t.get('held')]; held = [t['r_net'] for t in T if t.get('held')]
        out[w] = dict(label=LABEL[w], independent=INDEPENDENT[w], untouched=UNTOUCHED[w], taken=_st(taken), held=_st(held),
                      bounds=dict(validation=[vf, DEV_FROM], development=[DEV_FROM, fz], out_of_sample=[fz, None])[w])
    return dict(windows=out, version=ver, frozen_at=fz, validation_from=vf,
                note='Development results are in-sample by construction. Validation is independent of the hold-back choice but was seen once with the raw rules (11 Nov 2026). Only out of sample (after the freeze) is untouched evidence.')

def walk_forward(trades, months=3, min_score=8):
    """The frozen rules scored in consecutive windows (no re-fitting)."""
    T = sorted([t for t in trades if t.get('closed') and not t.get('held') and (t.get('score') or 0) >= min_score], key=lambda t: t['entry_t'])
    if not T: return []
    start = pd.Timestamp(T[0]['entry_t'][:10]).to_period('M').to_timestamp(); end = pd.Timestamp(T[-1]['entry_t'][:10]); out = []
    while start <= end:
        stop = start + pd.DateOffset(months=months); a, b = str(start.date()), str(stop.date())
        rs = [t['r_net'] for t in T if a <= t['entry_t'][:10] < b]
        if rs: out.append(dict(test_from=a, test_to=str((stop - pd.Timedelta(days=1)).date()), window=window_of(a + ' 00:00'), **_st(rs)))
        start = stop
    return out
