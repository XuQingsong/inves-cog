"""B-009 link checks, score marks, and the offline diagnostic packet."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _item(info_id, published, entities, tickers, root, headline):
    return {
        "info_id": info_id,
        "published_at": published,
        "entities": entities,
        "tickers": tickers,
        "source_root": root,
        "headline": headline,
        "summary": headline,
    }


def _candidate(info_ids):
    return {
        "mechanism": "供给",
        "scored": True,
        "info_ids": info_ids,
        "chain": [{"entity_id": "HDD"}],
        "affected": [{"ticker": "NVDA"}],
        "label": info_ids[0],
    }


@pytest.mark.phase1_blocking
def test_three_link_kinds_keep_or_drop_the_expected_ticker():
    from inves_cog.perception.attribution.links import inspect_links

    item = _item("n1", "2026-10-13T00:00:00+00:00", ["HDD"], ["NVDA"], "nikkei", "Toshiba expands disk output")
    base = {
        "info_ids": ["n1"],
        "affected": [{"ticker": "WDC"}, {"ticker": "INTC"}],
        "竞争解释": [],
        "反证条件": "产能未落地",
    }
    legal = inspect_links(
        {
            **base,
            "links": [
                {
                    "from": "Toshiba",
                    "to": "WDC",
                    "kind": "来源陈述",
                    "anchors": [
                        {"info_id": "n1", "source_field": "headline", "quote": "Toshiba expands", "ticker": "WDC"}
                    ],
                }
            ],
        },
        [item],
        [],
    )
    assert [row["ticker"] for row in legal["affected"]] == []
    assert legal["scope_layers"]["预期影响范围"] == legal["affected"]
    assert legal["research_gaps"] == [
        {"ticker": "WDC", "reason": "材料未点名"},
        {"ticker": "INTC", "reason": "材料未点名"},
    ]
    assert legal["quote_note"] == "引文匹配只证明出处，不证明支持推断"
    assert legal["scope_layers"]["已支持的市场关联"] == []
    assert legal["scope_layers"]["已量化或验证的经营暴露"] == []
    forged = inspect_links({**legal, "link_checked": False, "已支持的市场关联": [{"ticker": "WDC"}]}, [item], [])
    assert "已支持的市场关联" not in forged
    assert forged["model_scope_rejected"] == ["已支持的市场关联"]
    missing_quote = inspect_links(
        {
            **base,
            "links": [
                {
                    "from": "Toshiba",
                    "to": "WDC",
                    "kind": "来源陈述",
                    "anchors": [{"info_id": "n1", "source_field": "headline", "quote": "not in the text"}],
                }
            ],
        },
        [item],
        [],
    )
    assert missing_quote["affected"] == []
    assert missing_quote["research_gaps"][0]["ticker"] == "WDC"
    observed = {"relation_id": "rel-1", "from_entity": "Toshiba", "to_entity": "WDC", "status": "观察到"}
    rejected = {"relation_id": "rel-2", "from_entity": "Toshiba", "to_entity": "INTC", "status": "驳回"}
    related = inspect_links(
        {
            **base,
            "affected": [{"ticker": "WDC"}, {"ticker": "INTC"}],
            "links": [
                {"from": "Toshiba", "to": "WDC", "kind": "已有关系", "relation_id": "rel-1"},
                {"from": "Toshiba", "to": "INTC", "kind": "已有关系", "relation_id": "rel-2"},
            ],
        },
        [item],
        [observed, rejected],
    )
    assert [row["ticker"] for row in related["affected"]] == []
    hypothesis = {
        "from": "HDD",
        "to": "NVDA",
        "kind": "声明的假设",
        "hypothesis": "硬盘需求外溢",
        "hypothesis_type": "需求弹性",
        "falsify": {"metric": "剩余收益", "direction": "down", "window": "20个交易日"},
    }
    unfalsified = inspect_links(
        {"info_ids": ["n1"], "affected": [{"ticker": "NVDA"}], "links": [hypothesis], "竞争解释": [], "反证条件": "无"},
        [item],
        [],
    )
    assert unfalsified["affected"] == []
    assert unfalsified["research_gaps"][0]["reason"] == "假设标的缺少证伪预测"
    prediction = {"ticker": "NVDA", "control_basket": "软件", "direction": "down", "window": "20个交易日"}
    other = {**prediction, "ticker": "AMD"}
    shared = inspect_links(
        {
            "info_ids": ["n1"],
            "affected": [{"ticker": "NVDA"}, {"ticker": "AMD"}],
            "links": [hypothesis, {**hypothesis, "to": "AMD"}],
            "证伪预测": [prediction, other],
            "竞争解释": ["估值倍数"],
            "反证条件": "对照篮子同向",
        },
        [item],
        [],
    )
    assert shared["共用假设"] is True
    assert shared["hypothesis_count"] == 1
    assert shared["hypothesis_width"] == 1
    split = inspect_links(
        {
            **shared,
            "link_checked": False,
            "证伪预测": [prediction, {**other, "window": "5个交易日"}],
        },
        [item],
        [],
    )
    assert split["共用假设"] is False
    assert split["hypothesis_count"] == 2
    combined = inspect_links(
        {
            **base,
            "affected": [{"ticker": "WDC"}],
            "links": [
                {
                    "from": "Toshiba",
                    "to": "WDC",
                    "kind": "来源陈述",
                    "组合": True,
                    "anchors": [
                        {"info_id": "n1", "source_field": "headline", "quote": "Toshiba expands", "provides": "主体"},
                        {"info_id": "n1", "source_field": "headline", "quote": "disk output", "provides": "动作"},
                    ],
                }
            ],
        },
        [item],
        [],
    )
    assert combined["affected"] == []
    assert combined["links"][0]["组合"] is True
    bare = inspect_links(
        {**base, "links": [{**combined["links"][0], "组合": False, "anchors": combined["links"][0]["anchors"]}]},
        [item],
        [],
    )
    assert bare["affected"] == []


@pytest.mark.phase1_blocking
def test_score_marks_do_not_change_the_existing_total():
    from inves_cog.perception.attribution.chain import _apply_score

    start = datetime(2026, 10, 14, 13, 30, tzinfo=timezone.utc)
    end = datetime(2026, 10, 14, 20, 0, tzinfo=timezone.utc)
    anomaly = {"started_at": start, "ended_at": end, "direction": "down", "members": []}
    late = _item(
        "late", datetime(2026, 10, 14, 21, 0, tzinfo=timezone.utc), ["HDD", "NVDA"], ["NVDA"], "root-a", "NVDA HDD"
    )
    early = _item(
        "early", datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc), ["OTHER"], ["OTHER"], "root-b", "unrelated"
    )
    before = _apply_score([_candidate(["late"])], anomaly, [late], None)[0]
    after = _apply_score([_candidate(["early", "late"])], anomaly, [early, late], None)[0]
    assert before["score"] == 0.085714
    assert after["score"] == 0.657143
    assert after["evidence"]["diagnostics"]["时间分来源未被逐环引用"] is True
    assert after["evidence"]["diagnostics"]["仅共现条数"] == 1
    assert after["evidence"]["diagnostics"]["display_name"] == "时间与关联特征分"
    assert after["evidence"]["diagnostics"]["not_credibility"] is True
    five = [
        _item(
            f"n{index}",
            datetime(2026, 10, 13, 12, index, tzinfo=timezone.utc),
            ["HDD", "NVDA"],
            ["NVDA"],
            f"root-{index}",
            "NVDA HDD",
        )
        for index in range(5)
    ]
    full = _apply_score([_candidate([item["info_id"] for item in five])], anomaly, five, None)[0]
    assert full["score"] == 1.0
    assert full["evidence"]["diagnostics"]["仅共现条数"] == 5
    assert full["evidence"]["diagnostics"]["时间分来源未被逐环引用"] is True


@pytest.mark.phase1_blocking
def test_diagnostic_packet_checks_preregistration_and_does_not_call():
    from inves_cog.perception.attribution.diagnose import _digest, build_packet, execute_calls

    original = _item("base", "2026-10-12T00:00:00+00:00", ["HDD"], ["NVDA"], "root-a", "base")
    extra = _item("fill", "2026-10-13T00:00:00+00:00", ["HDD"], ["NVDA"], "root-b", "filled")
    reprint = _item("copy", "2026-10-13T01:00:00+00:00", ["HDD"], ["NVDA"], "root-b", "same root")
    spec = {
        "object_id": "synth-1",
        "as_of": "2026-10-14T20:00:00+00:00",
        "direction": "down",
        "reference_answers_generated_at": "2026-10-18T00:00:00+00:00",
        "reference_answers": [{"hypothesis": "供给", "tier": "可接受"}, {"hypothesis": "估值", "tier": "不可接受"}],
        "preregistered": [
            {"info_id": "fill", "registered_at": "2026-10-01T00:00:00+00:00", "sha256": _digest(extra)},
            {"info_id": "copy", "registered_at": "2026-10-01T00:00:00+00:00", "sha256": _digest(reprint)},
        ],
        "materials": {"original": [original], "completed": [original, extra, reprint]},
        "extractions": {
            "model": {"original": [{"info_id": "base"}], "completed": [{"info_id": "base"}, {"info_id": "secret"}]},
            "manual": {"original": [{"info_id": "base"}], "completed": [{"info_id": "fill"}]},
        },
        "claims": [{"info_id": "fill", "subject": "Toshiba"}, {"info_id": "base", "subject": "HDD"}],
        "delete": {"info_id": "fill"},
        "placebo": {"trade_date": "2026-10-13", "basket": "accelerators"},
        "anomaly": {
            "started_at": datetime(2026, 10, 14, 13, 30, tzinfo=timezone.utc),
            "ended_at": datetime(2026, 10, 14, 20, 0, tzinfo=timezone.utc),
            "direction": "down",
            "members": [],
        },
        "score_items": [original],
        "correct_candidate": {**_candidate(["base"]), "links": [{"anchors": [{"info_id": "base"}]}], "label": "正确"},
        "decoy_candidate": {**_candidate(["base"]), "label": "诱饵"},
    }
    packet = build_packet(spec)
    assert packet["refused"] is False
    assert packet["generation_order"] == ["四格", "删除变体", "对照对象", "盲审表", "调用计划", "诱饵评分"]
    assert packet["sha256"]
    assert len(packet["cells"]) == 4
    completed_model = next(
        cell for cell in packet["cells"] if cell["material"] == "completed" and cell["extraction"] == "model"
    )
    assert [row["info_id"] for row in completed_model["extraction_rows"]] == ["base"]
    assert "fill" in packet["deleted"]["removed"] and "copy" in packet["deleted"]["removed"]
    assert [row["info_id"] for row in packet["deleted"]["claims"]] == ["base"]
    kept_base = next(item for item in spec["materials"]["completed"] if item["info_id"] == "base")
    assert packet["deleted"]["items"] == [kept_base]
    assert packet["placebo"]["anomaly"]["trade_date"] == "2026-10-13"
    assert packet["reversed"]["anomaly"]["direction"] == "up"
    assert packet["reversed"]["items"] == packet["placebo"]["items"]
    assert all("group" not in row for row in packet["blind_table"])
    assert {row["group"] for row in packet["blind_map"]} == {
        "original/model",
        "original/manual",
        "completed/model",
        "completed/manual",
        "安慰剂",
        "方向反转",
    }
    assert packet["call_plan"]["executes"] is False
    assert packet["call_plan"]["runs"] == 3
    assert packet["call_plan"]["total_cap"] == 18
    with pytest.raises(RuntimeError, match="诊断工具不执行调用"):
        execute_calls(packet["call_plan"])
    labels = {row["label"]: row for row in packet["ranking"]}
    assert labels["诱饵"]["marks"]["仅共现条数"] > labels["正确"]["marks"]["仅共现条数"]
    late = build_packet(
        {
            **spec,
            "materials": {
                **spec["materials"],
                "completed": [original, {**extra, "published_at": "2026-10-15T00:00:00+00:00"}],
            },
        }
    )
    assert late["refused"] is True
    assert "cells" not in late
    unordered = build_packet(
        {**spec, "preregistered": [{**spec["preregistered"][0], "registered_at": "2026-10-19T00:00:00+00:00"}]}
    )
    assert unordered["refused"] is True


@pytest.mark.phase1_blocking
def test_review_tool_reads_caller_files_and_v3_judges_a_synthetic_recording(tmp_path):
    from inves_cog.perception.attribution.diagnose import review_files
    from inves_cog.perception.attribution.historical import judge_recording
    from inves_cog.perception.attribution.propose import PROMPT_VERSION, read_candidates

    response = tmp_path / "response.json"
    review = tmp_path / "review.json"
    response.write_text(
        json.dumps(
            {
                "anomaly": {
                    "started_at": "2026-10-14T13:30:00+00:00",
                    "ended_at": "2026-10-14T20:00:00+00:00",
                    "direction": "down",
                    "members": [],
                },
                "items": [
                    {
                        "info_id": "base",
                        "published_at": "2026-10-13T00:00:00+00:00",
                        "entities": ["HDD", "NVDA"],
                        "tickers": ["NVDA"],
                        "source_root": "root-a",
                        "headline": "NVDA",
                    }
                ],
                "candidates": [
                    {
                        "mechanism": "供给",
                        "scored": True,
                        "info_ids": ["base"],
                        "chain": [{"entity_id": "HDD"}],
                        "affected": [{"ticker": "NVDA"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    review.write_text(json.dumps({"conclusions": [{"candidate_index": 0, "note": "人工复核"}]}), encoding="utf-8")
    checked = review_files(response, review)
    assert checked["rows"][0]["human_note"] == "人工复核"
    assert checked["rows"][0]["marks"]["display_name"] == "时间与关联特征分"
    assert checked["sha256"]
    anomaly = {"case_kind": "toshiba", "trade_date": "2026-10-02", "members": [{"ticker": "WDC"}]}
    items = [{"info_id": "nikkei", "headline": "Toshiba expands disk output"}]
    recording = {
        "prompt_version": PROMPT_VERSION,
        "synthetic": True,
        "result": {"candidates": [{"mechanism": "供给", "scored": True, "info_ids": ["nikkei"]}]},
    }
    judged = judge_recording(anomaly, items, recording)
    assert judged["synthetic"] is True and judged["passes_7_1"] is True and judged["semantic_support"] is False
    old = judge_recording(
        anomaly, items, {"prompt_version": "evidence-bridge-v2-literal-anchors", "result": recording["result"]}
    )
    assert old["eligible"] is False
    with pytest.raises(ValueError, match="结构不合格"):
        read_candidates({"candidates": [{"mechanism": "供给", "info_ids": ["n1"], "links": "bad"}]})


@pytest.mark.phase1_cases
def test_case_attribution():
    from inves_cog.perception.attribution.historical import real_v3_recordings

    found = real_v3_recordings(ROOT / "recordings")
    assert found, "等待 v3 真实录音（需用户授权调用）"
