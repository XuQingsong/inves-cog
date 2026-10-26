"""B-063: news rules layer, technicals, VIX fallback — pure unit tests (no DB)."""

from datetime import datetime, timedelta, timezone

import pytest

from inves_cog.perception.news.rules import classify, rank_day, theme_of
from inves_cog.perception.technical import technicals, wilder_rsi

NY = timezone(timedelta(hours=-4))
POOL = {"NVDA", "BE", "JNJ", "SKHY", "BEZ", "LRCX", "MU", "META", "AAPL"}
HELD = {"NVDA", "BE"}


def _classify(headline, tickers, pool=POOL, held=HELD):
    return classify(headline, tickers, pool, held)


def test_earnings_tag():
    assert "财报" in _classify("Autoliv Reports Third Quarter 2026 Financial Results", ["NVDA"]).tags
    assert "财报" in _classify("Apple Q3 Results Beat on Revenue", ["AAPL"]).tags
    assert "财报" not in _classify("Apple Store Opens in Tokyo", ["AAPL"]).tags


def test_rating_tiers():
    strong = _classify("Bernstein Upgrades Bloom Energy to Buy", ["BE"])
    weak = _classify("Needham Maintains Buy on Lam Research, Lowers Price Target to $290", ["LRCX"])
    assert strong.importance - weak.importance >= 2
    assert weak.weak_rating_only and not strong.weak_rating_only
    assert "评级" in weak.tags and "评级" in strong.tags


def test_ma_excludes_partnership():
    r = _classify("Sazerac Launches Acceptance Period for Takeover Offer of Berentzen", ["BEZ"])
    assert "并购" in r.tags and "产品合作" not in r.tags


def test_primary_tickers_filter():
    r = _classify(
        "NVDA Drives Korea Chip Selloff to 'Capitulation' Levels",
        ["META", "MU", "NVDA", "SKHY", "AAA", "BBB"],
    )
    assert "META" not in r.primary_tickers and "NVDA" in r.primary_tickers


def test_dedup():
    ts = datetime(2026, 10, 23, 9, 0, tzinfo=NY)
    items = [
        {
            "info_id": i,
            "headline": "NVDA beats revenue estimates",
            "tickers": ["NVDA"],
            "published_at": ts + timedelta(minutes=i),
            "first_seen_at": ts + timedelta(minutes=i),
        }
        for i in range(3)
    ]
    ranked = rank_day(items, POOL, HELD, datetime(2026, 10, 23, tzinfo=NY).date())
    assert len(ranked) == 1 and ranked[0]["info_id"] == 0


def test_late_flag():
    pub = datetime(2026, 10, 23, 8, 0, tzinfo=NY)
    late = {
        "info_id": 1,
        "headline": "NVDA update",
        "tickers": ["NVDA"],
        "published_at": pub,
        "first_seen_at": datetime(2026, 10, 24, 9, 0, tzinfo=NY),
    }
    fresh = {"info_id": 2, "headline": "NVDA news", "tickers": ["NVDA"], "published_at": pub, "first_seen_at": pub}
    ranked = rank_day([late, fresh], POOL, HELD, pub.date())
    by_id = {n["info_id"]: n for n in ranked}
    assert by_id[1]["late"] and not by_id[2]["late"]


def test_theme_of():
    item = {"headline": "NVDA and META chips rally", "rule": _classify("NVDA and META chips rally", ["META", "NVDA"])}
    assert theme_of(item, {"NVDA": "芯片", "META": "互联网"}, HELD) == "芯片"


def test_technicals_shapes():
    up = [100 + i * 0.5 for i in range(260)]
    assert technicals(up, None)["shape"] == "多头排列"
    down = [200 - i * 0.5 for i in range(260)]
    t = technicals(down, None)
    assert t["shape"] in ("空头排列", "空头反弹", "震荡")
    assert t["rsi"] < 40
    assert technicals([100] * 10, None)["shape"] == "数据不足"


