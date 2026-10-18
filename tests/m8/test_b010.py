"""B-010 repairs for the B-009 recheck. Each test names the finding it locks."""

import hashlib
import json
from datetime import datetime, timezone

import pytest

from inves_cog.llm.client import canonical_payload
from inves_cog.perception.attribution.historical import recording_path


def _item(info_id, published, root, headline, **extra):
    row = {
        "info_id": info_id,
        "published_at": published,
        "source_root": root,
        "headline": headline,
        "summary": headline,
    }
    row.update(extra)
    return row


def _payload_hash(payload):
    return hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()


@pytest.mark.phase1_blocking
def test_missing_or_non_array_links_move_every_ticker_to_a_gap():
    from inves_cog.perception.attribution.historical import v3_candidates
    from inves_cog.perception.attribution.links import inspect_links
    from inves_cog.perception.attribution.propose import PROMPT_VERSION, propose_candidates

    items = [_item("n1", "2026-10-10T00:00:00+00:00", "r1", "Acme ships new chip")]
    affected = [{"ticker": "NVDA"}, {"ticker": "AMD"}, {"ticker": "INTC"}]
    bare = {"mechanism": "需求", "info_ids": ["n1"], "affected": affected}
    missing = inspect_links(bare, items, [])
    assert missing["affected"] == []
    assert missing["scope_layers"]["预期影响范围"] == []
    assert missing["link_checked"] is True
    assert missing["links_missing"] is True
    assert missing["mechanism"] == "需求"
    assert missing["info_ids"] == ["n1"]
    assert [gap["ticker"] for gap in missing["research_gaps"]] == ["NVDA", "AMD", "INTC"]
    assert {gap["reason"] for gap in missing["research_gaps"]} == {"未给逐环依据"}
    not_array = inspect_links({**bare, "links": "bad"}, items, [])
    assert not_array["links_missing"] is True
    assert not_array["affected"] == []
    assert not_array["mechanism"] == "需求"
    empty = inspect_links({**bare, "links": [], "竞争解释": [], "反证条件": "仍要解释"}, items, [])
    assert empty.get("links_missing") is not True
    assert empty["research_gaps"][0]["reason"] == "没有到达该标的的逐环路径"

    class Bare:
        def call(self, task, payload):
            return {"candidates": [{**bare, "affected": [{"ticker": "NVDA"}]}]}

    proposed = [
        row
        for row in propose_candidates(
            {"anomaly_id": "a", "universe": "pool", "direction": "down"}, items, [], Bare(), {"NVDA"}
        )
        if row.get("scored")
    ]
    assert proposed[0]["links_missing"] is True
    assert proposed[0]["affected"] == []
    assert proposed[0]["info_ids"] == ["n1"]

    class Shaped:
        def call(self, task, payload):
            return {"candidates": [{**bare, "links": {"from": "Acme"}}]}

    shaped = [
        row
        for row in propose_candidates(
            {"anomaly_id": "a", "universe": "pool", "direction": "down"}, items, [], Shaped(), {"NVDA"}
        )
        if row.get("scored")
    ]
    assert shaped[0]["links_missing"] is True
    assert shaped[0]["affected"] == []
    recording = {
        "prompt_version": PROMPT_VERSION,
        "result": {"candidates": [{**bare, "mechanism": "供给", "chain": [], "control_baskets": []}]},
    }
    gated = v3_candidates(recording, items, [])
    assert gated["v3"] is True
    assert gated["candidates"][0]["links_missing"] is True
    assert gated["candidates"][0]["affected"] == []
    old = {
        "prompt_version": "evidence-bridge-v2-literal-anchors",
        "result": {"candidates": [bare]},
    }
    legacy = v3_candidates(old, items, [])
    assert legacy["v3"] is False
    assert legacy["candidates"] == [bare]
    assert "links_missing" not in legacy["candidates"][0]


