#!/usr/bin/env python3
"""Backtesting lab (items 2a-2e): replay YOUR swing playbook on past data with the same engine and the same trade tracker the live
scanner uses, so the numbers describe the scanner you actually run.

How a replay works, for every stock and every past trading day:
  1. the daily analysis runs on the candles up to that day's close (exactly what the live scan sees at night);
  2. on the next session the hourly candles are fed in one by one; when the engine reports a fresh 1H confirmation (stage 4),
     a trade is opened at that hourly close with the engine's stop, and T1/T2/T3 at 1R/2R/3R;
  3. the trade is then managed by signals.walk, the live tracker: stop checked before targets inside a candle, half off at T1 with
     no early breakeven, a quarter at T2 and the stop to entry, the rest at T3, and expiry after 28 days.

What it cannot replay (free data limits), stated on the page too:
  - the 15m precision entry (15-minute history only goes back about 60 days): the entry is the 1H confirmation close instead;
  - hourly history goes back about two years, so that is the test window;
  - results-date and sector hold-backs (no historical calendar); the weekly-trend and room-to-resistance hold-backs ARE applied;
  - today's Nifty 500 list is used, so stocks that left the index are missing (results look a little better than reality).
A backtest is evidence, not a promise.

  python backtest.py --out pub/data [--top 250] [--variants] [--workers 4]"""
import argparse, datetime as dt, json, math, os, sys, time
import numpy as np, pandas as pd

IST = 'Asia/Kolkata'
COST_PCT = 0.30                 # round-trip cost of a delivery trade as % of entry: STT 0.2, stamp duty, exchange + GST, DP charge, slippage
ASSUMPTIONS = [
    'Entry is the close of the 1H confirmation candle (the 15m precision entry cannot be replayed: 15-minute history is about 60 days).',
    'Stop, targets and management are the live rules: half at T1 with no early breakeven, a quarter at T2 and stop to entry, the rest at T3, expiry after 28 days; the stop is assumed to fill before a target inside the same candle.',
    'Hold-backs applied: weekly trend against, room to resistance under 2R. Not applied: results within 14 days and sector falling (no historical data).',
    f'Net results subtract {COST_PCT:.2f}% of the entry price per trade for brokerage, taxes and slippage.',
    'The current Nifty 500 list is used, so stocks that dropped out of the index are missing (survivorship bias flatters the result).',
    'One trade at a time per stock; no limit on how many stocks are open together.']

# ------------------------------------------------------------------ statistics (pure functions)
def stats(rs):
    """Summary of a list of R results, in the order the trades closed."""
    rs = [float(x) for x in rs]; n = len(rs)
    if not n: return dict(n=0, win=None, avg=None, pf=None, total=0.0, max_dd=0.0, streak=0, avg_win=None, avg_loss=None)
    wins = [x for x in rs if x > 0]; losses = [x for x in rs if x <= 0]
    eq = np.cumsum(rs); peak = np.maximum.accumulate(np.concatenate([[0.0], eq])); dd = float((peak[1:] - eq).max()) if n else 0.0
    streak = cur = 0
    for x in rs:
        cur = cur + 1 if x <= 0 else 0; streak = max(streak, cur)
    gl = -sum(losses)
    return dict(n=n, win=round(100 * len(wins) / n, 1), avg=round(float(np.mean(rs)), 3), pf=(round(sum(wins) / gl, 2) if gl > 0 else None), total=round(float(sum(rs)), 2),
                max_dd=round(dd, 2), streak=int(streak), avg_win=round(float(np.mean(wins)), 2) if wins else None, avg_loss=round(float(np.mean(losses)), 2) if losses else None)

def group(trades, key, order=None, field='r_net'):
    out = {}
    for t in trades: out.setdefault(str(key(t)), []).append(t[field])
    rows = [dict(k=k, **{x: s[x] for x in ('n', 'win', 'avg', 'pf', 'total')}) for k, v in out.items() for s in [stats(v)]]
    return sorted(rows, key=(lambda r: order.index(r['k']) if order and r['k'] in order else 99) if order else (lambda r: -r['n']))

