# DownerStuff: the four corrections (19 Nov 2026)

Base: GitHub `main` at `cdc0aaa` (18 Nov 2026; the audit fixes of 18 Nov were not uploaded yet), plus the audit commit `3ebeddd`, plus this work:
branch `fix/four-corrections`, commit `45cfe8d` and the documents after it. The six audit fixes are preserved (checked in the code and by the
full suite). Nothing was pushed: this session has read-only access, so the files come as a zip for upload. No trade was placed; no order code exists.

Work started in an earlier part of this session and was resumed, reviewed and completed here; the unfinished work was backed up before anything
was changed.

---

## Issue 1: gold on XAUUSD spot

### 1. Data source before and after
| | Before | After |
|---|---|---|
| Instrument | COMEX gold **futures** (Yahoo `GC=F`, continuous front month), labelled "XAUUSD" | **XAUUSD spot** (gold in US dollars per troy ounce) |
| Provider | Yahoo Finance via yfinance | **Twelve Data**, symbol `XAU/USD`, free Basic plan (8 requests a minute, 800 a day, free key, no card) |
| Fallback | Yahoo was the only source | **None.** No key, a failed request, a failed check or stale candles: "XAUUSD SPOT DATA UNAVAILABLE: NO GOLD RECOMMENDATION" |
| Why not Yahoo `XAUUSD=X` | - | Rejected: Yahoo stopped carrying gold spot under that symbol years ago, and its working gold symbol is the futures contract `GC=F` |

Every download is validated before any rule sees it (`gold_feed.py`): the answer must name `XAU/USD`; the quote currency must be USD; the base
must be gold; the type must not be a future. The symbol must not match futures or MCX patterns (`=F`, `GC…`, `MGC`, `COMEX`, `MCX`, `GOLDM`).
Prices must lie between 100 and 100,000 USD/oz and move no more than 6% between 5-minute candles (12% daily). Candles must not be stamped in the
future. Candles then pass the audit's candle hygiene, and the unfinished candle is dropped. Timestamps are requested in UTC and shown in IST.
Request budget at one scan every 5 minutes: about 410 of the 800 free daily requests (5m every run, 15m each quarter hour, 1h hourly, daily twice).

### 2. Proof that spot is used throughout the gold pipeline
- Every gold frame carries `attrs.source = 'spot:Twelve Data:XAU/USD'`. The live loader refuses any frame without it, and every gold trade, paper
  record and backtest file stores it (`test_audit2.py`, `test_gold_live.py`).
- **Example B** (`test_audit3.py`, a full gold scan with Twelve Data answers served offline in their real format):
  - every request URL asked for `symbol=XAU/USD` and nothing else;
  - `gold.json` says: instrument XAUUSD Spot, USD, USD per troy ounce, Spot Gold, source `spot:Twelve Data:XAU/USD`;
  - the trigger's entry is the close of the last finished spot 5-minute candle, and its stop, targets and zone lie inside those candles;
  - **recalculated, not converted:** the same candles 40 dollars higher (as futures sit above spot) give entry, stop and T1 exactly 40 higher,
    so levels come from the candles served, and nothing is stored or adjusted from an old futures level;
  - the same candles answered as `GC=F`: refused, no setup, no price, the reason shown;
  - spot candles 90 minutes old in an open market: no trade opened (stale-data fail-safe);
  - no volume in the candles: no trigger, and the page says why (see the volume decision below).
- 08:50 readiness now makes one real request and validates it the same way, reporting the last spot close in USD/oz, or FAIL with the reason.

### 3. GC=F removed from the gold analysis pipeline
A code scan test (`test_audit2.py`) fails if `GC=F` appears anywhere in the gold data or level code. The remaining mentions are only
(a) the refusal pattern, (b) labels on archived futures history, (c) tests proving refusal. The old `GOLD_SYMBOL` repo variable is ignored and
no longer passed by any workflow. `gold_feed.fetch_like` refuses any symbol other than XAU/USD. There is no hidden fallback: Yahoo is not
imported anywhere in the gold path.

