"""B-068: latest price on stocks/stock/account pages."""

from datetime import date, datetime, timedelta

from inves_cog.ingest.market import NY
from inves_cog.web.brief import _snap_ret, _snap_tag

DAY = date(2036, 10, 26)
NOW = datetime.combine(DAY, datetime.strptime("10:30", "%H:%M").time(), tzinfo=NY)


def _snap(last, prev, source, vol=None):
    return {
        "ticker": "NVDA",
        "as_of": NOW,
        "session": "regular",
        "last": last,
        "prev_close": prev,
        "delay_minutes": 15,
        "source": source,
        "day_volume": vol,
    }


def test_snap_tag_iex_and_sip():
    assert _snap_tag(_snap(201, 199, "Alpaca:iex")) == f"IEX {NOW:%H:%M:%S}"
    assert _snap_tag(_snap(201, 199, "Alpaca:delayed_sip")) == f"延迟 15 分 {NOW:%H:%M}"


def test_snap_tag_session_fallback():
    assert "盘中" in _snap_tag(_snap(201, 199, "Yahoo"))


def test_snap_ret():
    assert abs(_snap_ret(_snap(201, 199, "Alpaca:iex")) - 201 / 199 + 1) < 1e-9


def test_day_volume_nullable_on_non_sip():
    assert _snap(201, 199, "Alpaca:iex")["day_volume"] is None


def test_scores_carry_signal_date():
    # regression: trading.daily_scores has signal_date, not trade_date
    from unittest.mock import MagicMock

    from inves_cog.web.brief import _scores

    older = {
        "ticker": "NVDA",
        "signal_date": DAY - timedelta(days=1),
        "tech": {},
        "derived": {},
        "quality": None,
        "growth": None,
        "valuation": None,
        "timing": None,
        "entry_pass": None,
        "tier": None,
    }
    conn = MagicMock()
    conn.execute.side_effect = [MagicMock(fetchall=lambda: []), MagicMock(fetchall=lambda: [older])]
    out = _scores(conn, DAY, carry=True)
    assert out["NVDA"]["carried_from"] == DAY - timedelta(days=1)


def test_stock_row_uses_snap_ret_today():
    from inves_cog.web.investor_html import _stock_row

    row = {
        "ticker": "NVDA",
        "sector": "半导体",
        "ret": -0.02,
        "snap_ret": 0.015,
        "snap_price": 205.0,
        "snap_tag": "IEX 10:20:11",
        "volume_multiple": 1.2,
        "held": True,
        "events": [],
    }
    html = _stock_row({"is_today": True}, row, DAY)
    assert "205.00" in html and "IEX 10:20:11" in html and "+1.50%" in html


def test_stock_row_close_ret_without_snapshot():
    from inves_cog.web.investor_html import _stock_row

    row = {"ticker": "NVDA", "ret": -0.02, "volume_multiple": 1.2, "held": True, "events": []}
    html = _stock_row({"is_today": True}, row, DAY)
    assert "-2.00%" in html


def test_carry_chip_render():
    from inves_cog.web.investor_html import _carry_chip

    assert "沿用 10/26" in _carry_chip({"carried_from": "2026-10-26"})
    assert _carry_chip({}) == ""
