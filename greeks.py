"""Black-Scholes Greeks and strike selection for Nifty weekly options (theoretical, not live quotes).

Inputs are the index spot, India VIX as the implied-volatility proxy and the time to expiry.
Real premiums differ with the volatility skew and the bid-ask spread, so always compare with the live option chain.
Greeks used: delta, gamma, theta, vega (this is what 'alpha' usually means in option talk: there is no Greek called alpha)."""
import datetime as dt
import math

R_FREE = 0.056        # about the India 91-day T-bill yield
Q_DIV = 0.013         # Nifty dividend yield
HOURS_PER_DAY = 6.25  # trading hours (09:15 to 15:30)
STEP = 50             # Nifty strike step
LOT_SIZE = 65         # Nifty lot size from the January 2026 series (NSE circular). Edit on the page if it changes.
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

def _pdf(x): return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)
def _cdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def bs(S, K, T, sigma, kind, r=R_FREE, q=Q_DIV):
    """Price and Greeks. kind is 'CE' (call) or 'PE' (put). theta is per calendar day, vega per 1 volatility point."""
    call = kind == 'CE'
    if T <= 1e-9 or sigma <= 0:
        v = max(S - K, 0.0) if call else max(K - S, 0.0)
        return dict(price=v, delta=(1.0 if S > K else 0.0) if call else (-1.0 if S < K else 0.0), gamma=0.0, theta=0.0, vega=0.0)
    sq = sigma * math.sqrt(T); d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / sq; d2 = d1 - sq
    eq, er = math.exp(-q * T), math.exp(-r * T)
    gamma = eq * _pdf(d1) / (S * sq); vega = S * eq * _pdf(d1) * math.sqrt(T)
    decay = -S * eq * _pdf(d1) * sigma / (2 * math.sqrt(T))
    if call:
        price = S * eq * _cdf(d1) - K * er * _cdf(d2); delta = eq * _cdf(d1)
        theta = decay - r * K * er * _cdf(d2) + q * S * eq * _cdf(d1)
    else:
        price = K * er * _cdf(-d2) - S * eq * _cdf(-d1); delta = -eq * _cdf(-d1)
        theta = decay + r * K * er * _cdf(-d2) - q * S * eq * _cdf(-d1)
    return dict(price=price, delta=delta, gamma=gamma, theta=theta / 365.0, vega=vega / 100.0)

def _to_date(x): return x if isinstance(x, dt.date) and not isinstance(x, dt.datetime) else dt.date.fromisoformat(str(x)[:10])

def weekly_expiry(now, holidays=()):
    """Next Nifty weekly expiry: every Tuesday 15:30 IST, moved to the previous trading day when Tuesday is a holiday."""
    hol = {_to_date(h) for h in holidays}
    d = now.date()
    while True:
        if d.weekday() == 1:
            e = d
            while e.weekday() >= 5 or e in hol: e -= dt.timedelta(days=1)
            if dt.datetime.combine(e, dt.time(15, 30), tzinfo=IST) > now: return e
        d += dt.timedelta(days=1)

def days_to_expiry(now, expiry):
    return max((dt.datetime.combine(expiry, dt.time(15, 30), tzinfo=IST) - now).total_seconds() / 86400.0, 1e-4)

def choose_expiry(now, holidays=()):
    """Use the nearest weekly unless it is under 2 days away (gamma and theta get violent), then the next one."""
    e1 = weekly_expiry(now, holidays); d1 = days_to_expiry(now, e1)
    if d1 >= 2.0: return e1, d1, f'Nearest weekly expiry {e1:%d %b}'
    e2 = weekly_expiry(dt.datetime.combine(e1 + dt.timedelta(days=1), dt.time(9, 0), tzinfo=IST), holidays)
    return e2, days_to_expiry(now, e2), f'Next weekly expiry {e2:%d %b} (the nearest, {e1:%d %b}, is under 2 days away)'

def reprice(S, K, T_days, sigma, kind, hold_hours):
    """Premium after the index has moved to S and `hold_hours` of trading time have passed."""
    return bs(S, K, max(T_days - hold_hours / HOURS_PER_DAY, 1e-4) / 365.0, sigma, kind)['price']

