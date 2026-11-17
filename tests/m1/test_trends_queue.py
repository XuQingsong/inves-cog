from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock

from inves_cog.ingest.http import SourceError
from inves_cog.ingest.pipeline import Pipeline


class Clock:
    def __init__(self, day):
        self.day = day

    def now_utc(self):
        return datetime.combine(self.day, datetime.min.time(), timezone.utc) + timedelta(hours=12)

    def today_trade_date(self):
        return self.day


class Repo:
    def __init__(self):
        self.cursors = {}

    def get_cursor(self, key):
        return self.cursors.get(key)

    def set_cursor(self, key, value, stamp):
        self.cursors[key] = value


def _pipeline(day, repo, trends, keywords):
    p = Pipeline.__new__(Pipeline)
    p.clock = Clock(day)
    p.repo = repo
    p.monitored = [{"trends_keywords": [keyword]} for keyword in keywords]
    p.trends = trends
    p.info = Mock()
    p.day_override = day
    return p


def _payload(keyword):
    return {"history": [{"date": date(2026, 11, 16), "value": 1.0}] * 60, "today": 2.0}


def test_trends_batches_keywords_and_durable_queue_completes():
    repo = Repo()
    calls = []

    class Trends:
        def get_batch(self, keywords):
            calls.append(list(keywords))
            return {keyword: _payload(keyword) for keyword in keywords}

    result = _pipeline(date(2026, 11, 17), repo, Trends(), ["A", "B", "C", "D"]).trends_task()
    assert calls == [["A", "B", "C"], ["D"]]
    assert result["processed_count"] == 4 and result["pending_count"] == 0 and result["status"] == "ok"
    assert repo.cursors["trends_queue"] == {
        "day": "2026-11-17",
        "pending": [],
        "completed": True,
    }
    assert all(f"trends:{keyword}" in repo.cursors for keyword in "ABCD")


def test_trends_timeout_leaves_checkpoint_and_next_day_resumes():
    repo = Repo()
    calls = []

    class Trends:
        def get_batch(self, keywords):
            calls.append(list(keywords))
            if len(calls) == 1:
                return {keyword: _payload(keyword) for keyword in keywords}
            raise SourceError("Task exceeded its 30-minute budget")

    first = _pipeline(date(2026, 11, 16), repo, Trends(), ["A", "B", "C", "D"]).trends_task()
    assert first["processed_count"] == 3 and first["pending_count"] == 1
    assert repo.cursors["trends_queue"]["pending"] == ["D"]

    class NextDay:
        def get_batch(self, keywords):
            calls.append(list(keywords))
            return {keyword: _payload(keyword) for keyword in keywords}

    second = _pipeline(date(2026, 11, 17), repo, NextDay(), ["A", "B", "C", "D"]).trends_task()
    assert calls[-1] == ["D"]
    assert second["processed_count"] == 1 and second["pending_count"] == 0
    assert repo.cursors["trends_queue"]["completed"] is True
