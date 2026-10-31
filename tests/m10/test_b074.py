"""B-074 Part A: analyst extras, actions, stock page modules, link scan."""

import json
from datetime import date, datetime, timezone


def _fixture():
    return {
        "quoteSummary": {
            "result": [
                {
                    "earningsTrend": {"trend": [{"period": "0q", "endDate": "x", "earningsEstimate": {"avg": 1.9}}]},
                    "financialData": {
                        "targetMeanPrice": 150.0,
                        "targetLowPrice": 100.0,
                        "targetHighPrice": 200.0,
                        "targetMedianPrice": 145.0,
                        "numberOfAnalystOpinions": 40,
                        "marketCap": 1e12,
                        "forwardPE": 20.5,
                    },
                    "upgradeDowngradeHistory": {
                        "history": [
                            {
                                "epochGradeDate": 1761600000,
                                "firm": "Cantor Fitzgerald",
                                "toGrade": "Overweight",
                                "fromGrade": "Neutral",
                                "action": "up",
                            },
                            {
                                "epochGradeDate": 1761500000,
                                "firm": "UBS",
                                "toGrade": "Neutral",
                                "fromGrade": "Buy",
                                "action": "down",
                            },
                        ]
                    },
                    "recommendationTrend": {
                        "trend": [
                            {"period": "0m", "strongBuy": 20, "buy": 10, "hold": 8, "sell": 1, "strongSell": 0},
                            {"period": "-1m", "strongBuy": 18, "buy": 12, "hold": 9, "sell": 1, "strongSell": 0},
                        ]
                    },
                }
            ],
            "error": None,
        }
    }


def test_analyst_extras_from_quote_summary():
    from inves_cog.ingest.fundamentals.providers import tables_from_yahoo_json

    tables = tables_from_yahoo_json(_fixture())
    assert tables["analyst"]["targetMeanPrice"] == 150.0
    assert tables["analyst"]["numberOfAnalystOpinions"] == 40
    assert tables["analyst"]["recommendationTrend"]["trend"][0]["strongBuy"] == 20
    assert len(tables["upgrade_history"]) == 2


def test_put_analyst_actions_rows():
    from inves_cog.ingest.earnings_data import put_analyst_actions

    class C:
        def __init__(self):
            self.calls = []

        def execute(self, sql, args):
            self.calls.append((sql, args))
            return self

    c = C()
    put_analyst_actions(
        c,
        "NVDA",
        {"raw": {"upgrade_history": _fixture()["quoteSummary"]["result"][0]["upgradeDowngradeHistory"]["history"]}},
    )
    assert len(c.calls) == 2
    assert c.calls[0][1][2] == "Cantor Fitzgerald" and c.calls[0][1][3] == "up"


def test_actions_module_render():
    from inves_cog.web.investor_html import _actions_module

    rows = [
        {
            "action_date": date(2026, 10, 30),
            "firm": "UBS",
            "action": "down",
            "from_grade": "Buy",
            "to_grade": "Neutral",
            "current_pt": 80,
            "prior_pt": 120,
            "source": "yahoo",
        },
        {
            "action_date": date(2026, 10, 28),
            "firm": "Cantor",
            "action": "up",
            "from_grade": "Neutral",
            "to_grade": "Overweight",
            "current_pt": 210,
            "prior_pt": None,
            "source": "yahoo",
        },
    ]
    html = _actions_module({"analyst_actions": rows})
    assert "↓" in html and "↑" in html and "前值暂缺" in html and "UBS" in html
    empty = _actions_module({"analyst_actions": []})
    assert "尚未采集" in empty


def test_confirmed_events_highlight_and_links():
    from inves_cog.web.investor_html import _confirmed_events

    payload = {
        "news_events": [
            {
                "importance": 80,
                "kind": "guidance",
                "headline": "Cuts Outlook",
                "url": "https://x/1",
                "published_at": "2026-10-29",
            }
        ]
    }
    html = _confirmed_events(payload)
    assert 'target="_blank"' in html and 'rel="noopener"' in html and "Cuts Outlook" in html


def test_ratings_distribution_render():
    from inves_cog.web.investor_html import _ratings_module

    payload = {
        "analyst": {
            "trend": {
                "trend": [
                    {"period": "0m", "strongBuy": 20, "buy": 10, "hold": 8, "sell": 1, "strongSell": 0},
                    {"period": "-1m", "strongBuy": 18, "buy": 12, "hold": 9, "sell": 1, "strongSell": 0},
                ]
            }
        }
    }
    html = _ratings_module(payload)
    assert "强买" in html and "上月 18" in html


def test_key_stats_and_earnings_hist():
    from inves_cog.web.investor_html import _key_stats, _earnings_hist_module

    p = {
        "analyst": {
            "market_cap": 2e11,
            "forward_pe": 20.5,
            "pt_mean": 150,
            "pt_low": 100,
            "pt_high": 200,
            "opinions": 40,
        },
        "bar_stats": {"lo52": 60, "hi52": 100, "vol": 2e6, "vol_ratio": 2.0, "next_earnings": "2026-11-03"},
    }
    html = _key_stats(p)
    assert "200.0B" in html and "150" in html and "40 家" in html
    hist = _earnings_hist_module(
        {"earnings_hist": [{"q": "2026-09-30", "est": 1.0, "act": 1.1, "gap": 10.0, "next_day": 0.02}]}
    )
    assert "+10%" in hist and "次日涨跌" in hist
