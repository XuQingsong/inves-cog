"""M8 rule tests. Recorded model output stays out of this file."""

import json
import subprocess
from datetime import datetime, timedelta, timezone
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
    state, history = transition(state, "市场确认", history, when="t2", trigger="four", evidence_ids=["c"])
    with pytest.raises(ValueError, match="市场层"):
        transition(
            state,
            "基本面核查中",
            history,
            when="t3",
            trigger="multiple",
            evidence_ids=["c"],
            mechanism="估值倍数",
        )
    state, history = transition(
        state,
        "基本面核查中",
        history,
        when="t3",
        trigger="supply",
        evidence_ids=["c"],
        mechanism="供给",
    )
    assert state == "基本面核查中"


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
    start = datetime(2026, 10, 14, 13, 30)
    early = [
        {"source_root": "ft", "outcome": "命中", "published_at": datetime(2026, 10, 8, 12)},
        {"source_root": "desk", "outcome": "命中", "published_at": datetime(2026, 10, 9, 15)},
        {"source_root": "same", "outcome": "命中", "published_at": start},
    ]
    assert second_hit_conclusion(early, anomaly_start=start) == "未检验"
    later = [*early, {"source_root": "wire", "outcome": "命中", "published_at": datetime(2026, 10, 15, 14)}]
    assert second_hit_conclusion(later, anomaly_start=start) == "确认"


@pytest.mark.phase1_blocking
def test_search_budget():
    from inves_cog.perception.attribution.retrieve import supplement_calls

    assert supplement_calls(1, 200) == (0, "补证未执行")
    assert supplement_calls(3, 199) == (1, "补证未执行")
    assert supplement_calls(1, 10) == (1, None)


@pytest.mark.phase1_blocking
def test_verified_not_from_market_evidence():
    from inves_cog.perception.attribution.candidates import verified_from_evidence
    from inves_cog.perception.attribution.operating import Verdict

    as_of = datetime(2026, 10, 20, 13, 30)
    blocked = ["price", "social_heat", "unverified", "filing", "second_hit", "consensus", "flow"]
    for kind in blocked:
        assert verified_from_evidence([kind], as_of=as_of, expected_direction="down") is False
    assert verified_from_evidence(["second_hit", "consensus"], as_of=as_of, expected_direction="down") is False
    label = {
        "kind": "company_primary",
        "source_level": 1,
        "published_at": as_of,
        "direction": "down",
    }
    assert verified_from_evidence([label], as_of=as_of, expected_direction="down") is False
    consensus = {
        "kind": "consensus",
        "coverage": 10,
        "same_direction_revisions": 10,
        "eps_change": -0.06,
        "published_at": as_of,
        "direction": "down",
    }
    assert verified_from_evidence([consensus], as_of=as_of, expected_direction="down") is False
    with pytest.raises(ValueError, match="经营证据规则"):
        Verdict("支持", [], object())


@pytest.mark.phase1_blocking
def test_retrieval_recovers_low_rank_item():
    from inves_cog.perception.attribution.candidates import validate_candidates
    from inves_cog.perception.attribution.retrieve import rank_items

    noise = [
        {
            "info_id": f"noise-{index}",
            "entities": [],
            "similarity": 0.95,
            "source_level": 1,
            "rank": 1000 - index,
        }
        for index in range(45)
    ]
    chart = {
        "info_id": "muse-chart",
        "entities": ["CPU", "META", "Muse"],
        "similarity": 0.2,
        "source_level": 4,
        "rank": 1,
    }
    ranked = rank_items([*noise, chart], {"CPU", "META"})
    identifiers = {row["info_id"] for row in ranked}
    assert "muse-chart" in identifiers
    assert chart["rank"] < min(row["rank"] for row in noise)
    kept = validate_candidates(
        [{"mechanism": "需求", "info_ids": ["muse-chart"], "affected": [{"ticker": "META"}]}],
        identifiers,
        {"META"},
    )
    assert any(row["info_ids"] == ["muse-chart"] for row in kept)