### 4. Gold levels and modules recalculated
Nothing is converted: every gold number is computed fresh from spot candles on the next run, by the same engines.
| Module | Levels |
|---|---|
| `gold_live.py` (intraday 5m/15m, swing 1D/1H, positional) | swing highs/lows, liquidity sweep, CHoCH, BOS, FVG, order block, fib, zone, 9 EMA, volume check, entry, stop, T1/T2/T3, risk in USD and R, lots |
| `backtest_tf.py` gold intraday / swing / positional | the same, replayed on spot history |
| `signals.py` gold ledgers | tracked trades and paper records from spot only |
| `site/js/lab.js` gold page and gold backtest tabs | show spot results only; anything else is labelled "historical futures-based analysis" and not shown as XAUUSD |

**Historical data:** old gold backtest files are moved unchanged to `*.futures-archive.json`, labelled "historical futures-based analysis (COMEX
GC=F): excluded from XAUUSD spot statistics", and the next run starts fresh. Open gold trades from the futures era are kept, marked
`futures_based`, `excluded_from_stats`, and archived (not followed on spot). Nothing is deleted, and futures and spot histories are never joined.

**Gold sections now state:** Instrument: XAUUSD Spot · quote currency USD · USD per troy ounce · Spot Gold · data: Twelve Data XAU/USD (verified spot).

### Decision for you: volume on spot gold
Spot gold trades over the counter, so there is **no exchange volume**. Your gold rules require a volume confirmation. With the rule as written
(the default), **no gold trigger can ever be taken**, and the page says why. I did not switch it off, because that changes your strategy.
Your options:
1. Keep the rule: gold shows structure and zones but never triggers.
2. Set the repo variable `GOLD_VOLUME_RULE=off`: gold runs every rule except volume. This is a new strategy version; freeze it before paper testing.

### To switch gold on
1. Register at twelvedata.com (free Basic plan, no card) and copy the API key.
2. GitHub > Settings > Secrets and variables > Actions > New secret: `TWELVEDATA_API_KEY`.
3. Decide the volume rule (above).
4. Run Actions > readiness: "XAUUSD spot feed" must say it answered and passed the checks, with a current USD/oz price close to your broker's.

**Not verifiable here:** the real Twelve Data answer, its delay on the free plan (one comparison site calls free data "delayed") and how much
gold history the free plan serves for backtests. If the real answer's description differs from the documented format, validation refuses it and
gold stays off (fail-safe), so the readiness check is the first real test.

---

## Issue 2: loss limits by exit date

### 5. Journal schema changes (schema 2)
| Field | Meaning |
|---|---|
| `d`, `tm` | entry date and time (unchanged) |
| `xd`, `xtm` | **new:** exit date and time, stored on the trade. Required to save a closed trade, and never before the entry |
| `parts` | **new:** partial exits `[{d, tm, qty, px, chg}]`, each on its own date, never more than the position |
| `entry`, `exit`, `qty`/`cap`, `dir`, `chg`, `ovr`, `inst` | unchanged; realized gross and net come from `pnl.js` |
| `xd_unknown` | set by the migration on old closed trades without an exit date |
| journal `schema: 2` | migration marker |

**Migration (safe, additive):** on first load, each journal is copied **byte for byte, as stored** to `tji_backup_before_schema2_<id>` in the
browser, then marked schema 2. Nothing is deleted. Old closed trades get **no invented exit date**: they are flagged `xd_unknown`, still count in
totals, and count in no day, week or month until you add the date. The dashboard warns while any recent one is missing. The Angel One fills import
now writes the broker's real exit date and time. Cloud loads go through the same migration. The nightly encrypted backup also covers the
pre-migration state. Tested on an old journal (`test_journal_js.py`, part 3).

### 6 and 7. Daily and weekly loss: before and after (Example A)
`riskStatus` used to sum closed trades by **entry** date. Now `pnl.js` gives each realized leg its own exit date, and the day, week (Monday to
Friday on the IST calendar) and month sum those legs. Unrealized P&L of open positions is computed separately and never added in.

