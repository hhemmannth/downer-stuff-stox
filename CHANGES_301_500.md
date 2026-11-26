# DownerStuff: items 301-500 status (25 Nov 2026, asset version 35)

Your strategy, entry and exit rules, indicators, hold-backs, the gold volume rule and your API credentials were not changed. Nothing places a real trade; there is no live order code in the tool. No journal data is deleted by any of these changes: every new journal field is additive.

**What the marks mean**
- **Done:** built and checked in a headless browser or by an automated test on my machine.
- **Partly:** built, but part of it could not be built or checked here (the reason is given).
- **Not possible:** cannot be built with the data or permissions the tool has.

"Tested" here means my local copy of your site with test data, or the Python tests. **Nothing was run on GitHub Actions or on your iPhone.**

## 301-360 Final touch: the shell (batch 11)

**Done**
- Error capture and the error log (Settings → Copy error log). One broken card shows a fallback instead of blanking the page.
- An offline copy through a service worker:
  - versioned files come from the cache;
  - data and pages come from the network, with the cached copy as a fallback.
- A "new version ready" notice, plus an automatic retry when nothing loaded.
- Remembered filters, recently viewed symbols, and a watchlist with pins.
- Breadcrumbs and Copy link.
- Glossary hints, glass tooltips, count-up numbers, the A+ ring, avatars and sector dots.
- Directional page transitions, keyboard shortcuts (press ?), swipe between pages, and a collapsible sidebar.
- Command actions in search, and one-time tips.
- Help (with a system map), Glossary, Privacy and Launch checklist pages.
- Privacy page: download all your data, and delete the cloud copy.
- Fixes at 320 px: every page fits a small phone.

**Partly**
- **325, GitHub Actions minutes used:** needs a token with billing access, which the workflows do not have. Not built.

**Done (from 324, 326, 327)**
- The workflow schedule check.
- A phone push when a system check fails.
- Publishing never replaces a good data file with a broken one.

## 361-372 Charts: last touches (batch 12)

**Done**
- Measure tool.
- Draw lines and boxes. They are saved with your journal and synced; you can undo the last drawing.
- Candle-by-candle replay.
- Heikin-Ashi and line styles.
- 1.5× volume dots in the Full view. Labels hide while you drag.
- Export the chart's candles as CSV.
- Score badges (Structure, Zone, Confirm, Context).
- A strip showing every timeframe, a zone touch count, and a side-by-side comparison of two stocks.

**Not possible**
- **366, option chain / open interest:** the tool has no OI data source (Angel One candles and Yahoo only).

## 373-400 Journal, security and settings (batch 13)

**Done: journal and review**

| Item | What it does |
|---|---|
| 373 | Five review questions on every trade. |
| 374 | Tags with suggestions. Journal search finds `#tag`. |
| 375 | Mood and energy before trading (1-5) on the Journal page. Two new Edge finder views in Analytics: mood and energy. |
| 376 | A streak of trading days in a row without a rule break. |
| 377 | Trade of the week, or last week's best when this week has none. |
| 378 | The scanner's planned entry, stop, T1 and grade are stored with a trade logged from the scanner. The form shows them next to yours, with the slippage in R. |
| 379 | Your own rules from your lessons. Add them in Settings, or double-tap a lesson in Analytics. They appear under the pre-trade checklist. |
| 380 | A monthly report page (`#/monthly`). It goes month to month and can be saved as a PDF. |
| 381 | A "Drawdown and risk of ruin" card in Analytics. It reshuffles your own R results 2,000 times at your normal risk. It is not a forecast and changes no setting. |
| 382 | A capital tracker for deposits and withdrawals. It shows the account value now. |
| 383 | Goal progress bars: a monthly R target and a rule-break limit. |
| 384 | A reminder when results are due within 3 days on an open trade (Journal and Today). |
| 385 | The alert's "Log this trade" button opens the trade form. This was already wired; I verified it in the code. |

**Done: security and settings**

| Item | What it does |
|---|---|
| 387, 388 | A screen lock with a PIN (stored as a hash) and an inactivity timer. |
| 391 | A change log of adds, edits and deletes, with the device that made each one. |
| 392 | Start in private mode. |
| 397 | Settings export and import, to move to a new phone. |
| 398 | Feedback notes for the next update, with Copy all. |

**Partly**
- **388, Face ID / fingerprint (WebAuthn):** built, but not tested. The test browser has no Face ID. The PIN lock is tested.
- **The lock in general:** it is a privacy screen, not encryption.
- **396, walkthrough:** the first-visit tour from version 34 is kept. A step-by-step walkthrough of every page was not added.

**From the final-touch layer**
- 386, 399, 400, and the rest of 386-400, were built there.

## 401-430 Server-side data checks (batch 14, `checks.py`)

These run after every scan and appear on System health. Each check that crashes or lacks its input shows as **not tested**, never green. Every check below is **done** and tested on your last published data, with no false alarms.

**What `validation.py` already checked**
- Plan geometry, chart candles, freshness and the stale-data fail-safe.
- The sealed paper records and the frozen strategy version.
- The gold instrument, the holiday calendar, and data sources (Angel One vs Yahoo, candle hygiene).

