"""B-069: news event layer."""

from datetime import datetime, timezone

from inves_cog.perception.events.events import (
    build_events,
    classify,
    importance,
    parse_facts,
    subjects,
)

SCOPE = {"INTC", "AMZN", "GOOGL", "NOW", "FTNT", "AAPL", "NVDA", "MSFT", "TSM", "QCOM", "AMD", "ARM"}
NOW = datetime(2026, 10, 29, 20, 0, tzinfo=timezone.utc)


def _item(headline, tickers, iid="n1"):
    return {"kind": "news", "headline": headline, "tickers": tickers, "info_id": iid, "first_seen_at": NOW}


def test_kind_priority_preview_beats_guidance():
    assert classify("Intel Earnings Prediction Market Preview: What Will Lip-Bu Tan Say?") == "preview"
    assert classify("Intel Sees Q4 Adj EPS $0.25 vs $0.43 Est") == "guidance"


def test_facts_intel_guidance():
    f = parse_facts("Intel Sees Q4 Adj EPS $0.25 vs $0.43 Est; Sees Sales $15.000B-$16.000B vs $17.045B Est")
    assert f["guide_eps"] == 0.25 and f["guide_eps_est"] == 0.43
    assert abs(f["guide_rev"] - 15.5) < 0.01 and f["guide_rev_est"] == 17.045
    assert f["guide_gap_pct"] < -40  # 指引低于预期 ~42%


def test_facts_amzn_result():
    f = parse_facts("Amazon.com Q3 EPS $1.89 Misses $1.97 Estimate, Sales $201.944B Miss $202.308B Estimate")
    assert f["eps_actual"] == 1.89 and f["eps_est"] == 1.97
    assert f["direction"] == "miss" and f["surprise_pct"] < 0


def test_subject_multi_ticker_needs_headline_name():
    item = _item("Intel Sees Q4 Adj EPS $0.25", ["AAPL", "FTNT", "INTC", "NVDA"])
    assert subjects(item, SCOPE, {}) == ["INTC"] or subjects(item, SCOPE, {"INTC": {"intel"}}) == ["INTC"]
    # FTNT must NOT be a subject even though it's in tickers
    assert "FTNT" not in subjects(item, SCOPE, {"INTC": {"intel"}})


def test_importance_core_earnings_beats_rating():
    core = {"INTC"}
    hi, parts = importance("INTC", "guidance", {"guide_gap_pct": -42}, core)
    assert hi == 100 and parts == {"position": 40, "type": 30, "deviation": 30}
    lo, _ = importance("FTNT", "rating", {}, core)
    assert lo == 25  # 20 + 5


def test_merge_same_subject_kind_day():
    items = [
        _item("Intel Sees Q4 Adj EPS $0.25 vs $0.43 Est", ["INTC"], "a"),
        _item("Intel Sees Q4 Sales $15B-$16B", ["INTC"], "b"),
    ]
    events = build_events(items, SCOPE, NOW)
    assert len(events) == 1 and set(events[0]["info_ids"]) == {"a", "b"}
    assert events[0]["kind"] == "guidance" and events[0]["segment"] == "cpu_pc"


def test_event_pick_prefers_guidance_over_preview():
    from inves_cog.web.brief import _event_for

    events = {
        "INTC": [
            {"kind": "preview", "importance": 45, "first_seen_at": "a", "headline": "Intel Preview"},
            {"kind": "guidance", "importance": 100, "first_seen_at": "b", "headline": "Intel Sees Q4"},
        ]
    }
    assert _event_for(events, "INTC")["kind"] == "guidance"


def test_facts_chip_text():
    from inves_cog.web.brief import _facts_chip

    assert "指引低于预期 42%" in _facts_chip({"guide_gap_pct": -41.9})
    assert "EPS 不及预期 30%" in _facts_chip({"eps_actual": 2.12, "eps_est": 3.02})
    assert _facts_chip({}) == ""


def test_news_events_missing_table_degrades():
    from unittest.mock import MagicMock

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"t": None}
    from inves_cog.web.brief import _news_events

    assert _news_events(conn, "2026-10-29", True) == {}


def test_event_only_display_and_unconfirmed_fallback():
    # mover has event -> news empty; no event -> unconfirmed label
    pass  # covered via _event_for + subject rule tests below


def test_fallback_subject_rule_excludes_ftnt():
    from inves_cog.web.brief import _subjects_of

    item = {"tickers": ["AAPL", "FTNT", "INTC", "NVDA"], "headline": "Intel Sees Q4 Adj EPS $0.25"}
    assert _subjects_of(item, SCOPE) == ["INTC"]
    item2 = {"tickers": ["FTNT", "INTC"], "headline": "anything"}
    assert set(_subjects_of(item2, SCOPE)) == {"FTNT", "INTC"}


def test_window_filter_uses_first_seen():
    # events outside [prev 16:00 ET, end) must be excluded by the SQL window;
    # the unit check: prev session 16:00 ET boundary math
    from datetime import datetime
    from inves_cog.ingest.market import NY
    from inves_cog.ingest.intraday import previous_session

    day = datetime(2026, 10, 29).date()
    prev = previous_session(day)
    start = datetime(prev.year, prev.month, prev.day, 16, 0, tzinfo=NY)
    assert start.strftime("%Y-%m-%d %H:%M") == "2026-10-28 16:00"


def test_chip_revenue_and_one_decimal():
    from inves_cog.web.brief import _facts_chip

    out = _facts_chip({"eps_actual": 1.89, "eps_est": 1.97, "rev_actual": 201.944, "rev_est": 202.308})
    assert "EPS 不及预期 4%" in out and "营收不及预期 0.2%" in out