def monte_carlo(rs, trades_per_year, risks=(0.5, 0.75, 1.0), sims=2000, seed=7):
    """Shuffle-with-replacement the trade results into `sims` possible years at each risk-per-trade and read off what a normal and a bad
    year look like: return, deepest drawdown, longest losing streak, and the chance of a 10% or 20% drawdown."""
    rs = np.asarray(rs, dtype=float); n = int(max(5, round(trades_per_year)))
    if len(rs) < 20: return dict(trades_per_year=n, sims=0, note='Not enough trades for a simulation (need 20).', risks={})
    rng = np.random.default_rng(seed); draw = rng.choice(rs, size=(sims, n), replace=True)
    lose = draw <= 0; streaks = np.zeros(sims, dtype=int); cur = np.zeros(sims, dtype=int)
    for j in range(n):
        cur = np.where(lose[:, j], cur + 1, 0); streaks = np.maximum(streaks, cur)
    out = {}
    for rk in risks:
        eq = np.cumprod(1 + draw * rk / 100.0, axis=1); peak = np.maximum.accumulate(np.concatenate([np.ones((sims, 1)), eq], axis=1), axis=1)[:, 1:]
        dd = ((peak - eq) / peak).max(axis=1) * 100; ret = (eq[:, -1] - 1) * 100
        out[str(rk)] = dict(ret_p5=round(float(np.percentile(ret, 5)), 1), ret_p50=round(float(np.percentile(ret, 50)), 1), ret_p95=round(float(np.percentile(ret, 95)), 1),
                            dd_p50=round(float(np.percentile(dd, 50)), 1), dd_p95=round(float(np.percentile(dd, 95)), 1), dd10=round(float((dd >= 10).mean() * 100), 1),
                            dd20=round(float((dd >= 20).mean() * 100), 1), losing_year=round(float((ret < 0).mean() * 100), 1))
    return dict(trades_per_year=n, sims=sims, streak_p50=int(np.percentile(streaks, 50)), streak_p95=int(np.percentile(streaks, 95)), risks=out)

def split_stats(trades, cut, field='r_net'):
    a = [t[field] for t in trades if t['entry_t'] < cut]; b = [t[field] for t in trades if t['entry_t'] >= cut]
    f = lambda s: {k: s[k] for k in ('n', 'win', 'avg', 'pf')}
    return f(stats(a)), f(stats(b))

# ------------------------------------------------------------------ the replay
def _naive(ts):
    ts = pd.Timestamp(ts); return ts.tz_convert(IST).tz_localize(None) if ts.tzinfo is not None else ts

