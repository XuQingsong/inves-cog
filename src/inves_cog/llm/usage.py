"""Shared dialogue accounting; request text and credentials are never stored."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

_context = ContextVar("inves_cog_llm_context", default=None)
FIELDS = (
    "call_id task model purpose input_tokens output_tokens latency_ms status info_ids created_at item_count".split()
)


@dataclass
class DialogueResult:
    data: dict
    usage: dict | None = None


@contextmanager
def usage_context(**values):
    current = dict(_context.get() or {})
    current.update(values)
    token = _context.set(current)
    try:
        yield
    finally:
        _context.reset(token)


def call_context(task):
    context = _context.get() or {}
    purpose = context.get("purpose") or task
    if context.get("job_task"):
        purpose = context["job_task"] + "|" + purpose
    return purpose, list(context.get("info_ids") or [])


def tokens(usage):
    usage = usage if isinstance(usage, dict) else {}

    def valid(value):
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

    return (
        valid(usage.get("prompt_tokens", usage.get("input_tokens"))),
        valid(usage.get("completion_tokens", usage.get("output_tokens"))),
    )


class PostgresRecorder:
    def __init__(self, url):
        self.url = url

    def __call__(self, row):
        import psycopg

        placeholders = ",".join(["%s"] * len(FIELDS))
        with psycopg.connect(self.url) as connection:
            connection.execute(
                f"INSERT INTO ingest.llm_calls ({','.join(FIELDS)}) VALUES ({placeholders})",
                [row.get(name) for name in FIELDS],
            )
