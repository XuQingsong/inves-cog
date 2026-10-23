"""B-044: v4 candidate prompt, low reasoning, morning page first, snapshot direction."""

import json
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.llm.client import Client
from inves_cog.perception.attribution.documents import make_document, passage_schema
from inves_cog.perception.attribution.morning import main as morning_main
from inves_cog.perception.attribution.propose import (
    PROMPT_VERSION,
    candidate_instruction,
    candidate_output,
    candidate_payload,
    propose_candidates,
)
from inves_cog.perception.attribution.replay_window import Counting, _event
from inves_cog.perception.attribution.snapshot import capture_if_ready
from tests.m8.test_b036 import CUTOFF, Memory, _clock, _db_event, _jobs
from tests.m8.test_b036 import DAY as SNAP_DAY
from tests.m8.test_b039_run import DAY, MORNING, STARTED, Pages, _news

pytestmark = pytest.mark.phase1_blocking

ROOT = Path(__file__).resolve().parents[2]
_CONTRACT = ROOT / "docs/phase1/contracts/m8-candidate-prompt-v4"
_HEADLINE = "Zeta Corp doubles hard-drive output in Asia"
_QUOTE = "Zeta Corp doubles hard-drive output"


def _request_config():
    values = {}
    for prefix in ("LLM_HARD", "LLM_STANDARD"):
        values[prefix + "_API_KEY"] = "fixture"
        values[prefix + "_BASE_URL"] = "https://fixture.invalid/v1"
        values[prefix + "_API_STYLE"] = "openai"
    return values


def _send(box):
    from inves_cog.ingest.http import Response

    def send(method, url, **kwargs):
        box.append(kwargs["json"])
        return Response(200, {"choices": [{"message": {"content": "{}"}}]})

    return send


def test_prompt_files_are_the_request_and_other_tasks_keep_their_bodies():
    instruction = (_CONTRACT / "instruction.txt").read_text(encoding="utf-8")
    output = json.loads((_CONTRACT / "output.json").read_text(encoding="utf-8"))
    assert candidate_instruction() == instruction
    assert candidate_output() == output
    assert PROMPT_VERSION == "evidence-bridge-v4.1-links"
    plain = candidate_payload({"anomaly_id": "a"}, [{"info_id": "n1", "headline": "h"}], [])
    assert plain["output"] == output

    body = "Introductory context."
    item = {"info_id": "n1", "headline": "h", "summary": "s", "body": body}
    item["source_document"] = make_document(item, [[0, len(body)]], char_budget=len(body))
    documented = candidate_payload({"anomaly_id": "a"}, [item], [])
    expected = json.loads(json.dumps(output))
    extra = passage_schema()
    for candidate in expected["schema"]["candidates"]:
        for link in candidate.get("links") or []:
            for anchor in link.get("anchors") or []:
                anchor.update(extra)
    assert documented["output"] == expected
    assert documented["output"]["example"] == output["example"]

    box = []
    client = Client.from_environment(_request_config(), send=_send(box))
    registry = client.registry
    assert registry.resolve("anomaly_candidates").model == "glm-5.3"
    assert registry.resolve("anomaly_candidates").timeout_seconds == 300
    assert registry.resolve("anomaly_candidates").retries == 0
    low_tokens = {
        "graph_seed_draft": 8192,
        "exposure_draft": 8192,
        "segment_mapping_draft": 4096,
    }
    for task in registry.tasks:
        client.call(task, {})
        request = box[-1]
        if task == "anomaly_candidates":
            assert request["messages"][0]["content"] == instruction
            assert request["reasoning_effort"] == "low"
            assert "max_tokens" not in request
            assert request["model"] == "glm-5.3"
            continue
        assert request["messages"][0]["content"].startswith("You are a structured extraction component")
        assert task in request["messages"][0]["content"]
        if task in low_tokens:
            assert request["reasoning_effort"] == "low"
            assert request["max_tokens"] == low_tokens[task]
        else:
            assert "reasoning_effort" not in request
            assert "max_tokens" not in request
        assert registry.resolve(task).timeout_seconds != 300


class _Example:
    def call(self, task, payload):
        assert task == "anomaly_candidates"
        return {"candidates": candidate_output()["example"]["candidates"]}


class _Bad:
    def call(self, task, payload):
        return {
            "candidates": [
                {
                    "mechanism": "供给",
                    "info_ids": ["n1"],
                    "affected": [
                        {"ticker": "AAA", "basket_id": "HDD", "direction": "down"},
                        {"ticker": "BBB", "basket_id": "HDD", "direction": "down"},
                    ],
                    "control_baskets": ["peers"],
                    "direction": "down",
                    "links": [
                        {
                            "from": "zeta_news",
                            "to": "abstract_supply",
                            "kind": "来源陈述",
                            "anchors": [
                                {
                                    "info_id": "n1",
                                    "source_field": "headline",
                                    "quote": _QUOTE,
                                    "provides": "a competitor adds HDD supply",
                                }
                            ],
                            "组合": False,
                        },
                        {
                            "from": "abstract_supply",
                            "to": "sector_beta",
                            "kind": "声明的假设",
                            "hypothesis": "The whole sector rerates.",
                            "hypothesis_type": "供给",
                            "falsify": {"metric": "peer index", "direction": "flat", "window": "next quarter"},
                        },
                    ],
                    "竞争解释": ["sector-wide risk-off selling"],
                    "反证条件": "peers fall as much",
                    "证伪预测": [
                        {
                            "ticker": "PEER",
                            "control_basket": "peers",
                            "direction": "down",
                            "window": "next 5 sessions",
                        }
                    ],
                }
            ]
        }


