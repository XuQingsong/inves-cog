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
