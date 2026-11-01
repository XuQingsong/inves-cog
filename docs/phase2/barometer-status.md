# P2-M1 barometer status (2026-11-01, branch p2-m1-barometer, PR #113)

## Done
- compute.py — comp.py port (anchors, dims, F/G, stage/pendulum/nature, 反弹特征, missing+inputs per day).
- loader.py — bars_daily canonical + yahoo_px_*/macro merge; flows inputs PIT-aligned (published_at→NY-naive dates); CFTC pivoted trader_class; ETF COALESCE(aum, shares*nav).
- Collectors: backfill_yahoo_px (10 syms incl. ^MOVE/^TNX), backfill_dgs10, backfill_shiller_pe — all loaded on prod.
- Migration: migrations/phase2_flows_0004_barometer.sql — applied on prod (renamed to sort after flows base; the old name broke fresh-DB CI).
- Backfill: flows.barometer_daily 2018-01-02→2026-10-30 = 2,220 rows on prod.
- Validation vs demo baro.json: fear mean 0.36/p95 1.3/max 3.4; greed mean 0.34/p95 1.3/max 4.0; all dims mean ≤0.96. Bugs found via diff: tz-aware published_at (all flows inputs NaN), aum NULL on ProShares, margin series id, multpl entity regex.
- §5 readings verified (panic→绝望/悲观, overheat→堆积未释放, bear rallies→超卖反弹型, 2025-04-09 falls back).
- Scheduler: _barometer() in schedule_flows.py — official 16:45 ET + 15-min intraday slots (state-keyed).
- Tests: tests/phase2/test_barometer.py (anchors/stage/nature/missing) 4/4.

## Left
- PR #113 CI pending on a0733a3f (migration rename); earlier CI failure was only the filename sort issue.
- dgs10 job is a no-op without FRED_API_KEY on server — using ^TNX (same as prototype). Shiller/multpl is page-only.
- Deploy: apply migration already done; flows program restart + barometer program scheduling per deploy brief (targeted, no regen of supervisord).
- Page: waits for the new visual design (§4).
- Known minor diffs vs prototype: JPY weekend alignment (~1d), early-window 资管净多分位 wobble; both within reported stats.
