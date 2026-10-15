"""Registry-routed dialogue interface, with explicit recorded/offline operation."""

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from inves_cog.llm.registry import Registry, TaskSpec
from inves_cog.llm.usage import DialogueResult, PostgresRecorder, call_context, tokens, usage_context

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class CallSpec(TaskSpec):
    task: str


class LLMUnavailable(RuntimeError):
    def __init__(self, message, *, retryable=True):
        super().__init__(message)
        self.retryable = retryable


def canonical_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("LLM payload must be a JSON object")
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Client:
    def __init__(
        self,
        *,
        registry=None,
        recordings=None,
        transport: Callable | None = None,
        clock=None,
        recorder=None,
        monotonic=time.monotonic,
    ):
        self.registry = (
            registry if isinstance(registry, Registry) else Registry(registry or ROOT / "config/llm_tasks.yaml")
        )
        if recordings is not None and transport is not None:
            raise ValueError("Choose recorded mode or injected transport")
        self.recordings = Path(recordings) if recordings is not None else None
        self.transport = transport
        if recorder is not None and clock is None:
            raise ValueError("LLM accounting requires an injected Clock")
        self.clock, self.recorder, self.monotonic = clock, recorder, monotonic

    @classmethod
    def from_environment(cls, values=None, *, send=None, clock=None, recorder=None, monotonic=time.monotonic):
        from inves_cog.clock import SystemClock
        from inves_cog.llm.transport import OpenAICompatibleTransport

        values = os.environ if values is None else values
        if recorder is None and values.get("INVES_COG_DATABASE_URL"):
            recorder = PostgresRecorder(values["INVES_COG_DATABASE_URL"])
        if recorder is not None and clock is None:
            clock = SystemClock()
        return cls(
            transport=OpenAICompatibleTransport(values, send=send), clock=clock, recorder=recorder, monotonic=monotonic
        )

    def context(self, *, purpose, info_ids):
        return usage_context(purpose=purpose, info_ids=info_ids)

    def _invoke(self, spec, payload, digest):
        if self.recordings is not None:
            path = self.recordings / spec.task / (digest + ".json")
            if not path.is_file():
                raise LLMUnavailable(f"Missing recording: {spec.task}/{digest}.json")
            recording = json.loads(path.read_text())
            if recording.get("task") != spec.task or recording.get("payload_sha256") != digest:
                raise ValueError("Recording task or canonical payload hash mismatch")
            if "error" in recording:
                raise LLMUnavailable(str(recording["error"]))
            result = recording.get("result")
            if not isinstance(result, dict):
                raise ValueError("Recording result must be a JSON object")
            return DialogueResult(result, recording.get("usage"))
        if self.transport is None:
            raise LLMUnavailable("Dialogue connection not configured: 等待 R4")
        result = self.transport(spec, payload)
        if isinstance(result, dict):
            return DialogueResult(result)
        if not isinstance(result, DialogueResult) or not isinstance(result.data, dict):
            raise LLMUnavailable("Dialogue output must be a JSON object")
        return result

    def _attempt(self, spec, payload, digest):
        timer = self.monotonic() if self.recorder else None
        usage, success = None, False
        try:
            response = self._invoke(spec, payload, digest)
            usage, success = response.usage, True
            return response.data
        except Exception as exc:
            usage = getattr(exc, "usage", None)
            raise
        finally:
            if self.recorder is not None:
                input_tokens, output_tokens = tokens(usage)
                missing = input_tokens is None or output_tokens is None
                status = "ok" if success else "failed"
                if missing:
                    status = "usage_missing" if success else "failed_usage_missing"
                purpose, info_ids = call_context(spec.task)
                row = {
                    "call_id": uuid.uuid4().hex,
                    "task": spec.task,
                    "model": spec.model,
                    "purpose": purpose,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "latency_ms": max(0, (self.monotonic() - timer) * 1000),
                    "status": status,
                    "info_ids": info_ids,
                    "created_at": self.clock.now_utc(),
                }
                try:
                    self.recorder(row)
                except Exception as exc:
                    raise LLMUnavailable(
                        f"LLM usage persistence failed: {type(exc).__name__}", retryable=False
                    ) from exc

    def call(self, task: str, payload: dict) -> dict:
        spec = self.registry.resolve(task)
        spec = CallSpec(**asdict(spec), task=task)
        digest = hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()
        attempts = 1 if self.recordings is not None else spec.retries + 1
        for attempt in range(attempts):
            try:
                return self._attempt(spec, payload, digest)
            except (LLMUnavailable, TimeoutError, ConnectionError) as exc:
                if attempt == attempts - 1 or not getattr(exc, "retryable", True):
                    raise LLMUnavailable(f"{task}: {spec.failure_status}") from exc
        raise AssertionError("Unreachable dialogue state")


_configured_client = None


def configure(client: Client):
    global _configured_client
    _configured_client = client


def call(task: str, payload: dict) -> dict:
    """Shared module-level interface. R4 supplies the real transport explicitly."""
    client = _configured_client or Client.from_environment()
    return client.call(task, payload)
