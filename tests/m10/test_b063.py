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
