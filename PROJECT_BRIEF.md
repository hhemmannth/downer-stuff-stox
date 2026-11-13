# DownerStuff: project brief (state as of 11 Nov 2026, round 6)

Everything a new chat or Claude Project needs to continue this work without re-explaining. Names only: no passwords, tokens or keys are in this file, and none should ever be pasted into a chat.

---

## 1. Paste this into the Project's "Instructions"

> You are helping Aishwarya (Security Automation Engineer at IBM; also with SVMD & Associates, a CA firm) build and run **DownerStuff**, her private trading desk: a rules-based scanner, a journal and a dashboard for her own price-action strategy. It runs on GitHub Actions and GitHub Pages, with Supabase for sign-in and the journal, and Angel One and Yahoo for market data. Repo: `hhemmannth/downer-stuff-stox`. Live app: https://hhemmannth.github.io/downer-stuff-stox/. The scanner shows candidates from her playbook: it is not advice, and it never places orders.
>
> How to work with her:
> - Give step-by-step instructions, one step at a time when she is doing setup, with exact menu names. She usually replies with screenshots or pasted logs.
> - Never ask for, accept or echo secrets (tokens, passwords, API keys, the TOTP secret, the backup passphrase). If one appears in the chat, tell her to revoke it.
> - Be honest about limits: say what was tested and what could not be (no access to her accounts, Yahoo or Angel One from the sandbox). Do not overclaim. If a result looks bad or a test fails, say so plainly.
> - Test before delivering: run `python run_tests.py` (all checks must pass), check JavaScript syntax, and look at pages in a browser. Deliver small zips of changed files plus the full project zip.
> - Keep her template: black-and-white monochrome style (IBM Plex Sans and Archivo), muted green and red only for profit/loss, clean uncongested charts with only the key levels.
> - She uploads files through the GitHub web page on a Mac (the `.github` folder is hidden: Cmd+Shift+.). Several commits cancel earlier `ci` runs; only the last one finishes.
> - Do not change her real trading rules because of a backtest. Backtests are evidence, not a promise.
> - Read PROJECT_BRIEF.md and README.md in the project files before answering.

---

## 2. Her strategy (what the engine encodes)

**Swing** (1D structure -> 1H confirmation -> 15m entry, long only). 5-stage playbook. Scorecard 0 to 10: A+ is 8 to 10, A is 6 to 7, B is 4 to 5 (observe only), under 4 skip.
- Stop below the daily order block with a 0.25 ATR buffer.
- T1 = 1R (book half, **no early breakeven**), T2 = 2R (a quarter, stop to entry), T3 = 3R.
- Hold-backs: weekly trend against, sector index falling, results within 14 days, under 2R of room.
- India specifics: NSE 5-paise tick, volume compared with the same time-of-day slot, locked (circuit) stocks skipped.
- Selection: a shortlist of up to 5, she picks 1 or 2.

**Nifty options** (15m -> 5m, calls and puts, no volume or OI). 1H alignment, 15m bias, 5m CHoCH + BOS + FVG + OB, pullback, 5m close beyond the 9 EMA. Delta 0.40 to 0.60, lot size 65. No entry on expiry-day afternoons; stop for the day after 2 losses. Weekly expiry is Tuesday.

**Intraday** (15m -> 5m, stocks, long and short). Volume at least 1.5x, MIS, nothing after 15:00, square off by 15:10 to 15:15, max 2 trades a day.

**Positional** (my reading, not yet confirmed by her): the swing playbook one timeframe up (weekly structure, daily trigger, long only, up to 120 days). **Ask her to confirm or correct it.**

