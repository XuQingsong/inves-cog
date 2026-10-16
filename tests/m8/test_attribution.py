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
def test_market_move_uses_residual_return_and_positive_eps():
    from inves_cog.perception.attribution.magnitude import market_move

    members = [
        {"ticker": "LOSS", "eps_ttm": -1.0, "pe_ttm": 10, "market_cap_prev": 500, "resid": -0.2, "ret": -0.8},
        {"ticker": "ZERO", "eps_ttm": 0.0, "pe_ttm": 10, "market_cap_prev": 500, "resid": -0.2, "ret": -0.8},
        {"ticker": "OK", "eps_ttm": 2.0, "pe_ttm": 10, "market_cap_prev": 100, "resid": -0.1, "ret": -0.9},
    ]
    assert market_move(members) == {"delta_e_mkt": -1.0, "verdict": None}
    blocked = [
        {"ticker": "LOSS", "eps_ttm": -1.0, "pe_ttm": 10, "market_cap_prev": 100, "resid": -0.2, "ret": -0.9},
        {"ticker": "FLAT", "eps_ttm": 2.0, "pe_ttm": 0, "market_cap_prev": 100, "resid": -0.2, "ret": -0.9},
        {"ticker": "PRICE", "eps_ttm": 2.0, "pe_ttm": 10, "market_cap_prev": 100, "ret": -0.9},
    ]
    assert market_move(blocked) == {"delta_e_mkt": None, "verdict": "无法检验"}


@pytest.mark.phase1_blocking
def test_channels_follow_the_mechanism_and_the_best_source():
    from inves_cog.perception.attribution.magnitude import channel_rows, implied_magnitude

    citations = [{"source_level": 4}, {"source_level": 1}, {"source_level": None}]
    supply = channel_rows(
        "供给",
        citations,
        [
            {
                "channel": "供给/价格",
                "status": "观察到",
                "exposure_usd": 100,
                "basis": "分部收入",
                "segment_margin": 0.4,
                "op_margin_ttm": 0.1,
            },
            {
                "channel": "供给/价格",
                "status": "候选",
                "exposure_usd": 900,
                "basis": "分部收入",
                "segment_margin": 0.4,
            },
        ],
    )
    assert supply == [
        {"channel": "供给/价格", "source_level": 1, "exposure_usd": 100, "incremental_margin": 0.4},
    ]
    demand = channel_rows(
        "需求",
        [{"source_level": 2}],
        [
            {
                "channel": "直接收入",
                "status": "有支持",
                "exposure_usd": 80,
                "basis": "公司",
                "segment_margin": 0.9,
                "op_margin_ttm": 0.2,
            }
        ],
    )
    assert demand[0]["channel"] == "直接收入"
    assert demand[0]["incremental_margin"] == 0.2
    assert channel_rows("竞争", [{"source_level": 3}], [])[0]["channel"] == "直接收入"
    financing = channel_rows(
        "客户融资",
        [{"source_level": 2}],
        [
            {"channel": "订单/积压", "status": "已确立", "exposure_usd": 100, "op_margin_ttm": 0.3},
            {"channel": "融资/对手方", "status": "驳回", "exposure_usd": 80, "op_margin_ttm": 0.3},
        ],
        years_to_realize=5,
    )
    assert [row["channel"] for row in financing] == ["订单/积压", "融资/对手方"]
    assert financing[0]["years_to_realize"] == 5
    assert financing[1]["exposure_usd"] is None
    multiple = implied_magnitude(
        {"delta_mktcap": 90000000000.0, "pe": 30.0, "channels": channel_rows("估值倍数", [], [])}
    )
    assert multiple["verdict"] == "不相容"
    assert "情绪" not in json.dumps(multiple, ensure_ascii=False)
    missing_margin = channel_rows(
        "供给",
        [{"source_level": 2}],
        [{"channel": "供给/价格", "status": "观察到", "exposure_usd": 100, "basis": "分部收入", "op_margin_ttm": 0.2}],
    )
    blocked = implied_magnitude({"delta_mktcap": -120.0, "pe": 12.0, "channels": missing_margin})
    assert missing_margin[0]["incremental_margin"] is None
    assert blocked["verdict"] == "无法检验"
    no_years = channel_rows(
        "客户融资",
        [{"source_level": 1}],
        [
            {"channel": "订单/积压", "status": "观察到", "exposure_usd": 100, "op_margin_ttm": 0.3},
            {"channel": "融资/对手方", "status": "观察到", "exposure_usd": 50, "op_margin_ttm": 0.2},
        ],
    )
    assert implied_magnitude({"delta_mktcap": -10.0, "pe": 10.0, "channels": no_years})["verdict"] == "无法检验"
    with pytest.raises(ValueError, match="渠道只接受"):
        channel_rows("情绪", [], [])


@pytest.mark.phase1_blocking
def test_missing_exposure_is_a_fill_task_and_not_incompatible():
    from inves_cog.perception.attribution.magnitude import exposure_tasks, implied_magnitude

    exposures = [
        {"channel": "订单/积压", "status": "观察到", "exposure_usd": None, "relation_id": "r-order", "ticker": "CRWV"},
        {
            "channel": "融资/对手方",
            "status": "有支持",
            "exposure_usd": 50,
            "relation_id": "r-loan",
            "ticker": "CRWV",
            "op_margin_ttm": 0.2,
        },
        {
            "channel": "融资/对手方",
            "status": "候选",
            "exposure_usd": None,
            "relation_id": "r-candidate",
            "ticker": "DELL",
        },
        {"channel": "直接收入", "status": "已确立", "exposure_usd": None, "relation_id": "r-income", "ticker": "NVDA"},
    ]
    tasks = exposure_tasks("客户融资", exposures)
    assert tasks == [
        {
            "channel": "订单/积压",
            "relation_id": "r-order",
            "ticker": "CRWV",
            "from_entity": None,
            "to_entity": None,
            "reason": "缺美元暴露",
        }
    ]
    assert exposure_tasks("估值倍数", exposures) == []
    assert all(task["reason"] != "不相容" for task in tasks)
    known = [
        {"channel": "直接收入", "source_level": 2, "exposure_usd": 4000000000.0, "incremental_margin": 0.5},
        {"channel": "融资/对手方", "source_level": 2, "exposure_usd": None},
    ]
    verdict = implied_magnitude({"delta_mktcap": -10000000000.0, "pe": 20.0, "channels": known})
    assert verdict["verdict"] == "相容"
    with pytest.raises(ValueError, match="渠道只接受"):
        exposure_tasks("情绪", [])


@pytest.mark.phase1_blocking
def test_market_confidence_and_fundamental_standing_stay_separate():
    from inves_cog.perception.attribution.report import explanation_report, split_conclusions

    anomaly = {"anomaly_id": "muse", "universe": "pool", "direction": "up"}
    impact = {"event": 0.0, "amplification": 0.0, "unexplained": 0.0}
    supply = {"scored": True, "score": 0.8, "mechanism": "供给", "affected": [{"ticker": "AMD"}]}
    report = explanation_report(anomaly, impact, [supply], [])
    assert report["market_confidence"] == "高"
    assert report["fundamental_standing"] == "待验证"
    multiple = {"scored": True, "score": 0.9, "mechanism": "估值倍数", "affected": [{"ticker": "META"}]}
    narrative = explanation_report(anomaly, impact, [multiple], [])
    assert narrative["market_confidence"] == "高"
    assert narrative["fundamental_standing"] is None
    weak = {"scored": True, "score": 0.4, "mechanism": "供给", "affected": [{"ticker": "AMD"}]}
    quiet = explanation_report(anomaly, impact, [weak], [])
    assert quiet["market_confidence"] == "低"
    assert quiet["fundamental_standing"] is None
    deadline = {
        "fundamental": "支持",
        "lifecycle": "已验证·有影响",
        "deadline_outcome": "支持",
        "closing_reason": "截止日证据支持",
        "operating_impact_proven": True,
    }
    closed = explanation_report(anomaly, impact, [supply], [], deadline)
    assert closed["market_confidence"] == "高"
    assert closed["fundamental_standing"] == "支持"
    copied = split_conclusions([supply], "高")
    assert copied["fundamental_standing"] == "待验证"
    medium = split_conclusions([{"scored": True, "score": 0.69, "mechanism": "需求"}], "局部支持")
    assert medium == {"market_confidence": "中", "fundamental_standing": "局部支持"}


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
def test_magnitude_component_drops_an_untested_channel():
    from inves_cog.perception.attribution.evidence import evidence_score, magnitude_component

    assert magnitude_component("相容") == 1.0
    assert magnitude_component("部分相容") == 0.6
    assert magnitude_component("不相容") == 0.2
    assert magnitude_component("无法检验") is None
    assert magnitude_component("情绪") is None
    base = {"time": 1.0, "gradient": 1.0, "specificity": 1.0, "narrative": 1.0, "alternatives": 1.0}
    scored = evidence_score({**base, "magnitude": magnitude_component("不相容")})
    skipped = evidence_score({**base, "magnitude": magnitude_component("无法检验")})
    assert scored["total"] == 0.88
    assert skipped["total"] == 1.0
    assert "情绪" not in json.dumps(scored, ensure_ascii=False)


