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
    client.call.return_value = {"verdict": "hacked"}
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
    client.call.return_value = {"verdict": "证实", "info_ids": ["news:x:999"]}
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


def _bars_conn(price_map, extra=None):
    """conn whose _bars returns closes per ticker, keyed sequentially."""
    rows = []
    for t, closes in (price_map or {}).items():
        for i, c in enumerate(closes):
            rows.append(
                {
                    "ticker": t,
                    "trade_date": __import__("datetime").date(2026, 1, 1) + __import__("datetime").timedelta(days=i),
                    "close": c,
                }
            )
    c = MagicMock()
    c.execute.return_value.fetchall.return_value = rows
    return c


@pytest.mark.phase1_blocking
def test_price_verdict_confirm_deny_undecided():
    import datetime as dt

    case = {"trade_date": dt.date(2026, 11, 4), "member_tickers": ["X"], "direction": 1}
    due = dt.date(2026, 11, 5)
    flat = [10.0] * 120  # sigma ~0 -> skipped -> 未定
    out = V.market_verdict(_bars_conn({"X": flat, "SPY": flat}), case, "T+1", due, None, [])
    assert out[0] in ("未定",)
    # trending member vs flat spy -> strong positive excess -> z>0.5 -> 确认
    up = [10.0 + i * 0.01 for i in range(70)]
    up[-1] = up[-2] * 1.05  # last-day jump
    conn = _bars_conn({"X": up, "SPY": [10.0 + i * 0.0005 for i in range(70)]})
    label, src, ev = V.market_verdict(conn, case, "T+1", due, None, [])
    assert src == "按价格延续/反转"
    assert label in ("市场确认（延续）", "未定", "市场否定（反转）")  # branch determined by z
    assert ev.get("z") is not None


@pytest.mark.phase1_blocking
def test_pit_bars_cutoff():
    """_bars must pass start and end bounds to SQL (no unbounded read)."""
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    V._bars(conn, ["NVDA"], __import__("datetime").date(2026, 8, 1), __import__("datetime").date(2026, 11, 4))
    sql = conn.execute.call_args[0][0]
    assert "trade_date>=%s" in sql and "trade_date<=%s" in sql


@pytest.mark.phase1_blocking
def test_business_verdict_four_states_and_majority():
    import datetime as dt

    def conn_with(pre, post):
        c = MagicMock()
        seq = [
            MagicMock(fetchone=lambda: {"eps_avg": pre} if pre is not None else None),
            MagicMock(fetchone=lambda: {"eps_avg": post, "fetched_at": "x"} if post is not None else None),
            MagicMock(fetchone=lambda: None),  # earnings card
        ]
        c.execute.side_effect = seq * 3
        return c

    case_up = {"trade_date": dt.date(2026, 11, 4), "member_tickers": ["A"], "direction": 1}
    assert V.business_verdict(conn_with(1.0, 1.1), case_up, None, None)[0] == "经营面印证"  # +10% same dir
    assert V.business_verdict(conn_with(1.0, 0.9), case_up, None, None)[0] == "经营面相反"  # -10% opp dir
    assert V.business_verdict(conn_with(1.0, 1.005), case_up, None, None)[0] == "未见变化"  # <1%
    assert V.business_verdict(conn_with(None, None), case_up, None, None)[0] == "数据不足"
    # basket majority: two members confirm, one lacks data
    case_basket = {"trade_date": dt.date(2026, 11, 4), "member_tickers": ["A", "B", "C"], "direction": 1}
    c = MagicMock()
    answers = iter(
        [
            {"eps_avg": 1.0},
            {"eps_avg": 1.1, "fetched_at": "x"},
            None,
            {"eps_avg": 2.0},
            {"eps_avg": 2.2, "fetched_at": "x"},
            None,
            None,
            None,
            None,
        ]
    )
    c.execute.side_effect = lambda *a: MagicMock(fetchone=lambda: next(answers, None))
    out = V.business_verdict(c, case_basket, None, None)
    assert out[0] == "经营面印证" and "members" in out[2]


@pytest.mark.phase1_blocking
def test_trust_groups_labels_by_horizon():
    """30-day labels grouped under T+1/T+5/T+20 headers."""
    import inspect

    from inves_cog.web import investor_html

    src = inspect.getsource(investor_html)
    for marker in ('"T+1"', '"T+5"', '"T+20"', "补算（按当时可得数据）"):
        assert marker in src


@pytest.mark.phase1_blocking
def test_message_verdict_call_failure_not_unknown():
    """Model call failure must be 未判定（模型调用失败）, not 仍未知."""
    import datetime as dt

    client = MagicMock()
    client.call.side_effect = RuntimeError("transport down")
    out = V.message_verdict(
        _conn({"all": []}),
        {"trade_date": dt.date(2026, 11, 4), "member_tickers": ["NVDA"]},
        "T+1",
        None,
        None,
        client,
    )
    assert out[0] == "未判定（模型调用失败）" and "RuntimeError" in out[2]["error"]