@pytest.mark.phase1_blocking
def test_five_dims_rules():
    from inves_cog.perception.attribution.dims import authenticity, narrative_states, trade_states

    assert authenticity([{"level": 4, "action": "确认"}, {"level": 3, "action": "确认"}]) == "未核实"
    assert authenticity([{"level": 2, "independent": False}, {"level": 4}]) == "未核实"
    assert authenticity([{"level": 2, "independent": True}]) == "部分核实"
    assert authenticity([{"level": 1, "action": "确认"}]) == "核实"
    assert authenticity([{"level": 1, "action": "修订"}, {"level": 1, "action": "确认"}]) == "修订"
    assert authenticity([{"level": 1, "action": "否认"}, {"level": 1, "action": "确认"}]) == "证伪"
    assert authenticity([{"level": 1, "action": "矛盾"}]) == "证伪"

    assert narrative_states([2]) == ["初现"]
    assert narrative_states([2, 3]) == ["初现", "扩散"]
    assert narrative_states([4, 5]) == ["初现", "稳定"]
    assert narrative_states([10, 10, 4, 4]) == ["初现", "稳定", "稳定", "衰减"]
    assert narrative_states([2, 1, 1, 2])[-1] == "重新活跃"

    release = [{"cumulative": -10, "close": 100}, {"cumulative": -9, "close": 101}]
    assert trade_states(release) == ["风险释放", "风险释放"]
    early = [*release, {"cumulative": -7.2, "close": 102}]
    assert trade_states(early)[-1] == "风险释放"
    repair = [*release, {"cumulative": -7, "close": 103}]
    assert trade_states(repair)[-1] == "初步修复"
    held = [{"cumulative": -10, "close": 100}, {"cumulative": -9, "close": 101}]
    held.extend({"cumulative": -5, "close": 110} for _ in range(5))
    assert trade_states(held)[-1] == "持续确认"
    assert trade_states(held)[-2] == "初步修复"
    broken = [*repair, {"cumulative": -6, "close": 99}]
    assert trade_states(broken)[-1] == "修复失效"


@pytest.mark.phase1_blocking
def test_tracks_and_deadline():
    from inves_cog.perception.attribution.tracks import (
        apply_deadline,
        capital_state,
        close_deadline,
        deadline_offset,
        reactivate,
    )

    assert deadline_offset(30, 12) == 12
    assert deadline_offset(5, 12) == 5
    assert deadline_offset(None, None) == 20
    assert capital_state(1, -4, -10) == "冲击中"
    assert capital_state(3, -12, -10) == "延续"
    assert capital_state(3, 1, -10) == "反转"
    assert capital_state(3, -4, -10) == "已消化"
    assert capital_state(3, -10, -10) == "消化中"

    from inves_cog.perception.attribution.operating import operating_verdict

    as_of = datetime(2026, 10, 20, 13, 30)
    guidance = {
        "kind": "company_primary",
        "source_level": 1,
        "citation": "8-K accession",
        "form": "8-K",
        "guidance_change": True,
        "direction": "down",
        "published_at": as_of,
    }
    opposed = {
        "kind": "eps_revision",
        "coverage": 10,
        "same_direction_revisions": 3,
        "eps_change": 0.03,
        "published_at": as_of,
    }
    supported = apply_deadline(operating_verdict([guidance], as_of=as_of, expected_direction="down"))
    assert supported["lifecycle"] == "已验证·有影响"
    denied = apply_deadline(operating_verdict([opposed], as_of=as_of, expected_direction="down"), level1_denial=True)
    assert denied["lifecycle"] == "已证伪"
    faded = apply_deadline(operating_verdict([opposed], as_of=as_of, expected_direction="down"))
    assert faded["lifecycle"] == "已衰减·无影响"
    assert faded["fundamental"] == "冲突"
    assert faded["deadline_outcome"] == "反证"
    assert faded["closing_reason"] == "截止日证据指向失效"
    unknown = apply_deadline(operating_verdict([], as_of=as_of, expected_direction="down", unknowns=["eps_consensus"]))
    assert unknown["deadline_outcome"] == "条件风险"
    assert unknown["fundamental"] == "失效"
    assert unknown["closing_reason"] == "截止日仍未知"
    assert unknown["unknowns"] == ["eps_consensus"]
    assert unknown["operating_impact_proven"] is False
    with pytest.raises(ValueError):
        close_deadline("观察")
    with pytest.raises(ValueError):
        apply_deadline("支持", renewed=True)
    with pytest.raises(ValueError):
        reactivate({"reprint": True, "source_level": 1, "original": True})
    assert reactivate({"original": True, "source_level": 2}) == "假设中"