@pytest.mark.phase1_blocking
def test_exposure_gradient_needs_three_observed_relations():
    from inves_cog.perception.attribution.evidence import exposure_gradient

    members = [
        {"ticker": "AAA", "resid_z": -3.0},
        {"ticker": "BBB", "resid_z": -1.0},
        {"ticker": "CCC", "resid_z": 2.0},
    ]
    relations = [
        {"ticker": "AAA", "exposure": "直接", "status": "观察到"},
        {"ticker": "BBB", "exposure": "间接", "status": "有支持"},
        {"ticker": "CCC", "exposure": "概念关联", "status": "已确立"},
    ]
    assert exposure_gradient(members, relations, direction="down") == 1.0
    flipped = [
        {"ticker": "AAA", "resid_z": 3.0},
        {"ticker": "BBB", "resid_z": 1.0},
        {"ticker": "CCC", "resid_z": -2.0},
    ]
    assert exposure_gradient(flipped, relations, direction="down") == 0.0
    assert exposure_gradient(members[:2], relations, direction="down") is None
    candidate = [{"ticker": "AAA", "exposure": "直接", "status": "候选"}]
    assert exposure_gradient(members, candidate, direction="down") is None
    flat = [
        {"ticker": "AAA", "exposure": "直接", "status": "观察到"},
        {"ticker": "BBB", "exposure": "直接", "status": "观察到"},
        {"ticker": "CCC", "exposure": "直接", "status": "观察到"},
    ]
    assert exposure_gradient(members, flat, direction="down") is None
    missing = [{"ticker": "AAA", "resid_z": -3.0}, {"ticker": "BBB", "resid_z": -1.0}, {"ticker": "CCC"}]
    assert exposure_gradient(missing, relations, direction="down") is None
    exited = [
        {"ticker": name, "exposure": "直接", "status": "已确立", "exit_reason": "关系退出"}
        for name in ("AAA", "BBB", "CCC")
    ]
    assert exposure_gradient(members, exited, direction="down") is None


@pytest.mark.phase1_blocking
def test_specificity_narrative_and_alternatives_are_separate_scores():
    from inves_cog.perception.attribution.evidence import alternative_exclusion, basket_specificity, narrative_support

    assert basket_specificity([3.0, 3.0], None) is None
    assert basket_specificity([3.0], []) is None
    assert basket_specificity([3.0, 3.0], [0.0]) == 1.0
    assert basket_specificity([1.5], [0.0]) == 0.5
    assert basket_specificity([0.0], [1.0]) == 0.0
    items = [
        {"source_root": "nikkei", "entities": ["toshiba", "WDC"]},
        {"source_root": "nikkei", "entities": ["toshiba", "WDC"]},
        {"source_root": "wire", "entities": ["toshiba"]},
        {"source_root": "desk", "tickers": ["WDC"]},
    ]
    assert narrative_support(items, ["toshiba"], ["WDC"]) == 0.2
    assert narrative_support([], ["toshiba"], ["WDC"]) == 0.0
    many = [{"source_root": f"root-{index}", "entities": ["toshiba", "WDC"]} for index in range(6)]
    assert narrative_support(many, ["toshiba"], ["WDC"]) == 1.0
    members = [
        {"ticker": "AAA"},
        {"ticker": "BBB", "earnings_reaction": True},
        {"ticker": "CCC", "rating_change": True},
    ]
    assert alternative_exclusion([]) is None
    assert alternative_exclusion(members) == 0.333333
    assert alternative_exclusion([{"ticker": "AAA", "resid_z": -4.0}]) == 1.0


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
def test_retrieval_entities_stop_at_one_hop():
    from inves_cog.perception.attribution.retrieve import retrieval_entities

    baskets = [
        {"name": "hdd", "members": ["WDC", "STX"]},
        {"name": "memory", "members": ["STX", "MU"]},
        {"name": "cpu", "members": ["NVDA"]},
    ]
    edges = [
        {"from_entity": "WDC", "to_entity": "toshiba", "status": "驳回"},
        {"from_entity": "toshiba", "to_entity": "flash", "status": "已确立"},
        {"from_entity": "NVDA", "to_entity": "tsmc", "status": "观察到"},
    ]
    monitored = [
        {"entity_id": "hdd_watch", "tickers": ["STX", "INTC"]},
        {"entity_id": "flash_watch", "tickers": ["flash"]},
        {"entity_id": "WDC", "tickers": ["WDC"]},
    ]
    found = retrieval_entities(["WDC"], baskets, edges, monitored)
    assert found["members"] == ["WDC"]
    assert found["basket_peers"] == ["STX"]
    assert found["neighbors"] == ["toshiba"]
    assert found["monitored"] == ["hdd_watch"]
    assert found["entities"] == ["WDC", "STX", "toshiba", "hdd_watch"]
    assert "MU" not in found["entities"]
    assert "NVDA" not in found["entities"]
    assert "flash" not in found["entities"]
    assert "INTC" not in found["entities"]
    assert retrieval_entities([], baskets, edges, monitored)["entities"] == []


@pytest.mark.phase1_blocking
def test_retrieval_union_keeps_rule_hits_outside_the_vector_cap():
    from inves_cog.perception.attribution.retrieve import retrieval_union, vector_query
    from inves_cog.perception.attribution.rules import m8_rules

    rules = m8_rules()
    anomaly = {"baskets": ["hdd"], "direction": "down", "members": ["WDC"], "neighbors": ["toshiba"]}
    assert vector_query(anomaly) == "hdd down WDC"
    vectors = [
        {
            "info_id": f"vec-{index:02d}",
            "source_root": f"root-{index:02d}",
            "similarity": 1 - index / 100,
            "model": rules["embedding_model"],
            "dimensions": rules["embedding_dimensions"],
            "entities": [],
        }
        for index in range(51)
    ]
    rule_only = {"info_id": "filing", "source_root": "sec", "tickers": ["WDC"], "entities": ["WDC"]}
    wrong_model = {
        "info_id": "old-embed",
        "source_root": "old",
        "similarity": 0.99,
        "model": "other-model",
        "dimensions": 1536,
        "entities": [],
    }
    same_root = {
        "info_id": "reprint",
        "source_root": "sec",
        "similarity": 0.99,
        "model": rules["embedding_model"],
        "dimensions": rules["embedding_dimensions"],
        "entities": [],
    }
    blank_a = {"info_id": "blank-a", "tickers": ["WDC"], "entities": []}
    blank_b = {"info_id": "blank-b", "tickers": ["WDC"], "entities": []}
    rows = retrieval_union([*vectors, rule_only, wrong_model, same_root, blank_a, blank_b], ["WDC"])
    identifiers = {row["info_id"] for row in rows}
    assert "vec-50" not in identifiers
    assert "vec-00" in identifiers
    assert "old-embed" not in identifiers
    assert "filing" in identifiers
    assert "reprint" not in identifiers
    filing = next(row for row in rows if row["source_root"] == "sec")
    assert filing["paths"] == ["rule", "vector"]
    assert {"blank-a", "blank-b"} <= identifiers


@pytest.mark.phase1_blocking
def test_shortlist_uses_the_retrieval_score_after_the_window():
    from inves_cog.perception.attribution.claims import claim_payload
    from inves_cog.perception.attribution.retrieve import shortlist

    start = datetime(2026, 10, 14, 13, 30)
    now = datetime(2026, 10, 14, 21, 0)
    noise = [
        {
            "info_id": f"noise-{index}",
            "published_at": start - timedelta(hours=1),
            "rank": 1000 - index,
            "entities": ["WDC"],
            "source_root": f"noise-{index}",
        }
        for index in range(45)
    ]
    unrelated = {
        "info_id": "unrelated",
        "published_at": start - timedelta(hours=1),
        "rank": 9000,
        "entities": [],
        "source_root": "other",
    }
    lead = {
        "info_id": "lead",
        "published_at": start - timedelta(days=6),
        "rank": 0,
        "entities": ["WDC"],
        "source_root": "nikkei",
        "source_level": 4,
    }
    too_old = {
        "info_id": "too-old",
        "published_at": start - timedelta(days=8),
        "rank": 5000,
        "entities": ["WDC"],
        "source_root": "old-root",
    }
    hidden = {
        "info_id": "hidden",
        "published_at": start - timedelta(hours=2),
        "first_seen_at": now + timedelta(hours=1),
        "rank": 5000,
        "entities": ["WDC"],
        "source_root": "hidden-root",
    }
    rows = shortlist([*noise, unrelated, lead, too_old, hidden], ["WDC"], start, now)
    identifiers = {row["info_id"] for row in rows}
    assert rows[0]["info_id"] == "lead"
    assert rows[0]["role"] == "background"
    assert "unrelated" not in identifiers
    assert "too-old" not in identifiers
    assert "hidden" not in identifiers
    assert len(rows) == 40
    payload_ids = {item["info_id"] for item in claim_payload(rows)["items"]}
    assert "lead" in payload_ids
    assert "noise-44" not in payload_ids


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
def test_independent_evidence_is_not_the_price_move():
    from inves_cog.perception.attribution.candidates import independent_of_price, market_confirmed

    price = [{"kind": "price", "source_root": "tape"}, {"kind": "price", "source_root": "tape-2"}]
    assert independent_of_price(price) is False
    one = [{"source_root": "nikkei", "source_level": 2}]
    assert independent_of_price(one) is False
    two = [{"source_root": "nikkei"}, {"source_root": "nikkei"}, {"source_root": "reuters"}]
    assert independent_of_price(two) is True
    heat = [{"heat_spike": True, "monitor": "hdd"}]
    assert independent_of_price(heat) is True
    assert independent_of_price([{"heat_spike": True}]) is False
    note = [{"kind": "commentary", "source_level": 3, "source_root": "barclays"}]
    assert independent_of_price(note) is True
    rumor = [{"kind": "commentary", "source_level": 4, "source_root": "social"}]
    assert independent_of_price(rumor) is False
    confirmed = market_confirmed(
        claim_time=False,
        response=True,
        independent=independent_of_price(two),
        alternative=0.5,
    )
    assert confirmed is False