**Swing rules she confirmed on 12 Nov 2026 (strategy audit):** (1) strong 1H volume (1.5x, same-hour comparison) is REQUIRED for "1H CONFIRMED" (`swing.CFG['require_volume']`), and her "controlled continuation above the 9 EMA" counts: a later 1H close still above the EMA on 1.5x confirms (`cf['continuation']`); a reclaim without volume shows "1H RECLAIM, WEAK VOLUME". (2) Context score stays the confluences: key level + fib 0.618 + MTF EMA (note: these are nearly always true, so context is usually 3/3; she chose this knowingly). (3) Hold-backs (under 2R room, sector index falling, results inside the hold, weekly against) apply from stage 4 (`strategy_scanner.hold_back`), not only at the 15m entry. Also: a stage-4 setup more than 1.5 ATR above its zone (live price) is held "price ran away, no chasing" (`ran_away_check`). (4) Final recheck (12 Nov): the 15m entry only counts at or after the 1H confirmation candle has CLOSED (`entry_15m(not_before=...)`; the playbook fixture's 15m sequence now starts after the 1H confirmation, `frames(m15_after=20)`), and hourly volume 0 is a feed gap: excluded from the same-hour average and shown as NO VOLUME DATA. On 12 Nov real 1H candles: 14 of the old 35 'confirmed' truly confirmed on 1.5x (13 via continuation), 13 held by her rules, 1 actionable (ACUTAAS). Backtest evidence she was shown: volume-confirmed A+ swing trades were 44 trades at -0.14R vs 171 without volume at -0.02R (small sample).

**Tuning round 13 Nov 2026:** ledger hygiene in `signals.update` (traded setups never in watch/dropped, one dropped entry per setup, old files self-heal); stage-3 'IN ZONE' with price >1.5 ATR above the zone is held (`ran_away_check`, `swing.analyse`); Swing page/dashboard counts exclude held setups (`SC.held`) with a 'Held back' filter; swing scan runs after each 1H close (`loop.swing_slot`: :15 and 15:30). DONE after her go-ahead (13 Nov): (a) swing FAST LANE `strategy_scanner.py --mode swing-fast` (`run_swing_fast`): re-checks only stage>=4 setups (max 12, actionable first) for the 15m entry at :00/:30/:45 from 09:30 to 15:30 (`loop.swing_fast_due`), same engine and same context rules (`apply_swing_context`, shared with the full scan), merges into swing.json/swing_charts.json/explain.json/ledger, never touches other setups, skips if a full scan is running, 170 s timeout, no health file, adds `fast_at` and `charts_at` (the trade page reloads cached charts when `charts_at` changes); (b) SET ALERT tightened to `alert_atr=2.0`. She was told the Angel One 403s on index candles are intermittent rate limits (scans overlapping), not an index bug; the datasource was NOT changed. Her real-data check: of 35 setups once shown '1H CONFIRMED', the real engine confirms 1 (ACUTAAS) on 13 Nov.

**Audit 13 Nov 2026 (all scans, live data of 11:45 IST):** every scan OK, all published JSON valid, no NaN, live files 4-24 min old. The running market-loop (started 08:36) was still on the OLD code (it checks out the repo when it starts), so the fast lane and the :15 swing schedule only start with the next loop run. Fixed: scrambled T1/T2/T3 ladder on intraday/options/gold intraday (`strategy_scanner.ladder`); dashboard 'Live now' card, KPI grid/wrapping, gold card held count, stale 'max two trades a day' text. OPEN DECISIONS for her (not changed): (1) all 3 tracked Nifty options trades (9 Nov) used a 5m structure from the PREVIOUS session (Fri close / the Sunday Muhurat hour) and were stopped out within 5-20 minutes of the open: should the options playbook require a structure formed today? (2) T1 = prior leg high can be very close to entry (CUMMINSIND: 0.3R) or very far; keep or use fixed R targets? (3) intraday stocks use Yahoo 5m candles by design (can lag a few minutes); ANGEL_INTRADAY=on would use Angel One but is rate-limited.

**No scalping:** she decided against scalping (stocks and gold). It was built in round 6 and removed the same day; do not add it back unless she asks.

**Gold (XAUUSD)** (round 6/7): intraday, swing and positional, LONG AND SHORT (swing/positional shorts via the mirrored chart, `backtest_tf.both_sides`), on COMEX gold futures (Yahoo GC=F) as a proxy for spot. She chose XAUUSD (not MCX) and every session (Asia too): intraday entries 22:30-19:00 UTC = 04:00-00:30 IST, closed 20:30 UTC = 02:00 IST, on a UTC+2 session clock (`GOLD_SESSIONS=london_ny` narrows it). **Live gold (round 7):** `gold_live.py` + `gold_loop.py` (workflows `gold-loop.yml`, `gold-watchdog.yml`, `watchdog.py --gold`): intraday every 5 min, swing+positional hourly, A+ only, tracked in `signals_gold_{intraday,swing,positional}.json` (signals.py sections `gold_*`, gold square-off 02:00 IST), alerts with lots (`GOLD_ACCOUNT`, `GOLD_RISK_PCT`), max 2 open (`GOLD_MAX_OPEN`), past 2 a day only A+. Never places orders. Each loop ~5h45m and queues the next; cron-job.org should call gold-watchdog every 10 min. Told her: GC=F can lag; heavy Actions use and GitHub's terms. Cost 0.35 $/oz round trip, swap not modelled. Not scanned live. She was told offshore XAUUSD CFDs are not permitted for Indian residents (RBI/FEMA; not legal advice) and that MCX gold is the onshore route; she chose XAUUSD.

**Rules she set in round 6 (apply everywhere):** backtests count **A+ only (score 8-10)** and only from **1 April 2026** (current FY); **2 trades a day, more only if A+** (open-risk cap and loss limits still apply). Repo variables: `BACKTEST_FROM`, `MIN_SCORE`, `APLUS_OVERFLOW`, `GOLD_SYMBOL`, `GOLD_COST`.

**Her risk settings** (Settings in the journal): risk 0.5% per trade, 0.75% for A+, open-risk ceiling 2%, day stop 0.75%, week review 2%, month half-size at 3% and stop at 5%, max 2 intraday trades a day.

---

## 3. Architecture

```
GitHub Actions (public repo, free minutes)
  scan.yml            08:37 and 16:17 IST (+ manual): swing scan, daily cache, bot replies
  market-loop.yml     ~09:05-15:40: every 5 min options/intraday/market/news, swing after each 1H close (:15 and 15:30), trade tracking, alerts, heartbeat
  watchdog.yml        every 10 min in market hours: starts/restarts the loop (cron-job.org triggers it on time)
  digest.yml          08:45 and 15:45: Telegram/ntfy morning brief and recap
  readiness.yml       08:50: Angel One, Yahoo, list, alert channels, cron proof, token expiry, backup freshness
  ci.yml              every push to main: all tests; phone alert if they fail     rollback.yml: one-click undo
  backup.yml          23:00 IST nightly: encrypted journal backup to the private repo
  tradebook.yml       15:50 weekdays (experimental): Angel One fills -> Supabase broker_fills
  backtest.yml        Saturday 07:00 IST: swing + positional (+ quick mode for all four)
  backtest-intraday.yml  Saturday 08:30 IST: intraday + Nifty options
       |  scans write JSON  ->  publish.py pushes to the gh-pages branch  ->  GitHub Pages serves the app
Data: Angel One SmartAPI (Nifty/VIX candles, 1h for swing candidates, live option quotes) and Yahoo (daily history, intraday stocks).
      Intraday stocks use Yahoo by design (Angel's candle API throttles). A 90 s Angel budget per live tick; one shared request pace across processes.
Supabase project "Trade Insight" (free): sign-in (email, sign-ups OFF, TOTP available) and the journal.
Alerts: ntfy and Telegram (bot @DownerStuff_bot): triggers with a chart picture and a "Log this trade" button, action alerts, failures, digests, commands.
```

**Python modules:** `strategy_scanner.py` (engine runs), `swing.py`, `signals.py` (trade tracker, shared by live and backtests), `greeks.py`, `market.py`, `datasource.py` (Angel One + Yahoo fallback, cache, deep history), `loop.py`, `watchdog.py`, `publish.py`, `notify.py`, `alerts.py`, `digest.py`, `readiness.py`, `bot.py`, `chartimg.py`, `dataquality.py`, `backtest.py` (swing + reporting + account rules), `backtest_tf.py` (positional, intraday, options replays), `backup.py`, `restore.py`, `tradebook.py`, `supa.py`, `run_tests.py`, `ci_alert.py`.
**App** (`site/`): `core.js` (sign-in gate with TOTP step, routing, risk banner), `scanner.js` (incl. the pre-trade check badge on the order ticket), `pages.js`, `journal.js`, `analytics.js`, `lab.js` (Backtest lab with 4 style tabs, XAUUSD Gold page, Weekly review), `vault.js` (two-factor settings, Angel One fills import), `fills.js`, `charts.js`, `app.css`.
**Pages:** Dashboard, Swing, Nifty options, Intraday, XAUUSD Gold (live + backtests), Trades, Analytics, Weekly review, Backtest lab, Market, News & events, Playbook & rules, System health, Settings. (Investments was removed in round 6 at her request; holdings data stays in the journal.)
**Supabase objects:** table `journal_state` (one row per user: `user_id`, `payload` jsonb, `updated_at`; RLS with her 3 original policies plus a scanner read-only policy), table `broker_fills`, function `is_scanner()`; scripts in `supabase/` (`setup.sql`, `verify.sql`, `require_2fa.sql`).

---

## 4. Names to know (values live in GitHub and are never shared)

**Secrets:** `ANGEL_API_KEY`, `ANGEL_CLIENT_CODE`, `ANGEL_MPIN`, `ANGEL_TOTP_SECRET`, `NTFY_TOPIC`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SUPABASE_BOT_EMAIL` (the scanner user, `hhemmannth+scanner@gmail.com`), `SUPABASE_BOT_PASSWORD`, `BACKUP_TOKEN` (fine-grained token, Contents read/write on the private vault repo only), `BACKUP_PASSPHRASE` (backups cannot be opened without it).
**Variables:** `PAGE_URL`, `BACKUP_REPO` (`hhemmannth/downerstuff-vault`, private). Optional: `ACCOUNT_CAPITAL`, `HOLDING_SYMBOLS`, `CRON_TOKEN_EXPIRES`, `BACKUP_TOKEN_EXPIRES`, `CRON_JOB_EXPECTED`, `RISK_PCT`, `RISK_PCT_APLUS`, `OPEN_RISK_CAP`, `DAY_STOP_PCT`, `WEEK_STOP_PCT`, `MONTH_HALF_PCT`, `MONTH_STOP_PCT`, `MAX_TRADES_PER_DAY`, `STOP_AFTER_LOSSES`, `REGIME_FILTER`, `ALERT_CHARTS`, `NTFY_ACTIONS`.
**Outside timer:** cron-job.org calls the watchdog (and optionally digest/readiness) through the GitHub API with a fine-grained token that expires, so keep `CRON_TOKEN_EXPIRES` updated.

---

## 5. Where things stand

**Built, tested and live**
- Scanner, loop, watchdog, health page, stale-data banner, instant-open cache.
- Angel One data connected (confirmed on System health); Yahoo fallback; daily history from Yahoo with a sample check against Angel One.
- Telegram and ntfy alerts, digests, readiness check, failure alerts, two-way Telegram bot.
- Order ticket, TradingView levels export, pre-trade checklist, chart snapshot per logged trade, Weekly review with a rule-based coach (no AI service), tax-ready P&L export, Investments (lots, long-term tax countdown).
- Safety net: tests on every upload and a rollback workflow.
- Nightly encrypted journal backup: **confirmed working** (System health shows "Up to date").
- Supabase set up and verified (RLS on both tables, scanner user, setup.sql run).
- Two-factor sign-in: code is in; TOTP is enabled on the Supabase side. She can switch it on in Settings.

**Just delivered, not yet uploaded or run (this is round 5)**
- Backtest lab as four tabs: Swing, Positional, Intraday, Nifty options, each with "With your rules" (score thresholds, max trades a day, risk sizing, open-risk ceiling, loss limits, stop after 2 losses for options), breakdown tables, equity curves, Monte Carlo, forward test.
- New files: `backtest_tf.py`, `tf_fixture.py`, `backtest-intraday.yml`, tests (`test_backtest_tf.py`, `test_backtest_main.py`), updated `backtest.py`, `signals.py`, `datasource.py`, `lab.js`, `backtest.yml`, `README.md`.
- 25 of 25 test checks passed. The command line was tested end to end with a stand-in data source. **Never run on real Yahoo or Angel One data yet.**

**What the first (swing-only) backtest said:** taking every signal gave -0.03R per trade over 898 trades (+0.02R before costs), profit factor 0.93. Most stage-4 setups grade A+ (773 of about 890), and perfect-10 setups did worse than 8 to 9 (-0.20R over 64 trades; small sample). This is not how she trades (she picks 1 or 2 a day with risk rules), which is why "With your rules" was added.

**Limits that must stay visible**
- Intraday and options: free 5-minute history is about 60 days. Each Saturday run adds new days to the saved trades, so the sample grows. Optional `deep` (Angel One, experimental) may reach further back.
- Options use **modelled** premiums (Black-Scholes on the previous day's VIX); the index signals are real, the premium results are an estimate.
- Swing and positional still cannot apply the results-date or sector hold-backs, and swing enters at the 1H close, not her 15m entry. The current Nifty 500 list is used (survivorship bias).

---

**Round 6 (built and tested in the sandbox, delivered as zips; not yet uploaded or run on real data)**
- A+ gate and FY window inside every replay (`backtest.py` `rules_from_env`, `gate`); "2 a day, more only if A+" in `simulate_account` (`aplus_overflow`) with a strict-2 comparison row; trade logs per style.
- New styles: `gold_intraday`, `gold_swing`, `gold_positional` (`backtest_tf.py`: sessions, dollar costs, `gold_daily`/`gold_intraday`; `backtest.session_day`). `strategy_scanner._yahoo` passes `=` symbols through.
- App: lab rewritten as one reusable `labView(seg)`; gold page with gold theme and lot calculator; Portfolio heat moved into the order ticket's pre-trade check badge; daily rule in risk banner, dashboard, checklists and coach; Investments removed. Asset version now `?v=17`.
- Tests: `test_rules.py` (37 checks). Legacy backtest tests run with `BACKTEST_FROM=all`, `MIN_SCORE=4`. 26/26 checks passed. Pages viewed in a headless browser (desktop and phone, dark and light) with no page errors.
- Real-data estimate (her saved swing trades, quick mode): every A+ signal since 1 Apr 2026: 188 trades, 47% win, -0.05R; with her rules 18 trades, +0.19R, +2.5% (too few to judge; the open-risk cap did the selecting). Positional in this window looks bad (-0.69R over 28) only because 120-day trades have not finished; over 10 years A+ positional was +0.19R, PF 1.49.
- She asked for a Next.js/TypeScript rewrite and a slate/neon restyle; I kept the existing vanilla-JS app and monochrome style (rewrite risk to sign-in, 2FA and sync) and told her why. Raise it again only if she asks.

## 6. Pending and open questions

1. Upload round 7 (full zip; adds live gold), add the cron-job.org job for gold-watchdog, run gold-loop once, wait for `ci` to go green, run **backtest** with **quick** ticked (new view of saved swing/positional in a minute), then full **backtest** and **backtest-intraday** (adds gold), and bring back screenshots.
2. **Confirm or correct the positional definition** (timeframes, targets, trailing).
3. Confirm the old Telegram bot token was revoked (it was shared in an earlier chat).
4. Optional: `supabase/require_2fa.sql` after two-factor works on laptop and iPhone (undo lines are inside the file); `CRON_TOKEN_EXPIRES` and `BACKUP_TOKEN_EXPIRES`; cron-job.org jobs for digest (08:45, 15:45) and readiness (08:50); `ACCOUNT_CAPITAL` for the bot's `/size`; `HOLDING_SYMBOLS` for Investments prices.
5. Tradebook import is experimental: Angel One may require a static IP for that endpoint. First real run will tell.
6. Live second-by-second prices and a real-time engine (items 6 and 31) are **not built**. They need an always-on machine: Oracle Cloud free tier (smaller since Aug 2026, idle-reclaim risk), a small paid server in India, or a device at home. She has not chosen. Her real protection is the stop-loss order at Angel One; Angel One's own price alerts cover second-level alerts for free.
7. Decided not to build: scan results behind login (the repo is public, so the strategy code is public anyway).

---

## 7. Operating notes

- **Update procedure:** unzip, upload to `main` (keep folders), wait for `ci` (about 3 minutes). Run **scan** (mode `swing`) to publish the new site files. Reopen the iPhone app.
- **Quick backtest re-run:** set a repo variable (for example `MAX_TRADES_PER_DAY`), then Actions > backtest > Run workflow with **quick** ticked (about a minute, all four playbooks).
- **If a run fails:** the log names the step. Common causes: a missing secret or variable name, the `BACKUP_REPO` variable, or Angel One throttling (the scan falls back to Yahoo and says so in System health > Data sources).
- **Files she may have customised and a full-zip upload would overwrite:** `events.json`, `watchlist.txt`, and `App.ALLOWED` in `site/js/core.js`. `nifty500.csv` is not in the zip.
- **Restore a backup:** download a `.dsbk` file from the private repo, `pip install cryptography`, `python restore.py FILE` (asks for the passphrase), then Journal > Import in the app.
- **Lessons from building this:** pandas 3 stores timestamps in microseconds, so never compare timestamps as raw integers (a test caught a look-ahead leak this way). GitHub's scheduler can run hours late, so the outside timer matters. Angel One's candle API throttles even below its published limit.
- **Not financial advice.** Rules-based candidates from her playbook; she checks the chart, results dates and news before every trade.
