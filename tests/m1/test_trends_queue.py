from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock

from inves_cog.ingest.adapters import Trends as TrendsAdapter
from inves_cog.ingest.deadline import budget
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


class RotatingTrends:
    def __init__(self, limit=None):
        self.calls = []
        self.limit = limit

    def get(self, keyword):
        assert isinstance(keyword, str)
        self.calls.append(keyword)
        if self.limit is not None and len(self.calls) > self.limit:
            raise SourceError("Task exceeded its 30-minute budget")
        return _payload(keyword)


def test_trends_adapter_builds_one_keyword_request(monkeypatch):
    calls = []

    class Rows:
        def iterrows(self):
            yield datetime(2026, 11, 16), {"A": 5, "isPartial": False}

    class Client:
        def build_payload(self, keywords, **kwargs):
            calls.append(list(keywords))

        def interest_over_time(self):
            return Rows()

    monkeypatch.setattr(TrendsAdapter, "_client", lambda self: Client())
    result = TrendsAdapter(clock=Clock(date(2026, 11, 17))).get("A")
    assert calls == [["A"]]
    assert result["today"] is None and result["history"] == [{"date": date(2026, 11, 16), "value": 5.0}]


def test_trends_requests_single_keywords_and_saves_rotation_cursor():
    repo = Repo()
    trends = RotatingTrends()
    result = _pipeline(date(2026, 11, 17), repo, trends, ["A", "B", "C", "D"]).trends_task()
    assert trends.calls == ["A", "B", "C", "D"]
    assert result["processed_count"] == 4 and result["pending_count"] == 0 and result["status"] == "ok"
    assert repo.cursors["trends_queue"]["position"] == 0
    assert repo.cursors["trends_queue"]["next_keyword"] == "A"
    assert all(f"trends:{keyword}" in repo.cursors for keyword in "ABCD")


def test_trends_stops_before_hard_budget_without_marking_keyword_failed():
    repo = Repo()
    trends = RotatingTrends()
    with budget(59):
        result = _pipeline(date(2026, 11, 17), repo, trends, ["A", "B"]).trends_task()
    assert trends.calls == []
    assert result["processed_count"] == 0 and result["pending_count"] == 2
    assert result["failures"] == [] and result["status"] == "degraded"
    assert result["note"] == "trends_rotation_budget_exhausted"
    assert repo.cursors["trends_queue"]["position"] == 0


def test_trends_cursor_wraps_over_budget_boundaries():
    repo = Repo()
    first_trends = RotatingTrends(limit=2)
    first = _pipeline(date(2026, 11, 16), repo, first_trends, ["A", "B", "C", "D"]).trends_task()
    assert first_trends.calls == ["A", "B", "C"]
    assert first["processed_count"] == 2 and first["pending_count"] == 2
    assert repo.cursors["trends_queue"]["position"] == 2
    assert repo.cursors["trends_queue"]["next_keyword"] == "C"

    second_trends = RotatingTrends(limit=3)
    second = _pipeline(date(2026, 11, 17), repo, second_trends, ["A", "B", "C", "D"]).trends_task()
    assert second_trends.calls == ["C", "D", "A", "B"]
    assert second["processed_count"] == 3 and second["pending_count"] == 1
    assert repo.cursors["trends_queue"]["position"] == 1
    assert repo.cursors["trends_queue"]["next_keyword"] == "B"

    third_trends = RotatingTrends()
    third = _pipeline(date(2026, 11, 18), repo, third_trends, ["A", "B", "C", "D"]).trends_task()
    assert third_trends.calls == ["B", "C", "D", "A"]
    assert third["processed_count"] == 4 and third["pending_count"] == 0


def test_trends_rotation_reaches_every_keyword_over_multiple_runs():
    repo = Repo()
    seen = set()
    for day in range(16, 21):
        trends = RotatingTrends(limit=2)
        _pipeline(date(2026, 11, day), repo, trends, ["A", "B", "C", "D", "E"]).trends_task()
        seen.update(trends.calls[:2])
        if len(seen) == 5:
            break
    assert seen == {"A", "B", "C", "D", "E"}


def test_trends_cursor_survives_keyword_list_shrink_and_insert():
    repo = Repo()
    repo.cursors["trends_queue"] = {"position": 4, "next_keyword": "removed"}
    trends = RotatingTrends()
    result = _pipeline(date(2026, 11, 17), repo, trends, ["A", "B"]).trends_task()
    assert trends.calls == ["A", "B"]
    assert result["status"] == "ok" and repo.cursors["trends_queue"]["position"] == 0

    repo.cursors["trends_queue"] = {"position": 0, "next_keyword": "C"}
    trends = RotatingTrends()
    _pipeline(date(2026, 11, 18), repo, trends, ["A", "new", "C"]).trends_task()
    assert trends.calls == ["C", "A", "new"]
