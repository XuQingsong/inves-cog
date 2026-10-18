"""B-012: a ticker stays in scope only when the quote names it or its hypothesis is its own."""

import pytest

pytestmark = pytest.mark.phase1_blocking


def _item(headline):
    return {
        "info_id": "n1",
        "published_at": "2026-10-13T00:00:00+00:00",
        "source_root": "wire",
        "headline": headline,
        "summary": headline,
    }


def _statement(quote, target):
    return {
        "from": "news",
        "to": target,
        "kind": "来源陈述",
        "anchors": [{"info_id": "n1", "source_field": "headline", "quote": quote}],
    }


def _hypothesis(ticker, text="需求外溢到这家公司"):
    return {
        "from": "板块",
        "to": ticker,
        "kind": "声明的假设",
        "hypothesis": text,
        "hypothesis_type": "需求弹性",
        "falsify": {"metric": "剩余收益", "direction": "down", "window": "20个交易日"},
    }


def _prediction(ticker, window="20个交易日"):
    return {"ticker": ticker, "control_basket": "软件", "direction": "down", "window": window}


def _inspect(headline, affected, links, **extra):
    from inves_cog.perception.attribution.links import inspect_links

    candidate = {
        "info_ids": ["n1"],
        "affected": [{"ticker": ticker} for ticker in affected],
        "links": links,
        "竞争解释": [],
        "反证条件": "无",
        **extra,
    }
    return inspect_links(candidate, [_item(headline)], [])


def test_a_coreweave_quote_keeps_only_the_named_ticker():
    headline = "CoreWeave Bond Yield Hits 15%"
    row = _inspect(headline, ["CRWV", "NVDA"], [_statement(headline, "AI云")])
    assert [item["ticker"] for item in row["affected"]] == ["CRWV"]
    assert row["research_gaps"] == [{"ticker": "NVDA", "reason": "材料未点名"}]


def test_a_muse_quote_does_not_keep_meta():
    headline = "Muse is the No. 1 free iPhone app in America"
    row = _inspect(headline, ["META"], [_statement(headline, "META")])
    assert row["affected"] == []
    assert row["research_gaps"] == [{"ticker": "META", "reason": "材料未点名"}]


def test_toshiba_quote_keeps_the_hypothesized_name_only():
    headline = "Toshiba to double hard disk drive supply"
    row = _inspect(
        headline,
        ["STX", "WDC"],
        [_statement(headline, "STX"), _hypothesis("WDC")],
        证伪预测=[_prediction("WDC")],
    )
    assert [item["ticker"] for item in row["affected"]] == ["WDC"]
    assert row["research_gaps"] == [{"ticker": "STX", "reason": "材料未点名"}]


def test_a_dell_quote_keeps_only_dell():
    headline = "Barclays Downgrades Dell Technologies"
    row = _inspect(headline, ["DELL", "SMCI"], [_statement(headline, "服务器")])
    assert [item["ticker"] for item in row["affected"]] == ["DELL"]
    assert row["research_gaps"] == [{"ticker": "SMCI", "reason": "材料未点名"}]


def test_a_deepseek_phrase_keeps_neither_named_chip_stock():
    headline = "DeepSeek R1 was released"
    row = _inspect(headline, ["NVDA", "AMD"], [_statement(headline, "加速芯片")])
    assert row["affected"] == []
    assert row["research_gaps"] == [
        {"ticker": "NVDA", "reason": "材料未点名"},
        {"ticker": "AMD", "reason": "材料未点名"},
    ]


def test_a_netapp_title_does_not_add_a_ticker_the_model_left_out():
    headline = "NetApp lifts its outlook"
    row = _inspect(headline, ["SMCI"], [_statement(headline, "SMCI")])
    assert row["affected"] == []
    assert all(gap["ticker"] != "NTAP" for gap in row["research_gaps"])
    assert "NTAP" not in {item.get("ticker") for item in row["scope_layers"]["预期影响范围"]}


def test_a_shared_hypothesis_and_falsifier_drops_both_tickers():
    text = "同一段需求外溢"
    row = _inspect(
        "No company is named here",
        ["NVDA", "AMD"],
        [_hypothesis("NVDA", text), _hypothesis("AMD", text)],
        证伪预测=[_prediction("NVDA"), _prediction("AMD")],
    )
    assert row["affected"] == []
    assert row["共用假设"] is True
    assert {gap["ticker"] for gap in row["research_gaps"]} == {"NVDA", "AMD"}
    assert {gap["reason"] for gap in row["research_gaps"]} == {"共用假设"}
