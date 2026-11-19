# DownerStuff: technical audit report

Date: 18 Nov 2026. Code audited: `hhemmannth/downer-stuff-stox` `main` at `cdc0aaa` (18 Nov 2026 14:29 IST), the live repo (newer than the Claude Project copy). Companion files: `SYSTEM_ARCHITECTURE.md`, `BUG_TRACKER.md`, `TEST_RESULTS.md`, `MODIFICATION_LOG.md`, `REMAINING_RISKS.md`.

What this audit could and could not do: it read every Python module, the JavaScript journal, analytics, health and core pages, the workflows and the Supabase SQL; it ran the full test suite before and after; it wrote 78 new independent checks; it rendered the app headless with fixture data. It had **no credentials and no network access to Angel One, Yahoo, Supabase or Telegram**, so nothing was run against real market data or your accounts, and no orders were placed or possible.

## A. Project overview
- **Architecture:** serverless. Python scans run as GitHub Actions jobs (5-minute market loop, hourly swing, gold loop, Saturday backtests), write JSON, and publish it to GitHub Pages; a static JS app reads it. Journal in Supabase (`journal_state`, RLS). Full map in `SYSTEM_ARCHITECTURE.md`.
- **Stack:** Python 3.11 (CI), pandas 3, numpy, yfinance, cryptography; vanilla JS; Supabase; GitHub Actions/Pages; ntfy and Telegram.
- **Modules:** 31 Python modules (including the new `validation.py` and `run_tests.py`) (scanner, swing engine, tracker, data source, backtests, gold, loop/watchdog, publish, alerts, backup) and 11 JS files. Inventory in `SYSTEM_ARCHITECTURE.md`.
- **APIs:** Angel One SmartAPI (login + TOTP, instrument list, candles, quotes, option chain, tradebook), Yahoo Finance (yfinance), Google News RSS, Supabase REST/auth, Telegram Bot API, ntfy, GitHub REST (watchdog, rollback).
- **Separate strategy-testing component:** inside this repo, the Backtest lab (`backtest.py`, `backtest_tf.py`) calls the **same** engine functions as the live scan (`swing.analyse`, `scan_intraday`, `signals.walk`, `holdbacks`). So backtest and live cannot drift apart in code, but a backtest is no independent proof that the engine is right, and they differ in what they replay (below). If you have a separately written tester elsewhere (another repo or a spreadsheet), it was not reachable from here: your GitHub account is not connected to this session.

## B. Software quality
- **Overall:** careful, heavily commented code with a real regression suite (911 assertions, 0 failures). Earlier bugs are documented in the comments, and most have tests. Errors in one scan section do not stop the others (`main` catches per section). Writes are atomic (`.tmp` then `os.replace`).
- **Confirmed and fixed:** B-01 to B-06 (`BUG_TRACKER.md`): stale-data fail-safe, candle hygiene, gap fills, 9 EMA seeding, independent validation, link scheme.
- **Unresolved:** O-01 to O-19 with reasons.
- **Code-quality concerns (no defect found):** very long lines and dense one-liners make review hard; many broad `except Exception: continue` in replays and scans hide the cause of a skipped symbol (they are logged in some places, not all); dependencies are unpinned; `strategy_scanner.py` (1,050 lines) mixes indicators, engine, I/O and runs.