@pytest.mark.phase1_blocking
def test_blind_files_hide_group_names_and_ids_repeat_from_the_seed(tmp_path):
    from inves_cog.perception.attribution.diagnose import write_packet

    spec = _spec()
    first = tmp_path / "a"
    second = tmp_path / "b"
    write_packet(spec, first)
    write_packet(spec, second)
    packet_text = (first / "packet.json").read_text(encoding="utf-8")
    table_text = (first / "blind_table.json").read_text(encoding="utf-8")
    mapping = json.loads((first / "blind_map.json").read_text(encoding="utf-8"))
    leaked = (
        "original/model",
        "original/manual",
        "completed/model",
        "completed/manual",
        "original-model",
        "placebo",
        "reversed",
        "安慰剂",
        "方向反转",
        '"group"',
        '"material"',
        '"extraction"',
        "blind_map",
    )
    for name in leaked:
        assert name not in packet_text
        assert name not in table_text
    table = json.loads(table_text)
    assert [row["id"] for row in table] == [row["id"] for row in json.loads((second / "blind_table.json").read_text())]
    assert {row["group"] for row in mapping} == {
        "original/model",
        "original/manual",
        "completed/model",
        "completed/manual",
        "安慰剂",
        "方向反转",
    }
    assert [row["id"] for row in table] == [row["id"] for row in mapping]
    assert all(row["id"] not in leaked for row in table)


