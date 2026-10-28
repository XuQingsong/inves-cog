"""B-068 follow-up: previous-date snapshot labels + volume carry."""

from datetime import date, datetime, timedelta

from inves_cog.ingest.market import NY
from inves_cog.web.brief import _member, _snap_tag

DAY = date(2036, 10, 28)  # pre-open; snapshots are from D-1 post-session
POST = datetime.combine(DAY - timedelta(days=1), datetime.strptime("19:43", "%H:%M").time(), tzinfo=NY)


def _snap(vol=None, sess="post"):
    return {
        "ticker": "NVDA",
        "as_of": POST,
        "session": sess,
        "last": 200.0,
        "prev_close": 199.0,
        "delay_minutes": 15,
        "source": "Alpaca:delayed_sip",
        "day_volume": vol,
    }


def _bars(vols):
    rows = [{"trade_date": DAY - timedelta(days=i + 1), "volume": v, "close": 200.0} for i, v in enumerate(vols)]
    return {"NVDA": sorted(rows, key=lambda r: r["trade_date"])}


def test_stale_snap_tag_shows_date_and_session():
    assert _snap_tag(_snap(), DAY) == "盘后 10/27 19:43"
    assert _snap_tag(_snap()) == "延迟 15 分 19:43"


def test_prev_session_volume_carry_label():
    m = _member(
        "NVDA",
        DAY,
        _bars([6_000_000] + [3_000_000] * 20),
        None,
        {"NVDA": {"ret": 0.01}},
        False,
        [],
        snap=_snap(),
        elapsed=None,
    )
    assert abs(m["volume_multiple"] - 2.0) < 0.01
    assert "沿用 10/27" in m["vol_label"]


def test_member_tag_includes_stale_date():
    m = _member(
        "NVDA", DAY, _bars([3_000_000] * 20), None, {"NVDA": {"ret": 0.01}}, False, [], snap=_snap(), elapsed=None
    )
    assert "10/27" in m["snap_tag"]