def test_rsi_wilder():
    gains = [100 + i for i in range(30)]
    assert wilder_rsi(gains) == 100.0
    mixed = [100 + ((-1) ** i) for i in range(30)]
    r = wilder_rsi(mixed)
    assert r is not None and 40 <= r <= 60


def test_engine_vix_series_order():
    """market_row VIX: CBOE wins, Yahoo only when CBOE missing; VIX3M Yahoo fallback."""
    pd = pytest.importorskip("pandas")
    from datetime import date as _d

    from inves_cog.marketstate.engine import market_row

    day = _d(2037, 6, 15)
    returns = pd.DataFrame({"SPY": [0.0]}, index=[day])
    macro = [
        {"series_id": "VIX_YAHOO", "observation_date": day, "value": 20.0},
        {"series_id": "VIXCLS", "observation_date": day, "value": 21.0},
        {"series_id": "VIX3M_YAHOO", "observation_date": day, "value": 22.0},
    ]
    row = market_row(returns, macro, [], [], day=day)
    assert row["vix"] == 20.0 and row["vix3m"] == 22.0
    macro.append({"series_id": "VIX_CBOE", "observation_date": day, "value": 19.0})
    row = market_row(returns, macro, [], [], day=day)
    assert row["vix"] == 19.0


def test_audit_gap_headlines():
    """Real headlines the 200-row audit flagged, now covered (B-063 follow-up)."""
    assert "评级" in _classify("BofA Securities Maintains Buy Rating on Seagate Technology", ["STX"]).tags
    assert "评级" in _classify("Truist Maintains Outperform on Bloom Energy", ["BE"]).tags
    assert "指引" in _classify("Sees Q4 Sales $1.2B vs $1.1B Est", ["AAPL"]).tags
    assert "指引" in _classify("Sees Q2 Adj EPS $0.30", ["AAPL"]).tags
    assert "指引" in _classify("Preliminary Third Quarter Update Beats Estimates", ["MU"]).tags
    assert "指引" in _classify("Chipmaker Seen Growing 25%-30% In 2027", ["NVDA"]).tags
    assert "指引" in _classify("Q4 Capex Implied $14B", ["MSFT"]).tags
    assert "指引" not in _classify("Analyst Says Outlook Is 'Grim' for Retail", ["M"]).tags
    assert "财报" in _classify("Meta Posts Strong Q3", ["META"]).tags
    assert "财报" in _classify("Q3 FCF Turns Negative", ["META"]).tags
    assert "财报" in _classify("Sales More Than Double YoY", ["NVDA"]).tags
    assert "财报前瞻" in _classify("NFLX Q3 Preview: What to Watch", ["NFLX"]).tags
    assert "并购" in _classify("Netflix Makes Hostile Bid for Warner Bros", ["NFLX"]).tags
    assert "并购" in _classify("Netflix Explores $8 Billion Sale", ["NFLX"]).tags
    assert "并购" in _classify("Studio Put Up For Sale", ["WBD"]).tags
    assert "并购" in _classify("Target to be acquired by PE firm", ["TGT"]).tags
    assert "产品合作" in _classify("Visa and Singapore Tourism Board Sign Three-Year Partnership MOU", ["V"]).tags
    assert "产品合作" in _classify("AMD Inks MoU with Hyperscaler", ["AMD"]).tags
    assert "产品合作" in _classify("Nokia Joins Open RAN Ecosystem", ["NOK"]).tags
    assert "产品合作" not in _classify("Analyst Says Company Has Launched Too Many Products", ["AAPL"]).tags
    split = _classify("Meta Announces 2-for-1 Stock Split and $40B Buyback, Raises Dividend", ["META"])
    assert "公司行动" in split.tags and split.importance >= 4
    spacex = _classify("SpaceX Earnings Boost Tesla Sentiment", ["TSLA"])
    assert "财报" not in spacex.tags and "财报前瞻" not in spacex.tags