@pytest.mark.phase1_blocking
def test_divergence_labels():
    from inves_cog.perception.attribution.labels import consensus_band, divergence_label

    assert consensus_band(-0.019, 1, 1, 100) == "未下修"
    assert consensus_band(-0.02, 0, 1, 100) == "其他"
    assert consensus_band(-0.03, 0, 5, 100) == "显著下修"
    assert consensus_band(0.0, 30, 0, 100) == "显著下修"
    assert consensus_band(None, 0, 1, 100) is None
    assert consensus_band(None, 30, 0, 100) == "显著下修"
    assert consensus_band(-0.019, 0, 1, None) is None
    assert consensus_band(-0.03, None, None, None) == "显著下修"

    base = {"moment": "截止日", "price": "大跌", "consensus": "未下修", "fundamental": "未变", "linkage": "已衰减"}
    assert divergence_label(**base) == "情绪性折价"
    assert divergence_label(**{**base, "moment": "跟踪中"}) is None
    assert divergence_label(**{**base, "consensus": None}) is None
    assert divergence_label(**{**base, "fundamental": None}) is None
    assert divergence_label("已验证", "大跌", "未下修", "未变", "估值倍数类") == "情绪性折价"
    assert divergence_label("截止日", "大跌", "显著下修", "支持不利", "已验证·有影响") == "合理重定价"
    assert divergence_label("截止日", "大跌", "未下修", "支持不利", "已验证·有影响", guidance_cut=True) == "合理重定价"
    assert divergence_label("截止日", "小跌或未跌", "显著下修", "支持不利", "已验证·有影响") == "滞后风险"
    assert divergence_label("截止日", "大涨", "未上修", "未变", "估值倍数类") == "情绪性溢价"
    assert divergence_label("已验证", "大涨", "显著上修", "支持有利", "已验证正向") == "基本面驱动上涨"


@pytest.mark.phase1_blocking
def test_systemic_event_tag_requires_level12():
    from inves_cog.perception.attribution.systemic import resolve_systemic_tag

    assert resolve_systemic_tag("关税冲击", ["only-wire"], {"only-wire": 4}) == "无"
    assert resolve_systemic_tag("关税冲击", ["note"], {"note": 4, "filing": 1}) == "无"
    assert resolve_systemic_tag("关税冲击", ["filing"], {"filing": 2}) == "关税冲击"


@pytest.mark.phase1_blocking
def test_unexplained_recheck_5d():
    from inves_cog.perception.attribution.unexplained import attention_line, classify_unexplained, recheck_flags

    assert classify_unexplained([0.49, 0.1]) == "已发现·原因未明"
    assert classify_unexplained([]) == "已发现·原因未明"
    assert classify_unexplained([0.5]) is None
    assert recheck_flags(6) == [True, True, True, True, True, False]
    assert attention_line(True, 4) == "请人工查看"
    assert attention_line(True, 3.9) is None
    assert attention_line(False, 5) is None


@pytest.mark.phase1_blocking
def test_anomaly_contract():
    from inves_cog.perception.attribution.candidates import validate_candidates
    from inves_cog.perception.attribution.impact import anomaly_status, decompose, require_anomaly_status

    anomalies = [
        {"anomaly_id": "pool", "universe": "pool", "status": anomaly_status("pool", [0.2])},
        {"anomaly_id": "wide", "universe": "wide", "status": anomaly_status("wide", [])},
    ]
    require_anomaly_status(anomalies)
    assert anomalies[0]["status"] == "已发现·原因未明"
    assert anomalies[1]["status"] == "已记录"
    with pytest.raises(ValueError):
        require_anomaly_status([{"anomaly_id": "blank", "status": ""}])

    kept = validate_candidates(
        [{"mechanism": "供给", "info_ids": [], "affected": [{"ticker": "WDC"}]}],
        {"nikkei"},
        {"WDC"},
    )
    assert [row for row in kept if row["scored"]] == []

    total = -0.08
    parts = decompose(total, 2_000_000_000, 20, 1_000_000_000_000, "部分相容", 2, 4)
    assert parts["event"] == -0.04
    assert parts["amplification"] == -0.02
    assert abs(parts["event"] + parts["amplification"] + parts["unexplained"] - total) <= 0.001
    unknown = decompose(total, None, 20, 1_000_000_000_000, "无法检验", 2, 4)
    assert unknown["event"] == 0.0
    assert abs(sum(unknown.values()) - total) <= 0.001


def _recording(root, task, payload, result):
    import hashlib

    from inves_cog.llm.client import canonical_payload

    digest = hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()
    folder = root / task
    folder.mkdir(parents=True, exist_ok=True)
    body = {"task": task, "payload_sha256": digest, "result": result}
    (folder / f"{digest}.json").write_text(json.dumps(body), encoding="utf-8")


