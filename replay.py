"""Replay a past trading day of the Nifty options playbook, candle by candle (item 18, 25 Nov 2026).

For every closed 5-minute candle of the day it runs the SAME engine the live loop runs (strategy_scanner.scan_intraday with the options
section and the 1H alignment hold), using only the candles that existed at that moment, and records what the scanner would have said.
It settles "was a trigger missed?" with evidence instead of memory. Nothing is traded, tracked or alerted, and no rule is changed.

Yahoo keeps about 60 days of 5-minute Nifty candles, so any day in that window can be replayed. The day's candles are saved with the result,
so the replay can be read again later even after Yahoo drops them.

    python replay.py --date 2026-11-23 --out pub/data          # writes data/replay/options_2026-11-23.json and updates data/replay/index.json
"""
import argparse, datetime as dt, json, os, sys
import pandas as pd
import strategy_scanner as sc

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
IST_NAME = 'Asia/Kolkata'


def _upto(df, close_at, minutes):
    """Candles whose bar has CLOSED by close_at (index = bar start)."""
    if df is None or not len(df): return df
    return df[df.index + pd.Timedelta(minutes=minutes) <= close_at]


def replay_day(df5, df15, h1, day, min_score=6, cfg=None, levels=None):
    """df5 / df15 / h1: Nifty candles indexed by IST bar start, covering `day` and enough history before it. Returns the replay document."""
    cfg = cfg or sc.CFG_I; day = pd.Timestamp(day).date()
    bars = df5[[d == day for d in df5.index.date]]
    rows = {'CALL': [], 'PUT': []}; first = {}; last = {}
    for ts in bars.index:
        close_at = ts + pd.Timedelta(minutes=5)
        a5 = _upto(df5, close_at, 5); a15 = _upto(df15, close_at, 15); a1 = _upto(h1, close_at, 60)
        if a5 is None or len(a5) < 30 or a15 is None or len(a15) < 3: continue
        lv = levels(a5) if levels else sc.prev_day_levels(a5)
        for side, label in (('long', 'CALL'), ('short', 'PUT')):
            try:
                ex = ['PDH/PDL sweep'] if sc.pdl_sweep(a15, a5, side) else []
                r = sc.scan_intraday(a5, a15, side, cfg, lv, extra_ticks=ex, section='options', h1=a1)
            except Exception as e:
                r = dict(state='error', note=str(e)[:120])
            if r and 'zone_bot' in r and r.get('score', 0) >= min_score:
                st = r.get('status', '')
                aligned = None if a1 is None or len(a1) < 10 else (a1.Close.iloc[-1] > sc.ema(a1.Close, 9).iloc[-1]) == (side == 'long')
                if aligned is False and st == 'TRIGGERED': st = 'WATCH (1H against)'
                rec = dict(t=close_at.strftime('%H:%M'), status=st, score=r.get('score'), grade=r.get('grade'), entry=_r(r.get('entry')), sl=_r(r.get('sl')), t1=_r(r.get('t1')))
            else:
                rec = dict(t=close_at.strftime('%H:%M'), status=sc.REASON.get((r or {}).get('state'), 'No setup.') if hasattr(sc, 'REASON') else 'No setup.', score=(r or {}).get('score'))
            key = (rec.get('status'), rec.get('score'))
            if last.get(label) != key: rows[label].append(rec); last[label] = key           # only the candles where something changed
            if rec.get('status') == 'TRIGGERED' and label not in first: first[label] = rec
    ema9 = sc.ema(df5.Close, 9)
    day_c = df5.loc[bars.index]
    return dict(date=str(day), section='options', generated_at=dt.datetime.now(IST).isoformat(timespec='seconds'), bars=int(len(bars)),
                sides=rows, first_trigger=first,
                chart=dict(tf='5m', times=[x.strftime('%Y-%m-%d %H:%M') for x in day_c.index],
                           candles=[[_r(a), _r(b), _r(c), _r(d)] for a, b, c, d in zip(day_c.Open, day_c.High, day_c.Low, day_c.Close)],
                           ema=[_r(v) for v in ema9.loc[bars.index]]),
                note='Replayed with the live options engine on the candles available at each moment. Nothing was traded or tracked.')


def _r(v):
    try: return None if v is None or v != v else round(float(v), 2)
    except Exception: return None


def write(out, doc):
    d = os.path.join(out, 'replay'); os.makedirs(d, exist_ok=True)
    json.dump(doc, open(os.path.join(d, f"options_{doc['date']}.json"), 'w'))
    ip = os.path.join(d, 'index.json')
    try: idx = json.load(open(ip))
    except Exception: idx = dict(days=[])
    idx['days'] = sorted({*idx.get('days', []), doc['date']}, reverse=True)[:40]; idx['updated'] = doc['generated_at']
    json.dump(idx, open(ip, 'w'))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--date', default=''); ap.add_argument('--out', default='pub/data'); ap.add_argument('--min-score', type=int, default=6)
    a = ap.parse_args(argv)
    day = pd.Timestamp(a.date).date() if a.date else dt.datetime.now(IST).date()
    end = pd.Timestamp(day).tz_localize(IST_NAME) + pd.Timedelta(hours=23)
    d5, _ = sc.download_many(['^NSEI'], '60d', '5m'); d15, _ = sc.download_many(['^NSEI'], '60d', '15m'); d1, _ = sc.download_many(['^NSEI'], '3mo', '1h')
    if '^NSEI' not in d5 or '^NSEI' not in d15: print('No Nifty candles downloaded: nothing replayed.', file=sys.stderr); return 2
    df5 = sc.tidy_intraday(d5['^NSEI'], end, 5); df15 = sc.tidy_intraday(d15['^NSEI'], end, 15); h1 = sc.tidy_intraday(d1['^NSEI'], end, 60) if '^NSEI' in d1 else None
    df5 = df5[df5.index < end]; df15 = df15[df15.index < end]; h1 = h1[h1.index < end] if h1 is not None else None
    if not any(d == day for d in df5.index.date): print(f'No 5-minute candles for {day} (holiday, weekend, or older than about 60 days).', file=sys.stderr); return 2
    doc = replay_day(df5, df15, h1, day, a.min_score); write(a.out, doc)
    print(f"replay {day}: {doc['bars']} candles, first trigger CALL {doc['first_trigger'].get('CALL', {}).get('t', '-')} PUT {doc['first_trigger'].get('PUT', {}).get('t', '-')}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
