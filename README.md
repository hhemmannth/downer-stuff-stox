# DownerStuffScreener

Scanner, trade tracker and trading journal in one app, for Indian markets. It runs inside GitHub (Actions + Pages) and you read it on your iPhone or laptop.

## Setup after this update (do these once, in this order)
1. **Upload** everything from this folder to your repo (Add file > Upload files). New files: `signals.py`, `publish.py`, `loop.py`, `test_signals.py`, `test_publish.py`, `test_invariants.py`, `site/journal.html` and `.github/workflows/market-loop.yml`. Replace `.github/workflows/scan.yml` too.
2. **Settings > Actions > General > Workflow permissions:** choose **Read and write permissions** and save. The scanner now publishes by pushing to a `gh-pages` branch.
3. **Actions > scan > Run workflow** (mode **all**). This creates the `gh-pages` branch with the site and data.
4. **Settings > Pages > Build and deployment > Source: Deploy from a branch**, branch **gh-pages**, folder **/(root)**, Save. Your address stays the same.
5. Nothing else is needed for the 5-minute updates: the **market-loop** workflow starts itself on weekdays at 09:05 IST. To start it right now: Actions > market-loop > Run workflow. If you created cron-job.org jobs, pause them; they are no longer needed.
6. **Journal:** open the Journal page once and sign in with your Trade Insight account, so your cloud journal syncs to this site.

## What runs when (IST, trading days)
| What | When |
|---|---|
| Nifty options + intraday stocks + market regime | every 5 minutes on the minute (about 40 s after each 5-minute candle closes), 09:05 to 15:40 |
| Swing (Nifty 500, sector index check) | every hour at :25 from 10:25 to 15:25, plus 08:37 and 16:17 |
| News | about every 30 minutes |

The loop runs inside one GitHub job (up to 6 hours, so a second loop finishes the session). Weekends and the holidays in `events.json` are skipped. The header shows the last update and the next one; it turns red with a link to the Actions tab if a section is late. Pages re-read the data every minute while the market is open.

## Trade tracking (nothing disappears any more)
- Every setup that **triggers** becomes a tracked trade. It stays in **Active trades** until the final target, the stop, the trailing stop (stop moves to entry after the first target and to the first target after the second) or, for options and intraday, 15:15.
- The trade page shows a timeline (trigger, T1, T2, stop...), R now, the current stop, best and worst price, and the chart marks hit targets and the trailed stop.
- Setups that disappear before triggering are listed under **Closed / invalidated** with the reason (zone broken, price ran away, 15m bias lost, structure too old...). An old link to such a setup shows the reason instead of "not found".
- The **Overview** shows the signal track record (win rate, average and total R per section) and the results of the scanner trades you logged in your journal.
- Phone alerts (ntfy) also announce T1/T2/T3, stop, trailing stop and expiry for triggered trades (`NTFY_EVENTS`, default on).

## Journal
Your Trade Insight journal is built in as the **Journal** page (same Supabase cloud). On any trade page, **Log in journal** opens the journal with the trade pre-filled: instrument (the option strike for Nifty trades), category, setup, timeframe, direction, grade, entry, stop, target, quantity from your risk, market regime, event risk and a note with the signal id. Check the fill price and save. The scanner marks trades that are already in your journal.

## Why options rarely triggered, and what changed
- The 15m bias needed a fresh 15m CHoCH. In a trending session the last CHoCH is often a day or more old, so the bias was lost. Now the bias is the latest 15m structure break, as long as it stays intact: a CHoCH, or a BOS that continued it.
- Only the first BOS after a CHoCH made a zone, so after one leg the structure went "stale". Now every later BOS of the same move (after a pullback) creates its own order block and gap.
- A trigger was visible for only 3 candles (15 minutes). It is now 6 candles (30 minutes) on the 5m and 3 candles on the 1H, and once it fires it is kept as a tracked trade.
- On a replay of 30 synthetic Nifty sessions scanned every 5 minutes, sessions with at least one options trigger went from 3 to 13. (Synthetic data, so treat the numbers as direction, not a promise.)
- `test_invariants.py` runs the engine on 360 random markets and checks every reported setup is consistent (levels in the right order, 2R/3R, grades, no crashes).

## Pages
| Page | What it does |
|---|---|
| **Overview** | Market regime, today's event risks, top setups from every section, headlines |
| **Swing** | Nifty 500, **long only**. 1D CHoCH + BOS, FVG + OB zone, 1H trigger, **sector index must not be falling** |
| **Options** | Nifty 50 index only, calls and puts. 15m **CHoCH only**, 5m CHoCH + BOS, 5m trigger. **No volume rule.** Strike picked with Greeks, OI panel |
| **Intraday** | Most liquid Nifty 500 stocks, long and short. 15m **CHoCH only**, 5m CHoCH + BOS, 5m trigger with volume |
| **Market** | Trending, range-bound or volatile (daily and today), VIX-implied move, breadth, sector strength, and which setups to prefer |
| **News** | Headlines (RBI, Fed/global, crude, flows, results, policy), expiry days, holidays, policy meetings, results dates of your setups |
| **Journal** | Your Trade Insight journal (same cloud account), with trades from the scanner pre-filled |
| **Trade** (tap any row) | Chart with entry, stop-loss, T1 to T3 and the entry zone marked, trade tracking timeline once it triggers, how to execute, how to trail, position size, why the trade qualifies, strike and Greeks (options), news for that stock |

