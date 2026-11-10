"""A clean chart picture for a phone alert (item 15): the last candles with only the levels that matter (zone, entry, stop, T1, T2).
Black-and-white candles (up hollow, down solid) to match the app; a muted red stop and muted green targets."""
import io

def pick_tf(charts, order=('15m', '1H', '5m', '1D')):
    """The most precise timeframe that has candles. charts = {'1D': {...}, '1H': {...}, ...}; returns (name, tf) or (None, None)."""
    for k in order:
        tf = (charts or {}).get(k)
        if tf and tf.get('candles'): return k, tf
    for k, tf in (charts or {}).items():
        if isinstance(tf, dict) and tf.get('candles'): return k, tf
    return None, None

def render(tf, levels, title='', bars=70):
    """tf = dict(times, candles=[[o,h,l,c],...], ema=[...]); levels = dict(entry, sl, t1, t2, zone_bot, zone_top). Returns PNG bytes, or None."""
    try:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
    except Exception: return None
    C = (tf.get('candles') or [])[-bars:]
    if len(C) < 5: return None
    n = len(C); ema = (tf.get('ema') or [])[-n:]; times = (tf.get('times') or [])[-n:]
    lv = {k: float(v) for k, v in (levels or {}).items() if isinstance(v, (int, float)) and v == v}
    ink, good, bad = '#000000', '#1E7A46', '#B3261E'
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=110); fig.patch.set_facecolor('white'); ax.set_facecolor('white')
    for i, (o, h, l, c) in enumerate(C):
        ax.plot([i, i], [l, h], color=ink, linewidth=0.8, zorder=2)
        ax.add_patch(Rectangle((i - 0.32, min(o, c)), 0.64, max(abs(c - o), (h - l) * 0.02 + 1e-9), facecolor='white' if c >= o else ink, edgecolor=ink, linewidth=0.8, zorder=3))
    if len(ema) == n and all(isinstance(x, (int, float)) for x in ema): ax.plot(range(n), ema, color='#8A8A8A', linewidth=1.0, zorder=1)
    if 'zone_bot' in lv and 'zone_top' in lv: ax.axhspan(lv['zone_bot'], lv['zone_top'], color='#000000', alpha=0.07, zorder=0)
    labels = [('t2', 'T2', good, (0, (2, 2))), ('t1', 'T1', good, (0, (2, 2))), ('entry', 'Entry', ink, 'solid'), ('sl', 'Stop', bad, (0, (5, 3)))]
    for k, name, col, style in labels:
        if k in lv:
            ax.axhline(lv[k], color=col, linewidth=1.1, linestyle=style, zorder=4)
            ax.text(n + 0.6, lv[k], f'{name} {lv[k]:,.2f}', color=col, fontsize=9, va='center', ha='left', fontweight='bold', zorder=6, bbox=dict(facecolor='white', edgecolor='none', pad=1.5))
    ys = [x for cdl in C for x in (cdl[1], cdl[2])] + [lv[k] for k in ('entry', 'sl', 't1', 't2') if k in lv]
    lo, hi = min(ys), max(ys); pad = (hi - lo) * 0.06 or 1.0
    ax.set_ylim(lo - pad, hi + pad); ax.set_xlim(-1, n + 11)
    for s in ('top', 'right'): ax.spines[s].set_visible(False)
    ax.spines['left'].set_color('#D8D8D8'); ax.spines['bottom'].set_color('#D8D8D8'); ax.tick_params(colors='#6B6B6B', labelsize=8, length=0)
    if times:
        step = max(1, n // 4); ax.set_xticks(range(0, n, step)); ax.set_xticklabels([(str(times[i]) if len(str(times[i])) <= 14 else str(times[i])[5:16].replace('T', ' ')) for i in range(0, n, step)])
    else: ax.set_xticks([])
    ax.grid(axis='y', color='#ECECEC', linewidth=0.6); ax.set_axisbelow(True)
    if title: ax.set_title(title, loc='left', fontsize=11, fontweight='bold', color=ink, pad=8)
    buf = io.BytesIO(); fig.tight_layout(); fig.savefig(buf, format='png'); plt.close(fig)
    return buf.getvalue()