@pytest.mark.phase1_blocking
def test_delete_keeps_other_items_byte_for_byte_and_refuses_a_missing_target():
    from inves_cog.perception.attribution.diagnose import build_packet

    spec = _spec()
    kept_source = spec["materials"]["completed"][0]
    packet = build_packet(spec)
    assert packet["deleted"]["removed"] == ["fill", "copy"]
    assert len(packet["deleted"]["items"]) == 1
    kept = packet["deleted"]["items"][0]
    assert json.dumps(kept, ensure_ascii=False, sort_keys=True, separators=(",", ":")) == json.dumps(
        kept_source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    assert kept["summary"] == kept_source["summary"]
    assert kept["claims"] == kept_source["claims"]
    missing = build_packet({**spec, "delete": {"info_id": "absent"}})
    assert missing["refused"] is True
    assert missing["reason"] == "删除目标不存在"
    assert "cells" not in missing
    assert "deleted" not in missing


@pytest.mark.phase1_blocking
def test_six_payloads_use_the_recording_hash_and_the_run_cap(tmp_path):
    from inves_cog.perception.attribution.diagnose import build_packet
    from inves_cog.perception.attribution.propose import PROMPT_VERSION

    spec = _spec()
    packet = build_packet(spec)
    plan = packet["call_plan"]
    assert plan["runs"] == 3
    assert plan["total_cap"] == 18
    assert plan["executes"] is False
    assert len(plan["calls"]) == 18
    objects = packet["objects"]
    assert len(objects) == 6
    groups = [row["group"] for row in objects]
    assert groups == [
        "original/model",
        "original/manual",
        "completed/model",
        "completed/manual",
        "安慰剂",
        "方向反转",
    ]
    seen = {}
    for row in objects:
        digest = _payload_hash(row["payload"])
        assert digest == row["payload_sha256"]
        assert recording_path("anomaly_candidates", row["payload"], tmp_path).name == f"{digest}.json"
        assert row["payload"]["output"]["selection_policy"]["version"] == PROMPT_VERSION
        seen[row["group"]] = row
        assert all(call["payload_sha256"] == digest for call in plan["calls"] if call["id"] == row["id"])
        assert sum(call["id"] == row["id"] for call in plan["calls"]) == 3
    manual = seen["completed/manual"]["payload"]["items"]
    by_id = {row["info_id"]: row for row in manual}
    assert by_id["fill"]["claims"] == [{"subject": "人工"}]
    assert by_id["base"]["claims"] == []
    model_claims = {row["info_id"]: row.get("claims") for row in seen["completed/model"]["payload"]["items"]}
    assert model_claims["base"] == [{"subject": "原说法"}]
    assert seen["方向反转"]["payload"]["anomaly"]["direction"] == "up"
    assert seen["安慰剂"]["payload"]["anomaly"]["trade_date"] == "2026-10-13"
    capped = build_packet({**spec, "runs": 2})
    assert capped["call_plan"]["total_cap"] == 12
    assert len(capped["call_plan"]["calls"]) == 12


@pytest.mark.phase1_blocking
def test_market_layer_follows_confirmation_and_second_hit_per_ticker():
    confirmed = _run_market(session="close", later=False)
    rows = confirmed["report"]["link_view"]["范围"]["已支持的市场关联"]
    assert rows == [{"ticker": "WDC", "source": "市场确认", "rule": "FR-M8-14"}]
    candidate = next(row for row in confirmed["report"]["candidates"] if row.get("mechanism") == "供给")
    assert candidate["scope_layers"]["已支持的市场关联"] == rows
    assert "已支持的市场关联" not in candidate
    hit = _run_market(session=None, later=True)
    hit_rows = hit["report"]["link_view"]["范围"]["已支持的市场关联"]
    assert hit_rows == [{"ticker": "WDC", "source": "二次命中", "rule": "FR-M8-15"}]
    hit_candidate = next(row for row in hit["report"]["candidates"] if row.get("mechanism") == "供给")
    assert hit_candidate["scope_layers"]["已支持的市场关联"] == hit_rows
    quiet = _run_market(session=None, later=False)
    assert quiet["report"]["link_view"]["范围"]["已支持的市场关联"] == []
    outsider = _run_market(session="close", later=False, extra_ticker="INTC")
    assert outsider["report"]["link_view"]["范围"]["已支持的市场关联"] == [
        {"ticker": "WDC", "source": "市场确认", "rule": "FR-M8-14"}
    ]


@pytest.mark.phase1_blocking
def test_preregistration_compares_time_zones_and_report_shows_hypothesis_width():
    from inves_cog.perception.attribution.chain import _apply_score, _report
    from inves_cog.perception.attribution.diagnose import build_packet

    spec = _spec()
    late_clock = build_packet(
        {
            **spec,
            "as_of": "2026-10-14T00:00:00+08:00",
            "materials": {
                **spec["materials"],
                "completed": [
                    spec["materials"]["completed"][0],
                    {**spec["materials"]["completed"][1], "published_at": "2026-10-13T20:00:00+00:00"},
                    spec["materials"]["completed"][2],
                ],
            },
        }
    )
    assert late_clock["refused"] is True
    assert late_clock["reason"] == "补齐材料不在对象时点之前"
    naive = build_packet(
        {
            **spec,
            "materials": {
                **spec["materials"],
                "completed": [
                    spec["materials"]["completed"][0],
                    {**spec["materials"]["completed"][1], "published_at": "2026-10-13T00:00:00"},
                    spec["materials"]["completed"][2],
                ],
            },
        }
    )
    assert naive["refused"] is True
    assert naive["reason"] == "时间缺少时区"
    start = datetime(2026, 10, 14, 13, 30, tzinfo=timezone.utc)
    end = datetime(2026, 10, 14, 20, 0, tzinfo=timezone.utc)
    anomaly = {"anomaly_id": "width", "started_at": start, "ended_at": end, "direction": "down", "members": []}
    item = _item("late", "2026-10-14T21:00:00+00:00", "root-a", "NVDA HDD", entities=["HDD", "NVDA"], tickers=["NVDA"])
    item["published_at"] = datetime(2026, 10, 14, 21, 0, tzinfo=timezone.utc)
    candidate = {
        "mechanism": "供给",
        "scored": True,
        "info_ids": ["late"],
        "chain": [{"entity_id": "HDD"}],
        "affected": [{"ticker": "NVDA"}],
        "hypothesis_width": 4,
    }
    plain = _apply_score(
        [{key: value for key, value in candidate.items() if key != "hypothesis_width"}], anomaly, [item], None
    )
    marked = _apply_score([candidate], anomaly, [item], None)
    assert plain[0]["score"] == marked[0]["score"] == 0.085714
    report = _report(anomaly, marked, [item], None, None, None, None)
    assert report["link_view"]["hypothesis_width"] == [{"candidate_index": 0, "hypothesis_width": 4}]


def _run_market(*, session, later, extra_ticker=None):
    start = datetime(2026, 10, 2, 13, 30, tzinfo=timezone.utc)
    published = datetime(2026, 10, 2, 11, 0, tzinfo=timezone.utc)
    as_of = datetime(2026, 10, 7, 20, 0, tzinfo=timezone.utc)
    item = {
        "info_id": "nikkei-hdd",
        "published_at": published,
        "first_seen_at": published,
        "headline": "Toshiba expands disk output",
        "summary": "Toshiba expands disk output",
        "tickers": ["WDC"],
        "entities": ["HDD", "WDC"],
        "source_root": "nikkei",
        "source_level": 2,
        "kind": "commentary",
        "claims": [{"subject": "Toshiba"}],
    }
    affected = [{"ticker": "WDC", "direction": "down"}]
    if extra_ticker:
        affected.append({"ticker": extra_ticker, "direction": "down"})
    anomaly = {
        "anomaly_id": "hdd",
        "universe": "pool",
        "direction": "down",
        "trade_date": "2026-10-02",
        "started_at": start,
        "ended_at": datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc),
        "members": [
            {
                "ticker": "WDC",
                "resid": -2.0,
                "earnings_reaction": False,
                "guidance_8k": False,
                "rating_change": False,
            }
        ],
    }
    if session:
        anomaly["session"] = session
    if later:
        event_at = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
        anomaly["later_events"] = [
            {
                "info_id": "tdk",
                "published_at": event_at,
                "first_seen_at": event_at,
                "source_root": "tdk",
                "entities": ["HDD"],
                "mechanism": "供给",
                "direction": "down",
                "expected_z": -2.0,
                "control_z": 0.2,
            }
        ]

    class Client:
        def call(self, task, payload):
            return {
                "candidates": [
                    {
                        "mechanism": "供给",
                        "info_ids": ["nikkei-hdd"],
                        "affected": affected,
                        "chain": [{"entity_id": "HDD"}],
                        "已支持的市场关联": [{"ticker": "WDC"}],
                        "links": [
                            {
                                "from": "Toshiba",
                                "to": "WDC",
                                "kind": "来源陈述",
                                "anchors": [
                                    {
                                        "info_id": "nikkei-hdd",
                                        "source_field": "headline",
                                        "quote": "Toshiba expands",
                                    }
                                ],
                            }
                        ],
                        "竞争解释": [],
                        "反证条件": "对照篮子同向",
                    }
                ]
            }

    from inves_cog.perception.attribution.chain import _one

    return _one(anomaly, [item], as_of=as_of, client=Client(), store=None, components=None, stage=None)