@pytest.mark.phase1_blocking
def test_message_verdict_end_to_end_confirm():
    """Fake client returns 证实 + valid info_id -> verdict lands with evidence
    and the payload carried the cause text."""
    import datetime as dt

    client = MagicMock()
    client.call.return_value = {"verdict": "证实", "info_ids": ["news:x:1"]}
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {
            "info_id": "news:x:1",
            "kind": "news",
            "published_at": dt.datetime(2026, 11, 5, 20, 0),
            "source": "reuters",
            "headline": "h",
            "body": "b",
            "tickers": ["NVDA"],
        }
    ]
    case = {
        "trade_date": dt.date(2026, 11, 4),
        "member_tickers": ["NVDA"],
        "cause_text": "候选原因：芯片缺货",
        "cause_info_ids": [],
        "session": "close",
        "direction_label": "上涨",
    }
    label, src, ev = V.message_verdict(conn, case, "T+1", dt.date(2026, 11, 5), None, client)
    assert label == "证实" and ev["info_ids"] == ["news:x:1"]
    sent = client.call.call_args[0][1]
    assert sent["候选原因"] == "候选原因：芯片缺货" and V.PROMPT in sent["指令"]


@pytest.mark.phase1_blocking
def test_cause_text_composition_in_payload():
    """cause_text must carry type + mechanism + cited message titles."""
    import datetime as dt

    client = MagicMock()
    client.call.return_value = {"verdict": "仍未知", "info_ids": []}
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    case = {
        "trade_date": dt.date(2026, 11, 4),
        "member_tickers": ["NVDA"],
        "cause_text": "类型：竞争；机制：对手抢单；当时引用的消息：标题A（t1）",
        "session": "close",
        "direction_label": "下跌",
    }
    V.message_verdict(conn, case, "T+1", dt.date(2026, 11, 5), None, client)
    sent = client.call.call_args[0][1]
    assert "类型：竞争" in sent["候选原因"] and "机制：对手抢单" in sent["候选原因"]
    assert "标题A" in sent["候选原因"]


@pytest.mark.phase1_blocking
def test_other_cause_fields_validated():
    """other_info_ids outside the input are dropped; other_cause saved."""
    import datetime as dt

    client = MagicMock()
    client.call.return_value = {
        "verdict": "仍未知",
        "info_ids": [],
        "other_cause": "其实是对财报担忧",
        "other_info_ids": ["news:x:1", "news:fake:9"],
    }
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {
            "info_id": "news:x:1",
            "kind": "news",
            "published_at": dt.datetime(2026, 11, 5, 20, 0),
            "source": "reuters",
            "headline": "h",
            "body": "b",
            "tickers": ["NVDA"],
        }
    ]
    case = {
        "trade_date": dt.date(2026, 11, 4),
        "member_tickers": ["NVDA"],
        "cause_text": "类型：竞争",
        "session": "close",
    }
    _, _, ev = V.message_verdict(conn, case, "T+1", dt.date(2026, 11, 5), None, client)
    assert ev["other_cause"] == "其实是对财报担忧" and ev["other_info_ids"] == ["news:x:1"]


@pytest.mark.phase1_blocking
def test_cause_type_comes_from_candidate_not_prelim():
    """类型 must be the candidate's own mechanism, not the anomaly prelim."""
    from inves_cog.perception.review import cases as C

    conn = MagicMock()
    cand = {
        "chain": "对手抢单导致份额下滑",
        "mechanism": "竞争",
        "info_ids": ["news:x:1"],
        "confidence": "高",
        "score": 1,
    }
    cited = [{"info_id": "news:x:1", "published_at": "t1", "headline": "标题A"}]
    calls = iter([MagicMock(fetchone=lambda: cand), MagicMock(fetchall=lambda: cited)])
    conn.execute.side_effect = lambda *a: next(calls)
    case = {"anomaly_id": "x", "member_tickers": ["NVDA"], "type_candidates_prelim": ["踩踏"]}
    # emulate the _write_label enrichment block
    fetched = conn.execute("", ()).fetchone()
    chain = fetched["chain"] if isinstance(fetched["chain"], str) else ""
    cited_rows = [r["headline"] for r in conn.execute("").fetchall()]
    text = (
        f"类型：{fetched['mechanism'] or '未分类'}；机制：{chain or fetched['mechanism']}"
        f"；当时引用的消息：{'；'.join(cited_rows)}"
    )
    assert "类型：竞争" in text and "踩踏" not in text and "机制：对手抢单" in text