@pytest.mark.phase1_blocking
def test_claim_fields_omit_unsupported(tmp_path):
    from inves_cog.llm.client import Client
    from inves_cog.perception.attribution.claims import attach_claims, claim_payload

    items = [{"info_id": "n1", "headline": "Toshiba expands", "summary": "HDD"}]
    payload = claim_payload(items)
    _recording(
        tmp_path,
        "claim_extraction",
        payload,
        {
            "items": [
                {
                    "info_id": "n1",
                    "claims": [{"subject": "Toshiba", "variable": "capacity", "quantity": None, "note": "drop"}],
                }
            ]
        },
    )
    attached = attach_claims(items, Client(recordings=tmp_path))
    assert attached[0]["claims"] == [{"subject": "Toshiba", "variable": "capacity"}]
    kept = attach_claims([{"info_id": "n1", "claims": [{"subject": "Toshiba"}]}], Client(recordings=tmp_path))
    assert kept[0]["claims"] == [{"subject": "Toshiba"}]


@pytest.mark.phase1_blocking
def test_wide_anomaly_skips_candidates(tmp_path):
    from inves_cog.llm.client import Client
    from inves_cog.perception.attribution.operating import operating_verdict
    from inves_cog.perception.attribution.propose import candidate_payload, propose_candidates
    from inves_cog.perception.attribution.report import explanation_report
    from inves_cog.perception.attribution.tracks import apply_deadline

    class Boom:
        def call(self, task, payload):
            raise AssertionError(task)

    assert propose_candidates({"anomaly_id": "w", "universe": "wide"}, [], [], Boom(), set()) == []
    anomaly = {
        "anomaly_id": "hdd",
        "universe": "pool",
        "direction": "down",
        "baskets": ["hdd"],
        "members": ["WDC"],
    }
    items = [{"info_id": "nikkei", "published_at": "2026-10-01T00:00:00", "headline": "expand", "source_level": 2}]
    payload = candidate_payload(anomaly, items, [])
    _recording(
        tmp_path,
        "anomaly_candidates",
        payload,
        {
            "candidates": [
                {"mechanism": "供给", "info_ids": ["nikkei"], "affected": [{"ticker": "WDC"}]},
                {"mechanism": "供给", "info_ids": [], "affected": [{"ticker": "WDC"}]},
                {"mechanism": "谣言", "info_ids": ["nikkei"], "affected": [{"ticker": "WDC"}]},
                {"mechanism": "需求", "info_ids": ["missing"], "affected": [{"ticker": "WDC"}]},
            ]
        },
    )
    rows = propose_candidates(anomaly, items, [], Client(recordings=tmp_path), {"WDC"})
    scored = [row for row in rows if row["scored"]]
    assert [row["mechanism"] for row in scored] == ["供给"]
    assert scored[0]["info_ids"] == ["nikkei"]
    deadline = apply_deadline(
        operating_verdict(
            [],
            as_of=datetime(2026, 10, 20, 13, 30),
            expected_direction="down",
            unknowns=["eps_consensus", "coverage"],
        )
    )
    impact = {"event": 0.0, "amplification": 0.0, "unexplained": -0.02}
    report = explanation_report(anomaly, impact, rows, "rules", deadline)
    assert report["closing_reason"] == "截止日仍未知"
    assert report["unknowns"] == ["eps_consensus", "coverage"]
    assert report["operating_impact_proven"] is False
    assert report["valuation"] == "不变 / 待基本面轨道"


@pytest.mark.phase1_blocking
def test_toshiba_midpoint_reaches_deadline():
    from inves_cog.perception.attribution.codes import n_code
    from inves_cog.perception.attribution.toshiba import NIKKEI, TDK, midpoint_report

    walked = midpoint_report()
    report = walked["report"]
    assert walked["lifecycle"] == "已验证·有影响"
    states = [row["new"] for row in walked["history"]]
    assert states == ["已发现", "假设中", "市场确认", "基本面核查中", "已验证·有影响"]
    scored = [row for row in report["candidates"] if row["scored"]]
    assert scored[0]["mechanism"] == "供给"
    assert scored[0]["info_ids"] == [NIKKEI]
    assert report["second_hit"] == "确认"
    assert report["second_hit_info_id"] == TDK
    assert report["operating_evidence_from_market"] is False
    assert report["fixture"] == "synthetic"
    assert report["closing_reason"] == "截止日证据支持"
    assert "投产与良率" in report["unknowns"]
    parts = report["impact"]
    total = parts["event"] + parts["amplification"] + parts["unexplained"]
    assert abs(total - (-0.05)) <= 0.001
    assert report["n_code"] is None
    assert report["deadline_sessions"] == 12
    assert report["tracks"][0]["capital"] == "冲击中"
    assert n_code(mechanism="估值倍数", narrative_shock=False, fundamental_unchanged=False, unexplained=False) == "N2"
    assert n_code(mechanism="供给", narrative_shock=True, fundamental_unchanged=True, unexplained=False) == "N1"
    assert n_code(mechanism="估值倍数", narrative_shock=False, fundamental_unchanged=False, unexplained=True) == "N6"


