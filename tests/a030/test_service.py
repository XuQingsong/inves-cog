from datetime import date, datetime, timezone

from inves_cog.clock import FrozenClock
from inves_cog.valuation_v1.service import build
from tests.m5.test_a019_batching import BatchRepository


def test_daily_build_emits_one_ceiling_for_every_monitored_ticker():
    repo = BatchRepository()
    day = date(2026, 11, 5)
    out = build(
        clock=FrozenClock(datetime(2026, 11, 6, 4, tzinfo=timezone.utc)),
        repository=repo,
        universe=[{"ticker": "AAA", "sector": "测试"}],
        as_of=day,
        persist=False,
    )
    assert len(out["ceilings"]) == 1
    assert out["ceilings"][0]["ticker"] == "AAA"
    assert out["ceilings"][0]["missing"]
    assert out["ranges"][0]["ceiling"] == out["ceilings"][0]
