"""PR-A evidence wiring: ended_at, naive-UTC stamps, member event flags, basket residuals."""

import pytest


def _dt(value):
    from datetime import datetime

    return datetime.fromisoformat(value)


@pytest.mark.phase1_blocking
def test_adapt_m7_sets_ended_at_for_both_sessions():
    from datetime import date

    from inves_cog.ingest.market import local_at, regular_bounds
    from inves_cog.perception.attribution.chain import adapt_m7

    opened, closed = regular_bounds(date(2026, 10, 14))
    close = adapt_m7({"session": "close", "trade_date": "2026-10-14"})
    assert close["started_at"] == opened
    assert close["ended_at"] == closed
    post = adapt_m7({"session": "post", "trade_date": "2026-10-14"})
    assert post["started_at"] == closed
    assert post["ended_at"] == local_at(date(2026, 10, 14), 20)
    kept = adapt_m7({"session": "close", "trade_date": "2026-10-14", "ended_at": _dt("2026-10-14T21:00:00+00:00")})
    assert kept["ended_at"] == _dt("2026-10-14T21:00:00+00:00")
    non_session = adapt_m7({"session": "holiday", "trade_date": "2026-10-14"})
    assert "ended_at" not in non_session


@pytest.mark.phase1_blocking
def test_naive_published_at_is_read_as_utc_and_noted():
    from inves_cog.perception.attribution.chain import _components
    from inves_cog.perception.attribution.evidence import bounded_time_alignment, publication_tz_assumed

    aware_start = _dt("2026-10-14T13:30:00+00:00")
    aware_end = _dt("2026-10-14T20:00:00+00:00")
    naive_early = {"info_id": "n1", "published_at": "2026-10-13T12:00:00"}
    assert bounded_time_alignment([naive_early], aware_start, aware_end) == 1.0
    assert publication_tz_assumed([naive_early]) is True
    assert publication_tz_assumed([{"info_id": "n2", "published_at": "2026-10-13T12:00:00+00:00"}]) is False
    naive_during = {"info_id": "n3", "published_at": _dt("2026-10-14T15:00:00")}
    assert bounded_time_alignment([naive_during], aware_start, aware_end) == 0.7
    candidate = {"info_ids": ["n3"], "affected": [], "chain": []}
    anomaly = {"started_at": aware_start, "ended_at": aware_end, "members": [], "direction": "up"}
    components = _components(candidate, anomaly, [naive_during])
    assert components["time"] == 0.7
    assert components["_notes"]["time_basis"] == "部分发布时间不带时区，按 UTC 推定"


@pytest.mark.phase1_blocking
def test_news_query_selects_source_root_and_flag_columns():
    from inves_cog.perception.attribution.morning import _NEWS

    for name in ("source_root", "is_guidance", "is_rating_change", "filing_items"):
        assert name in _NEWS
    assert "first_seen_at <= %s" in _NEWS


def _member_flags_setup():
    from inves_cog.perception.attribution.morning import _member_flags

    start = _dt("2026-10-14T13:30:00+00:00")
    end = _dt("2026-10-14T20:00:00+00:00")
    return _member_flags, start, end


@pytest.mark.phase1_blocking
def test_member_flags_true_false_and_none_semantics():
    _member_flags, start, end = _member_flags_setup()
    anomaly = {
        "started_at": start,
        "ended_at": end,
        "members": [{"ticker": "AAA"}, {"ticker": "BBB"}, {"ticker": "CCC"}],
    }
    items = [
        {
            "info_id": "i1",
            "kind": "sec_8k",
            "filing_items": "2.02,9.01",
            "is_guidance": True,
            "is_rating_change": False,
            "tickers": ["AAA"],
            "published_at": _dt("2026-10-14T10:00:00+00:00"),
        },
        {
            "info_id": "i2",
            "kind": "news",
            "is_guidance": False,
            "is_rating_change": False,
            "tickers": ["BBB"],
            "published_at": _dt("2026-10-14T11:00:00+00:00"),
        },
    ]
    _member_flags(anomaly, items)
    aaa, bbb, ccc = anomaly["members"]
    assert aaa["earnings_reaction"] is True
    assert aaa["guidance_8k"] is True
    assert aaa["rating_change"] is False
    assert bbb["earnings_reaction"] is False
    assert bbb["guidance_8k"] is False
    assert bbb["rating_change"] is False
    assert ccc["earnings_reaction"] is None
    assert ccc["guidance_8k"] is None
    assert ccc["rating_change"] is None


