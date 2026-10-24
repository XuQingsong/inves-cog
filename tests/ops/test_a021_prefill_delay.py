from datetime import date, datetime
from types import SimpleNamespace

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.ingest import pipeline
from inves_cog.ingest.market import BarResult
from inves_cog.ingest.pipeline import Pipeline, prefill_end

pytestmark = pytest.mark.phase1_blocking
DAY = date(2026, 10, 26)


def clock(text):
    return FrozenClock(datetime.fromisoformat(text.replace("Z", "+00:00")))


def test_prefill_end_stays_sixteen_minutes_behind_now():
    # 08:05 ET in daylight time; the newest queryable SIP minute is 07:49 ET.
    assert prefill_end(clock("2026-10-26T12:05:00Z"), DAY).isoformat() == "2026-10-26T11:49:00+00:00"


def test_prefill_end_keeps_the_0800_cutoff_when_it_is_old_enough():
    assert prefill_end(clock("2026-10-26T15:00:00Z"), DAY).isoformat() == "2026-10-26T12:00:00+00:00"


def test_prefill_end_never_precedes_the_window_start():
    # Winter time: the window opens at 04:00 ET = 09:00Z.
    assert prefill_end(clock("2026-11-02T09:05:00Z"), date(2026, 11, 2)).isoformat() == "2026-11-02T09:00:00+00:00"


def test_bars_prefill_requests_the_delayed_end_and_reports_it(monkeypatch):
    seen = {}

    def minute_bars(self, tickers, day, *, end=None):
        seen["end"] = end
        return BarResult(rows=[], exhausted=True, coverage={}, status="ok", missing_codes=[])

    monkeypatch.setattr(pipeline.MarketCollector, "minute_bars", minute_bars)
    alpaca = SimpleNamespace(http=None, headers={})
    fake = SimpleNamespace(
        clock=clock("2026-10-26T12:05:00Z"),
        day=DAY,
        codes=["NVDA"],
        alpaca=alpaca,
        require=lambda value, name: value,
        repo=SimpleNamespace(write=lambda *a, **k: None),
    )
    result = Pipeline.bars(fake, prefill=True)
    assert seen["end"].isoformat() == "2026-10-26T11:49:00+00:00"
    assert result["data_through"] == "2026-10-26T11:49:00+00:00"