def _spec():
    base = _item("base", "2026-10-12T00:00:00+00:00", "root-a", "base headline", claims=[{"subject": "原说法"}])
    fill = _item("fill", "2026-10-13T00:00:00+00:00", "root-b", "filled headline", claims=[{"subject": "模型"}])
    copy = _item("copy", "2026-10-13T01:00:00+00:00", "root-b", "same root", claims=[{"subject": "转述"}])
    from inves_cog.perception.attribution.diagnose import _digest

    return {
        "object_id": "synth-b010",
        "blind_seed": "seed-b010",
        "as_of": "2026-10-14T20:00:00+00:00",
        "direction": "down",
        "trade_date": "2026-10-14",
        "reference_answers_generated_at": "2026-10-18T00:00:00+00:00",
        "reference_answers": [{"hypothesis": "供给", "tier": "可接受"}],
        "preregistered": [
            {"info_id": "fill", "registered_at": "2026-10-01T00:00:00+00:00", "sha256": _digest(fill)},
            {"info_id": "copy", "registered_at": "2026-10-01T00:00:00+00:00", "sha256": _digest(copy)},
        ],
        "materials": {"original": [base], "completed": [base, fill, copy]},
        "extractions": {
            "model": {"original": [{"info_id": "base"}], "completed": [{"info_id": "base"}]},
            "manual": {
                "original": [{"info_id": "base", "claims": [{"subject": "人工"}]}],
                "completed": [{"info_id": "fill", "claims": [{"subject": "人工"}]}],
            },
        },
        "claims": [{"info_id": "fill", "subject": "Toshiba"}, {"info_id": "base", "subject": "HDD"}],
        "delete": {"info_id": "fill"},
        "placebo": {"trade_date": "2026-10-13", "basket": "accelerators"},
    }