## C. Data quality
- **Angel One:** first choice for candles and quotes; per-symbol fallback to Yahoo on any error; rate-limit back-off; a per-run time budget so a slow day cannot overrun the 5-minute tick (tested: 12/12 symbols returned in 0.5 s with a stalled Angel One). De-duplicates and sorts its candles. Real connectivity **not tested** (no credentials).
- **Yahoo:** used for the daily history of the Nifty 500 (fast), intraday stocks by design, and as fallback. **Before this audit its frames were not validated** (B-02); now every frame from every source passes `dataquality.sanitize`.
- **Integrity checks now in place:** unique, ordered timestamps; high >= max(open, close); low <= min(open, close); high >= low; positive prices; non-negative volume. Zero volume is **not** treated as an error (indices and quiet candles legitimately have none; the engine already reads 0 as "no volume data" rather than weak volume). Existing checks kept: unadjusted splits (35% jump), bad ticks (25% wick), halted stocks (3 sessions behind the market).
- **Timestamps and sessions:** intraday frames converted to IST; unfinished last candles dropped (`tidy_intraday`, `tidy_daily`, gold `_bar_open`); 15m and 1H bars used only after they end (tested in `test_backtest_tf.py`). NSE 2026 holidays in `events.json` match the NSE list for the rest of 2026; 2027 is missing (O-15). Muhurat session is listed as an event, not traded.
- **Stale data:** the app already showed a red banner when the loop was late; the engine itself did not refuse old candles. Now it does (B-01): **"data stale: no trade on old data"**, and System health counts the refusals.
- **Gold:** the instrument is COMEX gold futures `GC=F`, not spot XAUUSD (O-01). Never mixed with MCX in code (MCX is not used at all), but futures and spot are mixed in labelling: the setups say XAUUSD.
- **Cross-source check:** each morning a sample of Angel One and Yahoo closes is compared (System health > Data sources); differences over 1.5% raise an alert. Only like-for-like instruments are compared (same NSE symbol, daily close).

## D. Strategy accuracy (Section 4)
Checked against the playbook text in the code and README and your rules in this Project. No rule was changed.

| Component | What the code does | Verdict |
|---|---|---|
| Swing points | n-bar fractals (known n bars later) or a zigzag that confirms a swing only after a 0.8 ATR reversal, recording the bar at which it became known | No future data: every use filters on "known before this bar" |
| Liquidity sweep | A wick below the prior swing low with a close back above it, between that low and the CHoCH | Correct; informational only, not a gate (as your playbook says) |
| CHoCH | First **close** above the last lower high after lower highs and lower lows; base low must hold | Close-based, not wick; matches |
| BOS | After a pullback candle, a **close** above the running swing high with a displacement body >= 1 ATR (daily), 0.8 ATR (15m) | Close-based; premature wick breaks cannot qualify |
| FVG | Three candles: low of the third above the high of the first, at least 0.2 ATR, around the BOS | Correct bullish definition; shorts by mirroring prices (K - p), which turns it into the bearish definition exactly |
| Order block | Default: last down candle in the 6 bars before the BOS, from its low to its open. With `SWING_LUX_OB=on`: LuxAlgo's rule (lowest candle between the broken pivot and the break, full range) | Implements your 17 Nov choice. Note O-12: the default box differs from LuxAlgo's drawing |
| Mitigation / invalidation | Zone broken on a daily close below zone bottom minus 0.25 ATR; 1H broken likewise; 15m zone fails on a close 0.1 ATR below | Close-based; consistent |
| 9 EMA | `ewm(span=9, adjust=False)`: alpha = 2/(9+1), seeded with the first value, the same recursion as TradingView's `ta.ema`. **Defect fixed (B-04):** the 1H and 15m steps computed it on a cut window, so it restarted after the BOS | Now matches the chart |
| 1H confirmation | Latest pullback into the zone, rejection candle, then the first close above the 9 EMA within 21 candles of the pullback low with relative volume >= 1.5x against the same hour on earlier days (v1); a later candle still above the EMA with the volume also counts | Matches the README playbook |
| 15m entry | CHoCH + BOS + FVG inside the daily zone, a controlled retest, a close above the 9 EMA on 1.5x, never before the 1H confirmation candle has closed; no chasing beyond 0.5 ATR | Matches; freshness was in bars (fixed by the time-based gate, B-01) |
| Final recommendation | Score 0 to 10 (structure 2, zone 2, confirmation 3, context 3); hold-backs; strict 2 trades a day across swing, options and intraday, A+ only (8+); one open trade per stock and side; 15:00 options and 14:00 stock-intraday cut-offs; options stop after 2 losses | Matches your rules of 18 Nov 2026 |

**Implementation differences between live and backtest (documented, not bugs):** the swing backtest enters at the 1H confirmation close (not the 15m entry) and cannot replay results-date or sector hold-backs; options use modelled premiums; intraday history is ~60 days. The secondary strategy (17 Nov, `PLAYBOOK_V2=on`) runs through the same functions and received the same EMA fix.

**Correctly detected / false positives / false negatives on real charts:** not measured. See Section 5 below.

