# Modification log (audit of 18 Nov 2026)

Base: `main` at `cdc0aaa` (18 Nov 2026 14:29 IST). Work done on a local branch `audit/2026-11-18`; the repo had no uncommitted work. Nothing was pushed (this session has read-only access); the changed files are delivered as a zip for upload.

Rules followed: no strategy rule, indicator, entry or exit rule changed; nothing optimised for profit; no user data touched; no credentials read or changed; no orders.

| # | File | Function | Change | Bug | Tests run after the change |
|---|---|---|---|---|---|
| 1 | `dataquality.py` | new `sanitize`, `ohlc_problems` | Candle hygiene and an independent invariant check | B-02 | `test_audit.py`, `test_quality.py`, `test_data.py`: pass |
| 2 | `datasource.py` | `fetch`, new `clean`, `report`, `reset` | Every downloaded frame goes through `sanitize`; repair counts in the health report | B-02 | `test_datasource.py`, `test_audit.py`: pass |
| 3 | `backtest_tf.py` | `gold_intraday`, `gold_daily`, imports | Same hygiene on gold candles (they bypass `datasource.fetch`) | B-02 | `test_gold_live.py`, `test_backtest_tf.py`: pass |
| 4 | `signals.py` | `walk` | Gap through the stop fills at the open | B-03 | `test_signals.py`, `test_audit.py`, all backtest tests: pass |
| 5 | `signals.py` | new `BAR_MIN`, `stale_reason`, `gate_stale`; `update` | Stale-data fail-safe before the daily limit; `STALE_CHECK=off` switch for replay tests on old fixtures | B-01 | `test_signals.py`, `test_holdbacks.py`, `test_audit.py`: pass |
| 6 | `test_pipeline.py` | first line | Sets `STALE_CHECK=off`: its fixtures are dated weeks before the real clock, which the new gate correctly refuses. The gate itself is tested in `test_audit.py` | B-01 | `test_pipeline.py`: 53 pass |
| 7 | `swing.py` | `confirm_1h`, `entry_15m` | 9 EMA over all history, then the window | B-04 | `test_swing`, `test_pipeline`, `test_holdbacks`, `test_rules`, `test_backtest`, `test_backtest_main`, `test_fastlane`, `test_playbook_v2`, `test_invariants`, `test_scanner`: pass |
| 8 | `validation.py` | new module | Independent post-scan validation, `data/health/validation.json` | B-05 | `test_audit.py` section 8: pass |
| 9 | `strategy_scanner.py` | `write_health` | Calls `validation.write` (own try/except: a validation error can never stop a scan or its alerts) | B-05 | `test_pipeline.py`: pass; output inspected |
| 10 | `site/js/pages.js` | `HEALTH_LAZY`, new `validationCard`, `safeHref`, health page | Validation card on System health; news links http(s) only | B-05, B-06 | `node --check`; page rendered headless with fixture data and screenshotted |
| 11 | `site/index.html` | script tags | `?v=23` to `?v=24` so phones load the new `pages.js` instead of a cached copy | (deploy) | page loads |
| 12 | `test_audit.py` | new | 65 independent checks | - | 65 pass |
| 13 | `test_journal_js.py` | new | 13 checks of the journal maths in Node (skips if Node is missing) | - | 13 pass |
| 14 | audit documents | new | `AUDIT_REPORT.md`, `BUG_TRACKER.md`, `TEST_RESULTS.md`, `MODIFICATION_LOG.md`, `SYSTEM_ARCHITECTURE.md`, `REMAINING_RISKS.md` | - | - |

Full regression after all changes: `python run_tests.py` = ALL GOOD, 32/32 checks (30 test files + JavaScript syntax + workflow/JSON files).

## How to undo
Every change is in the files listed. Upload the originals from `main` at `cdc0aaa` (or use the `rollback` workflow right after uploading). `STALE_CHECK=off` exists for the replay tests; the workflows do not pass it, so the live gate cannot be switched off by accident (adding it to a workflow's env would, and is not recommended).

## Round 2: the four corrections (19 Nov 2026)
Branch `fix/four-corrections` from the audit commit `3ebeddd`; commit `45cfe8d` plus documents. Unfinished work from earlier in the session was backed up
(`wip-four-corrections-0205.tgz`) before review. Full table of files and functions: `FOUR_CORRECTIONS_REPORT.md` section 14.
| Area | Files | Change | Tests after |
|---|---|---|---|
| Gold spot | `gold_feed.py` (new), `gold_live.py`, `backtest_tf.py`, `backtest.py`, `readiness.py`, `site/js/lab.js`, 4 workflows | Twelve Data XAU/USD spot only, validated; no fallback; futures history archived; readiness probes the real feed | `test_gold_live`, `test_audit2`, `test_audit3`, `test_rules`, `test_digest` |
| Exit-dated P&L | `site/js/pnl.js` (new), `journal.js`, `analytics.js`, `pages.js`, `fills.js`, `vault.js` | exit date/time and partial exits; realized P&L by exit date; schema-2 migration with raw backup | `test_journal_js` (38) |
| Evaluation | `strategy_config.py`, `strategy_versions.json`, `evaluation.py` (new), `signals.py`, `publish.py`, `validation.py`, `backtest.py`, `lab.js` | frozen version 1.0.0 with hash; chronological windows; theoretical options class; sealed signals and paper records | `test_audit2`, `test_audit3`, `test_backtest_main` |
| Calendar | `market_calendar.py`, `market_calendar.json` (new), `loop.py`, `newsfeed.py`, `events.json`, `strategy_scanner.py` | one calendar; 2026 official incl. 15 Jan amendment; 2027 awaiting | `test_news`, `test_audit2`, `test_audit3` |
Regression: 34/34, 1,028 assertions, 0 failures. Six audit fixes re-checked in the code.