@pytest.mark.phase1_blocking
def test_attribution_tables_do_not_grant_ingest():
    text = (ROOT / "migrations/phase1_m8_0001_attribution.sql").read_text()
    for name in (
        "perception.retrievals",
        "perception.claims",
        "perception.candidates",
        "perception.linkage_events",
        "perception.tracks",
        "perception.second_hits",
        "perception.impact_decomposition",
        "perception.market_day",
        "perception.ticker_status",
        "perception.reports",
    ):
        assert name in text
    assert "ingest." not in text
    assert "GRANT" not in text


@pytest.mark.phase1_blocking
def test_case_direction_on_synthetic_headlines():
    from inves_cog.perception.attribution.cases import muse_chart, openai_cover, openai_labels, r1_or_store
    from inves_cog.perception.attribution.second_hit import second_hit_conclusion

    ranked = [
        {"labels": openai_labels("CoreWeave bond yield hits 15%")},
        {"labels": openai_labels("Barclays downgrades Dell to equal-weight")},
        {"labels": openai_labels("CPI 3.7% vs 3.6% est")},
        {"labels": openai_labels("Broadcom financing is not annualised revenue")},
    ]
    assert openai_cover(ranked) is True
    assert openai_cover(ranked[:2]) is False
    assert muse_chart("Muse topped the App Store chart") is True
    assert muse_chart("Meta delays a model") is False
    assert r1_or_store("DeepSeek R1 release") is True
    assert r1_or_store("DeepSeek funding round") is False
    start = datetime(2026, 10, 14, 13, 30)
    early = [{"source_root": "ft", "outcome": "命中", "published_at": datetime(2026, 10, 9, 0, 45)}]
    assert second_hit_conclusion(early, anomaly_start=start) == "未检验"


@pytest.mark.phase1_blocking
def test_operating_evidence_thresholds():
    import math

    from inves_cog.perception.attribution.operating import operating_verdict
    from inves_cog.perception.attribution.tracks import apply_deadline

    as_of = datetime(2026, 10, 20, 13, 30)

    def verdict(records, unknowns=()):
        return operating_verdict(records, as_of=as_of, expected_direction="down", unknowns=unknowns).outcome

    def seen(**kwargs):
        row = {"published_at": as_of, "first_seen_at": as_of}
        row.update(kwargs)
        return row

    guidance = seen(
        kind="company_primary",
        source_level=1,
        citation="8-K accession",
        form="8-K",
        guidance_change=True,
        direction="down",
    )
    assert verdict([guidance], unknowns=["投产与良率"]) == "支持"
    kept = operating_verdict([guidance], as_of=as_of, expected_direction="down", unknowns=["投产与良率"])
    assert kept.unknowns == ["投产与良率"]
    assert verdict([]) == "条件风险"
    assert verdict([seen(**{**guidance, "citation": ""})]) == "条件风险"
    assert verdict([seen(**{**guidance, "guidance_change": False})]) == "条件风险"
    assert verdict([seen(**{**guidance, "falsified": True})]) == "条件风险"
    assert verdict([seen(**{**guidance, "published_at": as_of + timedelta(minutes=1)})]) == "条件风险"
    call = seen(
        kind="company_primary",
        source_level=1,
        citation="call transcript p.4",
        call_quantitative=True,
        direction="down",
    )
    assert verdict([call]) == "支持"
    exact = seen(kind="eps_revision", coverage=10, same_direction_revisions=3, eps_change=-0.03)
    assert verdict([exact]) == "支持"
    assert verdict([seen(**{**exact, "same_direction_revisions": 2})]) == "条件风险"
    assert verdict([seen(**{**exact, "eps_change": -0.029})]) == "条件风险"
    assert verdict([seen(**{**exact, "coverage": None})]) == "条件风险"
    assert verdict([seen(**{**exact, "eps_change": 0.03})]) == "反证"
    assert verdict([seen(**{**exact, "coverage": math.nan})]) == "条件风险"
    assert verdict([seen(**{**exact, "same_direction_revisions": math.inf})]) == "条件风险"
    assert verdict([seen(**{**exact, "same_direction_revisions": 11})]) == "条件风险"
    assert verdict([seen(**{**exact, "eps_change": math.nan})]) == "条件风险"
    empty = operating_verdict([], as_of=as_of, expected_direction="down", unknowns=["投产与良率"])
    with pytest.raises(AttributeError, match="不能改写"):
        empty.outcome = "支持"
    untouched = apply_deadline(empty)
    assert untouched["operating_impact_proven"] is False
    assert untouched["unknowns"] == ["投产与良率"]
    proven = apply_deadline(operating_verdict([exact], as_of=as_of, expected_direction="down"))
    assert proven["operating_impact_proven"] is True
    industry = [
        seen(kind="industry", source_level=2, quantitative=True, source_root="nikkei", direction="down"),
        seen(kind="industry", source_level=3, quantitative=True, source_root="reuters", direction="down"),
    ]
    assert verdict(industry) == "支持"
    assert verdict([industry[0], {**industry[1], "source_root": "nikkei"}]) == "条件风险"
    assert verdict([industry[0]]) == "条件风险"
    assert verdict([{**industry[0], "source_level": 4}, industry[1]]) == "条件风险"
    competitor = seen(
        kind="competitor_primary",
        source_level=1,
        citation="peer 8-K",
        mapped_to_driver=True,
        direction="down",
    )
    assert verdict([competitor]) == "支持"
    assert verdict([seen(**{**competitor, "mapped_to_driver": False})]) == "条件风险"
    both = operating_verdict([guidance, {**exact, "eps_change": 0.03}], as_of=as_of, expected_direction="down")
    assert both.outcome == "条件风险"