@pytest.mark.phase1_blocking
def test_sentiment_amplification_does_not_change_the_fundamental():
    from inves_cog.perception.attribution.dims import sentiment_amplification
    from inves_cog.perception.attribution.report import explanation_report

    assert sentiment_amplification(None, "待验证") is None
    assert sentiment_amplification({}, "待验证") is None
    assert sentiment_amplification({"sources_today": 3}, "待验证") is None
    rising = {"sources_today": 3, "sources_yesterday": 2}
    assert sentiment_amplification(rising, "待验证") is True
    assert sentiment_amplification(rising, None) is True
    assert sentiment_amplification(rising, "失效") is True
    assert sentiment_amplification(rising, "局部支持") is False
    assert sentiment_amplification(rising, "支持") is False
    assert sentiment_amplification(rising, "冲突") is False
    flat = {"sources_today": 3, "sources_yesterday": 3}
    assert sentiment_amplification(flat, "待验证") is False
    assert sentiment_amplification({"search_ratio": 3}, "待验证") is False
    assert sentiment_amplification({"search_ratio": 3.1}, "待验证") is True
    assert sentiment_amplification({"rank_jump": 20}, "待验证") is False
    assert sentiment_amplification({"rank_jump": 21}, "待验证") is True
    anomaly = {"anomaly_id": "heat", "universe": "pool", "direction": "down"}
    impact = {"event": 0.0, "amplification": 0.0, "unexplained": 0.0}
    supply = {"scored": True, "score": 0.8, "mechanism": "供给", "affected": [{"ticker": "WDC"}]}
    quiet = explanation_report(anomaly, impact, [supply], [])
    assert quiet["sentiment_amplification"] is None
    assert quiet["fundamental_standing"] == "待验证"
    assert "operating_impact_proven" not in quiet
    hot = explanation_report(anomaly, impact, [supply], [], heat=rising)
    assert hot["sentiment_amplification"] is True
    assert hot["fundamental_standing"] == "待验证"
    assert hot["magnitude_channels"] is None
    assert "operating_impact_proven" not in hot
    as_of = datetime(2026, 10, 6, 21, 0)
    statement = {
        "source_level": 1,
        "quantity": "产能增加 20%",
        "published_at": datetime(2026, 10, 6, 9, 0),
        "first_seen_at": datetime(2026, 10, 6, 10, 0),
    }
    held = explanation_report(anomaly, impact, [supply], [], heat=rising, statements=[statement], as_of=as_of)
    assert held["fundamental_standing"] == "局部支持"
    assert held["sentiment_amplification"] is False


@pytest.mark.phase1_blocking
def test_weak_signal_only_raises_research_priority():
    from inves_cog.perception.attribution.lifecycle import transition, weak_signal
    from inves_cog.perception.attribution.report import explanation_report

    clues = [
        {"variable": "产能", "source_root": "a", "stage": "招聘", "sessions_ago": 0},
        {"variable": "产能", "source_root": "b", "stage": "招聘", "sessions_ago": 10},
        {"variable": "产能", "source_root": "c", "stage": "设备安装", "sessions_ago": 30},
    ]
    found = weak_signal(clues)
    assert found["research_priority"] is True
    assert found["lifecycle"] == "已发现"
    assert found["authenticity"] is None
    assert found["fundamental_standing"] is None
    assert found["overlay"] is False
    assert found["tasks"] == [
        {"variable": "产能", "reason": "弱信号补证", "is_evidence": False, "roots": 3, "stages": 2}
    ]
    with pytest.raises(ValueError):
        transition(None, "假设中", [], when="t", trigger="weak", evidence_ids=["a"])
    late = [{**clues[0], "sessions_ago": 31}, clues[1], clues[2]]
    assert weak_signal(late)["research_priority"] is False
    future = [{**clues[0], "sessions_ago": -1}, clues[1], clues[2]]
    assert weak_signal(future)["research_priority"] is False
    blocked = clues + [
        {"variable": "产能", "source_root": "d", "stage": "认证", "sessions_ago": 2, "contradiction": True}
    ]
    assert weak_signal(blocked)["research_priority"] is False
    outside = clues + [
        {"variable": "产能", "source_root": "d", "stage": "认证", "sessions_ago": 31, "contradiction": True}
    ]
    assert weak_signal(outside)["research_priority"] is True
    assert weak_signal(clues[:2])["research_priority"] is False
    assert weak_signal([{**row, "stage": "招聘"} for row in clues])["research_priority"] is False
    assert weak_signal([{**row, "source_root": "a"} for row in clues])["research_priority"] is False
    assert weak_signal([])["research_priority"] is False
    assert weak_signal(None) is None
    missing = [{**clues[0], "sessions_ago": None}, clues[1], clues[2]]
    assert weak_signal(missing)["research_priority"] is None
    incomplete = [{**clues[0], "stage": None}, clues[1], clues[2]]
    assert weak_signal(incomplete)["research_priority"] is None
    anomaly = {"anomaly_id": "clue", "universe": "pool", "direction": "down"}
    impact = {"event": 0.0, "amplification": 0.0, "unexplained": 0.0}
    supply = {"scored": True, "score": 0.8, "mechanism": "供给", "affected": [{"ticker": "WDC"}]}
    quiet = explanation_report(anomaly, impact, [supply], [])
    assert quiet["weak_signal"] is None
    assert quiet["fundamental_standing"] == "待验证"
    assert "lifecycle" not in quiet
    report = explanation_report(anomaly, impact, [supply], [], clues=clues)
    assert report["weak_signal"]["lifecycle"] == "已发现"
    assert report["fundamental_standing"] == "待验证"
    assert "operating_impact_proven" not in report
    assert "lifecycle" not in report


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

    assert classify_response(1.2, 0.4, direction="up") == "命中"
    assert classify_response(-1.2, 0.2, direction="up") == "反证"
    assert classify_response(0.4, 0.1, direction="up") == "无响应"
    assert classify_response(-1.2, 0.2, direction="down") == "命中"
    assert classify_response(1.2, 0.4, direction="down") == "反证"
    assert classify_response(-1.2, 1.1, direction="down") == "无响应"
    with pytest.raises(ValueError, match="方向只接受"):
        classify_response(-1.2, 0.2, direction="flat")
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
def test_price_retrieval_must_be_seen_before_the_response():
    from inves_cog.perception.attribution.second_hit import second_hit_conclusion

    start = datetime(2026, 10, 2, 13, 30)
    response = datetime(2026, 10, 6, 20, 0)
    event = {
        "source_root": "tdk",
        "outcome": "命中",
        "published_at": datetime(2026, 10, 6, 9, 0),
        "from_price_anomaly": True,
        "first_seen_at": datetime(2026, 10, 6, 14, 0),
        "response_at": response,
    }
    assert second_hit_conclusion([event], anomaly_start=start) == "确认"
    same_time = {**event, "first_seen_at": response}
    assert second_hit_conclusion([same_time], anomaly_start=start) == "未检验"
    missing = {**event, "first_seen_at": None}
    assert second_hit_conclusion([missing], anomaly_start=start) == "未检验"
    plain = {"source_root": "tdk", "outcome": "命中", "published_at": datetime(2026, 10, 6, 9, 0)}
    assert second_hit_conclusion([plain], anomaly_start=start) == "确认"


@pytest.mark.phase1_blocking
def test_missing_vectors_are_named_as_a_rule_fallback():
    from inves_cog.perception.attribution.report import explanation_report
    from inves_cog.perception.attribution.rules import m8_rules

    anomaly = {"anomaly_id": "pool-1", "universe": "pool", "direction": "down"}
    impact = {"event": 0.0, "amplification": 0.0, "unexplained": 0.0}
    rules = m8_rules()
    quiet = explanation_report(anomaly, impact, [], [])
    assert quiet["retrieval_gap"] is None
    empty = explanation_report(anomaly, impact, [], [], embeddings=[])
    assert empty["retrieval_gap"] == "向量检索降到规则检索"
    assert "operating_impact_proven" not in empty
    assert empty["fundamental_standing"] is None
    wrong = [{"model": rules["embedding_model"], "dimensions": 768}]
    named = explanation_report(anomaly, impact, [], [], embeddings=wrong)
    assert named["retrieval_gap"] == "向量检索降到规则检索"
    approved = [{"model": rules["embedding_model"], "dimensions": rules["embedding_dimensions"]}]
    kept = explanation_report(anomaly, impact, [], [], embeddings=approved)
    assert kept["retrieval_gap"] is None
    assert kept["market_confidence"] == "低"


