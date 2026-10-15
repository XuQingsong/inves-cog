"""Build deterministic synthetic provider recordings, never a live transport."""

import hashlib
import json

from inves_cog.llm.client import Client, canonical_payload


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
