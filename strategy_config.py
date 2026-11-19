"""Versioned, frozen strategy configuration (18 Nov 2026).

Every number the engines trade by (structure, zones, confirmation, entries, stops, targets, hold-backs, the daily rule, session times, costs,
risk settings, switches such as PLAYBOOK_V2 or GOLD_VOLUME_RULE) is collected from the modules themselves, written as canonical JSON and
hashed (SHA-256). strategy_versions.json keeps the frozen versions: version, freeze time, hash, the full configuration and the rules in words.

Why: an evaluation (paper trading, or an out-of-sample backtest) only means something if the rules did not change while it ran. So:
  - every tracked trade and paper record carries the version and the hash it was produced with;
  - CI (test_audit2.py) fails if the code's rules no longer match the latest frozen version: a rule change then needs a NEW
    version (python strategy_config.py freeze 1.1.0 "what changed"), which restarts that version's evaluation from zero;
  - System health shows a warning when the live run's effective rules (repo variables included) differ from the frozen version.

  python strategy_config.py show | check | freeze VERSION "note\""""
import datetime as dt, hashlib, json, os, sys

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'strategy_versions.json')

def _plain(x):
    if isinstance(x, dict): return {str(k): _plain(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
    if isinstance(x, (list, tuple, set)): return [_plain(v) for v in (sorted(x) if isinstance(x, set) else x)]
    if isinstance(x, float): return round(x, 10)
    return x

def build(env=None):
    """The effective configuration right now (module constants + the repo variables that change rules)."""
    e = env if env is not None else os.environ
    import strategy_scanner as sc, swing, holdbacks, signals, backtest as bt, backtest_tf as tf, greeks, gold_feed
    flags = {k: str(e.get(k, '') or '').strip().lower() for k in ('PLAYBOOK_V2', 'SWING_LUX_OB', 'HOLDBACKS', 'GOLD_VOLUME_RULE', 'GOLD_SESSIONS', 'REGIME_FILTER', 'APLUS_OVERFLOW')}
    cfg = dict(
        engine=dict(swing_daily=sc.CFG, intraday_5m=sc.CFG_I, bias_15m=sc.CFG_B, v2_15m=sc.CFG_I2, swing_playbook=swing.CFG, gold_swing_holdbacks=swing.GOLD_HB,
                    positional=tf.CFG_P, gold_positional=tf.CFG_GP, gold_no_volume=tf.GOLD_NO_VOLUME),
        holdbacks=dict(rules=holdbacks.RULES, off=holdbacks.off(e), swing_regimes=list(swing.CFG.get('hold_regimes') or ())),
        tracker=dict(swing_expiry_days=signals.SWING_EXPIRY_DAYS, positional_expiry_days=signals.POSITIONAL_EXPIRY_DAYS, square_off=signals.SQUARE_OFF, last_entry=signals.LAST_ENTRY,
                     last_entry_by=signals.LAST_ENTRY_BY, gold_square_off=signals.GOLD_SQUARE, swing_like=signals.SWINGLIKE, day_rules=signals.day_rules(e),
                     partials='swing-like: half at T1 (no breakeven), a quarter at T2 (stop to entry, then trail daily higher lows); others: half at T1 (stop to entry), a quarter at T2 (stop to T1)'),
        sessions=dict(nse=tf.NSE_SESSION, gold_all=tf.GOLD_ALL, gold_london_ny=tf.GOLD_LNY),
        options=dict(lot=greeks.LOT_SIZE, strike_step=greeks.STEP, r_free=greeks.R_FREE, div=greeks.Q_DIV),
        costs=dict(delivery_pct=bt.COST_PCT, segments={k: v.get('cost_pct') for k, v in bt.SEGMENTS.items()}, options_fixed_inr=tf.OPT_FIXED_INR, options_var=tf.OPT_VAR, gold_usd_per_oz=tf.gold_cost(e)),
        risk=bt.account_from_env(e), gold_instrument=gold_feed.INSTRUMENT, flags=flags)
    return _plain(cfg)

def digest(cfg): return hashlib.sha256(json.dumps(cfg, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()

RULES_TEXT = dict(
    timeframes='Swing: weekly location, 1D structure, 1H confirmation, 15m entry (long only). Intraday stocks and Nifty options: 15m bias, 5m structure and trigger. '
               'Positional: weekly structure, daily trigger. Gold (XAUUSD spot): the same engines; intraday, swing and positional, long and short.',
    entry='Daily (or 5m) CHoCH then BOS with displacement; zone = order block + FVG (+ fib 0.618-0.705); pullback into the zone; confirmation = rejection and a close back over '
          'the 9 EMA on relative volume >= 1.5x (swing: same hour on earlier days); swing entry = 15m CHoCH + BOS + FVG in the zone, retest, 15m close over the 9 EMA on 1.5x; no chasing.',
    stop='Below the order block / zone / pullback low minus 0.25 ATR (mirrored for shorts). Never widened.',
    targets='Swing: T1 1R (half, no early breakeven), T2 2R (a quarter, stop to entry), T3 3R, trail below each new daily higher low; expiry 28 days (positional 120). '
            'Intraday/options: T1 = prior leg extreme or 1R, then 2R and 3R; stop to entry at T1; square-off 15:15 IST (gold 02:00 IST).',
    filters='Score 0-10 (A+ 8-10 only taken); at most 2 new trades a day (India shared, gold separate), strict; hold-backs in holdbacks.py and swing.CFG; '
            'no options after 15:00 or on expiry afternoons, stop after 2 losses; no stock intraday from 14:00; stale data = no trade.',
    risk='0.5% a trade (A+ 0.75%), open risk cap 2%, day stop 0.75%, week 2%, month half size 3% and stop 5% (journal Settings / repo variables).')

def load(path=None):
    try: return json.load(open(path or PATH))
    except Exception: return dict(versions=[])

def latest(path=None):
    v = load(path).get('versions') or []
    return v[-1] if v else None

def current(env=None, path=None):
    """(version label, hash, matches_frozen). The label is the latest frozen version when the hash matches it, else 'unfrozen'."""
    h = digest(build(env)); L = latest(path)
    return (L['version'], h, True) if L and L['hash'] == h else ('unfrozen' if not L else L['version'] + '+changed', h, False)

_CUR = {}
def stamp(env=None):
    """Cached (version, hash, matches) for this process: written on every new tracked trade."""
    if 'v' not in _CUR:
        try: _CUR['v'] = current(env)
        except Exception as ex: _CUR['v'] = ('unknown', f'error: {str(ex)[:60]}', False)
    return _CUR['v']

def freeze(version, note, env=None, path=None, now=None):
    data = load(path); vs = data.setdefault('versions', [])
    if any(v['version'] == version for v in vs): raise SystemExit(f'version {version} already exists: versions are never edited, pick a new number')
    cfg = build(env); h = digest(cfg)
    if vs and vs[-1]['hash'] == h: raise SystemExit(f'nothing changed since {vs[-1]["version"]}: no new version needed')
    t = (now or dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))).isoformat(timespec='seconds')
    vs.append(dict(version=version, frozen_at=t, hash=h, note=note, rules=RULES_TEXT, evaluation_starts=t, config=cfg))
    data['_about'] = ('Frozen strategy versions (strategy_config.py). Never edit a version: change the rules in code, then freeze a NEW version. '
                      'Each version\'s paper-trading evaluation starts at its evaluation_starts time; earlier results belong to earlier versions.')
    with open(path or PATH, 'w') as f: json.dump(data, f, indent=1, sort_keys=False)
    return vs[-1]

def main(argv=None):
    a = list(argv if argv is not None else sys.argv[1:]) or ['check']
    if a[0] == 'show': print(json.dumps(build(), indent=1)); return 0
    if a[0] == 'freeze':
        if len(a) < 3: print('usage: python strategy_config.py freeze VERSION "what changed"'); return 2
        v = freeze(a[1], a[2]); print(f"frozen {v['version']} at {v['frozen_at']}, hash {v['hash'][:16]}"); return 0
    ver, h, ok = current(); L = latest()
    print(f"rules hash {h[:16]}: " + (f'matches frozen version {ver}' if ok else f"does NOT match the latest frozen version ({L['version'] if L else 'none'}): freeze a new version"))
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
