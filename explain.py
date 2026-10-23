"""Plain-English logic, execution steps and trailing plan for every setup. Pure text from the numbers, no guesses."""

def _n(v, d=2):
    if v is None: return '-'
    s = f'{v:,.{d}f}'
    return s[:-3] if d == 2 and s.endswith('.00') else s

def _words(direction):
    up = direction == 'long'
    return dict(up=up, trend='up' if up else 'down', old='down' if up else 'up', above='above' if up else 'below', below='below' if up else 'above', lh='lower high' if up else 'higher low',
                ob_candle='down' if up else 'up', zone_kind='demand' if up else 'supply', high='high' if up else 'low', support='support' if up else 'resistance', hl='higher low' if up else 'lower high',
                buy='buy' if up else 'sell short', sell='sell' if up else 'buy back', rise='rises' if up else 'falls', ema_side='above' if up else 'below')

TICK_TEXT = {
    'key level': 'A round number, previous-day high/low or the broken structure level sits inside the zone, so more orders cluster there.',
    'fib': 'The zone overlaps the 0.618 to 0.705 retracement of the impulse leg: the classic "discount" area where pullbacks often end.',
    'MTF EMA': 'Price is on the trend side of the 9 EMA on the trigger timeframe and the one above it, so the timeframes agree.',
    'weekly trend': 'The weekly chart is rising (close above a rising 9 EMA), so you are buying with the higher timeframe.',
    'Nifty trend': 'Nifty itself is above its 21 EMA: the broad market is not working against a long.',
    'order block (15m)': 'The 15m order block (last opposite candle before the 15m CHoCH) overlaps the 5m zone: two timeframes defend the same price.',
    'PDH/PDL sweep': 'Earlier today a 15m candle wicked through the previous-day low (calls) or high (puts) and closed back inside: liquidity was taken before the move.'}