def replay_symbol(sym, daily, h1, sector='', regimes=None, min_score=4, window_days=250, start_at=None):
    """All the trades the playbook would have opened on one stock. daily: OHLCV with a daily index; h1: hourly OHLCV (tz-aware IST)."""
    import swing, signals, strategy_scanner as sc
    d = daily.dropna(subset=['Open', 'High', 'Low', 'Close']); trades = []
    if h1 is None or len(h1) < 30 or len(d) < sc.CFG['min_bars'] + 5: return trades
    hdays = pd.DatetimeIndex([_naive(t).normalize() for t in h1.index]); h_first = hdays[0]; lows = d.Low.values
    busy_until = None; cfg = swing.CFG
    for i in range(sc.CFG['min_bars'], len(d) - 1):
        day, nxt = d.index[i], d.index[i + 1]
        if nxt < h_first or (start_at is not None and nxt < start_at): continue
        if busy_until is not None and nxt <= busy_until: continue
        w = d.iloc[max(0, i + 1 - window_days): i + 1]
        if not sc.liquid(w, sc.CFG) or bool((w.High.tail(5) == w.Low.tail(5)).any()): continue
        try: r = swing.analyse(w)
        except Exception: continue
        if not r or r.get('stage', 0) < 2: continue
        # shortcut with no effect on results: a 1H confirmation needs a touch of the zone since the BOS; if no daily low (including the
        # coming session) reached the zone top, no touch is possible, so the hourly replay of that session is skipped
        bos = pd.Timestamp(r['bos_date'][:10]); j0 = int(d.index.searchsorted(bos)) + 1
        if j0 > i + 1 or float(lows[j0:i + 2].min()) > r['zone_top']: continue
        sel = np.nonzero(hdays == pd.Timestamp(nxt).normalize())[0]
        if not len(sel): continue
        lo = int(np.searchsorted(h1.index.values, (h1.index[sel[0]] - pd.Timedelta(days=92)).to_datetime64()))
        for k in sel:
            try: rr = swing.analyse(w, h1.iloc[lo:k + 1])
            except Exception: continue
            if not rr or rr.get('stage', 0) < 4 or (rr.get('cf') or {}).get('confirm_age') != 0 or rr['score'] < min_score: continue
            entry = float(h1.Close.iloc[k]); sl = float(rr['sl']); risk = entry - sl
            if risk <= 0 or entry - rr['zone_top'] > cfg['entry_chase_atr'] * rr['atr'] * 3: continue       # confirmation far above the zone: the live scan would call it chasing
            room = rr.get('room_r'); held = []
            if rr['weekly'].get('up') is False: held.append('weekly trend against')
            if room is not None and room < cfg['min_room_r']: held.append('room under 2R')
            t_in = h1.index[k]; item = dict(symbol=sym, direction='long', label='LONG', grade=rr['grade'], score=rr['score'], entry=round(entry, 2), sl=round(sl, 2),
                                            t1=round(entry + risk, 2), t2=round(entry + 2 * risk, 2), t3=round(entry + 3 * risk, 2), stage=4, bos_date=rr['bos_date'], status='TRIGGERED')
            sig = signals.new_signal('swing', item, t_in)
            fut = h1.iloc[k + 1:]; fut = fut[fut.index <= t_in + pd.Timedelta(days=signals.SWING_EXPIRY_DAYS + 2)]
            end = min(h1.index[-1], t_in + pd.Timedelta(days=signals.SWING_EXPIRY_DAYS + 1))
            signals.walk(sig, fut, end + pd.Timedelta(hours=1))
            closed = sig['status'] == 'CLOSED'; r_g = float(sig.get('r_final', sig.get('r_now', 0.0))); cost_r = (COST_PCT / 100.0) * entry / risk
            t_out = pd.Timestamp(sig['closed']) if closed else h1.index[-1]
            trades.append(dict(sym=sym, sector=sector or 'Other', grade=rr['grade'], score=int(rr['score']), structure=int(rr['structure']), zone_q=int(rr['zone_q']), confirm=int(rr['confirm']), context=int(rr['context']),
                               entry_t=str(_naive(t_in))[:16], exit_t=str(_naive(t_out))[:16], entry=round(entry, 2), sl=round(sl, 2), risk_pct=round(100 * risk / entry, 2),
                               outcome=sig['outcome'] if closed else 'OPEN', r=round(r_g, 2), r_net=round(r_g - cost_r, 2), hold_days=int((_naive(t_out) - _naive(t_in)).days),
                               hits=len(sig['hits']), rvol=(None if rr.get('rvol') is None or (isinstance(rr['rvol'], float) and math.isnan(rr['rvol'])) else round(float(rr['rvol']), 2)),
                               weekly_up=bool(rr['weekly'].get('up')), room_r=(None if room is None else round(float(room), 2)), held=held, regime=(regimes or {}).get(str(pd.Timestamp(day).date()), 'Unknown'),
                               weekday=pd.Timestamp(nxt).strftime('%a'), closed=closed))
            busy_until = _naive(t_out).normalize()
            break
    return trades

def _work(job):
    sym, daily, h1, sector, regimes, overrides, start_at = job
    import swing
    old = {k: swing.CFG[k] for k in (overrides or {})}
    try:
        swing.CFG.update(overrides or {}); return replay_symbol(sym, daily, h1, sector, regimes, start_at=start_at)
    except Exception as ex: print(f'  backtest error {sym}: {ex}', file=sys.stderr); return []
    finally: swing.CFG.update(old)