@pytest.mark.phase1_blocking
def test_magnitude_channels_keep_their_own_verdicts():
    from inves_cog.perception.attribution.magnitude import implied_magnitude
    from inves_cog.perception.attribution.report import explanation_report

    anomaly = {"anomaly_id": "openai", "universe": "pool", "direction": "down"}
    impact = {"event": 0.0, "amplification": 0.0, "unexplained": 0.0}
    direct = implied_magnitude(
        {
            "delta_mktcap": -800000000000.0,
            "pe": 32.0,
            "channels": [
                {"channel": "直接收入", "exposure_usd": 10000000000.0, "source_level": 4, "incremental_margin": 0.3}
            ],
        }
    )
    backlog = implied_magnitude(
        {
            "delta_mktcap": -60000000000.0,
            "pe": 30.0,
            "channels": [
                {
                    "channel": "订单/积压",
                    "exposure_usd": 150000000000.0,
                    "source_level": 4,
                    "years_to_realize": 5,
                    "incremental_margin": 0.3,
                }
            ],
        }
    )
    partial = implied_magnitude(
        {
            "delta_mktcap": -10000000000.0,
            "pe": 20.0,
            "channels": [
                {"channel": "直接收入", "exposure_usd": 4000000000.0, "source_level": 2, "incremental_margin": 0.5},
                {"channel": "融资/对手方", "exposure_usd": None, "source_level": 2},
            ],
        }
    )
    direct["verdict"] = "情绪"
    report = explanation_report(anomaly, impact, [], [], magnitude=direct)
    assert report["magnitude_channels"] == [{"channel": "直接收入", "delta_e_evt": 300000000.0, "verdict": "不相容"}]
    assert report["fundamental_standing"] is None
    assert "operating_impact_proven" not in report
    assert "情绪" not in json.dumps(report["magnitude_channels"], ensure_ascii=False)
    listed = explanation_report(anomaly, impact, [], [], magnitude=backlog)
    assert listed["magnitude_channels"][0]["verdict"] == "部分相容"
    split = explanation_report(anomaly, impact, [], [], magnitude=partial)
    assert [row["verdict"] for row in split["magnitude_channels"]] == ["相容", "无法检验"]
    assert explanation_report(anomaly, impact, [], [])["magnitude_channels"] is None


@pytest.mark.phase1_blocking
def test_one_level12_quantity_is_local_support_only():
    from inves_cog.perception.attribution.report import explanation_report
    from inves_cog.perception.attribution.tracks import local_support

    as_of = datetime(2026, 10, 6, 21, 0)
    statement = {
        "source_level": 2,
        "quantity": "产能增加 20%",
        "published_at": datetime(2026, 10, 6, 9, 0),
        "first_seen_at": datetime(2026, 10, 6, 10, 0),
    }
    assert local_support([statement], as_of) == "局部支持"
    assert local_support([{**statement, "source_level": 4}], as_of) == "待验证"
    assert local_support([{**statement, "quantity": None}], as_of) == "待验证"
    assert local_support([{**statement, "kind": "price"}], as_of) == "待验证"
    later = {**statement, "first_seen_at": datetime(2026, 10, 7, 9, 0)}
    assert local_support([later], as_of) == "待验证"
    anomaly = {"anomaly_id": "toshiba", "universe": "pool", "direction": "down"}
    impact = {"event": 0.0, "amplification": 0.0, "unexplained": 0.0}
    supply = {"scored": True, "score": 0.8, "mechanism": "供给", "affected": [{"ticker": "WDC"}]}
    report = explanation_report(anomaly, impact, [supply], [], statements=[statement], as_of=as_of)
    assert report["fundamental_standing"] == "局部支持"
    assert report["market_confidence"] == "高"
    assert "operating_impact_proven" not in report
    multiple = {"scored": True, "score": 0.9, "mechanism": "估值倍数", "affected": [{"ticker": "MU"}]}
    narrative = explanation_report(anomaly, impact, [multiple], [], statements=[statement], as_of=as_of)
    assert narrative["fundamental_standing"] is None
    deadline = {
        "fundamental": "支持",
        "lifecycle": "已验证·有影响",
        "deadline_outcome": "支持",
        "closing_reason": "截止日证据支持",
        "operating_impact_proven": True,
    }
    closed = explanation_report(anomaly, impact, [supply], [], deadline, statements=[statement], as_of=as_of)
    assert closed["fundamental_standing"] == "支持"


@pytest.mark.phase1_blocking
def test_fingerprint_registers_only_a_medium_market_score():
    from inves_cog.perception.attribution.second_hit import later_matches_fingerprint, prediction_fingerprint

    candidate = {
        "scored": True,
        "score": 0.5,
        "confidence": "中",
        "mechanism": "供给",
        "chain": [{"entity_id": "toshiba"}, {"entity_id": "toshiba"}, {"entity_id": "tdk"}],
        "affected": [
            {"basket_id": "hdd", "ticker": "WDC", "direction": "down"},
            {"ticker": "STX", "direction": "down"},
        ],
        "control_baskets": ["memory"],
    }
    fingerprint = prediction_fingerprint(candidate)
    assert fingerprint == {
        "entities": ["toshiba", "tdk"],
        "baskets": [{"basket_id": "hdd", "direction": "down"}],
        "control_baskets": ["memory"],
        "layer": "市场",
    }
    assert "operating_impact_proven" not in fingerprint
    assert prediction_fingerprint({**candidate, "confidence": "低", "score": 0.8}) is None
    assert prediction_fingerprint({**candidate, "confidence": None, "score": 0.49}) is None
    assert prediction_fingerprint({**candidate, "scored": False, "confidence": "高"}) is None
    start = datetime(2026, 10, 2, 13, 30)
    later = {"published_at": datetime(2026, 10, 6, 9), "entities": ["tdk", "other"]}
    assert later_matches_fingerprint(fingerprint, later, start) is True
    early = {"published_at": datetime(2026, 10, 1, 9), "entities": ["tdk"]}
    assert later_matches_fingerprint(fingerprint, early, start) is False
    unrelated = {"published_at": datetime(2026, 10, 6, 9), "entities": ["cpi"]}
    assert later_matches_fingerprint(fingerprint, unrelated, start) is False
    assert later_matches_fingerprint(None, later, start) is False


@pytest.mark.phase1_blocking
def test_search_budget():
    from inves_cog.perception.attribution.retrieve import supplement_calls

    assert supplement_calls(1, 200) == (0, "补证未执行")
    assert supplement_calls(3, 199) == (1, "补证未执行")
    assert supplement_calls(1, 10) == (1, None)


@pytest.mark.phase1_blocking
def test_supplement_runs_only_below_five_items():
    from inves_cog.perception.attribution.evidence import time_alignment
    from inves_cog.perception.attribution.retrieve import shortlist, stamp_supplement, supplement_plan

    start = datetime(2026, 10, 14, 13, 30)
    now = datetime(2026, 10, 14, 21, 0)
    assert supplement_plan(5, 3, 0, now=now) == {"calls": 0, "note": None, "first_seen_at": None}
    blocked = supplement_plan(4, 3, 200, now=now)
    assert blocked == {"calls": 0, "note": "补证未执行", "first_seen_at": None}
    assert supplement_plan(4, 2, 10, now=now) == {"calls": 2, "note": None, "first_seen_at": now}
    published = start - timedelta(days=6)
    item = stamp_supplement(
        {"info_id": "search-1", "published_at": published, "entities": ["WDC"], "source_root": "search"},
        now,
    )
    assert item["supplement"] is True
    assert time_alignment(item["published_at"], start, now) == 1.0
    assert shortlist([item], ["WDC"], start, now - timedelta(minutes=1)) == []
    visible = shortlist([item], ["WDC"], start, now)
    assert visible[0]["role"] == "background"
    assert visible[0]["info_id"] == "search-1"


@pytest.mark.phase1_blocking
def test_skipped_supplement_is_named_on_the_report():
    from inves_cog.perception.attribution.report import explanation_report
    from inves_cog.perception.attribution.retrieve import supplement_plan

    now = datetime(2026, 10, 14, 21, 0)
    anomaly = {"anomaly_id": "pool-1", "universe": "pool", "direction": "down"}
    impact = {"event": 0.0, "amplification": 0.0, "unexplained": 0.0}
    quiet = explanation_report(anomaly, impact, [], [], supplement=supplement_plan(5, 2, 0, now=now))
    assert quiet["supplement"] is None
    assert "补证未执行" not in quiet["unknowns"]
    assert quiet["type_candidates"] == ["原因未明"]
    blocked = supplement_plan(2, 2, 200, now=now)
    deadline = {
        "lifecycle": "已衰减·无影响",
        "deadline_outcome": "条件风险",
        "closing_reason": "截止日仍未知",
        "unknowns": ["eps_consensus"],
        "operating_impact_proven": False,
    }
    report = explanation_report(anomaly, impact, [], [], deadline, supplement=blocked)
    assert report["supplement"] == "补证未执行"
    assert report["unknowns"] == ["eps_consensus", "补证未执行"]
    assert report["operating_impact_proven"] is False
    assert report["lifecycle"] == "已衰减·无影响"


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

    class Once:
        def __init__(self):
            self.calls = 0

        def call(self, task, payload):
            self.calls += 1
            raise AssertionError(task)

    idle = Once()
    already = attach_claims([{"info_id": "n1", "claims": [], "role": "background"}], idle)
    assert idle.calls == 0
    assert already[0]["role"] == "background"
    assert already[0]["claims"] == []
    with pytest.raises(ValueError, match="40"):
        attach_claims([{"info_id": str(index)} for index in range(41)], idle)
    assert idle.calls == 0


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
    assert report["type_candidates"] == ["原因未明"]


@pytest.mark.phase1_blocking
def test_type_candidates_follow_score_not_case_name():
    from inves_cog.perception.attribution.report import type_candidates

    assert type_candidates([], ("待定",)) == ["待定", "原因未明"]
    narrative = [{"scored": True, "score": 0.8, "mechanism": "估值倍数"}]
    assert type_candidates(narrative) == ["叙事冲击"]
    weak = [{"scored": True, "score": 0.4, "mechanism": "估值倍数"}]
    assert type_candidates(weak) == ["原因未明"]
    supply = [{"scored": True, "score": 0.8, "mechanism": "供给"}]
    assert type_candidates(supply) == []
    assert type_candidates(supply, operating_impact_proven=True) == ["事件冲击"]
    named = {"case_kind": "openai_arr"}
    assert type_candidates([], (named["case_kind"],)) == ["openai_arr", "原因未明"]
    assert "叙事冲击" not in type_candidates([], (named["case_kind"],))


