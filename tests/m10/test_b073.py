"""B-073 UI redesign: severity badges, ticker links, search, price, chart."""

from datetime import date, datetime, timezone


def test_severity_levels():
    from inves_cog.web.investor_html import _severity

    assert _severity({"peak_z": -5.4, "status": "active"}) == ("sev-major", "重大")
    assert _severity({"peak_z": -3.1, "status": "active"}) == ("sev-watch", "关注")
    assert _severity({"gap": 42, "status": "active"}) == ("sev-major", "重大")
    assert _severity({"status": "faded"}) == ("sev-info", "一般")


def test_ticker_links_in_live_rows():
    from inves_cog.web.investor_html import _live_module

    row = {
        "scope": "stock",
        "subject": "INTC",
        "last_ret": -0.31,
        "peak_ret": -0.31,
        "peak_z": -6.4,
        "first_seen_at": datetime(2026, 10, 30, 14, 9, tzinfo=timezone.utc),
        "cause_event_id": "INTC:guidance:2026-10-29",
        "trade_date": date(2026, 10, 30),
        "cause_headline": "x",
        "cause_kind": "guidance",
        "cause_lag_minutes": 45,
        "status": "active",
    }
    html = _live_module({"news_modules": {"live": [row], "earnings_cards": []}})
    assert 'href="/s/INTC"' in html and "重大" in html


def test_ticker_links_in_earnings_module():
    from inves_cog.web.investor_html import _earnings_cards_module

    row = {
        "ticker": "AMD",
        "report_date": "2026-11-03",
        "report_time": "post",
        "stage": "upcoming",
        "card": {
            "consensus": {"eps": 1.94, "rev": 13e9, "as_of": "2026-10-30"},
            "implied_move": {"straddle_pct": 0.089, "note": "x"},
        },
        "missing": [],
    }
    html = _earnings_cards_module({"news_modules": {"earnings_cards": [row], "live": []}})
    assert 'href="/s/AMD"' in html and "8.9%" in html


def test_chart_svg_marks_and_ma():
    from inves_cog.web.investor_html import _chart_svg

    rows = [{"d": f"2026-10-{d:02d}", "c": 90 + d, "v": 1} for d in range(1, 25)]
    payload = {"chart": rows, "earnings_marks": [{"d": "2026-10-20", "t": "post"}], "anomaly_marks": ["2026-10-21"]}
    svg = _chart_svg(payload)
    assert "polyline" in svg and "财报" in svg and "异常" in svg


def test_price_now_prefers_snapshot_then_close():
    from inves_cog.web.stock_brief import _price_now

    bars = [
        {"trade_date": date(2026, 10, 29), "close": 95.0, "volume": 1},
        {"trade_date": date(2026, 10, 30), "close": 87.0, "volume": 1},
    ]
    pn = _price_now(None, "X", date(2026, 10, 30), bars, {"last": 75.0, "as_of": "x", "session": "post"})
    assert pn["source"] == "快照" and pn["px"] == 75.0
    pn = _price_now(None, "X", date(2026, 10, 30), bars, None)
    assert pn["source"] == "收盘" and pn["px"] == 87.0 and abs(pn["ret"] - (87 / 95 - 1)) < 1e-9


def test_tracked_stock_page_order():
    from inves_cog.web.investor_html import _stock

    rows = [{"d": f"2026-09-{d:02d}", "c": 90 + d, "v": 1} for d in range(1, 25)]
    payload = {
        "page": "/s/INTC",
        "symbol": "INTC",
        "oneliner": "x",
        "trend": {},
        "position": {"kind": "other"},
        "price_now": {"px": 75.0, "ret": -0.286, "session": "close", "at": "2026-10-30", "source": "收盘"},
        "bar_stats": {
            "day_hi": 90,
            "day_lo": 74,
            "hi52": 100,
            "lo52": 60,
            "pos52": 37.5,
            "vol": 1e6,
            "vol_ratio": 2.1,
            "next_earnings": "2026-11-03",
        },
        "chart": rows,
        "earnings_marks": [{"d": "2026-09-20", "t": "post"}],
        "anomaly_marks": ["2026-09-21"],
        "intraday_series": [{"t": "t", "p": 80}, {"t": "u", "p": 79}],
        "peers": ([{"ticker": "ARM", "px": 206.0, "ret": -0.1, "ret5": -0.02}], "cpu_pc"),
        "news_modules": {
            "live": [
                {
                    "subject": "INTC",
                    "scope": "stock",
                    "peak_ret": -0.31,
                    "cause_kind": "guidance",
                    "cause_headline": "h",
                    "status": "active",
                }
            ],
            "earnings_cards": [],
        },
    }
    html = _stock(payload)
    order = ["px-big", "chart-btns", "dchart", "今天发生了什么", "同环节", "基本面与估值"]
    pos = [html.index(k) for k in order]
    assert pos == sorted(pos), pos
