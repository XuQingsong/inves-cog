"""Synthetic Toshiba walk to a deadline. This is not frozen news and not a live model call."""

from datetime import datetime

from inves_cog.perception.attribution.candidates import market_confirmed, validate_candidates, verified_from_evidence
from inves_cog.perception.attribution.codes import n_code
from inves_cog.perception.attribution.evidence import evidence_score, time_alignment
from inves_cog.perception.attribution.impact import decompose
from inves_cog.perception.attribution.lifecycle import transition
from inves_cog.perception.attribution.operating import operating_verdict
from inves_cog.perception.attribution.report import CONSTRAINT_ITEMS, explanation_report
from inves_cog.perception.attribution.second_hit import classify_response, second_hit_conclusion
from inves_cog.perception.attribution.tracks import apply_deadline, capital_state, deadline_offset

SUPPLY_CHECKS = CONSTRAINT_ITEMS
NIKKEI = "nikkei-hdd"
TDK = "tdk-heads"


def supply_constraints(known):
    return [{"item": name, "status": "有数据" if name in known else "未知"} for name in SUPPLY_CHECKS]


def midpoint_report():
    start = datetime(2026, 10, 2, 13, 30)
    end = datetime(2026, 10, 2, 20, 0)
    nikkei_at = datetime(2026, 10, 1, 12, 0)
    tdk_at = datetime(2026, 10, 6, 14, 0)
    anomaly = {
        "anomaly_id": "toshiba-2026-10-02",
        "universe": "pool",
        "trade_date": "2026-10-02",
        "direction": "down",
        "baskets": ["hdd"],
        "members": ["WDC"],
    }
    retrieved = {NIKKEI, TDK}
    proposal = {
        "mechanism": "供给",
        "info_ids": [NIKKEI],
        "affected": [{"ticker": "WDC"}],
        "chain": [{"entity_id": "toshiba"}],
    }
    candidates = validate_candidates([proposal], retrieved, {"WDC"})
    scored = candidates[0]
    scored["evidence"] = evidence_score(
        {
            "time": time_alignment(nikkei_at, start, end),
            "gradient": 0.8,
            "specificity": 0.7,
            "narrative": 0.6,
            "magnitude": 0.6,
            "alternatives": 0.8,
        }
    )
    scored["score"] = scored["evidence"]["total"]
    impact = decompose(-0.05, 1_500_000_000, 15, 1_000_000_000_000, "部分相容", 1, 4)
    state, history = transition(None, "已发现", [], when="2026-10-02T13:30:00Z", trigger="异常", evidence_ids=[])
    state, history = transition(
        state, "假设中", history, when="2026-10-02T13:40:00Z", trigger="证据分达到假设", evidence_ids=[NIKKEI]
    )
    confirmed = market_confirmed(claim_time=True, response=True, independent=True, alternative=0.8)
    if confirmed and scored["mechanism"] == "供给":
        state, history = transition(
            state, "市场确认", history, when="2026-10-02T20:00:00Z", trigger="四项同时成立", evidence_ids=[NIKKEI]
        )
        state, history = transition(
            state,
            "基本面核查中",
            history,
            when="2026-10-02T20:05:00Z",
            trigger="供给机制进入核查",
            evidence_ids=[NIKKEI],
            mechanism="供给",
        )
    checks = supply_constraints({"新增供给占需求增量"})
    unknowns = [row["item"] for row in checks if row["status"] == "未知"]
    as_of = datetime(2026, 10, 20, 13, 30)
    filing = {
        "kind": "company_primary",
        "info_id": "synthetic-8k-guidance",
        "source_level": 1,
        "source_root": "sec",
        "citation": "synthetic 8-K accession 0000000000-26-000001",
        "form": "8-K",
        "guidance_change": True,
        "direction": "down",
        "published_at": datetime(2026, 10, 20, 12, 0),
        "first_seen_at": datetime(2026, 10, 20, 12, 0),
        "fixture": "synthetic",
    }
    verdict = operating_verdict([filing], as_of=as_of, expected_direction="down", unknowns=unknowns)
    deadline = apply_deadline(verdict)
    if verdict.outcome == "支持" and deadline["lifecycle"] == "已验证·有影响":
        state, history = transition(
            state,
            "已验证·有影响",
            history,
            when="2026-10-20T13:30:00Z",
            trigger=deadline["closing_reason"],
            evidence_ids=[filing["info_id"]],
        )
    followups = [
        {"source_root": "nikkei", "outcome": "命中", "published_at": nikkei_at, "info_id": NIKKEI},
        {
            "source_root": "tdk",
            "outcome": classify_response(-1.4, 0.2, direction="down"),
            "published_at": tdk_at,
            "info_id": TDK,
        },
    ]
    report = explanation_report(
        {**anomaly, "status": state},
        impact,
        candidates,
        {"retrieved": sorted(retrieved), "gap": "synthetic fixture, not frozen news"},
        deadline,
        known_constraints={row["item"] for row in checks if row["status"] == "有数据"},
        deadline_on="2026-10-20",
    )
    report["fixture"] = "synthetic"
    report["constraints"] = checks
    report["second_hit"] = second_hit_conclusion(followups, anomaly_start=start)
    report["second_hit_info_id"] = TDK
    report["deadline_sessions"] = deadline_offset(12, None)
    report["tracks"] = _tracks()
    report["n_code"] = n_code(mechanism="供给", narrative_shock=False, fundamental_unchanged=False, unexplained=False)
    report["operating_evidence_from_market"] = verified_from_evidence(
        [{"kind": "second_hit"}, {"kind": "consensus"}],
        as_of=as_of,
        expected_direction="down",
    )
    report["operating_evidence_id"] = filing["info_id"]
    return {"lifecycle": state, "history": history, "report": report}


def explanation_document():
    """The midpoint walk as one JSON document. Synthetic, and not a live conclusion."""
    walked = midpoint_report()
    return {
        "fixture": "synthetic",
        "closes_ac_m8_06": False,
        "closes_case": False,
        "operating_conclusion": "合成生命周期，不是真实经营结论",
        "event_id": "evt-toshiba-2026-10-02",
        "anomaly_id": walked["report"]["anomaly_id"],
        "lifecycle": walked["lifecycle"],
        "history": walked["history"],
        "report": walked["report"],
    }


def _tracks():
    rows = [
        ("2026-10-02", "初现", capital_state(1, -0.05, -0.05), "待验证"),
        ("2026-10-06", "扩散", capital_state(3, -0.02, -0.05), "局部支持"),
        ("2026-10-20", "稳定", capital_state(8, -0.01, -0.05), "支持"),
    ]
    return [
        {"trade_date": day, "emotion": emotion, "capital": capital, "fundamental": fundamental}
        for day, emotion, capital, fundamental in rows
    ]