**What `checks.py` adds**
- Every published JSON file opens.
- Setup rows:
  - duplicate rows;
  - stage outside 1-5;
  - a score above its maximum;
  - a held-back setup shown as triggered;
  - a zero price;
  - a swing price more than 25% from the entry (a stale feed or a split);
  - a results countdown that does not match the results date.
- Setup counts per section, and failed downloads.
- Timestamps carry a timezone.
- Missing sessions in the daily charts.
- Nifty spot and VIX are present and in range.
- The sector map: every setup has a sector, and the map is recent.
- Tracked trades:
  - a stop is never moved against the trade;
  - events are in time order;
  - no target is hit before the trade existed;
  - every closed trade has an exit.
- Backtests are recent and have a window.

## 431-445 Journal integrity (browser)

**Done.** These checks run on System health → Journal checks, with a link to each trade. They only list problems; they never change a trade.
- Duplicate ids.
- Missing or future dates.
- An exit date before the entry date.
- An exit price without an exit date.
- Zero quantity or zero entry.
- A stop equal to the entry, or on the wrong side.
- An exit more than five times away from the entry (a typo?).
- Partial exits larger than the quantity.
- Fields that are not numbers.
- A trade open for more than 90 days.
- A setup that is not in your setups list.
- Likely duplicate trades.

## 446-462 Front-end checks

**Done**
- "Run all checks now" on System health checks:
  - browser storage, and the space used;
  - whether the browser keeps storage;
  - the offline copy;
  - that all page files are the same version;
  - errors today;
  - the device clock against the server;
  - online status;
  - scan data freshness;
  - data file shape;
  - journal consistency;
  - the cloud copy.
- The UI test now covers every page:
  - desktop and phone, in both light and dark;
  - small phones (320 px), in light.
- Error log and card fallbacks (from batch 11).

## 463-478 Workflows and secrets

**Done**
- Secrets present: reported by **name only**, never a value. This runs only on GitHub.
- Leak scan: fails as CRITICAL if any secret value appears in a published file. The value is never written anywhere.
- Every workflow the desk needs exists with its schedule or trigger.

**Partly**
- **Actions minutes:** needs billing access (see 325).

## 479-486 Alerts

**Done**
- Duplicate alerts were already blocked.
- New rate limit: at most 12 trade alerts a run (`NTFY_MAX_PER_RUN`). The rest are folded into one summary.
- New alert log: time, title, channel, and failures. It never holds the topic, a token or a chat id. System health shows it.
- A failing system check is pushed once.

## 487-494 Self-healing

**Done**
- **487:** the scan retries once after a crash, 60 seconds later.
- **490:** the app reloads data and re-syncs the journal when the phone wakes after 5 minutes or more, or comes back online.
- **494:** data ages are corrected for a wrong device clock.

**Already existed**
- **488:** Angel One falls back to Yahoo.

**Partly**
- **491-493:** the offline copy and the automatic retry on load are covered by batch 11.

**Not done**
- **489, rebuilding the paper ledger automatically.** The ledger is sealed by design, and rebuilding it silently would undo that protection.

## 495-500 Reporting

**Done**

| Item | What it does |
|---|---|
| 495 | The evening digest has a system-checks line. |
| 496 | The Saturday digest reports this week's runs and the failing checks. |
| 497 | An errors history of the last 90 runs, on System health. |
| 498 | A "Run all checks now" button, with a link to re-run the server checks. |
| 500 | The launch checklist now includes this device's checks. It stays a paper-trading checklist; there is no live trading. |

## Not verified

- The workflow changes have not run on GitHub:
  - the scan retry;
  - the alert log, rate limit and health push;
  - the digest lines;
  - the server checks inside a real scan.
- Face ID / fingerprint unlock.
- How everything looks and behaves on your actual iPhone.

## Test run (25 Nov 2026, on my machine)

The full suite ran with `python run_tests.py`: **ALL GOOD, 37/37 checks passed**. These include:
- `test_checks.py` (new);
- `test_ui_pages.py`, which covers every page:
  - desktop and phone, in light and dark;
  - small phones (320 px), in light.

Separate headless-browser scripts were also run. They cover batches 11-14: journal additions, the lock, health checks, charts, sync conflicts and the phone layouts. All of them passed.

## How to install

1. Unzip and upload everything into your repository's main branch. Keep the folders as they are: `site/`, `site/js/`, `.github/workflows/`. Then wait for **ci** to go green.
2. Actions → **scan** → Run workflow. This publishes the site and writes the first server checks.
3. Restart **market-loop** and **gold-loop** (cancel the running ones, then Run workflow).
4. On the phone, open the site and hard refresh (Cmd+Shift+R on a Mac). Open the Launch checklist (Help menu, or `#/launch`): it should say "asset version 35" and be green apart from lines that need market hours.
5. Optional settings:
   - `NTFY_MAX_PER_RUN` (default 12);
   - `NTFY_HEALTH=off` to stop the system-check push.
