# DownerStuff

Scanner, journal, analytics, market and news in one app, built on your swing playbook. Runs in GitHub (Actions + Pages); open it on your iPhone or laptop.

## Update your repo (replace the old code)
1. Upload everything in this folder to your repo's **main** branch (Add file > Upload files), keeping the folders (`site/js/...`, `.github/workflows/...`).
2. Delete these old files from the repo if they are there: `oi.py`, `test_oi.py`, `site/ds.js`, `site/ds.css`.
3. Actions > **scan** > Run workflow (mode **all**). This publishes the new app to the `gh-pages` branch. Pages settings stay as they are (Deploy from a branch: gh-pages, root).
4. Open the site, go to **Settings** and sign in with your Trade Insight account: your journal syncs (same cloud data as Trade Insight).
5. On the iPhone: Safari > Share > Add to Home Screen (the icon is new).

Nothing else changes: the market loop still scans every 5 minutes during market hours, swing hourly at :25 plus 08:37 and 16:17, and phone alerts still come from ntfy (they now open the exact trade).

## What is in the app
| Page | What it does |
|---|---|
| **Dashboard** | Indices and regime, today's swing shortlist (max 5, pick 1 or 2), your risk status against your daily, weekly and monthly limits, open positions and tracked signals, insights, events |
| **Swing** (primary) | The playbook pipeline: Entry · 1H confirmed · In zone · Set alert · Developing. Setup cards with stage, score, levels, ticks and cautions. **Why isn't a stock here?** type any NSE symbol to see the step where the scan stopped |
| **Nifty options** | 1H alignment, 15m bias, 5m setup and trigger, strike by delta (Black-Scholes with India VIX). No volume or OI rules |
| **Intraday** | Liquid Nifty 500 stocks, long and short, MIS rules |
| **Trade page** | 1D / 1H / 15m charts with the zone, fib, CHoCH/BOS, entry, stop and targets; the playbook checklist; scorecard; plan; position size from your capital and risk; tracking timeline; **Log trade** |
| **Journal** | Your trades (same format and cloud as Trade Insight): add, edit, close, filter, CSV and backup export, import |
| **Analytics** | Net P&L, win rate, expectancy, profit factor, drawdown, streaks, equity / drawdown / R curves, monthly and calendar views, R distribution, rolling progress, edge finder (setup, segment, grade, timeframe, weekday, hour, emotion, rule break, regime, event, exit, direction, source), discipline, MAE/MFE, signals vs your execution, insights |
| **Market / News** | Regime, expected move, breadth, sector strength, playbook by segment; headlines by topic, events calendar, risk flags |
| **Playbook & rules** | Your swing playbook walk-through, timeframe tables, scorecard and your 29 rules |
| **System health** | Is the 5-minute loop alive (last tick, next tick, scan time), how fresh each section is, the last scans and what failed, symbols with no data |
| **Settings** | Cloud sign-in, journals, risk rules (capital, risk per trade, loss limits), theme |

