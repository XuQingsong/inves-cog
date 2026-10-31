"""B-074 Part B: market state, grouped highlights, tape tiers, news links."""

from datetime import date


def _series(values, end=date(2026, 10, 30)):
    from datetime import timedelta

    return [(end - timedelta(days=len(values) - 1 - i), v) for i, v in enumerate(values)]


def test_market_state_band_classification(monkeypatch):
    import inves_cog.web.brief as brief

    calm = [100 + (0.5 if i % 2 else -0.5) for i in range(21)]

    def fake(spy_last, qqq_last):
        data = {"SPY": calm + [calm[-1] * (1 + spy_last)], "QQQ": calm + [calm[-1] * (1 + qqq_last)]}
        monkeypatch.setattr(brief, "_close_series", lambda c, t, d, n=22: _series(data[t]))

    payload = {"advancers": 100, "decliners": 400, "leaders_down": [{"name": "CPU"}], "leaders_up": [{"name": "能源"}]}
    live = [{"scope": "basket", "cause_event_id": "e1", "cause_headline": "INTC 指引", "cause_label": "INTC 指引"}]
    fake(-0.018, -0.035)
    st = brief._market_state(None, date(2026, 10, 30), payload, live)
    assert st["band"] == "剧烈" and "科技股领跌" in st["sentence"] and "INTC 指引" in st["sentence"]
    assert "集中在CPU" in st["sentence"] and "能源逆势上涨" in st["sentence"]
    fake(0.0005, 0.001)
    st = brief._market_state(None, date(2026, 10, 30), payload, [])
    assert st["band"] == "平静" and "窄幅整理" in st["sentence"] and "原因未明" not in st["sentence"]


def test_quote_yields_in_bp(monkeypatch):
    import inves_cog.web.brief as brief

    vals = [4.0 + (0.02 if i % 2 else -0.02) for i in range(21)] + [4.12]
    monkeypatch.setattr(brief, "_close_series", lambda c, t, d, n=22: _series(vals))
    q = brief._quote(None, "^TNX", date(2026, 10, 30))
    assert q["ret"] is None and round(q["chg_bp"]) == 14 and q["mult"] > 2


def test_hl_grouped_merges_by_cause_and_ranks_market_first():
    from inves_cog.web.brief import _hl_grouped

    live = [
        {
            "scope": "stock",
            "subject": "INTC",
            "cause_event_id": "INTC:g",
            "peak_z": -6,
            "peak_ret": -0.31,
            "status": "active",
        },
        {
            "scope": "basket",
            "subject": "cpu",
            "cause_event_id": "INTC:g",
            "peak_z": -5,
            "peak_ret": -0.17,
            "basket_name": "CPU",
            "status": "active",
        },
        {
            "scope": "market",
            "subject": "QQQ",
            "cause_event_id": "INTC:g",
            "peak_z": None,
            "peak_ret": -0.044,
            "status": "active",
        },
        {
            "scope": "stock",
            "subject": "STX",
            "cause_event_id": None,
            "peak_z": -5.5,
            "peak_ret": -0.10,
            "status": "active",
        },
        {
            "scope": "basket",
            "subject": "ai",
            "cause_event_id": None,
            "peak_z": -3,
            "peak_ret": -0.09,
            "members": {"AMD": -0.1},
            "status": "faded",
        },
    ]
    items = _hl_grouped(live, ["AMD"])
    assert items[0]["why"] == "大盘层面异常" and len(items[0]["members"]) == 3 and items[0]["subject"] == "INTC"
    assert items[-1]["subject"] == "ai"  # faded ranks last


def test_tape_tier_assignment():
    from inves_cog.web.investor_html import _tape_module

    payload = {
        "tape": [
            {"sym": "SPY", "name": "标普", "px": 660.0, "ret": -0.031, "mult": 2.4},
            {"sym": "^TNX", "name": "10年期", "px": 4.1, "chg_bp": 12, "mult": 0.4, "ret": None},
        ]
    }
    html = _tape_module(payload)
    assert "tape-track" in html and "t4n strong" in html and "+12bp" in html and "4.10%" in html


def test_market3_news_links_blank():
    from inves_cog.web.investor_html import _market3_module

    payload = {
        "market3": {
            "groups": {"美股指数": [{"sym": "SPY", "name": "标普", "px": 1, "ret": 0.01, "mult": 1}]},
            "daily": {},
            "intraday": {},
        },
        "news_modules": {"feed": [{"title": "X", "url": "https://a/b", "published": None}]},
    }
    html = _market3_module(payload)
    assert 'target="_blank"' in html and 'rel="noopener"' in html and "lightweight-charts.js" in html