def pick_strike(side, spot, entry, sl, targets, vix, now, holidays=(), hold_hours=0.75):
    """side is 'long' (buy a CALL) or 'short' (buy a PUT). entry, sl and targets are index levels.
    Returns the recommended strike, its Greeks, premium estimates at SL/T1/T2/T3 and five candidates."""
    kind = 'CE' if side == 'long' else 'PE'; iv_src = 'India VIX'
    if not vix or vix <= 0: vix, iv_src = 14.0, 'assumed 14 (India VIX unavailable)'
    sigma = vix / 100.0; expiry, dte, why_exp = choose_expiry(now, holidays); T = dte / 365.0
    late = (now.hour * 60 + now.minute) >= 14 * 60
    lo, hi = (0.50, 0.70) if (late or dte < 3) else (0.40, 0.60)
    atm = round(entry / STEP) * STEP; rows = []
    for k in range(-2, 3):
        K = atm + k * STEP; g = bs(entry, K, T, sigma, kind); p0 = g['price']
        if p0 < 5: continue
        sl_p = reprice(sl, K, dte, sigma, kind, 0.5); t_p = [reprice(t, K, dte, sigma, kind, hold_hours * (i + 1)) for i, t in enumerate(targets)]
        loss = max(p0 - sl_p, 0.01); gain1 = t_p[0] - p0
        itm = (entry - K) if kind == 'CE' else (K - entry)
        rows.append(dict(strike=int(K), kind=kind, moneyness=('ATM' if abs(itm) < STEP / 2 else f"{'ITM' if itm > 0 else 'OTM'} {int(abs(itm))}"), premium=p0, delta=abs(g['delta']), gamma=g['gamma'],
                         theta_day=g['theta'], theta_hour=g['theta'] / HOURS_PER_DAY, theta_pct_hour=100 * abs(g['theta']) / HOURS_PER_DAY / p0, vega=g['vega'],
                         premium_sl=sl_p, premium_targets=t_p, loss=loss, gain_t1=gain1, rr_t1=gain1 / loss))
    if not rows: raise ValueError('no strikes priced')
    ok = [r for r in rows if lo <= r['delta'] <= hi and r['premium'] >= 20 and r['theta_pct_hour'] <= 4.0] or [r for r in rows if lo <= r['delta'] <= hi] or rows
    best = max(ok, key=lambda r: (round(r['rr_t1'], 3), r['delta']))
    for r in rows: r['recommended'] = r is best
    be = best['premium'] / best['delta']
    reasons = [why_exp + f" ({dte:.1f} days to go).",
               f"Delta {best['delta']:.2f}: the option moves about {best['delta']:.2f} points for every index point in your favour (target band {lo:.2f} to {hi:.2f}" + (', late in the day or short-dated, so we pay for delta rather than theta)' if (late or dte < 3) else ').'),
               f"Gamma {best['gamma']:.4f}: delta rises about {best['gamma'] * 50:.2f} after a 50-point move your way, so winners accelerate and losers hurt less.",
               f"Theta {best['theta_day']:.1f} per day (about {best['theta_hour']:.1f} per trading hour, {best['theta_pct_hour']:.1f}% of the premium): time is the cost of waiting, so exit if the move stalls.",
               f"Vega {best['vega']:.1f} per volatility point: a 1-point fall in India VIX costs about {best['vega']:.1f} per unit, so avoid buying right before events that crush volatility.",
               f"The index must move about {be:.0f} points your way just to recover the premium (premium divided by delta).",
               f"Volatility input: {iv_src} {vix:.1f}, held constant. These are model prices: compare with the live chain before you place the order."]
    return dict(side=side, kind=kind, instrument=f"NIFTY {best['strike']} {kind}", expiry=expiry.isoformat(), dte_days=round(dte, 2), iv=vix, iv_source=iv_src, hold_hours=hold_hours,
                lot_size=LOT_SIZE, delta_band=[lo, hi], strike=best['strike'], premium=best['premium'], delta=best['delta'], gamma=best['gamma'], theta_day=best['theta_day'],
                theta_hour=best['theta_hour'], vega=best['vega'], premium_sl=best['premium_sl'], premium_targets=best['premium_targets'], breakeven_points=be, reasons=reasons, candidates=rows)