**Example A**: a swing entered Tue 10 Nov, closed Wed 18 Nov at 11:05 for −₹3,000; capital ₹2,00,000; your limits day 1%, week 2%:
| | Before (audit code) | After |
|---|---|---|
| Today | 0.00%, green, no message | **−₹3,000 = −1.50%**, limit ₹2,000, **used 150%, ₹0 left, red**: "Day is over: down 1.50% (limit 1.00%). No recovery trade." |
| This week | 0.00% | **−₹3,000 = −1.50%**, limit ₹4,000, **used 75%, ₹1,000 left, amber**: "Reduce size: down 1.50% this week." |
| Month | counted | −₹3,000 |

Other cases (all in `test_journal_js.py`):
- A trade closed last Friday is not in today or this week, but is in this month.
- An exit on Sunday 15 Nov falls in last week; an exit on Monday 16 Nov falls in this week.
- Partial exits: 50 @ 520 on 17 Nov (+₹970) and 50 @ 490 on 18 Nov (−₹520). Today = −₹520 and the week = +₹450, with nothing counted twice.
- Three instruments, long and short, sum correctly.
- An open position adds nothing to realized P&L.
- A closed trade with no exit date stays out of the day and week totals, and the banner warns (amber, not green).

The dashboard table shows, for today, this week and this month: realized P&L, the limit, used %, what is left, and status. Unrealized P&L is shown
apart.

### 8. Trade Insight
`site/js/pnl.js` is the single source of truth. It has no dependencies, runs alone (tested), and gives the journal the identical answer. Trade
Insight's repository could not be opened from here (private, or GitHub not connected), so it is **not changed or verified**. Exact steps are in
`TRADE_INSIGHT_INTEGRATION.md`, plus a one-minute check that Trade Insight keeps the new exit-date fields when it saves.

---

## Issue 3: backtesting without leakage

### 9. Hold-back leakage: what happened and what changed
Findings: the 18 Nov 2026 hold-backs were chosen **after** looking at the outcomes of the A+ trades from 1 Apr to 18 Nov 2026. The **same trades**
then scored them, and the "first 60% / last 40%" check sat inside that same window. So that window cannot validate them.
Changes:
- the window is labelled **Development: in-sample**;
- the Backtest lab no longer says the hold-backs "kept you out of worse trades";
- the phone summary marks headline numbers "in-sample window".
- **Validation window** (1 Apr 2025 to 31 Mar 2026): not used to choose the hold-backs, but **not untouched** either, because the 11 Nov 2026 full
  backtest (raw rules) already showed this period. It is labelled "independent of hold-backs", never "untouched".
- **Out of sample** (after the freeze): the only untouched evidence. It grows weekly and through paper trading.
- Windows are chronological, fixed on 18 Nov 2026, and each is scored only on its own trades.
- **Walk-forward:** consecutive 3-month windows of the frozen rules, with no re-fitting (re-fitting would be optimising, which you ruled out).
- Replays start at the validation window, so independent trades exist.

### 10. Strategy versioning
`strategy_config.py` collects every rule number from the modules themselves (structure, zones, confirmation, entries, stops, targets, hold-backs,
daily rule, sessions, costs, risk settings, switches such as `PLAYBOOK_V2` and `GOLD_VOLUME_RULE`), writes canonical JSON and hashes it (SHA-256).
- **Version 1.0.0** is frozen: 18 Nov 2026 17:02 IST, hash `7514b8e4…3cbf5056`, with the full configuration and the rules in words
  (`strategy_versions.json`).
- **CI fails** when the code's rules stop matching the latest frozen version. A rule change then needs `python strategy_config.py freeze 1.1.0 "what
  changed"`, which restarts that version's evaluation.
- Version numbers are never reused. Changing any single rule changes the hash (tested).
- Every tracked trade carries the version and hash. System health warns when repo variables change the effective rules.
- **Switching `GOLD_VOLUME_RULE=off` changes the hash:** freeze a new version first.