## Keeping the live scans running
- **market-loop** scans every 5 minutes from about 09:05 to 15:40 and runs the swing scan hourly at :25. It writes a heartbeat (`data/health/loop.json`) on every tick.
- **watchdog** runs every 10 minutes in market hours. No loop running or queued: it starts one. Loop silent for 20 minutes: it cancels and restarts it. It sends a phone push only when it acts, and does nothing on weekends, NSE holidays and outside 09:10-15:25.
- **In the app** a red banner appears on every page when live data is more than 11 minutes old in market hours, with a link to start the loop.
- **On-time starts (recommended):** GitHub sometimes skips scheduled runs. On cron-job.org (free, time zone Asia/Kolkata) add one job, Monday to Friday, every 10 minutes from 09:05 to 15:25:
  `POST https://api.github.com/repos/hhemmannth/downer-stuff-stox/actions/workflows/watchdog.yml/dispatches` with body `{"ref":"main"}` and headers `Authorization: Bearer <fine-grained token: this repo only, Actions read and write>`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`. A successful call returns 204. Extra calls are harmless.
- **scan** (manual or 08:37 / 16:17) is separate: it does one scan and stops. You never need to run the loop before it.

## Swing: how the scanner follows your playbook
| Stage | Playbook step | What the scanner checks |
|---|---|---|
| 1 Developing | 1D CHoCH | First daily close above the last lower high after lower highs and lower lows. Alert only |
| 2 Set alert | 1D BOS with displacement, FVG + OB, fib, key level | Strong candle (body ≥ 1 ATR) closing above the swing high; OB = last down candle before it; FVG; fib 0.618–0.705 of the leg; round number / broken level in the zone |
| 3 In zone | 1H pullback | Price is back in the daily zone |
| 4 1H confirmed | 1H rejection + close above the 9 EMA on ≥ 1.5x volume | Volume is compared with the same hour on earlier days |
| 5 Entry (TRIGGERED) | 15m precision entry | 15m CHoCH + BOS + FVG inside the zone, a controlled retest, then a 15m close above the 9 EMA on ≥ 1.5x volume. If price has already run away: no chasing |

Weekly location (trend up, near support) and the liquidity sweep are shown on every setup. An entry is **held back** (shown, not alerted) when the weekly trend is against it, the sector index is falling, results fall within 14 days, or the nearest overhead swing high is less than 2R away (your "target at least 2R" rule).

Plan: stop below the daily OB with a 0.25 ATR buffer; T1 = 1R (partial), T2 = 2R, T3 = 3R; trail by daily structure. Tracking follows your rules: no breakeven at T1, stop to entry at T2.

Scorecard: Structure 0–2, Zone 0–2, Confirmation 0–3 (1H), Context 0–3 (key level, fib 0.618, MTF EMA; futures OI is on the checklist for you to check). A+ 8–10, A 6–7, B 4–5, under 4 no trade.

Daily swings are read with a zigzag (a swing counts once price reverses by 0.8 ATR), which marks structure the way you do by eye. On your playbook's own example the engine finds the same OB (1,041–1,052), FVG (1,055–1,076), fib zone (1,060–1,065), 1H rejection (1,053), 15m CHoCH 1,061 / BOS 1,065 / FVG 1,065–1,069 and the 1,070 entry with the stop near 1,036: 10/10 A+ (`test_swing.py`).

## Options (Nifty)
1H alignment (price on the trade's side of the 1H 9 EMA) → 15m CHoCH bias, previous-day high/low sweep, 9 EMA → 5m CHoCH + BOS, FVG + OB, fib, pullback, 9 EMA close. Open interest is no longer used anywhere. Held back on expiry-day afternoons and after two losses in a day. No new options or intraday trades after 15:00.

## Market data: Angel One first, Yahoo as the fallback
With the four Angel One secrets set, candles and quotes come from **Angel One SmartAPI**: the exchange's own data, free with your
Angel One account. Anything Angel cannot serve (a failed login, an unknown symbol, an API error) falls back to **Yahoo Finance**,
one symbol at a time, so a scan never comes back empty. Without the secrets everything runs on Yahoo as before.
Reading data needs no static IP: SEBI's static-IP rule (from 1 April 2026) applies to placing orders, and this app never places orders.

What it improves:
- **Accuracy:** official NSE candles and volumes. Nifty options use the **live option price** (volatility implied from the live chain instead of India VIX) and show the live last price, bid, ask and spread.
- **Speed:** a year of daily candles for the Nifty 500 is downloaded once a day and cached (kept between runs by `actions/cache`). The hourly swing scans reuse it with no daily download at all; after the close only today's candle is added (one quote call per 50 stocks).
- **A check you can see:** System health → Data sources shows where each run's candles came from and compares recent closes between Angel One and Yahoo.

Set it up (once):
1. Log in at **smartapi.angelone.in**, create an app (a Trading API key also covers market and historical data) and copy the **API key**. If the form asks for a static IP, your home internet IP is fine: it only limits order placement.
2. On the SmartAPI site, enable **TOTP**. It shows a QR code and a text **secret** (letters and digits). Copy the text secret.
3. In GitHub → Settings → Secrets and variables → Actions → **Secrets**, add: `ANGEL_API_KEY`, `ANGEL_CLIENT_CODE` (your Angel One client ID), `ANGEL_MPIN` (your 4-digit login PIN) and `ANGEL_TOTP_SECRET` (the text secret from step 2).
4. Run Actions → scan → mode `swing`, then open System health → Data sources: it should say **Angel One: connected**. If not, it shows the reason (for example "login failed: Invalid totp") and the scan carries on with Yahoo.

## Phone alerts: ntfy and/or Telegram
Every push (triggers, scan updates, T1/T2/T3, stops, expiry, watchdog restarts) goes to every channel you set up. Either one alone is enough.
- **ntfy:** the `NTFY_TOPIC` secret, as before.
- **Telegram:** open Telegram, message **@BotFather**, send `/newbot` and follow the steps; copy the **bot token**. Open your new bot and send it any message. Then open `https://api.telegram.org/bot<YOUR TOKEN>/getUpdates` in a browser and copy the number after `"chat":{"id":`. Add the secrets `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (several chat ids can be separated by commas). Messages come with an **Open in DownerStuff** button that goes straight to the trade.
- Test both: Actions → scan → tick **test_alert** → Run workflow.

