"""B-074 Part B: market state, grouped highlights, tape tiers, link scan."""


def test_market_state_band_classification(monkeypatch):
    from datetime import date
    import inves_cog.web.brief as brief

    def fake(snaps, prev, sig):
        monkeypatch.setattr(brief, "_snap_rows", lambda c, ts: {t: snaps[t] for t in ts if t in snaps})
        monkeypatch.setattr(brief, "_prev_snap", lambda c, t, a: prev[t])
        monkeypatch.setattr(brief, "_sigma20", lambda c, d, t: sig[t])

    payload = {"advancers": 100, "decliners": 400, "leaders_down": [{"name": "cpu"}], "leaders_up": []}
    live = [{"scope": "basket", "cause_event_id": "e1", "cause_headline": "INTC 指引"}]
    fake(
        {"SPY": {"last": 98.2, "as_of": "x"}, "QQQ": {"last": 96.5, "as_of": "x"}},
        {"SPY": 100, "QQQ": 100}, {"SPY": 0.01, "QQQ": 0.01},
    )
    st = brief._market_state(None, date(2026, 10, 30), payload, live)
    assert st["band"] == "剧烈" and "科技股领跌" in st["sentence"] and "INTC 指引" in st["sentence"]
    fake(
        {"SPY": {"last": 100.2, "as_of": "x"}, "QQQ": {"last": 100.3, "as_of": "x"}},
        {"SPY": 100, "QQQ": 100}, {"SPY": 0.01, "QQQ": 0.01},
    )
    st = brief._market_state(None, date(2026, 10, 30), payload, [])
    assert st["band"] == "平静" and "原因未明" not in st["sentence"]


def test_hl_grouped_merges_by_cause():
    from inves_cog.web.brief import _hl_grouped

    live = [
        {"scope": "stock", "subject": "INTC", "cause_event_id": "INTC:g", "peak_z": -6, "peak_ret": -0.31, "status": "active"},
        {"scope": "basket", "subject": "cpu", "cause_event_id": "INTC:g", "peak_z": -5, "peak_ret": -0.17, "basket_name": "CPU", "status": "active"},
        {"scope": "stock", "subject": "AMD", "cause_event_id": None, "peak_z": -3, "peak_ret": -0.10, "status": "active"},
    ]
    items = _hl_grouped(live, ["AMD"])
    assert len(items) == 2
    merged = next(i for i in items if len(i["members"]) == 2)
    assert len(merged["members"]) == 2


def test_tape_tier_assignment():
    from inves_cog.web.investor_html import _tape_module

    payload = {"tape": [{"sym": "SPY", "name": "标普", "px": 660.0, "ret": -0.031, "mult": 2.4},
                        {"sym": "^TNX", "name": "10年期", "px": 4.1, "chg_bp": 12, "mult": 0.4, "ret": None}]}
    html = _tape_module(payload)
    assert "tape-track" in html and "t4n" in html and "标普" in html
    assert "bp" in html


def test_news_links_blank():
    from inves_cog.web.investor_html import _market3_module

    payload = {"market3": {"groups": {"美股指数": [{"sym": "SPY", "name": "标普", "px": 1, "ret": 0.01}]},
                           "daily": {}, "intraday": {}},
               "feed_rel": [{"rel": "5 分钟前", "title": "X", "url": "https://a/b"}]}
    html = _market3_module(payload)
    assert 'target="_blank"' in html and 'rel="noopener"' in html and "5 分钟前" in html