### 11. Options pricing methodology and limitations (Example C)
| Item | Used | How |
|---|---|---|
| Actual historical option prices | **No** | No free source of intraday historical NSE option prices was found (NSE bhavcopies give daily settlement prices only) |
| Underlying movement | Yes | Real Nifty 5m/15m candles decide entries, stops and targets (the live engine) |
| Option premiums | Yes | **Estimated** with Black-Scholes at the index level and time of each leg |
| Implied volatility | Yes | **Assumed**: previous day's India VIX, held constant (no skew, no smile) |
| Greeks | Yes | Estimated from the same model (strike by delta) |
| Bid-ask, slippage | No | Only the cost allowance (₹40 + 0.15% of premium turnover) |

Every options result is classified **THEORETICAL SIMULATION**: in the report file (`evidence: theoretical_simulation` with the table above), in
the phone summary ("Nifty options (THEORETICAL, estimated premiums)") and in the Backtest lab. It is never combined with price-verified results,
and no options edge is claimed from it.

### 12. Paper-trading validation
Each new tracked signal stores a **sealed copy** of the original signal: time, instrument, version, hash, entry, stop, targets, conditions. Its
SHA-256 is stored too. Later candles move the live stop and record hits, but never touch the seal. System health re-hashes every seal after each
scan, and a rewritten signal is a CRITICAL error.

When a trade closes, **one permanent paper record** is written:
- signal time, instrument, version and hash;
- entry, stop, targets;
- exit price and time;
- observed best, worst and last price, and the data source;
- the cost and **slippage assumptions written out** (slippage is now an explicit field: 0R separate, with any slippage coming out of the cost
  allowance);
- gross R, costs, net R and outcome.

Paper records are never pruned, and publishing never overwrites one already on the branch.

**Reporting classes, never pooled into one win rate:** Historical backtest · Out-of-sample backtest · Paper trading · Actual live trading
(your journal) · Theoretical options simulation.

---

## Issue 4: NSE holiday calendar

### 13. Source and status (Example D)
`market_calendar.json` is the **one** calendar. Every module reads it through `market_calendar.py`: loop, watchdog, scans, Nifty expiry, backtests,
digest, readiness and the app. `events.json` no longer holds holidays, and a test fails if holiday dates are hard-coded anywhere else.