@pytest.mark.phase1_blocking
def test_member_flags_window_and_pit_bounds():
    _member_flags, start, end = _member_flags_setup()
    anomaly = {"started_at": start, "ended_at": end, "members": [{"ticker": "AAA"}]}
    outside_before = {
        "info_id": "old",
        "kind": "news",
        "is_rating_change": True,
        "tickers": ["AAA"],
        "published_at": _dt("2026-10-13T12:00:00+00:00"),
    }
    outside_after = {
        "info_id": "future",
        "kind": "sec_8k",
        "filing_items": "2.02",
        "tickers": ["AAA"],
        "published_at": _dt("2026-10-14T21:00:00+00:00"),
    }
    inside = {
        "info_id": "in",
        "kind": "news",
        "is_guidance": False,
        "tickers": ["AAA"],
        "published_at": _dt("2026-10-13T13:31:00+00:00"),
    }
    _member_flags(anomaly, [outside_before, outside_after, inside])
    member = anomaly["members"][0]
    assert member["earnings_reaction"] is False
    assert member["rating_change"] is False
    anomaly["members"] = [{"ticker": "AAA"}]
    _member_flags(anomaly, [outside_before, outside_after])
    assert anomaly["members"][0]["earnings_reaction"] is None


def _registry_rows():
    return [
        {
            "basket_id": "l2_00",
            "level": "L2",
            "name": "AI 算力芯片",
            "members": [{"ticker": "AAA", "effective_from": "2015-01-01"}, {"ticker": "BBB"}],
        },
        {
            "basket_id": "l2_01",
            "level": "L2",
            "name": "存储",
            "members": [{"ticker": "CCC"}, {"ticker": "DDD"}],
        },
        {
            "basket_id": "l2_02",
            "level": "L2",
            "name": "零售",
            "members": [{"ticker": "EEE"}],
        },
    ]


def _basket_anomaly():
    return {
        "baskets": ["AI 算力芯片"],
        "members": [
            {"ticker": "AAA", "resid_z": 4.0},
            {"ticker": "BBB", "resid_z": 2.0},
            {"ticker": "CCC", "resid_z": -1.0},
        ],
        "universe": "pool",
    }


@pytest.mark.phase1_blocking
def test_basket_residuals_aggregation_by_name():
    from inves_cog.perception.attribution.morning import enrich_anomalies

    anomaly = _basket_anomaly()
    enrich_anomalies([anomaly], [], _registry_rows(), "2026-10-14")
    assert anomaly["basket_residuals"] == {"l2_00": [4.0, 2.0]}
    assert anomaly["basket_members"] == [{"basket_id": "l2_00", "members": ["AAA", "BBB"]}]
    assert set(anomaly["universe_baskets"]) == {"l2_00", "l2_01", "l2_02"}
    assert anomaly["universe_baskets"]["l2_00"]["members"] == ["AAA", "BBB"]


@pytest.mark.phase1_blocking
def test_specificity_uses_candidate_controls_when_they_resolve():
    from inves_cog.perception.attribution.chain import _residuals

    anomaly = _basket_anomaly()
    anomaly["basket_residuals"] = {"l2_00": [4.0, 2.0], "l2_01": [-1.0]}
    candidate = {"affected": [{"basket_id": "l2_00"}], "control_baskets": ["l2_01"]}
    expected, control, source = _residuals(candidate, anomaly)
    assert expected == [4.0, 2.0]
    assert control == [-1.0]
    assert source is None


@pytest.mark.phase1_blocking
def test_specificity_system_controls_when_unresolved_with_note():
    from inves_cog.perception.attribution.chain import _components, _residuals

    anomaly = _basket_anomaly()
    anomaly["basket_residuals"] = {"l2_00": [4.0, 2.0], "l2_01": [-1.0], "l2_02": [0.5]}
    anomaly["basket_members"] = [{"basket_id": "l2_00", "members": ["AAA", "BBB"]}]
    anomaly["universe_baskets"] = {
        "l2_00": {"members": ["AAA", "BBB"]},
        "l2_01": {"members": ["CCC", "DDD"]},
        "l2_02": {"members": ["EEE"]},
        "l2_09": {"members": ["AAA", "ZZZ"]},
    }
    candidate = {"affected": [{"basket_id": "l2_00"}], "control_baskets": ["free text peers"]}
    expected, control, source = _residuals(candidate, anomaly)
    assert expected == [4.0, 2.0]
    assert sorted(control) == [-1.0, 0.5]
    assert source == "system"
    components = _components({**candidate, "info_ids": []}, anomaly, [])
    assert components["_notes"]["control_source"] == "对照篮子为系统选取"


@pytest.mark.phase1_blocking
def test_apply_score_carries_notes_into_evidence():
    from inves_cog.perception.attribution.chain import _apply_score

    anomaly = {
        "started_at": _dt("2026-10-14T13:30:00+00:00"),
        "ended_at": _dt("2026-10-14T20:00:00+00:00"),
        "direction": "up",
        "members": [{"ticker": "AAA", "earnings_reaction": False, "guidance_8k": False, "rating_change": False}],
    }
    item = {"info_id": "n1", "published_at": _dt("2026-10-13T10:00:00")}
    candidate = {
        "scored": True,
        "mechanism": "需求",
        "info_ids": ["n1"],
        "affected": [{"ticker": "AAA"}],
        "chain": [],
    }
    rows = _apply_score([candidate], anomaly, [item], {})
    evidence = rows[0]["evidence"]
    assert evidence["notes"]["time_basis"] == "部分发布时间不带时区，按 UTC 推定"
    assert evidence["components"]["time"] == 1.0
    assert evidence["components"]["alternatives"] == 1.0