## Section 5: historical strategy validation (not done here, and why)
A meaningful 50-case validation needs real historical candles and your own chart annotation of what should have happened. This sandbox has neither, and making up expected outcomes would defeat the purpose. What exists already: your written playbook example (engine finds the same OB 1,041 to 1,052, FVG 1,055 to 1,076, entry 1,070, stop ~1,036, 10/10; still true after the fixes) and the CUPID / SANSERA LuxAlgo order-block fixture. Neither was re-verified on a live chart by me.

**Procedure for you (about 2 hours):** fill one row per case in a sheet with these columns:
`instrument, date, timeframe, expected_sweep, expected_choch_level, expected_bos_level, expected_zone_low, expected_zone_high, expected_signal (TRIGGERED / WATCH / NONE), expected_entry, expected_stop, note`.
Pick 50: about 10 successful longs, 5 failed longs, 5 shorts (intraday/gold), 5 false breakouts, 5 sweeps without CHoCH, 5 CHoCH without BOS, 5 BOS without a valid retest, 5 weak-volume confirmations, 5 clear no-trade days. For each, type the symbol in **Why isn't a stock here?** on the day, or send me the sheet and the scan output; any row where the engine and your chart disagree becomes a regression test before anything is changed.

## E. Financial accuracy (Section 6)
Recomputed by hand in `test_audit.py` and `test_journal_js.py`.
- **Plan maths:** stop below the OB / zone / pullback low minus 0.25 ATR; T1/T2/T3 = 1R/2R/3R (swing); intraday/options ladder sorted nearest first. Validation now re-checks every published plan after each scan.
- **Tracker R:** half at T1, quarter at T2, rest at exit; swing keeps the original stop at T1 (no early breakeven), moves to entry at T2 and trails daily higher lows; intraday/options move to entry at T1 and to T1 at T2. All verified, long and short. **Fixed:** gap fills (B-03).
- **Same candle stop and target:** stop assumed first (never the favourable fill). Verified.
- **Position size:** quantity = floor(capital x risk % / stop distance); 0.75% for A+, 0.5% otherwise. Verified.
- **Journal:** gross = (exit - entry) x qty x direction; net = gross - charges (or your override); R = net / risk. Verified for long, short, lot 65, capital-based quantity, open trades, zero quantity. **Open:** loss limits by entry date (O-04), no partial exits or automatic charges (O-05).
- **Statistics:** win rate, expectancy, profit factor, average win/loss, drawdown, streaks verified in the backtest; the journal uses a ±0.1R breakeven band (O-06).
- **Charges:** options cost covers the 0.15% STT on the sell premium in force since 1 Apr 2026; delivery 0.30% and intraday 0.08% are flat allowances to calibrate from contract notes (O-07). Lot size 65 (Nifty, since January 2026) confirmed.
- **Rounding:** NSE prices are published on the 0.05 tick; gold levels are rounded to 0.01 (COMEX trades in 0.10 steps, most XAUUSD feeds in 0.01), which is fine for display.

## F. Backtesting integrity (Section 7)
| Check | Finding |
|---|---|
| Look-ahead / leakage | None found. Intraday, positional (existing tests) and now swing (`test_audit.py`, data-dependent stand-in): truncating history leaves every earlier closed trade identical; the daily frame never contains the session being replayed; 15m/1H bars are used only after they end |
| Repainting | Zones can change as new candles arrive (an FVG needs the candle after the BOS), but only with data that exists at that time |
| Candle-close confirmation | Entries at the close of the confirming candle; exits are walked from the next candle |
| Stop vs target in one candle | Stop first |
| Gaps | **Fixed:** stop gaps fill at the open (B-03) |
| Costs and slippage | Included in R (flat %); see O-07, O-08 |
| Expiry | Weekly Tuesday expiry with holiday shift; no options entry on expiry afternoons; time decay via Black-Scholes |
| Options P&L | Modelled premiums, not real ones (O-03) |
| Survivorship | Current Nifty 500 list (O-11) |
| Overfitting | **Main concern (O-02):** hold-backs fitted in-sample; no development / validation / unseen split; 7.5-month window |
| Duplicate trades | One trade at a time per stock and side; same structure key never reopened |
| Metrics | Verified against hand calculations |

No optimisation for profit was done. **Re-run both backtest workflows after uploading**: B-03 and B-04 change results (B-03 can only make them worse or equal).

