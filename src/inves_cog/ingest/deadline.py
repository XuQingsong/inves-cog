"""Cooperative task budget shared by every HTTP request and item loop."""

import time
from contextlib import contextmanager
from contextvars import ContextVar

_budget = ContextVar("ingest_budget", default=None)


def remaining():
    value = _budget.get()
    if value is None:
        return None
    deadline, timer = value
    seconds = deadline - timer()
    if seconds <= 0:
        from inves_cog.ingest.http import SourceError

        raise SourceError("Task exceeded its 30-minute budget")
    return seconds


def check():
    remaining()


@contextmanager
def budget(seconds, timer=time.monotonic):
    token = _budget.set((timer() + seconds, timer))
    try:
        yield
    finally:
        _budget.reset(token)
