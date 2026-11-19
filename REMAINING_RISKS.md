# Remaining risks (audit of 18 Nov 2026)

Ranked by how much each could cost you. Details and IDs in `BUG_TRACKER.md`.

1. **Gold levels are futures, not spot (O-01).** Computed on COMEX `GC=F`, labelled XAUUSD. Basis of roughly $10 to $60 and roll jumps. Re-read every gold level on your XAUUSD chart; do not place broker orders from the alert numbers as they are.
2. **The edge is unproven out of sample (O-02, O-03).** The hold-backs were fitted on the same 2026 trades they are scored on; the first full swing backtest (before hold-backs) was -0.03R per trade after costs; the options tab uses modelled premiums. Only trades taken after the rules are frozen can show whether the playbook works. Backtests are evidence, not a promise.
3. **Loss limits can miss realised swing losses (O-04).** The banner counts a trade on its entry date. A swing stopped out today does not trip today's or this week's limit.
4. **Data you cannot see from here.** Angel One, Yahoo, Supabase, Telegram and GitHub schedules were not exercised with real credentials. The readiness check (08:50) and System health are the production evidence; read them each morning.
5. **Execution is better on paper than in a broker (O-07, O-08, O-09).** Entries at the trigger close, flat cost assumptions, no market impact. Expect live results to be worse than the tracker.
6. **Calendar runs out on 25 Dec 2026 (O-15).** Add the 2027 NSE holidays before January.
7. **Public scan data (O-18).** Anyone with the URL can read `data/*.json` (setups, tracked signals). Your journal is protected by Supabase.
8. **Unpinned dependencies.** `yfinance`, `pandas`, `numpy` are not version-pinned; a breaking release can change behaviour (pandas 3 already caused a timestamp bug once). CI catches most of it, not all. Consider pinning the versions the tests pass with.
9. **Single maintainer.** Your developer has left; the safety net is `ci` + `rollback` and these documents. Never upload a change that has not passed `python run_tests.py`.

## Before limited live trading (not yet)
- Spot XAUUSD data (or a live basis correction) for gold.
- An exit-date field in the journal so loss limits count realised P&L on the day it happens.
- At least 2 to 3 months of paper trades per segment, judged without changing the rules mid-way, compared with what the backtest predicted.
- Costs calibrated from your contract notes.
- The 50-case manual chart validation in `AUDIT_REPORT.md` done by you, with any engine misses fixed and re-tested.

## Update (19 Nov 2026, four corrections)
- Risk 1 (gold futures) is fixed in code, but gold now stays **off** until you add the free Twelve Data key, decide the volume rule and pass readiness.
- Risk 3 (loss limits) is fixed in DownerStuff; Trade Insight still needs `TRADE_INSIGHT_INTEGRATION.md`; old closed trades need their exit dates.
- Risk 6 (calendar) is fixed; 2027 must be copied from the NSE circular in December.
- Risk 2 is unchanged in substance: version 1.0.0 is frozen today and has **no** out-of-sample evidence yet. Paper trading under frozen rules is the test.