@pytest.mark.phase1_blocking
def test_scope_is_a_relation_label_and_tracking_is_not_evidence():
    from inves_cog.perception.attribution.report import CONSTRAINT_ITEMS, impact_scope, tracking_list
    from inves_cog.perception.attribution.toshiba import midpoint_report

    supply = [{"scored": True, "score": 0.8, "mechanism": "供给", "affected": [{"ticker": "WDC"}]}]
    observed = impact_scope(supply, [{"ticker": "WDC", "exposure": "直接", "status": "观察到"}])
    assert observed[0]["exposure"] == "直接"
    candidate = impact_scope(supply, [{"ticker": "WDC", "exposure": "直接", "status": "候选"}])
    assert candidate[0]["exposure"] == "概念关联"
    assert candidate[0]["reason"] == "候选关系不是经营暴露"
    exited = impact_scope(
        supply, [{"ticker": "WDC", "exposure": "直接", "status": "已确立", "exit_reason": "关系退出"}]
    )
    assert exited[0]["exposure"] == "概念关联"
    assert exited[0]["exit_reason"] == "关系退出"
    bare = impact_scope(supply, [], direction="down")
    assert bare[0]["exposure"] == "纯共振"
    assert bare[0]["direction"] == "down"
    multiple = [
        {"scored": True, "score": 0.8, "mechanism": "估值倍数", "affected": [{"ticker": "MU"}]},
    ]
    theme = impact_scope(multiple, [{"ticker": "MU", "exposure": "直接", "status": "已确立"}])
    assert theme[0]["exposure"] == "概念关联"
    assert theme[0]["reason"] == "估值倍数停在市场层"
    weak = [{"scored": True, "score": 0.4, "mechanism": "供给", "affected": [{"ticker": "WDC"}]}]
    assert impact_scope(weak, [{"ticker": "WDC", "exposure": "直接", "status": "观察到"}]) == []

    tasks = tracking_list(["供给"], {"新增供给占需求增量"}, deadline_on="2026-10-20")
    assert [row["item"] for row in tasks] == list(CONSTRAINT_ITEMS)
    assert all(row["is_evidence"] is False and row["source"] is None for row in tasks)
    assert tasks[0]["status"] == "有数据"
    assert tasks[1]["status"] == "未知"
    assert tracking_list(["竞争"]) == []
    assert tracking_list(["估值倍数"]) == []

    walked = midpoint_report()
    report = walked["report"]
    assert walked["lifecycle"] == "已验证·有影响"
    assert report["type_candidates"] == ["事件冲击"]
    assert report["scope"][0]["ticker"] == "WDC"
    assert report["scope"][0]["exposure"] == "纯共振"
    assert report["valuation"] == "不变 / 待基本面轨道"
    assert [row["item"] for row in report["tracking"]] == list(CONSTRAINT_ITEMS)
    assert all(row["is_evidence"] is False for row in report["tracking"])
    assert report["tracking"][0]["status"] == "有数据"


@pytest.mark.phase1_blocking
def test_constraint_conclusion_does_not_prove_operating_impact():
    from inves_cog.perception.attribution.report import CONSTRAINT_ITEMS, constraint_conclusion, tracking_list
    from inves_cog.perception.attribution.toshiba import midpoint_report

    def concluded(level):
        return [
            {"item": name, "status": "结论", "source": name, "source_level": level, "is_evidence": False}
            for name in CONSTRAINT_ITEMS
        ]

    unclear = constraint_conclusion(tracking_list(["供给"], {"新增供给占需求增量"}))
    assert unclear["label"] == "约束不清但有上下界"
    assert unclear["has_bounds"] is False
    assert unclear["operating_impact_proven"] is False
    assert unclear["closes_case"] is False
    bounded = tracking_list(["需求"])
    bounded[0]["bounds"] = True
    assert constraint_conclusion(bounded)["has_bounds"] is True
    assert constraint_conclusion(bounded)["label"] == "约束不清但有上下界"

    rows = concluded(1)
    assert constraint_conclusion(rows)["label"] == "约束不清但有上下界"
    assert constraint_conclusion(rows, impact="有限")["label"] == "可计算且冲击有限"
    material = constraint_conclusion(rows, impact="实质")
    assert material == {
        "label": "可计算且冲击实质",
        "has_bounds": False,
        "operating_impact_proven": False,
        "closes_case": False,
    }
    assert constraint_conclusion(concluded(4), impact="实质")["label"] == "约束不清但有上下界"
    conflict = concluded(1)
    conflict[0]["conflict"] = True
    assert constraint_conclusion(conflict, impact="实质")["label"] == "关键约束冲突"
    reprint = concluded(4)
    reprint[0]["conflict"] = True
    assert constraint_conclusion(reprint, impact="实质")["label"] == "约束不清但有上下界"
    assert constraint_conclusion([]) is None

    walked = midpoint_report()
    conclusion = walked["report"]["constraint_conclusion"]
    assert walked["lifecycle"] == "已验证·有影响"
    assert walked["report"]["operating_impact_proven"] is True
    assert conclusion["label"] == "约束不清但有上下界"
    assert conclusion["operating_impact_proven"] is False
    assert conclusion["closes_case"] is False
    assert "关键约束冲突" not in walked["report"]["type_candidates"]


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
def test_ticker_codes_follow_the_scored_candidate():
    from inves_cog.perception.attribution.codes import ticker_codes
    from inves_cog.perception.attribution.report import explanation_report

    supply = {"scored": True, "score": 0.8, "mechanism": "供给", "affected": [{"ticker": "WDC"}]}
    multiple = {"scored": True, "score": 0.8, "mechanism": "估值倍数", "affected": [{"ticker": "MU"}]}
    weak = {"scored": True, "score": 0.4, "mechanism": "估值倍数", "affected": [{"ticker": "MU"}]}
    pool = {"anomaly_id": "pool-1", "universe": "pool", "members": ["WDC", "MU"]}
    wide = {"anomaly_id": "wide-1", "universe": "wide", "members": ["WDC"]}
    assert ticker_codes(wide, [supply], narrative_shock=True, fundamental_unchanged=True) == []
    assert ticker_codes(pool, [weak]) == [
        {"ticker": "WDC", "n_code": "N6", "mechanism": None},
        {"ticker": "MU", "n_code": "N6", "mechanism": None},
    ]
    assert ticker_codes(pool, [supply]) == []
    assert ticker_codes(pool, [supply], narrative_shock=True, fundamental_unchanged=False) == []
    narrative = ticker_codes(pool, [supply], narrative_shock=True, fundamental_unchanged=True)
    assert narrative == [{"ticker": "WDC", "n_code": "N1", "mechanism": "供给"}]
    both = ticker_codes(pool, [multiple, supply], narrative_shock=True, fundamental_unchanged=True)
    assert both == [
        {"ticker": "MU", "n_code": "N2", "mechanism": "估值倍数"},
        {"ticker": "WDC", "n_code": "N1", "mechanism": "供给"},
    ]
    report = explanation_report(pool, {"event": 0.0, "amplification": 0.0, "unexplained": 0.0}, [multiple], [])
    assert report["ticker_status"] == [{"ticker": "MU", "n_code": "N2", "mechanism": "估值倍数"}]


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


@pytest.mark.phase1_blocking
def test_backfill_leads_do_not_close_m7_case_days():
    from inves_cog.perception.attribution.cases import muse_chart, openai_cover, openai_labels, r1_or_store
    from inves_cog.perception.attribution.manual import attach_backfill

    payload = json.loads((ROOT / "tests/fixtures/phase1/m8/manual_leads_2026-10-16.json").read_text())
    leads = {row["kind"]: row for row in payload["leads"]}
    read_on = payload["read_on"]
    paired = {
        "r1_release": ("2025-01-20", "2025-01-20:close:001"),
        "openai_arr": ("2026-10-14", "2026-10-14:close:001"),
        "muse_rank": ("2026-09-21", "2026-09-21:close:001"),
    }
    for kind, (day, anomaly_id) in paired.items():
        lead = leads[kind]
        attached = attach_backfill(
            {"anomaly_id": anomaly_id, "trade_date": datetime.fromisoformat(day + "T21:00:00")},
            lead,
            read_on,
        )
        assert attached["mode"] == "后补录历史复盘"
        assert attached["collected_then"] is False
        assert attached["vectors_then"] is False
        assert attached["aligned"] is True
        assert attached["gap"]
        assert attached["case_clause_met"] is False
    revenue = leads["openai_arr"]
    assert openai_cover([{"labels": openai_labels(revenue["excerpt"])}]) is False
    assert muse_chart(leads["muse_rank"]["excerpt"]) is True
    assert r1_or_store(leads["r1_release"]["excerpt"]) is True
    crossed = attach_backfill(
        {"anomaly_id": "2026-10-14:close:001", "trade_date": "2026-10-14"},
        leads["muse_rank"],
        read_on,
    )
    assert crossed["aligned"] is False
    assert crossed["case_clause_met"] is False