def build_logic(section, it, r):
    d = it['direction']; w = _words(d); idx = section == 'options'; dec = 1 if idx else 2; f = lambda v: _n(v, dec); out = []
    tf_s = {'swing': '1D', 'options': '5m', 'intraday': '5m'}[section]; tf_t = {'swing': '1H', 'options': '5m', 'intraday': '5m'}[section]
    if section != 'swing':
        out.append(dict(title='15m bias', text=f"On the 15m, the latest structure break is {w['trend']}: price closed {w['above']} {f(r.get('b15_level'))} on {r.get('b15_date', '-')} ({r.get('b15_kind', 'CHoCH')}), so the 15m has turned {w['trend']} and is still {w['trend']}. "
                                              f"That is the only 15m requirement here. It stays valid while price does not trade {w['below']} {f(r.get('b15_base'))}."))
    leg = r.get('leg', 1) or 1
    out.append(dict(title=f'{tf_s} structure', text=f"On the {tf_s}, price broke {w['above']} the {w['lh']} at {f(it.get('choch_level'))} on {it.get('choch_date')} (CHoCH), then pushed through {f(it.get('bos_level'))} on {it.get('bos_date')} with a strong displacement candle (BOS" + (f" number {leg}: the trend broke structure again after a pullback, so this is a continuation zone" if leg > 1 else '') + "). "
                                                    f"Two steps in a row mean the {tf_s} trend has really changed from {w['old']} to {w['trend']}, not just bounced."))
    zone = f"The order block {f(it.get('ob_low'))} to {f(it.get('ob_high'))} (the last {w['ob_candle']} candle before the displacement)"
    if it.get('fvg_low') is not None: zone += f" and the fair value gap {f(it['fvg_low'])} to {f(it['fvg_high'])} (the gap the move left behind)"
    zone += f" form the entry zone {f(it['zone_bot'])} to {f(it['zone_top'])}. " + ('They overlap, which makes the zone stronger. ' if it.get('zone_q') == 2 else 'Only one of the two is present, so the zone is a notch weaker. ') + f"Unfilled orders usually wait in a {w['zone_kind']} zone, which is why price tends to react there."
    out.append(dict(title='Entry zone', text=zone))
    pb = r.get('pullback_low'); out.append(dict(title='Pullback', text=f"Price has come back to {f(it['price'])}, inside or just {w['above']} the zone" + (f", and the pullback {w['high'] if not w['up'] else 'low'} so far is {f(pb)}" if pb is not None and pb == pb else '') + ". Buying a pullback instead of the breakout gives a close stop and a better reward-to-risk."))
    got = []; miss = []
    (got if r.get('rejection') else miss).append(f"a {tf_t} rejection candle in the zone (long wick, close back {w['above']} the middle)")
    (got if r.get('reclaim') else miss).append(f"a {tf_t} close back {w['ema_side']} the 9 EMA")
    if section != 'options': (got if r.get('rvol_ok') else miss).append('volume at least 1.5 times normal on the trigger candle' + (' for that time of day' if section == 'swing' else ''))
    conf = ('Confirmed: ' + '; '.join(got) + '. ' if got else '') + ('Still missing: ' + '; '.join(miss) + '. ' if miss else '')
    conf += 'The entry is the close of the trigger candle.' if it['status'] == 'TRIGGERED' else 'Do not enter until every item is in: waiting costs a little price and saves a lot of bad trades.'
    out.append(dict(title='Confirmation', text=conf))
    ic = it.get('index_check')
    if ic and section == 'swing':
        where = f"{it.get('sector') or (ic.get('sector_index') or 'its group')}"
        base = f"The stock belongs to {where}, tracked by {ic['sector_index']}" + (' (built from the Nifty 500 stocks in the same industry because no index data was available)' if ic.get('source') == 'basket' else '') + '. '
        if ic['state'] == 'falling': tail = 'It is falling: ' + '; '.join(ic['reasons']) + '. A stock rarely holds a long when its whole group is selling, so the trade is held at WATCH until the index stabilises.'
        elif ic['state'] == 'unknown': tail = 'Index data was not available this run: check the index chart yourself before you buy.'
        else: tail = 'It is ' + ('strong' if ic['state'] == 'strong' else 'holding up') + ': ' + '; '.join(ic['reasons']) + (f", {ic['today']:+.1f}% today" if ic.get('today') is not None else '') + '. The group is not working against the trade.'
        out.append(dict(title='Sector index confirmation', text=base + tail))
    if it.get('ticks'):
        out.append(dict(title='Confluences', text=' '.join(f"{t[:1].upper() + t[1:]}: {TICK_TEXT.get(t, '')}" for t in it['ticks'])))
    out.append(dict(title='Stop-loss', text=f"SL {f(it['sl'])} sits {w['below']} the order block and the pullback extreme with a 0.25 ATR buffer. If price trades through it, the {tf_s} structure is broken and the idea is wrong, so you leave with a small, planned loss. Risk to the stop is {_n(it.get('risk_pct'), 1)}% of price" + ('' if idx else '.')))
    out.append(dict(title='Targets', text=f"T1 {f(it['t1'])} is the previous swing {w['high']} where resting orders sit ({_n(it.get('r_t1'), 1)}R). T2 {f(it['t2'])} is 2R and T3 {f(it['t3'])} is 3R. Take part profit at T1 and let the rest run with a trailing stop."))
    ot = it.get('options_trade')
    if ot:
        out.append(dict(title='Strike choice (Greeks)', text=' '.join(ot['reasons'])))
    cautions = list(it.get('notes') or [])
    if it.get('sector'): cautions.append(f"sector {it['sector']} is {it.get('sector_state', 'neutral')}" + (f", {it['rs20']:+.1f}% vs Nifty over 20 days" if it.get('rs20') is not None else ''))
    if (it.get('results') or {}).get('days') is not None: cautions.append(f"results in {it['results']['days']} day(s) on {it['results']['date']}")
    if cautions: out.append(dict(title='Cautions', text='; '.join(c[:1].upper() + c[1:] for c in cautions) + '.'))
    return out

