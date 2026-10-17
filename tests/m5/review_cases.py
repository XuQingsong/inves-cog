"""K04 regressions: a successful fallback and an unpublished daily candidate."""

from datetime import date, datetime, timezone

from inves_cog.ingest.fundamentals.state import FinState, StateStore


def assert_eps_split_comparability():
    from tests.m5.split_cases import assert_canonical_eps_units

    assert_canonical_eps_units()


class ReviewRepository:
    def __init__(self, *, peers=False):
        self.peers = peers
        self.states = [
            FinState(
                ticker=ticker,
                extractor="fixed",
                filed=date(2026, 8, 1),
                period_end=date(2026, 6, 30),
                values={"ni_ttm": 100, "rev_ttm": 1000, "eps_ttm": 2, "fcf_ttm": 100, "shares": 50},
                field_sources={"shares": {"method": "diluted_weighted_approximation"}},
            )
            for ticker in ["AAA", "BBB"]
        ]

    def restore(self, *args):
        from inves_cog.valuation_v1.lifecycle import ValuationBook

        return ValuationBook()

    def shadow_history(self, *args):
        return {}, {}

    def inputs(self, through, tickers):
        eps = 6 if through.day == 9 else 6.06
        return {
            "store": StateStore(self.states),
            "states": {s.ticker: [s] for s in self.states},
            "bars": {
                s.ticker: [{"trade_date": date(2026, 10, 8), "close": 100}, {"trade_date": through, "close": 110}]
                for s in self.states
            },
            "consensus": {
                s.ticker: [
                    {
                        "ticker": s.ticker,
                        "as_of": through,
                        "captured_at": None,
                        "source": "muse_import",
                        "fy_cy": date(2026, 12, 31),
                        "fy_ny": date(2027, 12, 31),
                        "eps_cy": eps,
                        "eps_ny": eps,
                    }
                ]
                for s in self.states
            },
            "baskets": [{"name": "test-L2", "level": "L2", "members": [{"ticker": "AAA"}, {"ticker": "BBB"}]}]
            if self.peers
            else [],
        }

    def holdings(self, *args, **kwargs):
        return {"holdings": [], "candidates": [], "reason": None}


def run(day, repo, book=None):
    from inves_cog.clock import FrozenClock
    from inves_cog.valuation_v1.service import build

    return build(
        clock=FrozenClock(datetime(2026, 10, day + 1, 2, 30, tzinfo=timezone.utc)),
        repository=repo,
        universe=[{"ticker": t, "sector": "test"} for t in ["AAA", "BBB"]],
        as_of=date(2026, 10, day),
        persist=False,
        book=book,
    )


def assert_pe_reason_recovery():
    recovered = run(9, ReviewRepository(peers=True))["ranges"][0]["inputs"]
    assert recovered["pe_p50"] == 50
    assert not recovered.get("pe_reason"), "L2 fallback succeeded; stale failure must disappear"
    missing = run(9, ReviewRepository())["ranges"][0]["inputs"]
    assert missing["pe_p50"] is None and missing["pe_reason"]


def assert_daily_candidate_trace():
    from inves_cog.valuation_v1.lifecycle import ValuationBook

    repo, book = ReviewRepository(peers=True), ValuationBook()
    first = run(9, repo, book)["ranges"][0]
    second = run(12, repo, book)["ranges"][0]
    assert second["inputs"]["eps_ntm"] == first["inputs"]["eps_ntm"] == 6
    assert second["candidate_inputs"]["eps_ntm"] == 6.06
    assert second["trigger_audit"]["recomputed"] is False
    assert second["trigger_audit"]["consensus_event"] is False
    evidence = second["source_evidence"]["consensus"]
    assert evidence["captured_at"] is None and evidence["capture_status"] == "unknown_import_time"
    assert evidence["snapshot_as_of"] == "2026-10-12"
    assert second["source_evidence"]["financial"]["capture_status"] == "not_provided_by_M2_contract"
    # Reopening a stored pre-repair result must not retain its obsolete type
    # simply because no new financial filing arrived on the upgrade day.
    legacy = ValuationBook()
    run(9, repo, legacy)
    legacy.published["AAA"]["method_version"] = "v1.1"
    legacy.types["AAA"].current = "周期"
    legacy.types["AAA"].observations = {"2026-06-30": "周期"}
    upgraded = run(12, repo, legacy)["ranges"][0]
    assert upgraded["trigger_audit"]["method_refresh"] is True
    assert upgraded["type"] == "稳定" and upgraded["inputs"]["eps_ntm"] == 6.06
