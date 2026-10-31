"""B-074 Part A: analyst extras, actions, stock page modules, link scan."""

from datetime import date


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
    # yfinance frame keys + price targets; old rows skipped; raw is stripped
    snap = {
        "raw": {
            "upgrade_history": [
                {
                    "Firm": "Goldman Sachs",
                    "ToGrade": "Neutral",
                    "FromGrade": "Buy",
                    "Action": "down",
                    "priceTargetAction": "Lowers",
                    "currentPriceTarget": 80.0,
                    "priorPriceTarget": 120.0,
                    "epochGradeDate": 1793318400,
                },
                {"Firm": "Old", "Action": "main", "epochGradeDate": 946684800},
            ]
        }
    }
    c2 = C()
    assert put_analyst_actions(c2, "INTC", snap) == 1
    args = c2.calls[0][1]
    assert args[2] == "Goldman Sachs" and args[3] == "down" and args[7] == 120.0 and args[8] == 80.0
    assert "upgrade_history" not in snap["raw"]


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
    assert "$120 → " in html and "$80 ↓" in html and 'class="down">$80' in html
    assert "Buy → Neutral" in html and "前值暂缺 → $210" in html and "UBS" in html
    assert "上调 0 家 · 下调 1 家" in html
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
    from inves_cog.web.investor_html import _earnings_hist_module, _key_stats

    p = {
        "analyst": {
            "market_cap": 2e11,
            "forward_pe": 20.5,
            "pt_mean": 150,
            "pt_low": 100,
            "pt_high": 200,
            "opinions": 40,
        },
        "bar_stats": {"lo52": 60, "hi52": 100, "vol": 2e6, "vol_ratio": 2.0},
        "next_report": {"report_date": "2026-11-03", "time": "post"},
    }
    html = _key_stats(p)
    assert "200.0B" in html and "150" in html and "40 家" in html and "2026-11-03 盘后" in html
    # column fallbacks when raw.analyst is absent
    html = _key_stats({"analyst": {"pt_mean_col": 328.95, "coverage": 51.0, "eps_cq": 2.47325}})
    assert "$328.95" in html and "51 家" in html and "2.47" in html
    hist = _earnings_hist_module(
        {
            "earnings_hist": [
                {"q": "2026-09-30", "est": 1.0, "act": 1.1, "gap": 10.0, "next_day": None, "report_date": None}
            ]
        }
    )
    assert "+10.0%" in hist and "次日涨跌" in hist and "日期未知" in hist and "—" in hist