## Rules by section
| | Swing | Options | Intraday |
|---|---|---|---|
| Bias | Weekly trend and Nifty trend (info) | 15m CHoCH, still intact | 15m CHoCH, still intact |
| Structure and zone | 1D CHoCH + BOS, FVG + OB | 5m CHoCH + BOS, FVG + OB | 5m CHoCH + BOS, FVG + OB |
| Trigger | 1H rejection, 9 EMA close, volume 1.5x **for the same time of day** | 5m rejection, 9 EMA close | 5m rejection, 9 EMA close, volume 1.5x |
| Score | Structure 2, Zone 2, Confirmation 3, Context 3 | Structure 2, Zone 2, Confirmation 2, Context 4 | Structure 2, Zone 2, Confirmation 3, Context 3 |
| Confluences | key level, fib, MTF EMA, weekly trend, Nifty trend | key level, fib, MTF EMA, **15m order block, OI wall** | key level, fib, MTF EMA |
| Side | Long only | Calls and puts | Long and short |

Grades: 8 to 10 A+, 6 to 7 A, 4 to 5 B (observe). The stop is below the order block with a 0.25 ATR buffer and is never widened.

## Sector index confirmation (swing)
A long must not be going against its own index. Each stock with a setup is mapped to its NSE index from the Nifty 500 industry (Bank Nifty and Nifty PSU Bank for banks, Nifty IT, Auto, Pharma, FMCG, Metal, Realty, Energy, Media, Infra, Financial Services). Industries with no index of their own, or an index Yahoo does not return, use an equal-weight basket of the Nifty 500 stocks in the same industry. The index is **falling** if it is more than half an ATR under its 21 EMA, or under its 9 EMA with a falling 21 EMA, or down 3% in 5 days, or down 1% today. A falling index turns a TRIGGERED long into **WATCH (index falling)** (no alert) until it stabilises, and the trade page explains why. The trail plan also sells half if the sector index closes under its 21 EMA.

## India-specific refinements (swing and everywhere)
- Prices are rounded to the NSE tick of 5 paise.
- Volume on the 1H candle is compared with the same time-of-day candle of earlier days (the 09:15 candle is always heavy, so the whole-day average flattered it).
- Stocks with a locked (zero-range) session in the last 5 days are skipped: you cannot exit a locked circuit.
- Sector strength and relative strength vs Nifty (20 days) from the Nifty 500 industries are shown with every stock.
- Results date (Yahoo, when it has one) is flagged. Exit or cut size before results.
- Weekly Nifty expiry is Tuesday (the previous trading day when Tuesday is a holiday), lot size 65. Holidays are in `events.json`.
- Execution notes use GTT/OCO for delivery, MIS with SL-M for intraday, and the 15:10 square-off.

## Option strike selection
Theoretical Black-Scholes prices with India VIX as the volatility. For the setup's entry, stop and targets it re-prices five strikes at the stop and at T1, T2, T3 (after the time you would plausibly hold) and picks the best premium reward-to-risk with delta in 0.40 to 0.60 (0.50 to 0.70 late in the day or when the expiry is under 3 days away). You see delta, gamma, theta (per day and per hour), vega, premium at SL and each target. If the nearest weekly expiry is under 2 days away it uses the next one. These are model prices: always compare with the live option chain.

## Open interest
The scanner asks NSE for the option chain. NSE often blocks cloud servers, so this is best effort. When it works the OI panel shows the call wall, put wall, PCR and max pain, and OI becomes a confluence tick. When it does not, type the walls from your own chain into the OI panel: the verdict updates instantly and is remembered on your phone.

## Files you will edit most
- `strategy_scanner.py`: the `CFG`, `CFG_I` and `CFG_B` blocks hold the rule thresholds.
- `events.json`: holidays and macro events. Add your own.
- `watchlist.txt`: fallback list. Put a `nifty500.csv` in the repo root for the full list with industries.
- `site/ds.css` and `site/ds.js`: the look and the pages.

## Limits
- Yahoo Finance data is unofficial and can be delayed; 500 symbols can be rate-limited. A failed run keeps the last good page.
- The index has no volume feed here. The options rules do not use volume at all.
- Futures OI, results dates, sector news and the live option premium are not guaranteed: check them.
- A scan finds candidates by rules. It is not a trade signal and not investment advice.

## Tests (no internet needed)
`python test_scanner.py`, `test_data.py`, `test_greeks.py`, `test_oi.py`, `test_market.py`, `test_news.py`, `test_sector.py`, `test_signals.py`, `test_publish.py`, `test_invariants.py`, `test_pipeline.py`