## Backtest lab, new pages and alert upgrades (final bundle)
**Backtest lab (Research > Backtest lab).** The `backtest` workflow replays your swing playbook on about two years of history with the live engine (`swing.analyse`) and the live trade tracker (`signals.walk`), every Saturday 07:00 IST or by hand (Actions > backtest > Run workflow; 30 to 45 minutes for the 250 most liquid stocks, set `top` to 0 for all 500). The page shows expectancy after costs, win rate, profit factor, drawdown, an equity curve, results by grade, score, confirmation, zone, context, market regime, sector, weekday, month, volume and stop width, a first-60% / last-40% split, rule variants (volume 1.2x / 2.0x, stop buffer 0.15 / 0.40 ATR, narrow zones) that only count as better when they win in both halves, a Monte Carlo of what a year can look like at 0.5%, 0.75% and 1% risk, and a live forward test that compares tracked signals with the backtest.
What it cannot replay, also stated on the page: the 15m precision entry (the entry is the 1H confirmation close), results-date and sector hold-backs, and stocks that left the Nifty 500. The window is about two years because free hourly history stops there.

**Scanner upgrades.** Relative-strength rank (RS 0-100) on every setup; data-quality checks (probable split or bonus, bad ticks, halted stocks) that keep bad candles out of the scan and explain why under "Why isn't a stock here?"; a note when the backtest says the current market regime has been weak for the playbook (set the variable `REGIME_FILTER` to `hold` to hold those setups back instead); ex-dividend notes for stage 4 and 5 setups; a Portfolio heat card (three or more candidates in one sector, pairs that move together); India VIX percentile and a bid-ask spread warning on options (with Angel One).

**Alerts.** Trigger alerts on Telegram carry a clean chart picture (zone, entry, stop, T1, T2) and two buttons: Open in DownerStuff and Log this trade (opens the journal form pre-filled). Action alerts tell you when an A+ setup enters its zone, when the 1H confirms, when a setup you were waiting on is invalidated and when its sector index turns down (at most 6 per scan; `NTFY_ACTIONS=off` to stop them, `ALERT_CHARTS=off` for text only).

**Telegram bot.** Send `/setups`, `/why SYMBOL`, `/size SYMBOL`, `/open`, `/status`, `/brief`, `/recap` or `/help` to your bot. It answers only your chat id. There is no server waiting for messages, so it replies when a scan runs: within 5 minutes during market hours. `/size` needs the variable `ACCOUNT_CAPITAL`.

**Trade page.** Order ticket (quantity from your capital and risk, entry, stop, targets, product) with a Copy button; you place the order yourself. Copy TradingView levels gives a Pine script that draws the zone, entry, stop and targets.

**Journal.** A pre-trade checklist appears before a new trade is saved (your rules for swing, options or intraday); unticked rules are saved with the trade. Trades logged from the scanner keep a small chart of the moment they were logged.
**Weekly review (Journal > Weekly review).** Net result, R, rule breaks, a plain-language note on every trade from a rule-based coach (no AI service, nothing leaves your device), the one thing to fix next week, what your own scanner trades say about the scorecard, and a tax-ready P&L download per financial year (intraday, F&O and delivery kept apart, with turnover).
**Investments (Journal > Investments).** Long-term lots with value, gain, days held, the date each lot becomes long-term for tax, an estimate of tax if sold today, and drift from your target weights. Set the variable `HOLDING_SYMBOLS` (for example `NIFTYBEES,JUNIORBEES`) to have the scan fetch their prices; quantities never leave your journal.

**Optional repo variables (Settings > Secrets and variables > Actions > Variables).**
| Variable | What it does |
|---|---|
| `ACCOUNT_CAPITAL`, `RISK_PCT`, `RISK_PCT_APLUS` | capital in rupees and risk per trade (default 0.5 and 0.75) for the bot's `/size` |
| `HOLDING_SYMBOLS` | comma-separated NSE symbols of your long-term holdings, priced every 30 minutes |
| `REGIME_FILTER` | `hold` = hold back setups when the backtest says this regime is weak (default: a note only) |
| `ALERT_CHARTS`, `NTFY_ACTIONS` | `off` switches off chart pictures or action alerts |
| `CRON_TOKEN_EXPIRES`, `CRON_JOB_EXPECTED` | see the readiness check above |