@pytest.mark.phase1_blocking
def test_historical_case_mode_does_not_open_production_path():
    from inves_cog.perception.attribution.manual import historical_case, production_visible

    payload = json.loads((ROOT / "tests/fixtures/phase1/m8/manual_leads_2026-10-16.json").read_text())
    assert payload["evidence_mode"] == "后补录历史案例"
    assert payload["closes_ac_m8_06"] is False
    leads = {row["kind"]: row for row in payload["leads"]}
    read_on = payload["read_on"]
    release = historical_case(leads["r1_release"], "2025-01-20", read_on)
    revenue = historical_case(leads["openai_arr"], "2026-10-14", read_on)
    muse = historical_case(leads["muse_rank"], "2026-09-21", read_on)
    assert release["usable"] is True and release["role"] == "发布"
    assert revenue["usable"] is True and revenue["role"] == "背景"
    assert muse["usable"] is True and muse["role"] == "背景"
    assert "72" in muse["uncertainty"]
    for row in (release, revenue, muse):
        assert row["collected_then"] is False
        assert row["vectors_then"] is False
        assert row["closes_case"] is False
        assert row["closes_ac_m8_06"] is False
    late = {**leads["openai_arr"], "published_on": "2026-10-20", "updated_on": "2026-10-20"}
    assert historical_case(late, "2026-10-14", read_on)["usable"] is False
    as_of = datetime(2026, 10, 14, 21, 0)
    item = {
        "info_id": leads["openai_arr"]["id"],
        "published_at": datetime(2026, 10, 8, 17, 12),
        "first_seen_at": datetime(2026, 10, 16, 12, 0),
    }
    assert production_visible([item], as_of) == []
    with pytest.raises(ValueError, match="案例模式"):
        production_visible([item], as_of, mode="后补录历史案例")


@pytest.mark.phase1_blocking
def test_historical_case_report_keeps_citations_and_lists_gaps(tmp_path):
    from inves_cog.llm.client import Client, LLMUnavailable
    from inves_cog.perception.attribution.historical import historical_report, retrieval_items

    payload = json.loads((ROOT / "tests/fixtures/phase1/m8/manual_leads_2026-10-16.json").read_text())
    leads = payload["leads"]
    by_kind = {row["kind"]: row for row in leads}
    read_on = payload["read_on"]
    visible = {row["info_id"] for row in retrieval_items(leads, "2026-10-14", read_on)}
    assert by_kind["openai_arr"]["id"] in visible
    late = {**by_kind["openai_arr"], "id": "after-cutoff", "published_on": "2026-10-20", "updated_on": "2026-10-20"}
    assert retrieval_items([late], "2026-10-14", read_on) == []

    class Stub:
        def __init__(self):
            self.calls = 0

        def call(self, task, body):
            self.calls += 1
            assert task == "anomaly_candidates"
            return {
                "candidates": [
                    {"mechanism": "估值倍数", "info_ids": ["missing-id"], "affected": []},
                    {"mechanism": "需求", "info_ids": [by_kind["openai_arr"]["id"]], "affected": []},
                ]
            }

    client = Stub()
    anomaly = {
        "anomaly_id": "2026-10-14:close:001",
        "universe": "pool",
        "trade_date": "2026-10-14",
        "case_kind": "openai_arr",
        "members": [{"ticker": "NVDA"}],
        "baskets": ["OpenAI合作方"],
    }
    report = historical_report(anomaly, leads, read_on, client)
    assert client.calls == 1
    assert report["closes_case"] is False
    assert report["closes_ac_m8_06"] is False
    assert report["collected_then"] is False
    assert report["missing"] == ["前 4 名未含至少 3 类"]
    assert [row["info_ids"] for row in report["candidates"] if row["scored"]] == [[by_kind["openai_arr"]["id"]]]
    release = {
        "anomaly_id": "2025-01-20:close:001",
        "universe": "pool",
        "trade_date": "2025-01-20",
        "case_kind": "r1_release",
        "members": [{"ticker": "NVDA"}],
        "baskets": ["软件"],
    }

    class Cite:
        def call(self, task, body):
            return {"candidates": [{"mechanism": "竞争", "info_ids": [by_kind["r1_release"]["id"]], "affected": []}]}

    release_report = historical_report(release, leads, read_on, Cite())
    assert release_report["closes_case"] is False
    assert "候选未连接加速芯片范围" in release_report["missing"]
    toshiba = {
        "anomaly_id": "2026-10-02:close:001",
        "universe": "pool",
        "trade_date": "2026-10-02",
        "case_kind": "toshiba",
        "members": [{"ticker": "WDC"}],
        "baskets": ["HDD"],
    }
    quiet = Stub()
    assert historical_report(toshiba, [], read_on, quiet)["missing"] == ["日经扩产原文未冻结"]
    assert quiet.calls == 0
    with pytest.raises(LLMUnavailable, match="待分析"):
        historical_report(anomaly, leads, read_on, Client(recordings=tmp_path))


@pytest.mark.phase1_blocking
def test_export_headlines_fill_known_categories_without_live_visibility():
    from inves_cog.perception.attribution.cases import openai_labels
    from inves_cog.perception.attribution.historical import headline_lead, historical_report, retrieval_items
    from inves_cog.perception.attribution.manual import production_visible

    payload = json.loads((ROOT / "tests/fixtures/phase1/m8/export_headlines.json").read_text())
    assert payload["evidence_mode"] == "后补录历史案例"
    assert payload["closes_ac_m8_06"] is False
    rows = payload["items"]
    leads = [headline_lead(row) for row in rows]
    by_kind = {}
    for row in rows:
        by_kind.setdefault(row["kind"], row["info_id"])
    early = {item["info_id"] for item in retrieval_items(leads, "2026-10-02", "2026-10-16")}
    assert by_kind["toshiba_supply"] in early
    assert by_kind["tdk_second_hit"] not in early
    later = {item["info_id"] for item in retrieval_items(leads, "2026-10-14", "2026-10-16")}
    assert {by_kind["coreweave_debt"], by_kind["barclays_downgrade"], by_kind["cpi_hot"]} <= later
    assert all(item["source_level"] == 4 for item in retrieval_items(leads, "2026-10-14", "2026-10-16"))
    headlines = {row["kind"]: row["headline"] for row in rows}
    assert openai_labels(headlines["coreweave_debt"]) == {"coreweave_debt"}
    assert openai_labels(headlines["barclays_downgrade"]) == {"barclays_downgrade"}
    assert openai_labels(headlines["cpi_hot"]) == {"cpi_hot"}

    morning = datetime.fromisoformat("2026-10-15T09:15:00+08:00")
    seen = production_visible(
        [
            {
                "info_id": row["info_id"],
                "published_at": datetime.fromisoformat(row["published_at"]),
                "first_seen_at": datetime.fromisoformat(row["first_seen_at"]),
            }
            for row in rows
            if row["kind"] in {"coreweave_debt", "barclays_downgrade", "cpi_hot"}
        ],
        morning,
    )
    assert {row["info_id"] for row in seen} == {by_kind["coreweave_debt"]}

    class Cite:
        def __init__(self, ids, mechanism="估值倍数"):
            self.ids = ids
            self.mechanism = mechanism

        def call(self, task, body):
            return {"candidates": [{"mechanism": self.mechanism, "info_ids": self.ids, "affected": []}]}

    opened = {
        "anomaly_id": "2026-10-14:close:001",
        "universe": "pool",
        "trade_date": "2026-10-14",
        "case_kind": "openai_arr",
        "members": [{"ticker": "NVDA"}],
        "baskets": ["OpenAI合作方"],
    }
    report = historical_report(
        opened,
        leads,
        "2026-10-16",
        Cite([by_kind["coreweave_debt"], by_kind["barclays_downgrade"], by_kind["cpi_hot"]]),
    )
    assert report["missing"] == []
    assert report["closes_case"] is False
    assert report["closes_ac_m8_06"] is False
    assert report["collected_then"] is False
    disk = {
        "anomaly_id": "2026-10-02:close:001",
        "universe": "pool",
        "trade_date": "2026-10-02",
        "case_kind": "toshiba",
        "members": [{"ticker": "WDC"}],
        "baskets": ["HDD"],
    }
    multiple = historical_report(disk, leads, "2026-10-16", Cite([by_kind["toshiba_supply"]]))
    assert multiple["closes_case"] is False
    assert multiple["missing"] == ["机制不是供给"]
    toshiba = historical_report(disk, leads, "2026-10-16", Cite([by_kind["toshiba_supply"]], "供给"))
    assert toshiba["missing"] == []
    assert toshiba["closes_case"] is False
    assert toshiba["closes_ac_m8_06"] is False
    assert toshiba["collected_then"] is False


@pytest.mark.phase1_blocking
def test_candidate_capture_path_is_the_recording_file(tmp_path):
    from inves_cog.llm.client import Client, LLMUnavailable
    from inves_cog.perception.attribution.historical import candidate_capture, historical_report

    payload = json.loads((ROOT / "tests/fixtures/phase1/m8/export_headlines.json").read_text())
    leads = [
        {
            "id": row["info_id"],
            "kind": row["kind"],
            "case_id": row["case_id"],
            "published_on": row["published_at"][:10],
            "excerpt": row["headline"],
            "source_level": row["source_level"],
        }
        for row in payload["items"]
        if row["kind"] in {"coreweave_debt", "barclays_downgrade", "cpi_hot"}
    ]
    anomaly = {
        "anomaly_id": "2026-10-14:close:001",
        "universe": "pool",
        "trade_date": "2026-10-14",
        "case_kind": "openai_arr",
        "members": [{"ticker": "NVDA"}],
        "baskets": ["OpenAI合作方"],
    }
    path = candidate_capture(anomaly, leads, "2026-10-16", tmp_path)
    assert path.parent == tmp_path / "anomaly_candidates"
    with pytest.raises(LLMUnavailable, match="待分析"):
        historical_report(anomaly, leads, "2026-10-16", Client(recordings=tmp_path))
    cited = [row["id"] for row in leads if row["kind"] != "barclays_downgrade" or "Dell" in row["excerpt"]]
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "task": "anomaly_candidates",
                "payload_sha256": path.stem,
                "result": {"candidates": [{"mechanism": "估值倍数", "info_ids": cited[:3], "affected": []}]},
            }
        ),
        encoding="utf-8",
    )
    report = historical_report(anomaly, leads, "2026-10-16", Client(recordings=tmp_path))
    assert report["closes_ac_m8_06"] is False
    assert report["collected_then"] is False
    assert report["evidence_mode"] == "后补录历史案例"


