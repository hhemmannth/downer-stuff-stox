# Test results (audit of 18 Nov 2026)

Environment: Python 3.13.18, pandas 3.0.5, numpy 2.5.3, Node 22, PyYAML 6.0.3, Linux sandbox. No network to Angel One, Yahoo, Supabase or Telegram (all such tests use stand-ins and recorded fixtures). No orders at any point.

## Baseline (before any change)
`python run_tests.py` on `main` at `cdc0aaa`: **ALL GOOD, 30/30 checks** (28 test files + JavaScript syntax + workflow/JSON files), 4 min 20 s.

## After the audit fixes
`python run_tests.py`: **ALL GOOD, 32/32 checks** (30 test files + JavaScript syntax + workflow/JSON files), 4 min 18 s.

Individual assertions (lines starting `PASS` / `FAIL`), counted per file:

| File | Pass | Fail | | File | Pass | Fail |
|---|---|---|---|---|---|---|
| test_alerts | 20 | 0 | | test_journal_js **(new)** | 13 | 0 |
| test_audit **(new)** | 65 | 0 | | test_market | 18 | 0 |
| test_backtest | 62 | 0 | | test_news | 15 | 0 |
| test_backtest_main | 15 | 0 | | test_notify2 | 19 | 0 |
| test_backtest_tf | 64 | 0 | | test_pipeline | 53 | 0 |
| test_bot | 16 | 0 | | test_playbook_v2 | 21 | 0 |
| test_data | 13 | 0 | | test_publish | 18 | 0 |
| test_datasource | 35 | 0 | | test_quality | 13 | 0 |
| test_digest | 35 | 0 | | test_rules | 38 | 0 |
| test_fastlane | 39 | 0 | | test_scanner | 61 | 0 |
| test_fills | 14 | 0 | | test_sector | 18 | 0 |
| test_gold_live | 35 | 0 | | test_signals | 35 | 0 |
| test_greeks | 24 | 0 | | test_swing | 45 | 0 |
| test_holdbacks | 64 | 0 | | test_vault | 28 | 0 |
| test_invariants | property test (prints a table, no PASS lines) | 0 | | test_watchdog | 15 | 0 |

**Total: 911 passed, 0 failed, 0 skipped** (+ the invariants property test, passed).

Coverage (`coverage run` over all test files, Python only, tests and fixtures excluded): **88% of 4,358 statements**. Lowest: `gold_loop.py` 15%, `ci_alert.py` 38%, `loop.py` 44%, `tradebook.py` 60%, `watchdog.py` 60% (process loops and GitHub API calls). `swing.py` 99%, `signals.py` 98%, `dataquality.py` 100%, `holdbacks.py` 100%. JavaScript has no coverage measurement; only the journal maths (`test_journal_js.py`) and syntax are tested automatically.

## What the new tests prove (`test_audit.py`, `test_journal_js.py`)
Expected values are worked out by hand in the test, not taken from the code.

| Area | Checks |
|---|---|
| Candle hygiene | duplicate kept once (latest), sorted, high < low dropped, close above high repaired, negative volume to 0, missing open, zero volume kept; 200 randomly corrupted frames all clean afterwards; `fetch` cleans Yahoo frames and records repairs |
| API failures | Angel One down: all symbols via Yahoo; both down: nothing invented, all reported failed; all-NaN answer never becomes a candle; slow Angel One: time budget hands the rest to Yahoo (0.5 s, 12/12 returned) |
| Stale-data fail-safe | fresh 5m opens; 55-min-old 5m refused with the reason; swing pre-open with yesterday's entry refused; post-close same-session allowed; a stale stock uses no daily slot; `STALE_CHECK=off` works |
| Tracker maths | swing long half/quarter/rest = +1.00R; T1 then original stop = 0.00R (no early breakeven); intraday short = +0.50R; stop and target in one candle = -1.00R (stop first); all targets in one candle = +1.75R; gap through long stop = -1.60R; gap through short stop = -1.75R; 15:15 square-off = +0.40R; zero-width stop no division |
| Backtest statistics | win rate, expectancy, profit factor, average win/loss, max drawdown (2.0R), losing streak (2), empty and no-loss cases; account: A+ 0.75% vs 0.5% risk, strict 2 a day, compounding |
| Options and Greeks | cost formula (Rs 66.33 example), covers the 0.15% STT on sell premium (since 1 Apr 2026); put-call parity; delta bounds and call-put delta identity; intrinsic at expiry; weekly expiry moves to Mon 23 Nov 2026 (Guru Nanak Jayanti on Tue 24 Nov) |
| Swing replay, no look-ahead | with a data-dependent stand-in engine (24 trades): cutting the history leaves all 15 trades closed before the cut identical; the daily frame never included the session being replayed; exits after entries |
| Validation module | correct plan passes; missing sections are "not tested"; Angel One not set up is "unavailable"; wrong-side stop and unordered targets are CRITICAL; bad candle and repeated time caught; stale file in market hours fails; Angel failing is a warning; failed section is an error; every error has all ten fields; booked R recomputed; wrong R and duplicate records reported; closed market is "not tested" |
| Journal maths (Node) | long gross/net/R after charges; planned R:R; short loss and short win (lot 65); quantity from capital; open trade has no P&L; manual net override; zero quantity; undated trades excluded; trade number per day; position size for A+ (0.75%) and A (0.5%) |

