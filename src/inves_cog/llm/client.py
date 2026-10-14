"""Registry-routed dialogue interface, with explicit recorded/offline operation."""
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Callable

from inves_cog.llm.registry import Registry, TaskSpec

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class CallSpec(TaskSpec):
    task: str


class LLMUnavailable(RuntimeError):
    pass


def canonical_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError('LLM payload must be a JSON object')
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


class Client:
    def __init__(self, *, registry=None, recordings=None, transport: Callable | None = None):
        self.registry = registry if isinstance(registry, Registry) else Registry(registry or ROOT / 'config/llm_tasks.yaml')
        if recordings is not None and transport is not None:
            raise ValueError('Choose recorded mode or injected transport')
        self.recordings = Path(recordings) if recordings is not None else None
        self.transport = transport

    @classmethod
    def from_environment(cls, values=None, *, send=None):
        from inves_cog.llm.transport import OpenAICompatibleTransport
        return cls(transport=OpenAICompatibleTransport(os.environ if values is None else values, send=send))

    def call(self, task: str, payload: dict) -> dict:
        spec = self.registry.resolve(task)
        digest = hashlib.sha256(canonical_payload(payload).encode('utf-8')).hexdigest()
        if self.recordings is not None:
            path = self.recordings / task / (digest + '.json')
            if not path.is_file():
                raise LLMUnavailable(f'Missing recording: {task}/{digest}.json')
            recording = json.loads(path.read_text())
            if recording.get('task') != task or recording.get('payload_sha256') != digest:
                raise ValueError('Recording task or canonical payload hash mismatch')
            if 'error' in recording:
                raise LLMUnavailable(str(recording['error']))
            result = recording.get('result')
            if not isinstance(result, dict):
                raise ValueError('Recording result must be a JSON object')
            return result
        if self.transport is None:
            raise LLMUnavailable('Dialogue connection not configured: 等待 R4')
        for attempt in range(spec.retries + 1):
            try:
                result = self.transport(CallSpec(**asdict(spec), task=task), payload)
                if not isinstance(result, dict):
                    raise LLMUnavailable('Dialogue output must be a JSON object')
                return result
            except (LLMUnavailable, TimeoutError, ConnectionError) as exc:
                if attempt == spec.retries:
                    raise LLMUnavailable(f'{task}: {spec.failure_status}') from exc
        raise AssertionError('Unreachable dialogue state')


_configured_client = None


def configure(client: Client):
    global _configured_client
    _configured_client = client


def call(task: str, payload: dict) -> dict:
    """Shared module-level interface. R4 supplies the real transport explicitly."""
    client = _configured_client or Client.from_environment()
    return client.call(task, payload)
