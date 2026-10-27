"""Restart-safe polling state; source health is a fifteen-minute aggregate."""

from datetime import datetime, timedelta


class SnapshotPoll:
    def __init__(self, repo, clock, health, *, lock_factory=None):
        self.repo, self.clock, self.health = repo, clock, health
        self.lock_factory = lock_factory

    def run(self, task, source, operation):
        # One owner per task, including manual invocations and restarted workers.
        from contextlib import nullcontext

        lock = self.lock_factory(task) if self.lock_factory else nullcontext(True)
        with lock as acquired:
            if not acquired:
                return {"processed_count": 0, "note": "another snapshot poll owns this task"}
            return self._run(task, source, operation)

    def _run(self, task, source, operation):
        now = self.clock.now_utc()
        key = "snapshot-poll:" + task
        state = self.repo.get_cursor(key) or {}
        if source.startswith("Alpaca") and self.repo.get_cursor("snapshot-alpaca-halted"):
            return {
                "processed_count": 0,
                "status": "degraded",
                "note": "Alpaca rate limit; operator intervention required",
            }
        retry = state.get("retry_at")
        if retry and now < datetime.fromisoformat(retry):
            return {"processed_count": 0, "status": "degraded", "note": "source backoff; no request"}
        result = operation()
        good = result.get("source_success", result.get("status") not in {"failed", "degraded"})
        failures = 0 if good else state.get("failures", 0) + 1
        delay = min(900, 60 * 2 ** min(failures - 1, 4)) if failures and task == "yahoo_intraday" else 0
        if result.get("rate_limited") and source.startswith("Alpaca"):
            self.repo.set_cursor("snapshot-alpaca-halted", {"at": now.isoformat(), "reason": "HTTP 429"}, now)
        state.update(
            failures=failures,
            retry_at=(now + timedelta(seconds=delay)).isoformat(),
            successes=state.get("successes", 0) + int(good),
            errors=state.get("errors", 0) + int(not good),
            items=state.get("items", 0) + result.get("processed_count", 0),
        )
        latest = result.get("latest_data_at")
        if latest and (not state.get("latest_data_at") or latest > state["latest_data_at"]):
            state["latest_data_at"] = latest
        flushed = state.get("health_at")
        if not flushed or now - datetime.fromisoformat(flushed) >= timedelta(minutes=15):
            self.health.record(
                source,
                success=good,
                count=state["items"],
                degraded=bool(state["errors"]) or result.get("status") == "degraded",
                note=f"success_count={state['successes']}; failure_count={state['errors']}; "
                f"latest_data_at={state.get('latest_data_at', 'none')}; backoff_seconds={delay}; "
                f"retry_at={state['retry_at']}; {result.get('note', '')}",
            )
            state.update(health_at=now.isoformat(), successes=0, errors=0, items=0)
        self.repo.set_cursor(key, state, now)
        return result