@pytest.mark.phase1_blocking
def test_replay_labels_later_recorded_items():
    from inves_cog.perception.attribution.replay import replay_mode, then_visible

    cst = timezone(timedelta(hours=8))
    toshiba = {
        "info_id": "news:benzinga:62130092",
        "published_at": datetime(2026, 10, 2, 19, 56, tzinfo=cst),
        "first_seen_at": datetime(2026, 10, 14, 17, 19, tzinfo=cst),
    }
    day = datetime(2026, 10, 2, 23, 59, tzinfo=cst)
    later = datetime(2026, 10, 15, 9, 15, tzinfo=cst)
    assert replay_mode([toshiba], day)["mode"] == "后补录历史复盘"
    assert replay_mode([toshiba], day)["collected_then"] is False
    assert replay_mode([toshiba], day)["vectors_then"] is False
    assert then_visible([toshiba], day) == []
    seen = replay_mode([toshiba], later)
    assert seen == {"mode": "当时可见", "late_ids": [], "collected_then": True, "vectors_then": False}
    assert then_visible([toshiba], later) == [toshiba]

    cpi = {
        "info_id": "news:benzinga:62350981",
        "published_at": datetime(2026, 10, 14, 20, 30, tzinfo=cst),
        "first_seen_at": datetime(2026, 10, 15, 14, 35, tzinfo=cst),
    }
    morning = replay_mode([cpi], later)
    assert morning["mode"] == "后补录历史复盘"
    assert morning["late_ids"] == ["news:benzinga:62350981"]
    assert then_visible([cpi], later) == []

    stamped = {**toshiba, "embedding_created_at": datetime(2026, 10, 14, 18, 0, tzinfo=cst)}
    assert replay_mode([stamped], later)["vectors_then"] is True
    assert replay_mode([stamped], datetime(2026, 10, 14, 17, 30, tzinfo=cst))["vectors_then"] is False


class _Calls:
    def __init__(self):
        self.rows = []

    def execute(self, sql, params=None):
        self.rows.append((sql, params))


def _pool_bundle():
    return {
        "anomaly_id": "toshiba-2026-10-02",
        "universe": "pool",
        "retrievals": [{"info_id": "nikkei-hdd", "role": "primary", "retrieval_mode": "rules"}],
        "candidates": [
            {"mechanism": "供给", "info_ids": ["nikkei-hdd"], "scored": True, "affected": [{"ticker": "WDC"}]},
            {"mechanism": "无事件/资金面", "info_ids": [], "scored": False},
        ],
        "linkage": {"event_id": "evt-1", "lifecycle": "已验证·有影响", "unknowns": ["投产与良率"]},
        "tracks": [{"trade_date": "2026-10-02", "emotion": "初现", "capital": "冲击中", "fundamental": "待验证"}],
        "impact": {"total_residual": -0.05, "event": -0.05, "amplification": 0.0, "unexplained": 0.0},
        "report": {"status": "已验证·有影响", "fixture": "synthetic"},
    }


