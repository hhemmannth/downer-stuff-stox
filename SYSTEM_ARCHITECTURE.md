# DownerStuff: system architecture (audit of 18 Nov 2026)

Audited code: `hhemmannth/downer-stuff-stox`, branch `main`, commit `cdc0aaa` (18 Nov 2026 14:29 IST). The Claude Project copy of the files is older (no gold section, no hold-backs), so the GitHub repo was audited.

## Technology stack

| Layer | What it is |
|---|---|
| Language | Python 3.11 in CI (tested here on 3.13), JavaScript (browser, no build step) |
| Backend | No server. Python scripts run as **GitHub Actions** jobs on a schedule and write JSON files |
| Frontend | Static single-page app in `site/` (vanilla JS, hash routing), served by **GitHub Pages** from the `gh-pages` branch |
| Database | **Supabase** (Postgres + auth): table `journal_state` (one jsonb row per user, the whole journal), table `broker_fills`; RLS policies in `supabase/setup.sql` |
| Local state | JSON ledgers (`signals_*.json`) and caches (`.cache/daily_cache.pkl`, `m15.pkl`) carried between runs on the `gh-pages` branch and in `actions/cache` |
| Market data | Angel One SmartAPI (official NSE candles and quotes, needs 4 secrets) first, Yahoo Finance (`yfinance`, unofficial) as fallback; gold from Yahoo `GC=F` (COMEX futures) |
| News | Google News RSS (no key) |
| Alerts | ntfy and Telegram (bot replies on the next scan, no server) |
| Dependencies | `yfinance`, `pandas`, `numpy`, `matplotlib`, `cryptography` (requirements.txt, unpinned) |
| Tests | Plain Python scripts `test_*.py` (no pytest), run by `run_tests.py` in the `ci` workflow on every push; plus `node --check` on the JS |

## Module inventory

| Module | Role |
|---|---|
| `strategy_scanner.py` | Entry point for every scan mode (swing, swing-fast, options, intraday, market, news, live, all). Indicators (EMA, ATR), swing points, zigzag pivots, structure finder (CHoCH, BOS, OB, FVG, fib), zone state, 5m/15m engine (`detect`, `scan_intraday`), JSON writers, health file |
| `swing.py` | The swing playbook engine: weekly location, daily CHoCH/BOS/zone, 1H confirmation, 15m entry, scorecard, plan, hold-backs, checklist |
| `signals.py` | Trade lifecycle tracker shared by the live scans and every backtest: open, walk candles, T1/T2/T3, stop, trail, square-off, daily 2-trade rule, **stale-data gate (new)** |
| `holdbacks.py` | Hold-back table by segment (18 Nov 2026), shared by live and backtest |
| `datasource.py` | Angel One client (login with TOTP, instrument tokens, candles, quotes, pacing, time budget), Yahoo fallback per symbol, daily cache, Angel-vs-Yahoo cross-check, **candle hygiene on every fetch (new)** |
| `dataquality.py` | Split / bad-tick / halted flags; **`sanitize` and `ohlc_problems` (new)** |
| `greeks.py` | Black-Scholes price and Greeks, weekly expiry (Tuesday, holiday-shifted), strike by delta |
| `market.py`, `sector_index.py` | Regime, breadth, sector index state |
| `newsfeed.py`, `explain.py` | Headlines and events calendar; plain-language logic and plan text |
| `backtest.py` | Swing replay (`replay_symbol`), statistics, account simulation ("With your rules"), Monte Carlo, report |
| `backtest_tf.py` | Positional, intraday, Nifty options (modelled premiums) and gold replays |
| `gold_live.py`, `gold_loop.py` | Gold (XAUUSD label, `GC=F` data) live scan and its own loop |
| `loop.py`, `watchdog.py` | 5-minute market loop with heartbeat; restarts it when silent |
| `publish.py` | Merges and pushes JSON to `gh-pages` without clobbering the other loop's files |
| `notify.py`, `alerts.py`, `digest.py`, `bot.py`, `chartimg.py`, `ci_alert.py`, `readiness.py` | Phone alerts, failure alerts, morning/evening digest, Telegram commands, chart images, CI failure alert, 08:50 readiness check |
| `backup.py`, `restore.py`, `supa.py`, `tradebook.py` | Encrypted nightly journal backup, restore, Supabase client, Angel One fills import |
| `validation.py` **(new)** | Independent re-check of everything published after each scan: `data/health/validation.json` |
| `site/js/core.js` | Sign-in gate (fails closed, TOTP step), routing, data loading, stale-data banner |
| `site/js/journal.js`, `analytics.js` | Journal storage and P&L maths, risk status, analytics statistics |
| `site/js/scanner.js`, `pages.js`, `lab.js`, `charts.js`, `vault.js`, `fills.js`, `m3d.js`, `playbook-data.js` | Pages, Backtest lab, charts, two-factor settings, fills import, 3D visuals, playbook text |

