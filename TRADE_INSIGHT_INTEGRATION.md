# Trade Insight: use the same realized-P&L rules (exit date)

DownerStuff and Trade Insight (`hhemmannth.github.io/Trading-analytics`) share one Supabase row (`journal_state`). From 19 Nov 2026 DownerStuff
dates realized P&L by the **exit date** using `site/js/pnl.js`. Trade Insight's repository could not be opened from the audit session (private, or
GitHub not connected), so these changes were **not applied or tested there**. Until they are, Trade Insight still shows daily and weekly loss by
entry date. Use DownerStuff's banner for your limits.

## What is already safe
- The new trade fields (`xd` exit date, `xtm` exit time, `parts` partial exits) are stored inside each trade object. A journal page that loads a
  trade with `{ ...TDEF, ...t }` and saves the object back (as DownerStuff's journal, which was built from the same code, does) keeps them.
- **Check once:** in Trade Insight, open a trade that has an exit date in DownerStuff, change its note, save, then reopen it in DownerStuff.
  If the exit date is still there, the field survives. If it is gone, Trade Insight rebuilds trades from a fixed key list; tell Claude and
  the fix is step 3 below.

## Steps (about 10 minutes, in the Trade Insight repo)
1. Copy `site/js/pnl.js` from DownerStuff into the Trade Insight repo unchanged. Load it before the journal script:
   `<script src="pnl.js"></script>` (or paste its contents into a `<script>` block before the journal code, if Trade Insight is one file).
2. In the journal code, replace the per-trade P&L lines in `enrich` with the same three lines DownerStuff uses:
   ```js
   const P = PnL.totals(t, t.q);
   t._legs = P.legs; t.closed = P.closed; t.gross = P.gross; t.net = P.net; t.realized = P.realized; t.openQty = P.openQty;
   t.xdUnknown = P.unknown.length > 0; t.xkey = (P.legs.filter(l => l.known).map(l => l.d).sort().pop()) || null; t.xmkey = t.xkey ? t.xkey.slice(0, 7) : null;
   ```
3. Add `xd: '', xtm: '', parts: null` to `TDEF` (and to `TKEYS` only if Trade Insight encodes trades as arrays).
4. In `riskStatus`, replace the day/week/month sums with:
   ```js
   const D = PnL.realized(T, d => d === td), W = PnL.realized(T, d => weekStart(d) === wk), M = PnL.realized(T, d => d.slice(0, 7) === mo);
   const day = D.net / cap, week = W.net / cap, month = M.net / cap;
   ```
5. Add the "Exit date" and "Exit time" inputs to the trade form (DownerStuff's `journal.js` has the exact markup and the `JR.exitProblem` save check).
6. Test: the ₹3,000 example (entered last week, closed today) must show −1.50% today in both apps.

The rule both apps then follow: realized P&L counts on the day it was realized; each partial exit counts on its own date; a closed trade with
no exit date counts in totals but in no day, week or month, and is flagged until you add the date. No date is ever guessed.