| Year | Status | Applied | Source |
|---|---|---|---|
| 2026 | **Official** | 16 weekday holidays | NSE circulars NSE/CMTR/71775 and NSE/FAOP/71777 (12 Dec 2025). **Amendment found and added in this session:** Thu 15 Jan 2026 (Maharashtra municipal elections), circulars NSE/CMTR/72260 and NSE/FAOP/72262 (12 Jan 2026). It had been missing, so backtests and the loop treated it as a trading day |
| 2027 | **Awaiting the official NSE circular** | **none** | NSE had not published 2027 at the time of this work (expected in December, as 2026's came in December 2025). Third-party "2027 lists" disagree with each other, so none is used |

Also recorded:
- weekend holidays (listed, changing nothing);
- Diwali Muhurat (Sun 8 Nov 2026) as a special session, not scanned;
- settlement holidays as "not loaded" (the app does not use settlement dates).

The single provisional 2027 date shown is Republic Day, Tue 26 Jan 2027. It is labelled **provisional, NOT applied**: until the circular confirms
it, 26 Jan 2027 counts as a trading day and its Tuesday expiry is not moved by a guess. Readiness **warns from 1 Dec** and **fails from 1 Jan 2027**
while 2027 is missing.

**To add 2027 (December):** copy the dates from the NSE circular "Trading holidays for the calendar year 2027" into `market_calendar.json`, set
`status` to `official`, fill `source`, run `python run_tests.py`.

---

## 14. Files modified (since the audit commit)
- **New:** `gold_feed.py`, `market_calendar.py`, `market_calendar.json`, `strategy_config.py`, `strategy_versions.json`, `evaluation.py`,
  `site/js/pnl.js`, `test_audit2.py`, `test_audit3.py`, `TRADE_INSIGHT_INTEGRATION.md`, this report.
- **Changed:**
  - Python: `gold_live.py`, `backtest.py`, `backtest_tf.py`, `signals.py`, `readiness.py`, `loop.py`, `newsfeed.py`, `publish.py`,
    `strategy_scanner.py`, `validation.py`, `events.json`.
  - App: `site/js/journal.js`, `analytics.js`, `lab.js`, `pages.js`, `fills.js`, `vault.js`, `site/index.html` (cache version 26).
  - Workflows: `gold-loop.yml`, `backtest.yml`, `backtest-intraday.yml`, `readiness.yml`.
  - Tests adapted to the new single calendar, the spot feed and the new checks: `test_gold_live.py`, `test_rules.py`, `test_news.py`,
    `test_digest.py`, `test_backtest_main.py`, `test_journal_js.py`, `test_data.py` (own temporary cache, fixing an order-dependent flake).

## 15. Database migrations
- **Supabase:** no SQL change. The new fields live inside the existing `journal_state.payload` jsonb, so no table, column or policy changed.
- **Browser journal:** schema 1 to 2, as described in section 5, with a raw backup first. Tested through the real load path on an old journal:
  every trade and field kept, backup identical to the stored data, no exit date invented.

## 16 to 19. Tests
- **Full suite** (`python run_tests.py`): **34/34 checks passed** (32 test files + JavaScript syntax + workflow/JSON files).
- **Individual assertions:** **1,028 passed, 0 failed, 0 skipped** across 32 test files (counted per file in `TEST_RESULTS.md`; the invariants
  property test prints a table and passed). New this round: `test_audit2.py` 57, `test_audit3.py` 26, `test_journal_js.py` 38 (was 13).
- **Coverage:** 88% of 4,762 Python statements (tests excluded). New modules: `market_calendar.py` 97%, `evaluation.py` 95%, `gold_feed.py` 91%,
  `gold_live.py` 89%, `strategy_config.py` 80%; `signals.py` 98%. JavaScript: the journal and `pnl.js` maths are tested in Node, the rest by syntax
  check and page rendering.
- **Application startup:** the app served locally with fixture data and opened in headless Chromium. Dashboard, XAUUSD Gold, Journal, Backtest
  lab, News & events and System health all rendered with no script errors. The gold page shows the spot instrument line, and News & events shows
  "2026 official, 2027 provisional, NOT applied" and the 24 Nov expiry moved to Mon 23 Nov.
- **Failures found and fixed during this session:**
  - the migration backup was taken after normalising (now the raw record);
  - the paper record lacked an explicit slippage field;
  - readiness only checked that a key existed (it now validates a real answer);
  - the phone summary did not label options THEORETICAL;
  - the 2026 calendar missed 15 Jan;
  - the validation window was described as "never looked at";
  - `test_data` depended on a cache left by other tests.

## 20. Remaining risks
1. **Not ready for live trading.** The rules are frozen as of today, and no out-of-sample or paper evidence exists yet for version 1.0.0. The only
   earlier full swing backtest was slightly negative after costs.
2. **Gold is off until you act:** add the key, decide the volume rule, and pass readiness. Its real feed, delay and history depth were not seen here.
3. **Trade Insight** still dates loss by entry until the steps are applied there.
4. **Old trades without exit dates** stay out of daily and weekly limits until you add them (the banner says so).
5. **2027 holidays** must be added from the NSE circular in December.
6. Options results stay theoretical; real option evidence can come only from paper or live fills.
7. Earlier open items still stand (costs to calibrate from contract notes, entry at the trigger close, survivorship): see `REMAINING_RISKS.md`.

## 21. External integrations not verified
Twelve Data (real answers, delay, free-plan history depth), Angel One, Yahoo, Supabase (live RLS, cloud sync of schema 2), Telegram and ntfy
delivery, GitHub Actions schedules in production, and Trade Insight. All were exercised only with deterministic stand-ins.

---

## Final verdict: **READY FOR EXTENDED PAPER TESTING** (unchanged), with gold **NOT READY** until the steps above pass

The four corrections are implemented and tested. Gold can no longer be computed from futures, realized losses count on the day they happen, the
evaluation can no longer pass in-sample results off as validation, and the calendar is official and centralised. This removes real defects,
but it is not evidence that the strategy makes money. That evidence can only come from trades taken after today's freeze, under frozen rules,
over weeks to months of paper trading. A profitable-looking backtest would not change this verdict, and nothing in this work justifies an upgrade.
