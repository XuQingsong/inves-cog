"""Retrieval ranking and evidence coverage quality checks."""

from datetime import datetime, timedelta, timezone

import pytest

from inves_cog.ingest.market import NY

UTC = timezone.utc


def _item(info_id, *, published, tickers=None, entities=None, level=None, similarity=None):
    return {
        "info_id": info_id,
        "published_at": published,
        "first_seen_at": published,
        "tickers": tickers or [],
        "entities": entities or [],
        "source_level": level,
        "similarity": similarity,
        "source_root": info_id,
    }


@pytest.mark.phase1_blocking
def test_overlap_is_not_diluted_by_basket_size():
    from inves_cog.perception.attribution.retrieve import _hit_overlap

    item = _item("mu-news", published=datetime(2026, 11, 5, 10, 0, tzinfo=UTC), tickers=["MU", "STX", "WDC"])
    small = _hit_overlap(item, {"MU", "STX", "WDC", "NVDA"})
    big = _hit_overlap(item, {"MU", "STX", "WDC"} | {f"T{i}" for i in range(500)})
    assert small == big == 1.0


@pytest.mark.phase1_blocking
def test_recency_prefers_same_day_news():
    from inves_cog.perception.attribution.retrieve import _recency

    start = datetime(2026, 11, 5, 14, 30, tzinfo=UTC)
    same_day = _item("a", published=datetime(2026, 11, 5, 10, 0, tzinfo=UTC))
    old = _item("b", published=datetime(2026, 11, 3, 10, 0, tzinfo=UTC))
    assert _recency(same_day["published_at"], start) > _recency(old["published_at"], start)
    assert _recency(datetime(2026, 11, 5, 15, 0, tzinfo=UTC), start) == 1.0


@pytest.mark.phase1_blocking
def test_big_basket_keeps_same_day_floor():
    from inves_cog.perception.attribution.retrieve import shortlist

    start = datetime(2026, 11, 5, 14, 30, tzinfo=UTC)
    now = datetime(2026, 11, 6, 2, 15, tzinfo=UTC)
    members = [f"T{i}" for i in range(35)]
    old = [_item(f"old-{i}", published=start - timedelta(hours=30), tickers=["T0"], level=1) for i in range(45)]
    fresh = [_item(f"fresh-{i}", published=start - timedelta(hours=i + 1), tickers=["T1"]) for i in range(12)]
    rows = shortlist([*old, *fresh], members, start, now, members=members)
    kept = {row["info_id"] for row in rows}
    assert sum(name.startswith("fresh-") for name in kept) >= 10
    assert len(rows) == 40


@pytest.mark.phase1_blocking
def test_ranking_is_deterministic_on_ties():
    from inves_cog.perception.attribution.retrieve import rank_items

    start = datetime(2026, 11, 5, 14, 30, tzinfo=UTC)
    a = _item("b-id", published=datetime(2026, 11, 5, 10, 0, tzinfo=UTC))
    b = _item("a-id", published=datetime(2026, 11, 5, 10, 0, tzinfo=UTC))
    c = _item("c-id", published=datetime(2026, 11, 5, 11, 0, tzinfo=UTC))
    first = rank_items([a, b, c], {"X"}, start=start)
    second = rank_items([c, b, a], {"X"}, start=start)
    assert [row["info_id"] for row in first] == [row["info_id"] for row in second]
    assert [row["info_id"] for row in first] == ["c-id", "a-id", "b-id"]


@pytest.mark.phase1_blocking
def test_under_covered_score_is_unproven():
    from inves_cog.perception.attribution.evidence import evidence_score

    thin = evidence_score({"time": 1.0})
    assert thin["total"] == 1.0
    assert thin["confidence"] == "待证实"
    assert thin["covered_count"] == 1
    two = evidence_score({"time": 1.0, "gradient": 0.5})
    assert two["confidence"] == "待证实"
    assert two["covered_count"] == 2
    full = evidence_score({"time": 1.0, "gradient": 1.0, "specificity": 0.8})
    assert full["confidence"] == "高"
    assert full["covered_count"] == 3


@pytest.mark.phase1_blocking
def test_time_freshness_decays_per_trading_day():
    from inves_cog.perception.attribution.evidence import time_alignment

    # Session start: Thursday 2026-11-05 09:30 ET; prior close Wednesday 11-04 16:00 ET.
    start = datetime(2026, 11, 5, 9, 30, tzinfo=NY)
    end = datetime(2026, 11, 5, 16, 0, tzinfo=NY)
    assert time_alignment(datetime(2026, 11, 4, 18, 0, tzinfo=NY), start, end) == 1.0
    assert time_alignment(datetime(2026, 11, 5, 8, 0, tzinfo=NY), start, end) == 1.0
    # Wednesday before its close is one trading day early -> 0.6.
    assert time_alignment(datetime(2026, 11, 4, 10, 0, tzinfo=NY), start, end) == pytest.approx(0.6)
    # Tuesday is two trading days early -> 0.36.
    assert time_alignment(datetime(2026, 11, 3, 10, 0, tzinfo=NY), start, end) == pytest.approx(0.36)
    # Floor at 0.2 for very old items.
    assert time_alignment(datetime(2026, 10, 20, 10, 0, tzinfo=NY), start, end) == pytest.approx(0.2)
    # Inside the session stays 0.7.
    assert time_alignment(datetime(2026, 11, 5, 12, 0, tzinfo=NY), start, end) == 0.7


@pytest.mark.phase1_blocking
def test_under_covered_confidence_display():
    from inves_cog.web.pages import _confidence_display

    evidence = {"components": {"time": 1.0, "gradient": None, "specificity": None, "narrative": None}}
    assert _confidence_display("高", evidence) == "待证实（证据项不足：仅 time）"
    assert _confidence_display(None, {"components": {}}) == "待证实（证据项不足：无分项）"
    three = {"components": {"time": 1.0, "gradient": 0.5, "specificity": 0.5}}
    assert _confidence_display("高", three) == "高"