def _news_item():
    return {"info_id": "n1", "headline": _HEADLINE, "summary": "Asia output rises.", "published_at": STARTED}


def test_v4_example_passes_the_gate_and_a_v3_shaped_output_does_not():
    anomaly = {"anomaly_id": "hdd", "universe": "pool", "members": ["AAA", "BBB"], "direction": "down"}
    universe = {"AAA", "BBB"}
    kept = propose_candidates(anomaly, [_news_item()], [], _Example(), universe)
    scored = [row for row in kept if row.get("scored")]
    assert len(scored) == 1
    affected = scored[0]["affected"]
    assert [row["ticker"] for row in affected] == ["AAA", "BBB"]
    assert {row["direction"] for row in affected} == {"down"}
    assert scored[0]["research_gaps"] == []

    rejected = propose_candidates(anomaly, [_news_item()], [], _Bad(), universe)
    removed = [row for row in rejected if row.get("scored")]
    assert removed
    assert removed[0]["affected"] == []
    assert removed[0]["research_gaps"]


class _Timeout(Counting):
    def __init__(self, folder):
        super().__init__()
        self.folder = folder
        self.order = []

    def call(self, task, payload):
        if task == "anomaly_candidates":
            page = self.folder / f"daily_page_{DAY}.txt"
            assert page.is_file() and page.stat().st_size > 0
            self.order.append("page-already-written")
            self.order.append(task)
            self.tasks.append(task)
            time.sleep(0.01)
            raise TimeoutError("注入超时")
        self.order.append(task)
        return super().call(task, payload)


def test_morning_page_is_written_before_a_blocking_candidate_call(tmp_path, monkeypatch):
    monkeypatch.setenv("INVES_COG_PAGE_DIR", str(tmp_path))
    first = _news("nvda-news", STARTED - timedelta(hours=2), STARTED - timedelta(hours=1))
    second = _news("mu-news", STARTED - timedelta(hours=3), STARTED - timedelta(hours=1))
    second["tickers"] = ["MU"]
    second["extraction_source"]["news_card"]["说了什么"] = "mu-news"
    pages = Pages()
    nvda = {
        "anomaly_id": "nvda-close",
        "trade_date": DAY,
        "session": "close",
        "direction": "down",
        "universe": "pool",
        "members": [{"ticker": "NVDA"}],
        "started_at": STARTED,
        "generated_at": STARTED,
    }
    mu = {**nvda, "anomaly_id": "mu-close", "members": [{"ticker": "MU"}]}
    pages.anomalies = [nvda, mu]
    news = [first, second]

    def execute_news(statement, params=None):
        compact = " ".join(statement.split())
        if "ingest.info_items" in compact:
            from tests.m8.test_b039_run import Cursor

            return Cursor(news)
        return Pages.execute(pages, statement, params)

    pages.execute = execute_news
    client = _Timeout(tmp_path)
    morning_main([], connection=pages, clock=FrozenClock(MORNING), client=client)
    first_page = client.order.index("page-already-written")
    first_candidates = client.order.index("anomaly_candidates")
    assert first_page < first_candidates
    assert "anomaly_candidates" not in client.order[:first_page]
    assert max(index for index, name in enumerate(client.order) if name == "move_card") < first_candidates
    assert Counter(client.tasks) == {"move_card": 2, "claim_extraction": 2, "anomaly_candidates": 2}
    text = (tmp_path / f"daily_page_{DAY}.txt").read_text(encoding="utf-8")
    assert "NVDA" in text and "MU" in text


def _preferred(affected, *, score=1, mechanism="供给"):
    return [{"mechanism": mechanism, "score": score, "scored": True, "affected": affected}]


def test_snapshot_direction_uses_the_preferred_candidate_not_claims():
    mixed_claims = [{"direction": "up"}, {"direction": "down"}]
    cases = {
        "down": (_preferred([{"ticker": "AAA", "direction": "down"}, {"ticker": "BBB", "direction": "down"}]), "down"),
        "mixed": (
            _preferred([{"ticker": "AAA", "direction": "down"}, {"ticker": "BBB", "direction": "up"}]),
            "受影响标的方向不一致",
        ),
        "empty": (_preferred([]), "没有保留的受影响标的"),
    }
    moment = datetime(2026, 10, 16, 4, 30, tzinfo=timezone.utc)
    for name, (candidates, expected) in cases.items():
        pages = Memory(_jobs(), [_db_event(candidates=candidates, claims=mixed_claims)])
        capture_if_ready(pages, SNAP_DAY, _clock(CUTOFF))
        cell = pages.snapshots[0]["events"][0]["fields"]["direction"]
        bundle = {
            "anomaly_id": name,
            "linkage": {"event_id": f"evt-{name}", "lifecycle": "假设中", "mechanism": "供给"},
            "report": {},
            "candidates": candidates,
            "claims": mixed_claims,
            "ticker_status": [{"ticker": "AAA", "exposure": "直接"}],
        }
        event, _gaps = _event(bundle, moment)
        replay = event["fields"]["direction"]
        if expected in {"down", "up"}:
            assert cell["value"] == replay["value"] == expected
            assert cell["missing_reason"] is None and replay["missing_reason"] is None
        else:
            assert cell["value"] is None and replay["value"] is None
            assert cell["missing_reason"] == replay["missing_reason"] == expected
