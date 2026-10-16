"""M8 rule tests. Recorded model output stays out of this file."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "docs/phase1/golden/m8_attribution.json"


def _golden():
    return json.loads(GOLDEN.read_text())


@pytest.mark.phase1_blocking
def test_implied_magnitude_rules():
    from inves_cog.perception.attribution.magnitude import implied_magnitude

    for case in _golden()["implied_magnitude"]:
        assert implied_magnitude(case["input"]) == case["expected"]


@pytest.mark.phase1_blocking
def test_evidence_scores():
    from inves_cog.perception.attribution.evidence import evidence_score

    for case in _golden()["evidence_scores"]:
        assert evidence_score(case["components"]) == case["expected"]


@pytest.mark.phase1_blocking
def test_time_alignment_late_news():
    from inves_cog.perception.attribution.evidence import time_alignment

    start = datetime(2026, 10, 14, 13, 30)
    end = datetime(2026, 10, 14, 20, 0)
    assert time_alignment(end + timedelta(minutes=1), start, end) == 0.0
    assert time_alignment(start - timedelta(hours=1), start, end) == 1.0
    assert time_alignment(start + timedelta(hours=1), start, end) == 0.7


@pytest.mark.phase1_blocking
def test_candidate_validation():
    from inves_cog.perception.attribution.candidates import validate_candidates

    rows = validate_candidates(
        [
            {"mechanism": "供给", "info_ids": [], "affected": [{"ticker": "WDC"}]},
            {"mechanism": "需求", "info_ids": ["outside"], "affected": [{"ticker": "WDC"}]},
            {
                "mechanism": "竞争",
                "info_ids": ["nikkei"],
                "affected": [{"ticker": "WDC"}, {"ticker": "NOT_A_NAME"}],
            },
        ],
        {"nikkei"},
        {"WDC"},
    )
    scored = [row for row in rows if row["scored"]]
    assert [row["mechanism"] for row in scored] == ["竞争"]
    assert scored[0]["affected"] == [{"ticker": "WDC"}]
    default = rows[-1]
    assert default["mechanism"] == "无事件/资金面"
    assert default["scored"] is False


@pytest.mark.phase1_blocking
def test_retrieval_background_window():
    from inves_cog.perception.attribution.retrieve import window_items

    start = datetime(2026, 10, 14, 13, 30)
    now = datetime(2026, 10, 14, 21, 0)
    items = [
        {"info_id": "six", "published_at": start - timedelta(days=6), "rank": 100},
        {"info_id": "eight", "published_at": start - timedelta(days=8), "rank": 100},
        {
            "info_id": "hidden",
            "published_at": start - timedelta(days=1),
            "first_seen_at": now + timedelta(hours=1),
            "rank": 100,
        },
    ]
    items.extend(
        {
            "info_id": f"fill-{index}",
            "published_at": start - timedelta(hours=1),
            "rank": index,
        }
        for index in range(45)
    )
    found = window_items(items, start, now)
    identifiers = {row["info_id"] for row in found}
    assert "six" in identifiers
    assert next(row for row in found if row["info_id"] == "six")["role"] == "background"
    assert "eight" not in identifiers
    assert "hidden" not in identifiers
    assert len(found) == 40


@pytest.mark.phase1_blocking
def test_embedding_model_isolation():
    from inves_cog.perception.attribution.retrieve import approved_vectors, retrieval_mode

    rows = [
        {"info_id": "old", "model": "text-embedding-v3", "dimensions": 1024},
        {"info_id": "current", "model": "text-embedding-async-v1", "dimensions": 1536},
        {"info_id": "other-dim", "model": "text-embedding-async-v1", "dimensions": 1024},
    ]
    assert [row["info_id"] for row in approved_vectors(rows)] == ["current"]
    assert retrieval_mode(rows) == "vector"
    assert retrieval_mode([rows[0], rows[2]]) == "rules"


@pytest.mark.phase1_blocking
def test_market_confirmation_four_conditions():
    from inves_cog.perception.attribution.candidates import market_confirmed

    full = {"claim_time": True, "response": True, "independent": True, "alternative": 0.5}
    assert market_confirmed(**full) is True
    for key, value in (("claim_time", False), ("response", False), ("independent", False), ("alternative", 0.49)):
        assert market_confirmed(**{**full, key: value}) is False


@pytest.mark.phase1_blocking
def test_lifecycle_transitions():
    from inves_cog.perception.attribution.lifecycle import transition

    with pytest.raises(ValueError):
        transition("已发现", "市场确认", [], when="t", trigger="skip", evidence_ids=["e"])
    state, history = transition(None, "已发现", [], when="t0", trigger="anomaly", evidence_ids=["a"])
    state, history = transition(state, "假设中", history, when="t1", trigger="score", evidence_ids=["b"])
    assert [row["new"] for row in history] == ["已发现", "假设中"]
    assert history[0]["old"] is None
    assert history[1]["evidence_ids"] == ["b"]
    assert state == "假设中"


@pytest.mark.phase1_blocking
def test_second_hit():
    from inves_cog.perception.attribution.second_hit import classify_response, second_hit_conclusion

    assert classify_response(1.2, 0.4) == "命中"
    assert classify_response(-1.2, 0.2) == "反证"
    assert classify_response(0.4, 0.1) == "无响应"
    events = [
        {"source_root": "wire", "outcome": "命中"},
        {"source_root": "wire", "outcome": "反证"},
        {"source_root": "desk", "outcome": "无响应"},
    ]
    assert second_hit_conclusion(events) == "确认"
    quiet = [{"source_root": "a", "outcome": "无响应"}, {"source_root": "b", "outcome": "无响应"}]
    assert second_hit_conclusion(quiet) == "否定"


@pytest.mark.phase1_blocking
def test_search_budget():
    from inves_cog.perception.attribution.retrieve import supplement_calls

    assert supplement_calls(1, 200) == (0, "补证未执行")
    assert supplement_calls(3, 199) == (1, "补证未执行")
    assert supplement_calls(1, 10) == (1, None)


@pytest.mark.phase1_blocking
def test_verified_not_from_market_evidence():
    from inves_cog.perception.attribution.candidates import verified_from_evidence

    assert verified_from_evidence(["second_hit", "consensus"]) is False
    assert verified_from_evidence(["filing"]) is True