@pytest.mark.phase1_blocking
def test_store_writes_perception_rows_only():
    from inves_cog.perception.attribution.store import Store

    calls = _Calls()
    Store(calls).save(_pool_bundle())
    sql = "\n".join(row[0] for row in calls.rows)
    assert "perception.retrievals" in sql
    assert "perception.candidates" in sql
    assert "perception.reports" in sql
    assert "ingest." not in sql
    scored = [params for statement, params in calls.rows if "perception.candidates" in statement]
    assert scored[0][6] == ["nikkei-hdd"]
    assert scored[1][6] == []
    assert scored[1][12] is False

    refused = _Calls()
    wide = {"anomaly_id": "wide-1", "universe": "wide", "candidates": [{"mechanism": "供给", "info_ids": ["x"]}]}
    with pytest.raises(ValueError, match="广域异常"):
        Store(refused).save(wide)
    assert refused.rows == []
    report_only = _Calls()
    Store(report_only).save(
        {
            "anomaly_id": "wide-1",
            "universe": "wide",
            "retrievals": [{"info_id": "late", "role": "background", "retrieval_mode": "rules"}],
            "report": {"status": "假设中"},
        }
    )
    saved = report_only.rows[-1][1][1]
    assert saved.obj["status"] == "已记录"
    empty = {"anomaly_id": "pool-1", "candidates": [{"mechanism": "供给", "info_ids": [], "scored": True}]}
    with pytest.raises(ValueError, match="必须引用"):
        Store(_Calls()).save(empty)


@pytest.mark.phase1_blocking
def test_attribution_rows_round_trip_on_disposable_database():
    listed = subprocess.run(
        ["docker", "ps", "--filter", "name=inves-cog-test-", "--format", "{{.Names}}"],
        check=True,
        capture_output=True,
        text=True,
    )
    names = [line for line in listed.stdout.splitlines() if line.endswith("-database-1")]
    assert len(names) == 1
    probe = Path(__file__).with_name("disposable_probe.sql").read_text()
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            names[0],
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "inves_cog_admin",
            "-d",
            "inves_cog",
        ],
        input=probe,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout


@pytest.mark.phase1_cases
def test_case_no_news_unexplained():
    from inves_cog.perception.attribution.unexplained import statuses_without_news

    class Boom:
        def call(self, task, payload):
            raise AssertionError(task)

    cases = [
        {"anomaly_id": "toshiba-2026-10-02", "universe": "pool", "fixture": "synthetic", "news": []},
        {"anomaly_id": "openai-2026-10-14", "universe": "pool", "fixture": "synthetic", "news": []},
        {"anomaly_id": "muse-2026-09-21", "universe": "pool", "fixture": "synthetic", "news": []},
        {"anomaly_id": "r1-release-2025-01-20", "universe": "pool", "fixture": "synthetic", "news": []},
    ]
    rows = statuses_without_news(cases, Boom())
    assert [row["anomaly_id"] for row in rows] == [case["anomaly_id"] for case in cases]
    assert {row["status"] for row in rows} == {"已发现·原因未明"}
    assert {row["fixture"] for row in rows} == {"synthetic"}
    labeled = {**cases[0], "fixture": "recording"}
    with pytest.raises(ValueError, match="synthetic"):
        statuses_without_news([labeled], Boom())


class _Boom:
    def call(self, task, payload):
        raise AssertionError(task)