## Scheduled jobs (GitHub Actions)

| Workflow | When (IST) | What |
|---|---|---|
| `scan` | ~08:37 and ~16:17 weekdays | swing + market + news, daily cache |
| `market-loop` | 09:05 start (backups 09:20, 09:35, 14:30, 14:50) | `loop.py`: every 5 min options + intraday + market (+news ~30 min), swing hourly at :25, swing fast lane every 15 min, heartbeat |
| `watchdog` | every 10 min 08:30-15:20 | starts / restarts the loop |
| `gold-loop`, `gold-watchdog` | Sunday 03:35 Monday onwards, every 6 h backups; watchdog every 10 min | gold scans all week |
| `digest` | 08:45, 15:45 | phone brief and recap |
| `readiness` | 08:50 | Angel One, Yahoo, list, channels, tokens, backup checks |
| `backtest`, `backtest-intraday` | Saturday 07:00, 08:30 | replays |
| `backup` | 23:00 daily | encrypted journal backup to the private vault repo |
| `tradebook` | 15:50 weekdays | Angel One fills to Supabase (experimental) |
| `ci`, `rollback` | every push / manual | tests; revert last commit |

## Data flow: market data to journal entry

```
Angel One SmartAPI ──┐ (per symbol; on error, rate limit or time budget -> Yahoo)
Yahoo Finance ───────┴─> datasource.fetch ─> dataquality.sanitize (NEW: duplicates, order, impossible candles)
                                                │
                     tidy_daily / tidy_intraday (drop the unfinished candle) ─> dataquality.flags (split, bad tick, halted)
                                                │
          swing.analyse (1D structure -> 1H confirm -> 15m entry)      scan_intraday / detect (15m bias -> 5m)
                                                │
                       scorecard + plan (entry, stop, T1/T2/T3, risk %) + hold-backs + context
                                                │
           build_item / swing_item (prices to the 0.05 tick) ─> signals.update:
                 gate_stale (NEW: stale candles -> "not taken") -> limit_items (2 a day, A+ only) -> new_signal -> walk
                                                │
             JSON in data/ (swing.json, options.json, signals_*.json ...) ─> validation.write (NEW) ─> publish.py ─> gh-pages
                                                │
     Browser app: pages read JSON; "Log trade" opens the journal form pre-filled ─> journal.js (localStorage + Supabase journal_state)
                                                │
                       analytics.js / risk banner / weekly review read the journal
```

Backtests reuse the same functions (`swing.analyse`, `sc.scan_intraday`, `signals.walk`, `holdbacks.reasons`) on historical candles, with costs subtracted in R.

## Logging and monitoring
- Every scan writes `data/health/<mode>.json` (sections ok/failed, data sources, Angel-vs-Yahoo check) and now `data/health/validation.json`.
- The loop writes `data/health/loop.json` on every tick; the app shows a red banner when it is more than 11 minutes old in market hours.
- Failures reach the phone through `alerts.py` with a cool-down.
- Logs are the GitHub Actions run logs; no secret is printed by the code reviewed (secrets go to `Authorization` headers and environment only).