@pytest.mark.phase1_blocking
def test_tdk_headline_is_eligible_but_untested_without_a_response():
    from inves_cog.perception.attribution.manual import production_visible
    from inves_cog.perception.attribution.second_hit import later_event

    payload = json.loads((ROOT / "tests/fixtures/phase1/m8/export_headlines.json").read_text())
    row = next(item for item in payload["items"] if item["kind"] == "tdk_second_hit")
    published = datetime.fromisoformat(row["published_at"])
    start = datetime.fromisoformat("2026-10-02T21:30:00+08:00")
    alone = later_event(published, start, source_root=row["info_id"])
    assert alone == {"eligible": True, "conclusion": "未检验"}
    measured = later_event(published, start, source_root=row["info_id"], outcome="命中")
    assert measured == {"eligible": True, "conclusion": "确认"}
    after = datetime.fromisoformat("2026-10-06T23:00:00+08:00")
    assert later_event(published, after, source_root=row["info_id"], outcome="命中")["eligible"] is False
    visible = production_visible(
        [
            {
                "info_id": row["info_id"],
                "published_at": published,
                "first_seen_at": datetime.fromisoformat(row["first_seen_at"]),
            }
        ],
        after,
    )
    assert visible == []


@pytest.mark.phase1_cases
def test_r1_accelerator_basket_still_needs_a_recording(tmp_path):
    from datetime import date

    from inves_cog.llm.client import Client, LLMUnavailable
    from inves_cog.perception.anomaly.cases import case_anomalies
    from inves_cog.perception.anomaly.replay import _identify
    from inves_cog.perception.attribution.historical import historical_report

    day = date.fromisoformat("2025-01-27")
    fixture = ROOT / "tests/fixtures/phase1/m7"
    rows = _identify(day, case_anomalies(fixture, "case_20250127_bars.jsonl.gz", day.isoformat()))
    found = next(
        row
        for row in rows
        if "加速" in " ".join(row["baskets"])
        and row["direction"] == "down"
        and any(member["ticker"] == "NVDA" for member in row["members"])
    )
    anomaly = {**found, "case_kind": "r1_release"}
    payload = json.loads((ROOT / "tests/fixtures/phase1/m8/manual_leads_2026-10-16.json").read_text())
    leads = payload["leads"]
    read_on = payload["read_on"]
    with pytest.raises(LLMUnavailable, match="待分析"):
        historical_report(anomaly, leads, read_on, Client(recordings=tmp_path))

    class Cite:
        def call(self, task, body):
            assert task == "anomaly_candidates"
            ids = [item["info_id"] for item in body["items"]]
            assert ids == ["manual-r1-2025-01-20"]
            return {"candidates": [{"mechanism": "竞争", "info_ids": ids, "affected": [{"ticker": "NVDA"}]}]}

    report = historical_report(anomaly, leads, read_on, Cite())
    assert "候选未连接加速芯片范围" not in report["missing"]
    assert report["missing"] == []
    assert report["closes_case"] is False
    assert report["closes_ac_m8_06"] is False
    assert report["collected_then"] is False
    assert report["vectors_then"] is False
    assert report["evidence_mode"] == "后补录历史案例"
    assert report["sources"] == ["manual-r1-2025-01-20"]


@pytest.mark.phase1_cases
def test_muse_case_keeps_the_september_18_date(tmp_path):
    from datetime import date

    from inves_cog.llm.client import Client, LLMUnavailable
    from inves_cog.perception.anomaly.cases import case_anomalies
    from inves_cog.perception.anomaly.replay import _identify
    from inves_cog.perception.attribution.historical import historical_report

    day = date.fromisoformat("2026-09-21")
    fixture = ROOT / "tests/fixtures/phase1/m7"
    rows = _identify(day, case_anomalies(fixture, "meta_bars.jsonl.gz", day.isoformat()))
    cpu = next(row for row in rows if "CPU" in " ".join(row["baskets"]) and row["universe"] == "pool")
    meta = next(
        row
        for row in rows
        if any(member["ticker"] == "META" for member in row["members"]) and row["severity"] == "alert"
    )
    payload = json.loads((ROOT / "tests/fixtures/phase1/m8/manual_leads_2026-10-16.json").read_text())
    leads = payload["leads"]
    read_on = payload["read_on"]
    quiet = {**meta, "case_kind": "muse_rank"}
    with pytest.raises(LLMUnavailable, match="待分析"):
        historical_report(quiet, leads, read_on, Client(recordings=tmp_path))

    class Cite:
        def call(self, task, body):
            assert task == "anomaly_candidates"
            items = body["items"]
            assert [item["info_id"] for item in items] == [
                "manual-r1-2025-01-20",
                "manual-axios-muse-2026-09-18",
            ]
            chart = items[1]
            assert chart["published_at"] == "2026-09-18"
            assert chart["role"] == "背景"
            return {
                "candidates": [{"mechanism": "需求", "info_ids": [chart["info_id"]], "affected": [{"ticker": "META"}]}]
            }

    for found in (cpu, meta):
        report = historical_report({**found, "case_kind": "muse_rank"}, leads, read_on, Cite())
        assert report["missing"] == []
        assert "受影响范围未含 CPU 或 META" not in report["missing"]
        assert report["closes_case"] is False
        assert report["closes_ac_m8_06"] is False
        assert report["collected_then"] is False
        assert report["sources"] == ["manual-r1-2025-01-20", "manual-axios-muse-2026-09-18"]


@pytest.mark.phase1_cases
def test_toshiba_reprint_is_not_operating_evidence(tmp_path):
    from datetime import date

    from inves_cog.llm.client import Client, LLMUnavailable
    from inves_cog.perception.anomaly.cases import case_anomalies
    from inves_cog.perception.anomaly.replay import _identify
    from inves_cog.perception.attribution.historical import headline_lead, historical_report, retrieval_items
    from inves_cog.perception.attribution.operating import operating_verdict
    from inves_cog.perception.attribution.second_hit import later_event

    day = date.fromisoformat("2026-10-02")
    fixture = ROOT / "tests/fixtures/phase1/m7"
    rows = _identify(day, case_anomalies(fixture, "toshiba_bars.jsonl.gz", day.isoformat()))
    found = next(row for row in rows if "HDD" in " ".join(row["baskets"]) and row["universe"] == "pool")
    members = {member["ticker"] for member in found["members"]}
    assert members == {"STX", "WDC"}
    anomaly = {**found, "case_kind": "toshiba"}
    payload = json.loads((ROOT / "tests/fixtures/phase1/m8/export_headlines.json").read_text())
    leads = [headline_lead(row) for row in payload["items"]]
    by_kind = {row["kind"]: row for row in payload["items"]}
    visible = retrieval_items(leads, day.isoformat(), "2026-10-16")
    assert [item["info_id"] for item in visible] == [by_kind["toshiba_supply"]["info_id"]]
    assert visible[0]["source_level"] == 4
    with pytest.raises(LLMUnavailable, match="待分析"):
        historical_report(anomaly, leads, "2026-10-16", Client(recordings=tmp_path))

    class Cite:
        def call(self, task, body):
            assert task == "anomaly_candidates"
            assert [item["info_id"] for item in body["items"]] == [by_kind["toshiba_supply"]["info_id"]]
            return {
                "candidates": [
                    {
                        "mechanism": "供给",
                        "info_ids": [by_kind["toshiba_supply"]["info_id"]],
                        "affected": [{"ticker": "WDC"}, {"ticker": "MU"}],
                    }
                ]
            }

    report = historical_report(anomaly, leads, "2026-10-16", Cite())
    assert report["missing"] == []
    assert report["closes_case"] is False
    assert report["closes_ac_m8_06"] is False
    assert report["collected_then"] is False
    assert report["candidates"][0]["affected"] == [{"ticker": "WDC"}]
    supply = by_kind["toshiba_supply"]
    verdict = operating_verdict(
        [
            {
                "kind": "company_primary",
                "source_level": supply["source_level"],
                "citation": supply["headline"],
                "form": "8-K",
                "guidance_change": True,
                "direction": "down",
                "published_at": datetime.fromisoformat(supply["published_at"]),
                "first_seen_at": datetime.fromisoformat(supply["first_seen_at"]),
            }
        ],
        as_of=datetime.fromisoformat(supply["first_seen_at"]),
        expected_direction="down",
    )
    assert verdict.outcome != "支持"
    published = datetime.fromisoformat(by_kind["tdk_second_hit"]["published_at"])
    start = datetime.fromisoformat("2026-10-02T21:30:00+08:00")
    assert later_event(published, start, source_root=by_kind["tdk_second_hit"]["info_id"]) == {
        "eligible": True,
        "conclusion": "未检验",
    }


def _cite(rows):
    class Cite:
        def call(self, task, body):
            assert task == "anomaly_candidates"
            return {"candidates": rows}

    return Cite()