**Not in this bundle** (each needs something outside this repo, so it could not be tested here): results behind your login and a nightly journal backup (need a table and policies in your Supabase project), importing your Angel One tradebook, two-factor sign-in, and second-by-second live prices or a real-time engine (need an always-on server). The journal's own Export button remains the way to back it up.

## Your daily routine and safety net (batch 1)
| Time (IST) | What runs | What you get |
|---|---|---|
| 08:37 | scan (swing) | the day's swing list and daily cache |
| 08:45 | **digest** (morning) | a phone message: market, expected move, swing shortlist, held-back setups, results due, events, open trades |
| 08:50 | **readiness** | one message: "Ready for the session" or exactly what to fix (Angel One, Yahoo, Nifty 500 list, alert channels, did cron-job.org fire yesterday, token expiry, last swing scan). The result also shows on System health |
| 09:05-15:40 | market-loop + watchdog | live scans every 5 minutes, restarted automatically if they stop |
| 15:45 | **digest** (evening) | triggers, targets and stops today, open trades, tomorrow's watch and events |
| 16:17 | scan (swing) | tomorrow's list |

**Failure alerts.** If a scan section fails, a data source stops answering, Yahoo returns too few stocks, Yahoo and Angel One disagree by more than 1.5%, the live scan fails twice in a row, or publishing fails three times in a row, your phone gets one message (and one "recovered" note afterwards). The same problem is not repeated for 1 to 3 hours. Two tracked option losses in a day also send "Options paused for today".

**Risk limits in the app.** The limits from Settings (day, week and month loss, open-risk cap, intraday trades, two full-risk losses) are checked on every page: a red or amber banner appears as soon as a limit is reached, with a pop-up and a short vibration the first time each day (tap "Turn on pop-up alerts" once per device). Your journal lives on your device and in your Supabase account, so this check runs in the app, while it is open.

**Safety net on uploads.** Every time you upload files to main, the `ci` workflow runs all the tests (about 2 minutes). If anything fails you get a phone alert naming the failing check. To undo an upload: Actions > **rollback** > Run workflow > type `yes` (it reverts the last commit; if that commit changed files under `.github/workflows`, GitHub does not allow a workflow to edit those, so undo those files by hand). You can also run `python run_tests.py` yourself.

**Outside timer for the new workflows (recommended).** On cron-job.org add three more jobs (Monday to Friday, same headers and token as the watchdog job), all `POST` to `https://api.github.com/repos/hhemmannth/downer-stuff-stox/actions/workflows/<file>/dispatches`:
- `digest.yml`, 08:45, body `{"ref":"main","inputs":{"mode":"morning"}}`
- `readiness.yml`, 08:50, body `{"ref":"main"}`
- `digest.yml`, 15:45, body `{"ref":"main","inputs":{"mode":"evening"}}`

**Two repo variables (Settings > Secrets and variables > Actions > Variables).** `CRON_TOKEN_EXPIRES` = the date your cron-job GitHub token expires (YYYY-MM-DD): the readiness check warns 14 days before. `CRON_JOB_EXPECTED` = `off` if you do not use cron-job.org (switches off that check).

**Market data.** The year of daily candles comes from Yahoo (about a minute for the whole Nifty 500, and it matched Angel One on every close we compared). Each morning a sample of stocks plus Nifty is checked against Angel One and shown under System health > Data sources. Angel One serves the Nifty candles, the hourly candles for swing candidates and the live option prices. Intraday stocks use Yahoo by design.

## Tests (no internet needed)
`python test_swing.py`, `test_scanner.py`, `test_pipeline.py`, `test_signals.py`, `test_publish.py`, `test_invariants.py`, `test_watchdog.py`, `test_datasource.py`, `test_alerts.py`, `test_digest.py`, `test_backtest.py`, `test_quality.py`, `test_notify2.py`, `test_bot.py`, `test_data.py`, `test_greeks.py`, `test_market.py`, `test_news.py`, `test_sector.py`

## Limits
Without the Angel One secrets, data is Yahoo Finance (unofficial, can be delayed) and option premiums are model prices. With them, premiums at your stop and targets are still model estimates around the live price. Results dates come from Yahoo and can be missing (check NSE). Rules-based candidates, not investment advice.
