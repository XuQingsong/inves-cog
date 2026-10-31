"""B-076: cause label, live 现价 header, confirmed events payload, feed filter."""


def test_cause_label_from_live_row():
    from inves_cog.web.brief import _cause_label

    r = {
        "cause_event_id": "INTC:g",
        "cause_subject": "INTC",
        "cause_kind": "guidance",
        "cause_facts": {"guide_gap_pct": -42.1},
    }
    assert _cause_label(r) == "INTC 指引（指引低于预期 42%）"
    r2 = {"cause_event_id": "AMD:e", "cause_subject": "AMD", "cause_kind": "earnings_result", "cause_facts": {}}
    assert _cause_label(r2) == "AMD 财报"
    assert _cause_label({"cause_event_id": None}) == ""


def test_live_table_has_price_header():
    from inves_cog.web.investor_html import _live_module

    payload = {
        "et_now": "x",
        "news_modules": {
            "live": [
                {
                    "scope": "stock",
                    "subject": "INTC",
                    "peak_ret": -0.3,
                    "status": "active",
                    "cause_event_id": "e1",
                    "cause_kind": "guidance",
                    "cause_label": "INTC 指引（指引低于预期 42%）",
                    "cause_headline": "Intel cuts",
                    "last_px": 65.7,
                    "first_seen_at": None,
                },
            ]
        },
    }
    html = _live_module(payload)
    assert "<th>现价</th>" in html and "INTC 指引（指引低于预期 42%）" in html
    assert 'title="Intel cuts"' in html


def test_market3_news_filters_out_universe():
    from inves_cog.web.investor_html import _market3_module

    def n(ticks, title):
        return {
            "headline": title,
            "url": "https://x",
            "published_at": None,
            "rule": {"primary_tickers": ticks, "held": False, "macro": False},
        }

    payload = {
        "market3": {
            "groups": {"美股指数": [{"sym": "SPY", "name": "x", "px": 1, "ret": 0}]},
            "daily": {},
            "intraday": {},
        },
        "held_tickers": ["AMD"],
        "ticker_scope": ["AMD", "INTC"],
        "news_modules": {"feed": [n(["AMD"], "in-scope"), n(["ZZZZ"], "out-scope"), n([], "macro-less")]},
    }
    html = _market3_module(payload)
    assert "in-scope" in html and "out-scope" not in html


def test_confirmed_events_render_when_payload_present():
    from inves_cog.web.investor_html import _confirmed_events

    assert _confirmed_events({"news_events": []}) == ""
    html = _confirmed_events(
        {
            "news_events": [
                {
                    "kind": "earnings_result",
                    "importance": 80,
                    "headline": "X",
                    "url": "https://u",
                    "published_at": "2026-10-29T20:00",
                },
                {"kind": "other", "importance": 50, "headline": "low"},
            ]
        }
    )
    assert "已确认事件" in html and 'target="_blank"' in html and "low" not in html


def test_next_earn_same_source():
    from inves_cog.web.investor_html import _next_earn

    assert "暂缺" in _next_earn({"next_earnings": None, "bar_stats": {}})
    out = _next_earn({"next_earnings": None, "bar_stats": {"next_earnings": "2026-11-17"}})
    assert "2026-11-17" in out


def test_earnings_hist_sorted_desc_and_single_card():
    from inves_cog.web.investor_html import _earnings_hist_module

    rows = [
        {"q": "2026-02-28", "act": 1.0},
        {"q": "2026-08-31", "act": 1.1},
        {"q": "2025-11-30", "act": 0.9},
        {"q": "2026-05-31", "act": 1.05},
    ]
    html = _earnings_hist_module({"earnings_hist": rows})
    assert html.count('class="card sec"') == 1
    assert html.index("2026-08-31") < html.index("2026-05-31") < html.index("2026-02-28") < html.index("2025-11-30")


def test_segment_label_chinese():
    from inves_cog.web.investor_html import _peers_module

    html = _peers_module({"peers": ([{"ticker": "AMD", "px": 1.0, "ret": 0.01}], "compute")})
    assert "环节：计算链" in html and "compute" not in html.split("环节：")[1][:12]


def test_key_stats_no_target_price():
    from inves_cog.web.investor_html import _key_stats

    html = _key_stats({"analyst": {"pt_mean": 200, "pt_low": 100, "pt_high": 300}, "bar_stats": {"next_earnings": "x"}})
    assert "目标价" not in html


def test_next_earn_from_next_report():
    from inves_cog.web.investor_html import _next_earn

    out = _next_earn({"next_earnings": None, "next_report": {"report_date": "2026-11-17", "time": "post"}})
    assert "2026-11-17" in out and "盘后" in out
    out = _next_earn({"next_earnings": None, "next_report": {"report_date": "2026-11-17", "time": "pre"}})
    assert "盘前" in out
