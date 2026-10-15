"""Handwritten recording checks for shared-call accounting."""

import hashlib
import json


def assert_usage_accounting(root, clock):
    from inves_cog.ingest.http import Response
    from inves_cog.llm.client import Client, LLMUnavailable, canonical_payload
    from inves_cog.llm.transport import OpenAICompatibleTransport

    payload = {"headline": "Handwritten accounting fixture", "body": "Original fixture prose."}
    digest = hashlib.sha256(canonical_payload(payload).encode()).hexdigest()
    folder = root / "entity_tagging"
    folder.mkdir(parents=True)
    path = folder / (digest + ".json")
    recording = {
        "task": "entity_tagging",
        "payload_sha256": digest,
        "result": {"entities": []},
        "usage": {"prompt_tokens": 11, "completion_tokens": 3},
    }
    path.write_text(json.dumps(recording))
    rows = []
    client = Client(recordings=root, clock=clock, recorder=rows.append, monotonic=lambda: 0)
    with client.context(purpose="M1:layer1", info_ids=["news:fixture:1"]):
        assert client.call("entity_tagging", payload) == {"entities": []}
    assert len(rows) == 1
    assert rows[0]["input_tokens"] == 11 and rows[0]["output_tokens"] == 3
    assert rows[0]["purpose"] == "M1:layer1" and rows[0]["info_ids"] == ["news:fixture:1"]
    assert rows[0]["created_at"] == clock.now_utc() and rows[0]["status"] == "ok"
    assert rows[0]["model"] == "deepseek-v4.1-flash"
    assert rows[0]["call_id"] and rows[0]["latency_ms"] >= 0
    recording.pop("usage")
    path.write_text(json.dumps(recording))
    client.call("entity_tagging", payload)
    assert rows[-1]["input_tokens"] is None and rows[-1]["output_tokens"] is None
    assert rows[-1]["status"] == "usage_missing"
    recording["error"] = "handwritten timeout"
    path.write_text(json.dumps(recording))
    try:
        client.call("entity_tagging", payload)
    except LLMUnavailable:
        pass
    else:
        raise AssertionError("recorded failure must be raised")
    assert rows[-1]["status"] == "failed_usage_missing" and len(rows) == 3

    # The actual protocol response carries usage separately from the public
    # extraction dict; no extra metadata leaks into call(task,payload)->dict.
    config = {
        "LLM_STANDARD_API_KEY": "fixture-not-a-key",
        "LLM_STANDARD_BASE_URL": "https://example.invalid/v1",
        "LLM_STANDARD_API_STYLE": "openai-compatible",
    }

    def send(*args, **kwargs):
        assert kwargs["json"]["enable_thinking"] is False
        return Response(
            200,
            {
                "choices": [{"message": {"content": '{"entities":[]}'}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 2},
            },
        )

    live_shape = Client(
        transport=OpenAICompatibleTransport(config, send=send), clock=clock, recorder=rows.append, monotonic=lambda: 0
    )
    assert live_shape.call("entity_tagging", payload) == {"entities": []}
    assert rows[-1]["input_tokens"] == 7 and rows[-1]["output_tokens"] == 2

    from inves_cog.ingest.repository import Repository

    class Connection:
        def __init__(self):
            self.writes = []
            self.stats = {"input_tokens": 11, "output_tokens": 3, "usage_missing_calls": 0}

        def execute(self, sql, values=None):
            self.returning_id = sql.startswith(("INSERT", "UPDATE"))
            if sql.startswith("INSERT"):
                self.writes.append((sql, values))
            return self

        def fetchone(self):
            return {"id": 1} if self.returning_id else self.stats

    connection = Connection()
    repo = Repository(connection)
    job = {
        "task_name": "news_test",
        "trade_date": clock.today_trade_date(),
        "started_at": clock.now_utc(),
        "ended_at": clock.now_utc(),
        "status": "ok",
        "processed_count": 1,
        "error_summary": None,
        "params_version": "p-2026.10",
    }
    repo.write_job(job)
    assert connection.writes[-1][1][-3:] == [11, 3, 0]
    assert "llm_input_tokens" in connection.writes[-1][0]
    connection.stats = {"input_tokens": None, "output_tokens": None, "usage_missing_calls": 1}
    repo.write_job(job)
    assert connection.writes[-1][1][-3:] == [None, None, 1]