## G. Journal and news
- **Journal:** storage keys and format shared with Trade Insight; localStorage + Supabase upsert of one jsonb row; persistence and restart behaviour depend on Supabase (not reachable here: **unable to verify**). Edit, delete and CSV/JSON export exist; backups are encrypted nightly. Maths verified (above). Risks: O-04, O-05, O-06, O-16.
- **News:** Google News RSS, de-duplicated by normalised title, publication time converted to IST, failures skipped. Stock mapping is a search, not a verified match (O-10); the "high impact" tag is a keyword heuristic and should be read as an interpretation. Links now restricted to http(s) (B-06).

## H. Security
- No credentials in the repo (searched for API keys, JWTs, GitHub and Telegram token patterns: none). The Supabase key in `core.js` is the publishable key, which is meant to be public; protection comes from RLS (policies in `setup.sql` reviewed: owner-only reads/updates, scanner read-only via `is_scanner()`), with sign-ups off per the project brief. Live RLS state **not verified**.
- Secrets are read from GitHub secrets and environment variables only; the code prints secret **names**, never values.
- The sign-in gate fails closed (an error asks for the code or shows retry; it never opens on the password alone).
- Journal backups are AES-256-GCM encrypted before leaving the job.
- Workflows request `contents: write` only where they publish; no `pull_request_target`.
- Telegram bot answers only the configured chat ids.
- Recommendations: put your email in `App.ALLOWED`; confirm the old Telegram token from an earlier chat was revoked (open item in the brief); pin dependency versions; remember `data/*.json` is public (O-18).

## I. Automated testing
- **Total:** 32 checks / 911 assertions, **0 failed, 0 skipped** (Node present; `test_journal_js.py` skips without it).
- **New:** `test_audit.py` (65), `test_journal_js.py` (13).
- **Coverage:** 88% of Python statements (tests excluded). Lowest: `gold_loop.py`, `ci_alert.py`, `loop.py`, `tradebook.py`, `watchdog.py`.
- **Unverified modules:** live API calls, Supabase, Telegram/ntfy delivery, GitHub production schedules, most JS pages beyond syntax and four rendered pages. Details in `TEST_RESULTS.md`.

## J. Modifications
12 code and test files changed or added, plus the 6 audit documents; full table in `MODIFICATION_LOG.md`. Tests were run after each change and the full suite at the end (32/32).

## K. Deployment readiness

**Classification: 2. READY FOR EXTENDED PAPER TESTING**, for the India segments (swing, intraday, Nifty options), with gold as **paper tracking only with levels re-read on your XAUUSD chart**.

Why paper testing: the code is technically sound for it. The full regression suite and 78 new independent checks pass. Data now passes integrity checks before any rule. The system refuses to open trades on stale candles, books gaps realistically, matches your TradingView 9 EMA, and reports its own errors on System health without false green.

Why not live yet, even limited:
1. The strategy's edge is unproven out of sample: hold-backs were fitted on the same 2026 trades, the first full swing backtest was slightly negative after costs, and options results are modelled (O-02, O-03).
2. Gold levels come from a different instrument than the one you trade (O-01).
3. The journal's loss limits can miss realised swing losses (O-04).
4. Nothing in this audit ran against real Angel One / Yahoo data or your Supabase project.

A profitable backtest would not change this classification on its own; months of paper trades judged on frozen rules, plus the fixes listed in `REMAINING_RISKS.md`, would.

## Checkpoint
All phases complete for this session. Next tasks: (1) upload the changed files and confirm `ci` is green; (2) run `backtest` and `backtest-intraday` and compare with the previous numbers (expect small changes from B-03/B-04); (3) check System health > Validation checks after the next live tick; (4) do the 50-case chart validation; (5) decide on O-01 (gold feed) and O-04 (journal exit date).

## Addendum (19 Nov 2026): the four corrections
Gold now runs on verified XAUUSD spot (or not at all), realized P&L is dated by the exit, in-sample results are labelled as such under a frozen,
hashed strategy version, options are classified theoretical, paper records are sealed, and the NSE calendar is one official file. Details and examples
A to D: `FOUR_CORRECTIONS_REPORT.md`. **Verdict unchanged: READY FOR EXTENDED PAPER TESTING** (India segments); gold NOT READY until its key, the volume
decision and the readiness check pass.