def run_all(daily, hourly, sectors, regimes, overrides=None, workers=1, start_at=None, progress=True):
    jobs = [(s, daily[s], hourly.get(s), sectors.get(s, ''), regimes, overrides, start_at) for s in daily if s in hourly]; trades = []; t0 = time.time()
    if workers > 1 and len(jobs) > 8:
        import multiprocessing as mp
        with mp.get_context('fork').Pool(workers) as pool:
            for n, res in enumerate(pool.imap_unordered(_work, jobs, chunksize=4), 1):
                trades += res
                if progress and n % 50 == 0: print(f'  replayed {n}/{len(jobs)} stocks, {len(trades)} trades, {time.time() - t0:.0f}s', flush=True)
    else:
        for n, j in enumerate(jobs, 1):
            trades += _work(j)
            if progress and n % 50 == 0: print(f'  replayed {n}/{len(jobs)} stocks, {len(trades)} trades, {time.time() - t0:.0f}s', flush=True)
    return sorted(trades, key=lambda t: t['exit_t'])

def regime_map(nifty):
    """Market regime label for every past day, from the same classifier the Market page uses."""
    import market
    out = {}
    if nifty is None: return out
    n = nifty.dropna(subset=['Close'])
    for i in range(market.MIN_BARS if hasattr(market, 'MIN_BARS') else 60, len(n)):
        try: out[str(pd.Timestamp(n.index[i]).date())] = market.classify_daily(n.iloc[max(0, i - 260): i + 1]).get('label', 'Unknown')
        except Exception: pass
    return out

VARIANTS = [
    ('Volume 1.2x', 'Accept a 1H confirmation on 1.2x volume instead of 1.5x', dict(rvol_min=1.2)),
    ('Volume 2.0x', 'Demand 2.0x volume on the 1H confirmation', dict(rvol_min=2.0)),
    ('Stop buffer 0.15 ATR', 'A tighter buffer below the order block', dict(sl_buffer_atr=0.15)),
    ('Stop buffer 0.40 ATR', 'A wider buffer below the order block', dict(sl_buffer_atr=0.40)),
    ('Narrow zones only', 'Skip zones wider than 1.5 ATR', dict(max_zone_atr=1.5)),
]