def build_plan(section, it):
    """Execution steps, the trailing plan and chart marks. All prices are levels you can place as orders or alerts."""
    d = it['direction']; w = _words(d); idx = section == 'options'; dec = 1 if idx else 2; f = lambda v: _n(v, dec)
    e, sl, t1, t2, t3 = it['entry'], it['sl'], it['t1'], it['t2'], it['t3']; risk = abs(e - sl); ot = it.get('options_trade'); sym = it['symbol']; side = 'buy' if d == 'long' else 'sell short'
    zone_edge = it['zone_bot'] if d == 'long' else it['zone_top']
    marks = [dict(label='T1: take half, SL to entry', price=t1, at='t1'), dict(label='T2: SL to T1', price=t2, at='t2'), dict(label='T3: exit or trail', price=t3, at='t3')]
    if section == 'swing':
        ex = [f"Size: quantity = your risk in rupees divided by {f(risk)} (entry minus stop). The page calculator does this for you.",
              f"Order: BUY {sym} as a delivery (CNC) limit order at {f(e)}, no higher than {f(e + 0.1 * (it.get('atr') or 0) if it.get('atr') else e)}. If the day ends unfilled, cancel it and look again tomorrow. Do not chase.",
              f"Protect at once: stop-loss at {f(sl)}. For delivery trades place a GTT (OCO) with the trigger at {f(sl)} and the target at {f(t1)}, so the exchange holds your exit even when you are offline.",
              f"Exit plan: sell half at T1 {f(t1)}, a quarter at T2 {f(t2)}, trail the rest."]
        tr = [dict(when='Order filled', action=f"Stop at {f(sl)}. It only ever moves in your favour, never down."), dict(when=f"Price reaches T1 {f(t1)}", action=f"Sell half. Move the stop to entry {f(e)} (cost). The trade is now free."),
              dict(when=f"Price reaches T2 {f(t2)}", action=f"Sell a quarter. Move the stop to T1 {f(t1)} to lock in profit."),
              dict(when='After T2', action='Trail the last quarter under each new 1H higher low, or exit on a daily close below the 9 EMA. Exit at T3 ' + f(t3) + '.'),
              dict(when=f"A daily close {w['below']} the zone edge {f(zone_edge)}", action='The pullback has failed. Exit even if the stop has not been hit.'),
              dict(when=f"{(it.get('index_check') or {}).get('sector_index', 'The sector index')} closes below its 21 EMA (daily)", action='Sell half: the group is turning against the trade. Sell the rest if the stock also loses its 9 EMA.'),
              dict(when='Results or big news within 2 days', action='Exit or cut to a quarter size. Your rule: no event risk in the hold.')]
        rules = ['Never widen the stop.', 'Daily limit: stop trading after two losses.', 'India: avoid adding after a 5% or larger one-day move; circuit-limit stocks can lock you in, so stay with liquid names.']
    elif section == 'intraday':
        ex = [f"Size: quantity = risk in rupees divided by {f(risk)}. Check the stock's margin and make sure the trade fits your daily loss limit.",
              f"Order: {side.upper()} {sym} (MIS) with a limit order at {f(e)}. If the next 5m candle closes {w['above']} the trigger candle's extreme without filling, skip it.",
              f"Protect at once: SL-M (or SL-L) at {f(sl)}.", f"Targets: half at T1 {f(t1)}, a quarter at T2 {f(t2)}, trail the rest. No new entries after 14:45."]
        tr = [dict(when='Order filled', action=f"Stop at {f(sl)}."), dict(when=f"Price reaches T1 {f(t1)}", action=f"Book half. Move the stop to entry {f(e)}."), dict(when=f"Price reaches T2 {f(t2)}", action=f"Book a quarter. Move the stop to T1 {f(t1)}."),
              dict(when='After T2', action=f"Trail under each new 5m {w['hl']}, or exit on a 5m close {w['below']} the 9 EMA."), dict(when='15:10', action='Square off whatever is left. Brokers auto-square MIS around 15:15 to 15:20 and charge for it.'),
              dict(when='No progress in 8 candles (40 minutes)', action='Exit at the market. A setup that does not move is a setup that failed.')]
        rules = ['Never widen the stop.', 'Stop for the day after two losses.', 'Skip the first 15 minutes of the session.']
    else:
        ot = ot or {}; unit = ot.get('instrument', f'NIFTY {"CE" if d == "long" else "PE"}'); p0 = ot.get('premium'); psl = ot.get('premium_sl'); pt = ot.get('premium_targets') or [None] * 3
        ex = [f"Strike: buy {unit} (expiry {ot.get('expiry', '-')}). Model premium {f(p0) if p0 else '-'}; check the live price and skip or size down if it is more than 15% above the model (volatility spiked).",
              f"Size: lots = risk in rupees divided by (premium risk per unit x lot size {ot.get('lot_size', 65)}). Premium risk per unit is about {f((p0 or 0) - (psl or 0)) if p0 else '-'} at the stop.",
              f"Order: limit at or near the ask when the {it['tf_trigger']} trigger candle closes. Market orders on options can fill far from the quote.",
              f"Stop: exit if a {it['tf_trigger']} candle closes {w['below']} the index level {f(sl)}. Set a TradingView alert on the index; the option stop is about {f(psl) if psl else '-'}.",
              f"Exit plan: half at index T1 {f(t1)} (about {f(pt[0]) if pt[0] else '-'}), a quarter at T2 {f(t2)}, trail the rest on the 5m 9 EMA."]
        tr = [dict(when='Order filled', action=f"Index stop {f(sl)} (premium about {f(psl) if psl else '-'}). Never average down."), dict(when=f"Index reaches T1 {f(t1)}", action='Sell half. Move the stop to your cost price.'),
              dict(when=f"Index reaches T2 {f(t2)}", action=f"Sell a quarter. Move the stop to the T1 level {f(t1)} on the index."), dict(when='After T2', action=f"Trail under each new 5m {w['hl']} or exit on a 5m close {w['below']} the 9 EMA."),
              dict(when='No progress in 6 to 8 candles (30 to 40 minutes)', action='Exit. Theta is working against you every minute you wait.'),
              dict(when='15:10', action='Exit everything. Do not carry weekly options overnight.')]
        rules = ['Never widen the stop and never average down an option.', 'Expiry day: no new buys after lunch, or size down hard.', 'Stop for the day after two losses.']
    return dict(execution=ex, trail=tr, rules=rules, marks=marks)
