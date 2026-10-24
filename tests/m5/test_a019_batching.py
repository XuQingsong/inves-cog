from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.ingest.fundamentals.state import FinState, StateStore
from inves_cog.valuation_v1.lifecycle import ValuationBook
from inves_cog.valuation_v1.service import build


class BatchRepository:
    def __init__(self, *, enforce=True):
        self.enforce = enforce
        self.calls = []
        self.states = [
            FinState(
                ticker=ticker,
                extractor="fixed",
                filed=date(year, 8, 1),
                period_end=date(year, 6, 30),
                values={
                    "ni_ttm": 10,
                    "eps_ttm": eps,
                    "rev_ttm": 100,
                    "rev_growth": 5,
                    "fcf_ttm": 12,
                    "cash": 10,
                    "debt": 1,
                    "shares": 2,
                },
                field_sources={"shares": {"method": "diluted_weighted_approximation"}},
            )
            for ticker in ("AAA", "BBB")
            for year, eps in ((2023, 2), (2024, 3), (2025, 4))
        ]

    def inputs(self, through, tickers):
        self.calls.append(tuple(tickers))
        if self.enforce:
            assert len(tickers) == 1, "do not materialize all production evidence at once"
        states = deepcopy([s for s in self.states if s.ticker in tickers and s.filed <= through])
        return {
            "store": StateStore(states),
            "states": {t: [s for s in states if s.ticker == t] for t in tickers},
            "bars": {
                t: [{"trade_date": date(2023, 8, 1) + timedelta(days=n), "close": 40 + n % 10} for n in range(1100)]
                for t in tickers
            },
            "consensus": {},
            "baskets": [],
            "sic": {},
        }

    def restore(self, through):
        return ValuationBook()

    def shadow_history(self, through):
        return {}, {}

    def holdings(self, *args, **kwargs):
        return {"holdings": [{"ticker": "AAA", "shares": 2}], "candidates": [], "cash": 200}


@pytest.mark.phase1_blocking
def test_a019_batches_preserve_full_payload_and_history():
    clock = FrozenClock(datetime(2026, 10, 23, 2, 30, tzinfo=timezone.utc))
    through = date(2026, 10, 22)
    universe = [{"ticker": t, "sector": "测试"} for t in ("AAA", "BBB")]
    baseline = BatchRepository(enforce=False)
    source = baseline.inputs(through, ["AAA", "BBB"])
    expected = build(clock=clock, repository=baseline, universe=universe, as_of=through, source=source, persist=False)
    batched = BatchRepository()
    actual = build(clock=clock, repository=batched, universe=universe, as_of=through, persist=False)
    assert actual == expected
    assert len(actual["ranges"]) == 2 and actual["panel"]
    assert all(len(call) == 1 for call in batched.calls)
    assert {call[0] for call in batched.calls} == {"AAA", "BBB"}


@pytest.mark.phase1_blocking
def test_a019_evidence_cache_keeps_one_complete_filing():
    from inves_cog.valuation_v1.repository import EvidenceCache, EvidenceView

    calls = []

    def read(key):
        calls.append(key)
        return {"eps_ttm": {"components": [{"source": key}]}, "unused_but_audited": [key]}

    cache = EvidenceCache(read)
    a, b = EvidenceView(cache, "a"), EvidenceView(cache, "b")
    assert a.get("eps_ttm")["components"] == [{"source": "a"}]
    assert b.get("unused_but_audited") == ["b"]
    assert cache.key == "b"
    assert dict(a) == {"eps_ttm": {"components": [{"source": "a"}]}, "unused_but_audited": ["a"]}
    assert calls == ["a", "b", "a"]


@pytest.mark.phase1_blocking
def test_a019_lazy_evidence_keeps_original_audit_hash_and_payload():
    from inves_cog.valuation_v1.repository import EvidenceCache, EvidenceView

    class LazyRepository(BatchRepository):
        def inputs(self, through, tickers):
            source = super().inputs(through, tickers)
            proofs = {i: row.field_sources for i, row in enumerate(source["store"].states)}
            cache = EvidenceCache(proofs.__getitem__)
            for i, row in enumerate(source["store"].states):
                row.field_sources = EvidenceView(cache, i)
            return source

    kwargs = dict(
        clock=FrozenClock(datetime(2026, 10, 23, 2, 30, tzinfo=timezone.utc)),
        universe=[{"ticker": t, "sector": "测试"} for t in ("AAA", "BBB")],
        as_of=date(2026, 10, 22),
        persist=False,
    )
    assert build(repository=LazyRepository(), **kwargs) == build(repository=BatchRepository(), **kwargs)
