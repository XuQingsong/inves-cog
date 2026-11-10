from unittest.mock import MagicMock

import pytest

from inves_cog.perception.review import verdicts as V


def _conn(rows_by_query):
    c = MagicMock()
    c.execute.side_effect = lambda q, *a: MagicMock(
        fetchall=lambda: rows_by_query.get("all", []), fetchone=lambda: rows_by_query.get("one")
    )
    return c


@pytest.mark.phase1_blocking
def test_market_verdict_second_hits_wins():
    hits = [{"info_id": "a", "outcome": "确认"}, {"info_id": "b", "outcome": "否定"}]
    label, src, ev = V.market_verdict(
        _conn({}), {"trade_date": __import__("datetime").date(2026, 11, 4)}, "T+1", None, None, hits
    )
    assert label == "确认" and src == "二次命中"


@pytest.mark.phase1_blocking
def test_message_verdict_invalid_json_downgrades():
    client = MagicMock()
    client.chat_json.return_value = {"verdict": "hacked"}
    out = V.message_verdict(
        _conn({"all": []}),
        {"trade_date": __import__("datetime").date(2026, 11, 4), "member_tickers": ["NVDA"]},
        "T+1",
        None,
        None,
        client,
    )
    assert out[0] == "仍未知"


@pytest.mark.phase1_blocking
def test_message_verdict_bad_info_ids_rejected():
    client = MagicMock()
    client.chat_json.return_value = {"verdict": "证实", "info_ids": ["news:x:999"]}
    out = V.message_verdict(
        _conn({"all": []}),
        {"trade_date": __import__("datetime").date(2026, 11, 4), "member_tickers": ["NVDA"]},
        "T+1",
        None,
        None,
        client,
    )
    assert out[0] == "仍未知"  # info_ids not in input -> downgrade


@pytest.mark.phase1_blocking
def test_business_verdict_states():
    conn = _conn({})
    out = V.business_verdict(
        conn, {"member_tickers": [None], "trade_date": __import__("datetime").date(2026, 11, 4)}, None, None
    )
    assert out[0] == "数据不足"