@pytest.mark.phase1_blocking
def test_m7_anomalies_without_visible_news_stay_unexplained():
    from inves_cog.perception.attribution.session import reports_without_visible_news

    as_of = datetime(2026, 10, 14, 21, 0)
    pool = {
        "anomaly_id": "2026-10-14:close:001",
        "universe": "pool",
        "trade_date": "2026-10-14",
        "members": [{"ticker": "NVDA"}],
    }
    wide = {
        "anomaly_id": "2026-10-14:close:002",
        "universe": "wide",
        "trade_date": "2026-10-14",
        "members": [{"ticker": "ZZZZ"}],
    }
    late = {
        "info_id": "later",
        "published_at": datetime(2026, 10, 2, 12, 0),
        "first_seen_at": datetime(2026, 10, 16, 12, 0),
    }
    reports = reports_without_visible_news([pool, wide], [late], as_of, _Boom())
    assert reports[0]["status"] == "已发现·原因未明"
    assert reports[0]["case_clause_met"] is False
    assert reports[0]["sources"] == []
    assert reports[0]["candidates"][0]["scored"] is False
    assert reports[1]["status"] == "已记录"
    assert reports[1]["candidates"] == []
    seen = {
        "info_id": "seen",
        "published_at": datetime(2026, 10, 14, 15, 0),
        "first_seen_at": datetime(2026, 10, 14, 16, 0),
    }
    with pytest.raises(ValueError, match="当时可见"):
        reports_without_visible_news([pool], [seen], as_of, _Boom())
    with pytest.raises(ValueError, match="编号或范围"):
        reports_without_visible_news([{"anomaly_id": "x"}], [], as_of, _Boom())


@pytest.mark.phase1_cases
def test_m7_case_days_have_status_without_claiming_the_clause():
    from datetime import date

    from inves_cog.perception.anomaly.cases import case_anomalies
    from inves_cog.perception.anomaly.replay import _identify
    from inves_cog.perception.attribution.session import reports_without_visible_news

    fixture = ROOT / "tests/fixtures/phase1/m7"
    windows = (
        ("toshiba_bars.jsonl.gz", "2026-10-02"),
        ("openai_bars.jsonl.gz", "2026-10-14"),
        ("meta_bars.jsonl.gz", "2026-09-21"),
        ("case_20250127_bars.jsonl.gz", "2025-01-27"),
    )
    for filename, day in windows:
        anomalies = _identify(date.fromisoformat(day), case_anomalies(fixture, filename, day))
        reports = reports_without_visible_news(anomalies, [], date.fromisoformat(day), _Boom())
        assert [row["anomaly_id"] for row in reports] == [row["anomaly_id"] for row in anomalies]
        pool = [row for row in reports if row["universe"] == "pool"]
        assert pool
        assert {row["status"] for row in pool} == {"已发现·原因未明"}
        assert all(row["case_clause_met"] is False for row in reports)
        assert all(row["status"] == "已记录" for row in reports if row["universe"] == "wide")


@pytest.mark.phase1_blocking
def test_manual_public_leads_leave_case_gaps():
    from datetime import date

    from inves_cog.perception.attribution.cases import muse_chart, openai_labels, r1_or_store
    from inves_cog.perception.attribution.manual import (
        calendar_after,
        remaining_gap,
        strictly_before_primary,
        supplement_replay,
    )

    payload = json.loads((ROOT / "tests/fixtures/phase1/m8/manual_leads_2026-10-16.json").read_text())
    assert payload["label"] == "后补录历史复盘"
    assert payload["read_on"] == "2026-10-16"
    assert payload["collected_then"] is False
    assert payload["vectors_then"] is False
    leads = {row["kind"]: row for row in payload["leads"]}
    assert set(leads) == {"r1_release", "openai_arr", "muse_rank"}

    release = leads["r1_release"]
    assert release["published_on"] == "2025-01-20"
    assert release["published_precision"] == "date"
    assert release["app_store_snapshot"] is False
    assert r1_or_store(release["excerpt"]) is True
    assert remaining_gap(release) == "只有发布日期，没有榜单快照"
    replay = supplement_replay(payload["read_on"], release["published_on"], "2025-01-20")
    assert replay == {"mode": "后补录历史复盘", "collected_then": False, "vectors_then": False}

    revenue = leads["openai_arr"]
    assert revenue["source_root"] == "reuters"
    assert revenue["timezone"] is None
    assert revenue["ft_original_frozen"] is False
    assert openai_labels(revenue["excerpt"]) == {"arr_background"}
    assert remaining_gap(revenue) == "FT 原文未冻结"
    anomaly = date(2026, 10, 14)
    assert strictly_before_primary(revenue["updated_on"], anomaly) is True
    assert calendar_after(revenue["published_on"], revenue["updated_on"], anomaly) is False
    assert supplement_replay(payload["read_on"], revenue["published_on"], anomaly)["vectors_then"] is False

    muse = leads["muse_rank"]
    assert muse["published_on"] == "2026-09-18"
    assert muse["before_open"] is False
    assert muse_chart(muse["excerpt"]) is True
    assert remaining_gap(muse) == "日期不在 09-19 至 09-21 开盘前"
    assert supplement_replay(payload["read_on"], muse["published_on"], "2026-09-21")["collected_then"] is False
