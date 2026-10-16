"""PIT data-contract assertions shared by the prescribed acceptance names."""

from datetime import date, datetime, timezone


def assert_inputs():
    from inves_cog.valuation_v1.inputs import consensus_inputs, diluted_shares

    row = {
        "as_of": date(2026, 10, 8),
        "captured_at": datetime(2026, 10, 8, 10, tzinfo=timezone.utc),
        "eps_cy": 6,
        "eps_ny": 12,
        "rev_cy": 100,
        "rev_ny": 160,
        "fy_cy": date(2026, 12, 31),
        "fy_ny": date(2027, 12, 31),
    }
    a = consensus_inputs([row], date(2026, 10, 8))
    assert a["eps_ntm"] == 11 and a["rev_ntm_consensus"] == 150
    assert a["consensus_next_year_eps_growth"] == 100
    assert consensus_inputs([row], date(2026, 10, 7))["eps_ntm"] is None
    assert (
        consensus_inputs([{**row, "captured_at": datetime(2026, 10, 10, tzinfo=timezone.utc)}], date(2026, 10, 8))[
            "eps_ntm"
        ]
        is None
    )
    assert consensus_inputs([{**row, "fy_cy": date(2025, 12, 31)}], date(2026, 10, 8))["eps_ntm"] is None
    broken = {**row, "as_of": date(2026, 10, 9), "eps_cy": None, "eps_ny": None}
    assert consensus_inputs([row, broken], date(2026, 10, 9))["eps_ntm"] is None
    assert (
        diluted_shares(10, {"method": "instant", "components": [{"tag": "dei:EntityCommonStockSharesOutstanding"}]})
        is None
    )
    assert diluted_shares(12, {"method": "diluted_weighted_approximation"}) == 12


def assert_service():
    from inves_cog.clock import FrozenClock
    from inves_cog.ingest.fundamentals.state import FinState, StateStore
    from inves_cog.valuation_v1.inputs import financial_inputs
    from inves_cog.valuation_v1.lifecycle import ValuationBook
    from inves_cog.valuation_v1.service import build

    d = date(2026, 10, 15)
    states = [
        FinState(
            ticker=t,
            extractor="fixed",
            filed=date(2026, 8, 1),
            period_end=date(2026, 6, 30),
            values={
                "ni_ttm": -1,
                "eps_ttm": -1,
                "rev_ttm": 100,
                "rev_growth": 30,
                "fcf_ttm": -1,
                "gross_margin": 56,
                "net_debt": 2,
                "cash": 3,
                "shares": 2,
            },
            field_sources={"shares": {"method": "diluted_weighted_approximation"}},
        )
        for t in ["AAA", "BBB", "CCC", "DDD"]
    ]
    assert financial_inputs(states[0], [], {"ticker": "AAA", "sector": "金融", "sic": 6021})["sic"] == 6021
    states[-1].values["ni_ttm"] = "invalid source value"

    class Repo:
        saved = None

        def restore(self, *args):
            return ValuationBook()

        def shadow_history(self, *args):
            return {}, {}

        def inputs(self, *args):
            return {
                "store": StateStore(states),
                "states": {s.ticker: [s] for s in states},
                "bars": {s.ticker: [{"trade_date": d, "close": 50}] for s in states},
                "consensus": {},
                "baskets": [],
            }

        def holdings(self, *args, **kwargs):
            return {
                "holdings": [{"ticker": "AAA", "shares": 10, "equity": 10000}],
                "candidates": [
                    {"ticker": "AAA", "side": "buy", "notional_est": 200},
                    {"ticker": "AAA", "side": "buy", "notional_est": 300},
                    {"ticker": "BBB", "side": "buy", "notional_est": 100},
                    {"ticker": "BBB", "side": "buy", "notional_est": 900},
                    {"ticker": "CCC", "side": "sell", "notional_est": 1000},
                ],
                "equity": 10000,
                "reason": None,
            }

        def save(self, *args):
            self.saved = args

    repo = Repo()
    out = build(
        clock=FrozenClock(datetime(2026, 10, 16, 2, 30, tzinfo=timezone.utc)),
        repository=repo,
        universe=[{"ticker": s.ticker, "sector": "测试"} for s in states],
        as_of=d,
        persist=False,
    )
    assert len(out["ranges"]) == 4 and out["ranges"][-1]["status"] == "failed"
    assert [r["ticker"] for r in out["panel"]] == ["AAA", "BBB"]
    assert out["summary"]["row_count"] == 2 and repo.saved is None

    by_ticker = {r["ticker"]: r for r in out["panel"]}
    assert by_ticker["AAA"]["weight_pct"] == 5
    assert by_ticker["AAA"]["target_weight_pct"] == 10
    assert by_ticker["BBB"]["weight_pct"] == 10