def report(trades, variants=(), window=None, universe=0, params=None, now=None):
    """Everything the Backtest lab page shows, from the list of trades."""
    done = [t for t in trades if t['closed']]; live = [t for t in done if not t['held']]; now = now or dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    rs_net = [t['r_net'] for t in live]; span_days = 1
    if live:
        a, b = pd.Timestamp(min(t['entry_t'] for t in live)), pd.Timestamp(max(t['exit_t'] for t in live)); span_days = max(1, (b - a).days)
    per_year = len(live) * 365.0 / span_days if live else 0
    eq = []; cum = 0.0
    for t in live: cum += t['r_net']; eq.append([t['exit_t'][:10], round(cum, 2)])
    step = max(1, len(eq) // 400); eq = eq[::step] + (eq[-1:] if eq and (len(eq) - 1) % step else [])
    cut = None
    if live:
        ts = sorted(t['entry_t'] for t in live); cut = ts[int(len(ts) * 0.6)]
    order_g = ['A+', 'A', 'B']; wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    out = dict(generated_at=now.isoformat(timespec='seconds'), window=window or {}, universe=universe, params=params or {}, assumptions=ASSUMPTIONS, cost_pct=COST_PCT,
               counts=dict(all=len(trades), closed=len(done), open=len(trades) - len(done), held_back=len(done) - len(live), taken=len(live)),
               summary=dict(net=stats(rs_net), gross=stats([t['r'] for t in live]), held_back=stats([t['r_net'] for t in done if t['held']]),
                            trades_per_year=round(per_year, 1), avg_hold_days=round(float(np.mean([t['hold_days'] for t in live])), 1) if live else None,
                            outcomes={k: sum(1 for t in live if t['outcome'] == k) for k in ('TARGET', 'TRAIL', 'SL', 'EXPIRED')}),
               by=dict(grade=group(live, lambda t: t['grade'], order_g), score=group(live, lambda t: t['score'], [str(x) for x in range(10, 0, -1)]),
                       confirm=group(live, lambda t: f"{t['confirm']}/3 confirmation", ['3/3 confirmation', '2/3 confirmation', '1/3 confirmation']),
                       zone=group(live, lambda t: f"zone quality {t['zone_q']}/2", ['zone quality 2/2', 'zone quality 1/2', 'zone quality 0/2']),
                       context=group(live, lambda t: f"{t['context']}/3 context", ['3/3 context', '2/3 context', '1/3 context', '0/3 context']),
                       regime=group(live, lambda t: t['regime']), sector=group(live, lambda t: t['sector'])[:14], weekday=group(live, lambda t: t['weekday'], wd),
                       month=group(live, lambda t: t['exit_t'][:7], sorted({t['exit_t'][:7] for t in live})),
                       volume=group(live, lambda t: 'no volume data' if t['rvol'] is None else ('2x or more' if t['rvol'] >= 2 else '1.5x to 2x' if t['rvol'] >= 1.5 else 'under 1.5x'), ['2x or more', '1.5x to 2x', 'under 1.5x', 'no volume data']),
                       stop=group(live, lambda t: 'stop under 3%' if t['risk_pct'] < 3 else 'stop 3% to 6%' if t['risk_pct'] < 6 else 'stop over 6%', ['stop under 3%', 'stop 3% to 6%', 'stop over 6%'])),
               equity=eq, split=dict(cut=cut, train=split_stats(live, cut)[0], test=split_stats(live, cut)[1]) if cut else None,
               montecarlo=monte_carlo(rs_net, per_year), variants=[],
               trades=[{k: t[k] for k in ('sym', 'grade', 'score', 'entry_t', 'exit_t', 'entry', 'sl', 'outcome', 'r', 'r_net', 'hold_days', 'regime', 'sector')} for t in live][-600:])
    base = stats(rs_net)
    for name, desc, vt in variants:
        v = [t for t in vt if t['closed'] and not t['held']]
        if cut: tr, te = split_stats(v, cut)
        else: tr = te = {k: stats([])[k] for k in ('n', 'win', 'avg', 'pf')}
        b_tr, b_te = (out['split']['train'], out['split']['test']) if out['split'] else (None, None)
        better = bool(b_tr and tr['avg'] is not None and te['avg'] is not None and b_tr['avg'] is not None and b_te['avg'] is not None and tr['avg'] > b_tr['avg'] and te['avg'] > b_te['avg'] and te['n'] >= 20)
        out['variants'].append(dict(name=name, desc=desc, all={k: stats([t['r_net'] for t in v])[k] for k in ('n', 'win', 'avg', 'pf')}, train=tr, test=te, better=better,
                                    verdict='Better in both halves: worth considering' if better else 'Not better in both halves: keep your current rule'))
    out['base'] = {k: base[k] for k in ('n', 'win', 'avg', 'pf')}
    return out

def regime_edge(bt, label, min_n=30):
    """Item 14: how the playbook did in this market regime in the backtest, or None when there is not enough evidence."""
    for r in ((bt or {}).get('by') or {}).get('regime', []):
        if r['k'] == label and r['n'] >= min_n and r['avg'] is not None:
            verdict = 'weak' if r['avg'] < 0 else 'strong' if r['avg'] >= 0.25 else 'ok'
            return dict(label=label, n=r['n'], avg=r['avg'], win=r['win'], verdict=verdict)
    return None

def notify_result(out, status):
    """One phone message when the weekly backtest finishes (or fails)."""
    import notify
    topic = os.environ.get('NTFY_TOPIC', '').strip(); page = os.environ.get('PAGE_URL', '').strip().rstrip('/'); ok = status == 'success'
    if not topic and not notify.telegram_ready(): print('backtest: no alert channel configured'); return 0
    try:
        s = json.load(open(os.path.join(out, 'backtest.json')))['summary']['net']
        body = f"{s['n']} trades · win {s['win']}% · expectancy {s['avg']}R after costs · profit factor {s['pf']} · max drawdown {s['max_dd']}R"
    except Exception: body = 'No result file was written.'; ok = False
    try: notify.post(os.environ.get('NTFY_URL', 'https://ntfy.sh').rstrip('/'), topic, 'Backtest finished' if ok else 'Backtest failed', body if ok else 'Open the run in GitHub Actions to see why.', 'bar_chart' if ok else 'warning', (page + '/#/backtest') if page else '')
    except Exception as ex: print(f'backtest: push failed: {ex}', file=sys.stderr)
    return 0

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='pub/data'); ap.add_argument('--notify', default=None, help='only send the result message; pass the job status'); ap.add_argument('--top', type=int, default=250, help='most liquid N stocks of the Nifty 500 (0 = all)')
    ap.add_argument('--variants', action='store_true', help='also test the rule variants (on the 120 most liquid stocks)'); ap.add_argument('--workers', type=int, default=max(1, min(4, os.cpu_count() or 1)))
    a = ap.parse_args(argv); t0 = time.time()
    if a.notify is not None: return notify_result(a.out, a.notify)
    import strategy_scanner as sc
    now = pd.Timestamp.now(tz=IST); syms, note, industries = sc.load_nifty500('nifty500.csv', 'watchlist.txt'); print(f'backtest: {note}', flush=True)
    raw, _ = sc.yahoo_many(syms, '3y', '1d'); daily = {s: sc.tidy_daily(f, now) for s, f in raw.items()}
    turn = {s: float((f.Close * f.Volume).tail(60).mean()) for s, f in daily.items() if len(f) > 260}
    pick = sorted(turn, key=lambda s: -turn[s]); pick = pick[:a.top] if a.top else pick
    print(f'backtest: {len(pick)} stocks, downloading two years of hourly candles', flush=True)
    hraw, _ = sc.yahoo_many(pick, '730d', '1h'); hourly = {s: sc.tidy_intraday(f, now, 60) for s, f in hraw.items()}
    nraw, _ = sc.yahoo_many(['^NSEI'], '3y', '1d'); regimes = regime_map(sc.tidy_daily(nraw['^NSEI'], now)) if '^NSEI' in nraw else {}
    dsel = {s: daily[s] for s in pick if s in hourly}
    print(f'backtest: replaying {len(dsel)} stocks on {a.workers} cores', flush=True)
    trades = run_all(dsel, hourly, industries, regimes, workers=a.workers)
    var = []
    if a.variants:
        small = {s: dsel[s] for s in list(dsel)[:120]}
        for name, desc, ov in VARIANTS:
            print(f'backtest: variant "{name}"', flush=True); var.append((name, desc, run_all(small, hourly, industries, regimes, overrides=ov, workers=a.workers, progress=False)))
        base_small = [t for t in trades if t['sym'] in small]
    first = min((str(h.index[0])[:10] for h in hourly.values() if len(h)), default=''); last = max((str(h.index[-1])[:10] for h in hourly.values() if len(h)), default='')
    rep = report(trades, var, window={'from': first, 'to': last}, universe=len(dsel), params=dict(top=a.top, variants=bool(a.variants), variant_universe=120 if a.variants else 0, seconds=round(time.time() - t0)))
    if a.variants and rep.get('split'):                       # variants are compared with the base rule on the same 120 stocks
        cut = rep['split']['cut']; b = [t for t in base_small if t['closed'] and not t['held']]; tr, te = split_stats(b, cut)
        rep['variant_base'] = dict(all={k: stats([t['r_net'] for t in b])[k] for k in ('n', 'win', 'avg', 'pf')}, train=tr, test=te)
        for v in rep['variants']:
            v['better'] = bool(v['train']['avg'] is not None and v['test']['avg'] is not None and tr['avg'] is not None and te['avg'] is not None and v['train']['avg'] > tr['avg'] and v['test']['avg'] > te['avg'] and v['test']['n'] >= 20)
            v['verdict'] = 'Better in both halves: worth considering' if v['better'] else 'Not better in both halves: keep your current rule'
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'backtest.json'), 'w') as f: json.dump(rep, f, separators=(',', ':'), default=str)
    s = rep['summary']['net']; print(f"backtest: {s['n']} trades, win {s['win']}%, expectancy {s['avg']}R net, profit factor {s['pf']}, max drawdown {s['max_dd']}R, {time.time() - t0:.0f}s")
    return 0

if __name__ == '__main__':
    sys.exit(main())