## End-to-end (Section 15)
- The pipeline test (`test_pipeline.py`) runs every scan mode with recorded fixture downloads: data, then validation, structure, signals, plan, tracker, JSON, alerts. 53 checks pass.
- The app was served locally with that run's output and opened in headless Chromium with the sign-in library stubbed (local test only): **System health** (new Validation checks card), **Swing**, **Nifty options** and **Journal** rendered; the Swing page showed the playbook example at entry 1,070.00, stop 1,036.55, 10/10 A+. The only console errors were 404s for optional files the fixture run does not produce (readiness, backup).

## Not tested (and why)
| Module / behaviour | Status |
|---|---|
| Real Angel One login, candles, quotes, option chain | **Not tested**: no credentials in this sandbox (by design) |
| Real Yahoo downloads | **Not tested**: the sandbox blocks the site; recorded fixtures only |
| Supabase sign-in, RLS on the live project, cloud sync, backup to the vault | **Unable to verify**: SQL files read, live project not reachable |
| GitHub Actions schedules, loop/watchdog in production, publish to gh-pages | **Partially tested**: unit tests with fakes; production behaviour not run |
| Telegram and ntfy delivery | **Partially tested**: message building tested, delivery not |
| Historical strategy validation on 50 manually annotated real charts (Section 5) | **Not done**: I cannot look at your charts or fetch real history here, and I will not invent expected outcomes. Template and procedure in `AUDIT_REPORT.md` |
| Memory / CPU profiling under load, database disconnection | **Not tested** beyond the API-failure and time-budget tests above |
| All other JavaScript pages (analytics charts, lab, vault, fills) | **Partially tested**: syntax and rendering of four pages only |

## Round 2: the four corrections (19 Nov 2026)
`python run_tests.py`: **ALL GOOD, 34/34 checks** (32 test files + JavaScript syntax + workflow/JSON files).
Individual assertions: **1,028 passed, 0 failed, 0 skipped** (was 911). New or extended: `test_audit2.py` 57, `test_audit3.py` 26, `test_journal_js.py` 38,
`test_gold_live.py` 44. Coverage: **88% of 4,762 statements**; `market_calendar.py` 97%, `evaluation.py` 95%, `gold_feed.py` 91%, `gold_live.py` 89%,
`strategy_config.py` 80%, `signals.py` 98%.
Application startup: Dashboard, XAUUSD Gold, Journal, Backtest lab, News & events and System health rendered in headless Chromium with fixture data, no script errors.
Found and fixed while testing: migration backup taken after normalising; no explicit slippage field in paper records; readiness only checked that the gold key existed;
options not labelled THEORETICAL in the phone summary; 15 Jan 2026 holiday missing; validation window described as "never looked at"; `test_data.py`
depended on a cache left by other tests.
Not verified (no access from the sandbox): real Twelve Data answers, its free-plan delay and history depth, Supabase sync of schema 2, Trade Insight.
Details: `FOUR_CORRECTIONS_REPORT.md`.
