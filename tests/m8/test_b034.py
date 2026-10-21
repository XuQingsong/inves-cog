"""B-034: the morning page uses the newest valuation already known."""

from datetime import datetime

import pytest

from inves_cog.perception.attribution.morning import main

MORNING = datetime.fromisoformat("2026-10-16T09:15:00+08:00")
DAY = "2026-10-15"
PRIOR = "2026-10-14"
LATER_DAY = "2026-10-16"
BEFORE = datetime.fromisoformat("2026-10-15T21:00:00+08:00")
EARLIER = datetime.fromisoformat("2026-10-15T18:00:00+08:00")
AFTER = datetime.fromisoformat("2026-10-16T10:30:00+08:00")
PRIOR_AT = datetime.fromisoformat("2026-10-14T21:00:00+08:00")

pytestmark = pytest.mark.phase1_blocking


class Quiet:
    def call(self, task, payload):
        return {"没有": True}


class Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


def _day(value):
    return str(value)[:10]


class Pages:
    def __init__(self, ranges, bars):
        self.ranges = list(ranges)
        self.bars = list(bars)
        self.jobs = []

    def execute(self, statement, params=None):
        compact = " ".join(statement.split())
        if compact.startswith("INSERT INTO ingest.job_runs"):
            row = {"id": len(self.jobs) + 1}
            self.jobs.append(row)
            return Cursor([row])
        if compact.startswith("UPDATE ingest.job_runs"):
            return Cursor([])
        if "perception.anomalies" in compact or "ingest.info_items" in compact:
            return Cursor([])
        if "valuation_v1.ranges" in compact:
            day, cutoff = params
            chosen = {}
            for row in self.ranges:
                row_day = _day(row["trade_date"])
                visible = row_day <= _day(day) if "trade_date <=" in compact else row_day == _day(day)
                if not visible or row["observed_at"] > cutoff:
                    continue
                current = chosen.get(row["ticker"])
                rank = (row_day, row["observed_at"])
                if current is None or rank > (_day(current["trade_date"]), current["observed_at"]):
                    chosen[row["ticker"]] = row
            return Cursor(list(chosen.values()))
        if "ingest.bars_daily" in compact:
            day, tickers = params
            rows = [row for row in self.bars if _day(row["trade_date"]) == _day(day) and row["ticker"] in tickers]
            return Cursor(rows)
        if "trading.ledger" in compact:
            return Cursor(
                [
                    {
                        "state": {"positions": {"AAA": 1, "BBB": 1}},
                        "trade_date": DAY,
                        "observed_at": BEFORE,
                    }
                ]
            )
        if "trading.plan" in compact:
            return Cursor(
                [
                    {
                        "payload": {"orders": [{"ticker": "AAA", "label": "确认加仓", "value": "10"}]},
                        "signal_date": DAY,
                        "trade_date": LATER_DAY,
                        "generated_at": BEFORE,
                    }
                ]
            )
        raise AssertionError(compact)


def _range(ticker, day, observed_at, neutral):
    return {
        "trade_date": day,
        "ticker": ticker,
        "status": "ok",
        "bear": "40",
        "neutral": neutral,
        "bull": "60",
        "payload": {"price": "1"},
        "observed_at": observed_at,
    }


def _page(ranges, bars=None):
    pages = Pages(ranges, bars if bars is not None else [{"ticker": "AAA", "trade_date": DAY, "close": "100"}])
    code = main(["--at", MORNING.isoformat()], connection=pages, client=Quiet())
    assert code == 0
    return pages


def test_prior_valuation_is_used_when_today_arrives_after_the_page(tmp_path, monkeypatch):
    monkeypatch.setenv("INVES_COG_PAGE_DIR", str(tmp_path))
    pages = _page(
        [
            _range("AAA", PRIOR, PRIOR_AT, "50"),
            _range("AAA", DAY, AFTER, "999"),
        ]
    )
    text = (tmp_path / f"daily_page_{DAY}.txt").read_text(encoding="utf-8")
    assert "中间 50.00" in text
    assert "999" not in text
    assert "估值 2026-10-14" in text and "价格 2026-10-15" in text
    assert "现价 100.00" in text
    assert "确认加仓 约 10.00 美元" in text
    assert pages.jobs


def test_a_report_day_valuation_known_before_the_page_wins():
    pages = Pages(
        [
            _range("AAA", PRIOR, PRIOR_AT, "50"),
            _range("AAA", DAY, BEFORE, "77"),
        ],
        [{"ticker": "AAA", "trade_date": DAY, "close": "100"}],
    )
    from inves_cog.perception.attribution.morning import _load

    loaded = _load(pages, MORNING, DAY)
    rows = loaded["valuation"]
    assert [row["ticker"] for row in rows] == ["AAA"]
    assert str(rows[0]["trade_date"])[:10] == DAY
    assert rows[0]["neutral"] == "77"
    assert rows[0]["price"] == "100"


def test_one_ticker_can_miss_without_hiding_another(tmp_path, monkeypatch):
    monkeypatch.setenv("INVES_COG_PAGE_DIR", str(tmp_path))
    _page([_range("AAA", PRIOR, PRIOR_AT, "50")])
    text = (tmp_path / f"daily_page_{DAY}.txt").read_text(encoding="utf-8")
    section = text.split("四、值多少（美元）", 1)[1].split("五、", 1)[0]
    assert "AAA" in section
    assert "BBB" not in section
    assert "现价 0.00" not in section and "中间 0.00" not in section


def test_future_rows_and_later_versions_stay_out(tmp_path, monkeypatch):
    monkeypatch.setenv("INVES_COG_PAGE_DIR", str(tmp_path))
    _page(
        [
            _range("AAA", DAY, EARLIER, "55"),
            _range("AAA", DAY, BEFORE, "77"),
            _range("AAA", DAY, AFTER, "999"),
            _range("AAA", LATER_DAY, BEFORE, "888"),
        ]
    )
    text = (tmp_path / f"daily_page_{DAY}.txt").read_text(encoding="utf-8")
    assert "中间 77.00" in text
    assert "55" not in text and "999" not in text and "888" not in text


def test_no_visible_valuation_stays_a_missing_line(tmp_path, monkeypatch):
    monkeypatch.setenv("INVES_COG_PAGE_DIR", str(tmp_path))
    _page([_range("AAA", LATER_DAY, AFTER, "999")])
    text = (tmp_path / f"daily_page_{DAY}.txt").read_text(encoding="utf-8")
    section = text.split("四、值多少（美元）", 1)[1].split("五、", 1)[0]
    assert "今天没有拿到估值" in section
    assert "999" not in text
    assert "0.00" not in section
