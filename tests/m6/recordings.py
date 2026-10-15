"""Build deterministic synthetic provider recordings, never a live transport."""

import hashlib
import json

from inves_cog.llm.client import Client, canonical_payload


def assert_graph_request_bounds():
    from inves_cog.ingest.http import Response

    requests = []

    def send(method, url, **kwargs):
        requests.append(kwargs["json"])
        return Response(200, {"choices": [{"message": {"content": "{}"}}]})

    client = Client.from_environment(
        {
            "LLM_HARD_API_KEY": "fixture",
            "LLM_HARD_BASE_URL": "https://fixture.invalid/v1",
            "LLM_HARD_API_STYLE": "openai",
        },
        send=send,
    )
    for task in ["graph_seed_draft", "exposure_draft"]:
        client.call(task, {"source_texts": []})
        assert requests[-1]["model"] == "glm-5.3"
        assert requests[-1]["max_tokens"] == 8192 and requests[-1]["reasoning_effort"] == "low"
    client.call("anomaly_candidates", {})
    assert "reasoning_effort" not in requests[-1] and "max_tokens" not in requests[-1]


def recorded_draft(fixture, *, clock, recordings):
    from inves_cog.perception.graph.drafting import DraftService

    payload = {"source_texts": [fixture["source"]]}
    digest = hashlib.sha256(canonical_payload(payload).encode()).hexdigest()
    for task in ("graph_seed_draft", "exposure_draft"):
        folder = recordings / task
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (digest + ".json")).write_text(
            json.dumps(
                {
                    "task": task,
                    "payload_sha256": digest,
                    "result": fixture[task],
                    "usage": {"prompt_tokens": 32, "completion_tokens": 16},
                }
            )
        )
    client = Client(recordings=recordings, clock=clock)
    return DraftService(llm=client, clock=clock).draft([fixture["source"]])