@pytest.mark.phase1_blocking
def test_muse_open_uses_the_cited_date_interval():
    from inves_cog.perception.attribution.historical import historical_report
    from inves_cog.perception.attribution.manual import open_relation

    assert open_relation("2026-09-18", "2026-09-21") == "早于开盘"
    assert open_relation("2026-09-21", "2026-09-21") == "未知"
    assert open_relation("2026-09-23", "2026-09-21") == "晚于开盘"
    anomaly = {
        "anomaly_id": "2026-09-21:close:001",
        "universe": "pool",
        "trade_date": "2026-09-21",
        "case_kind": "muse_rank",
        "members": [{"ticker": "META"}],
        "baskets": ["CPU"],
    }
    axios = {
        "id": "axios",
        "kind": "muse_rank",
        "case_id": "muse-2026-09-21",
        "published_on": "2026-09-18",
        "published_precision": "date",
        "before_open": False,
        "source_root": "axios",
        "excerpt": "Dated Sep 18, 2026. Muse is the No. 1 free iPhone app in America.",
    }
    same_day = {
        **axios,
        "id": "same-day",
        "published_on": "2026-09-21",
        "published_precision": "minute",
        "before_open": True,
    }
    cited = historical_report(
        anomaly,
        [axios, same_day],
        "2026-10-16",
        _cite(
            [
                {"mechanism": "需求", "info_ids": ["axios"], "affected": [{"ticker": "META"}]},
            ]
        ),
    )
    assert cited["missing"] == []
    assert cited["closes_case"] is False
    unknown = historical_report(
        anomaly,
        [axios, same_day],
        "2026-10-16",
        _cite(
            [
                {"mechanism": "需求", "info_ids": ["same-day"], "affected": [{"ticker": "META"}]},
            ]
        ),
    )
    assert unknown["missing"] == ["不能证明早于开盘"]
    assert unknown["closes_case"] is False


@pytest.mark.phase1_blocking
def test_r1_citation_must_name_the_release():
    from inves_cog.perception.attribution.historical import historical_report

    anomaly = {
        "anomaly_id": "2025-01-27:close:001",
        "universe": "pool",
        "trade_date": "2025-01-27",
        "case_kind": "r1_release",
        "members": [{"ticker": "NVDA"}],
        "baskets": ["AI加速芯片"],
    }
    release = {
        "id": "release",
        "kind": "r1_release",
        "case_id": "r1-release-2025-01-20",
        "published_on": "2025-01-20",
        "published_precision": "date",
        "source_root": "official-site",
        "excerpt": "The page says DeepSeek R1 was released that day.",
    }
    other = {
        "id": "unrelated-cpi",
        "kind": "cpi_hot",
        "case_id": "other",
        "published_on": "2025-01-20",
        "published_precision": "date",
        "excerpt": "CPI 3.7% vs 3.6%.",
    }
    leads = [release, other]
    noise = {"mechanism": "竞争", "info_ids": ["unrelated-cpi"], "affected": [{"ticker": "NVDA"}]}
    unrelated = historical_report(anomaly, leads, "2026-10-16", _cite([noise]))
    assert "候选未引用发布材料" in unrelated["missing"]
    assert unrelated["closes_case"] is False
    unlinked = historical_report(
        anomaly,
        leads,
        "2026-10-16",
        _cite(
            [
                {"mechanism": "竞争", "info_ids": ["release"], "affected": []},
            ]
        ),
    )
    assert unlinked["missing"] == ["候选未连接加速芯片范围"]
    fourth = historical_report(
        anomaly,
        leads,
        "2026-10-16",
        _cite(
            [
                noise,
                noise,
                noise,
                {
                    "mechanism": "竞争",
                    "info_ids": ["release"],
                    "affected": [{"ticker": "NVDA"}],
                },
            ]
        ),
    )
    assert "候选未引用发布材料" in fourth["missing"]
    linked = historical_report(
        anomaly,
        leads,
        "2026-10-16",
        _cite(
            [
                {"mechanism": "竞争", "info_ids": ["release"], "affected": [{"ticker": "NVDA"}]},
            ]
        ),
    )
    assert linked["missing"] == []
    assert linked["closes_case"] is False


@pytest.mark.phase1_blocking
def test_openai_rank_counts_candidates_not_citations():
    from inves_cog.perception.attribution.historical import historical_report

    anomaly = {
        "anomaly_id": "2026-10-14:close:001",
        "universe": "pool",
        "trade_date": "2026-10-14",
        "case_kind": "openai_arr",
        "members": [{"ticker": "NVDA"}],
        "baskets": ["OpenAI合作方"],
    }

    def lead(info_id, kind, excerpt):
        return {
            "id": info_id,
            "kind": kind,
            "case_id": "openai-2026-10-14",
            "published_on": "2026-10-14",
            "published_precision": "minute",
            "excerpt": excerpt,
            "source_level": 4,
        }

    cores = [lead(f"cw-{index}", "coreweave_debt", "CoreWeave bond yield hits 15%") for index in range(5)]
    barclays = lead("bar", "barclays_downgrade", "Barclays downgrades Dell to Equal-Weight")
    prices = lead("cpi", "cpi_hot", "CPI 3.7% vs 3.6%")
    leads = [*cores, barclays, prices]
    covered = historical_report(
        anomaly,
        leads,
        "2026-10-16",
        _cite(
            [
                {"mechanism": "估值倍数", "info_ids": [row["id"] for row in cores], "affected": []},
                {"mechanism": "估值倍数", "info_ids": ["bar"], "affected": []},
                {"mechanism": "估值倍数", "info_ids": ["cpi"], "affected": []},
            ]
        ),
    )
    assert covered["missing"] == []
    assert covered["closes_case"] is False
    fillers = [{"mechanism": "估值倍数", "info_ids": [f"cw-{index}"], "affected": []} for index in range(4)]
    fillers.append({"mechanism": "估值倍数", "info_ids": ["bar", "cpi"], "affected": []})
    parked = historical_report(anomaly, leads, "2026-10-16", _cite(fillers))
    assert parked["missing"] == ["前 4 名未含至少 3 类"]
    assert parked["closes_case"] is False


@pytest.mark.phase1_blocking
def test_claim_capture_is_separate_from_the_candidate_file(tmp_path):
    from inves_cog.llm.client import Client, LLMUnavailable
    from inves_cog.perception.attribution.claims import attach_claims
    from inves_cog.perception.attribution.historical import candidate_capture, claim_capture, retrieval_items

    anomaly = {
        "anomaly_id": "2026-10-14:close:001",
        "universe": "pool",
        "trade_date": "2026-10-14",
        "case_kind": "openai_arr",
    }
    lead = {
        "id": "note",
        "kind": "cpi_hot",
        "case_id": "openai-2026-10-14",
        "published_on": "2026-10-14",
        "published_precision": "minute",
        "excerpt": "CPI 3.7% vs 3.6%.",
        "source_level": 4,
    }
    claim = claim_capture(anomaly, [lead], "2026-10-16", tmp_path)
    candidate = candidate_capture(anomaly, [lead], "2026-10-16", tmp_path)
    assert claim.parent == tmp_path / "claim_extraction"
    assert candidate.parent == tmp_path / "anomaly_candidates"
    assert claim != candidate
    assert not claim.exists()
    assert not candidate.exists()
    items = retrieval_items([lead], anomaly["trade_date"], "2026-10-16")
    with pytest.raises(LLMUnavailable, match="抽取失败"):
        attach_claims(items, Client(recordings=tmp_path))
    late = {**lead, "id": "late", "published_on": "2026-10-20"}
    assert claim_capture(anomaly, [late], "2026-10-16", tmp_path) is None


@pytest.mark.phase1_cases
def test_case_capture_plan_prints_paths_without_calling(tmp_path, capsys):
    from inves_cog.llm.client import Client, LLMUnavailable
    from inves_cog.perception.attribution.capture_plan import case_bundles, main
    from inves_cog.perception.attribution.historical import historical_report

    fixture = ROOT / "tests/fixtures/phase1"
    assert main(["--fixture", str(fixture), "--root", str(tmp_path)]) == 0
    plans = json.loads(capsys.readouterr().out)
    by_kind = {}
    for row in plans:
        by_kind.setdefault(row["case_kind"], []).append(row)
        assert row["closes_case"] is False
        assert row["closes_ac_m8_06"] is False
        assert row["collected_then"] is False
        assert row["evidence_mode"] == "后补录历史案例"
        recording = Path(row["recording"])
        claim = Path(row["claim_recording"])
        assert recording.parent == tmp_path / "anomaly_candidates"
        assert claim.parent == tmp_path / "claim_extraction"
        assert claim != recording
        assert not recording.exists()
        assert not claim.exists()
    assert set(by_kind) == {"r1_release", "muse_rank", "toshiba", "openai_arr"}
    assert by_kind["r1_release"][0]["sources"] == ["manual-r1-2025-01-20"]
    muse_sources = {tuple(row["sources"]) for row in by_kind["muse_rank"]}
    assert muse_sources == {("manual-axios-muse-2026-09-18",)}
    assert by_kind["toshiba"][0]["sources"] == ["news:benzinga:62130092"]
    opened = set(by_kind["openai_arr"][0]["sources"])
    assert "manual-reuters-arr-2026-10-08" in opened
    assert "news:benzinga:62345955" in opened
    assert "news:benzinga:62350981" in opened
    assert "news:benzinga:62194029" not in opened
    bundle = next(row for row in case_bundles(fixture) if row["case_kind"] == "r1_release")
    with pytest.raises(LLMUnavailable, match="待分析"):
        historical_report(bundle["anomaly"], bundle["leads"], bundle["read_on"], Client(recordings=tmp_path))
