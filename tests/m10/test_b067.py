"""B-067: IEX realtime vs SIP delayed labeling."""

from datetime import date, datetime, timedelta

from inves_cog.ingest.market import NY
from inves_cog.web.brief import _strip_item

DAY = date(2036, 10, 26)
NOW = datetime.combine(DAY, datetime.strptime("10:30", "%H:%M").time(), tzinfo=NY)


def _snap(last, prev, source, minutes=0):
    return {
        "ticker": "NVDA",
        "as_of": NOW - timedelta(minutes=minutes),
        "session": "regular",
        "last": last,
        "prev_close": prev,
        "delay_minutes": 15 if "delayed" in source else 0,
        "source": source,
    }


def test_iex_newer_wins():
    sip = _snap(200.0, 199.0, "Alpaca:delayed_sip", minutes=16)
    iex = {**_snap(201.0, 199.0, "Alpaca:iex"), "alt": sip}
    item = _strip_item("NVDA", "NVDA", "stock", iex, None, DAY)
    assert item["value"] == "201.00" and "IEX 实时" in item["tag"] and "延迟 SIP" in item["title"]


def test_sip_when_iex_stale():
    iex = _snap(200.0, 199.0, "Alpaca:iex", minutes=30)
    sip = {**_snap(202.0, 199.0, "Alpaca:delayed_sip"), "alt": iex}
    item = _strip_item("NVDA", "NVDA", "stock", sip, None, DAY)
    assert "延迟 15 分" in item["tag"] and "Alpaca IEX" in item["title"]


def test_yahoo_fallback():
    yahoo = _snap(200.0, 199.0, "Yahoo")
    item = _strip_item("NVDA", "NVDA", "stock", yahoo, None, DAY)
    assert "盘中" in item["tag"] and "Yahoo" in item["title"]


def test_intra_line_iex_label():
    from inves_cog.web.investor_html import _intra_line

    sip = {
        "as_of": NOW,
        "last": 200.0,
        "prev_close": 199.0,
        "source": "Alpaca:delayed_sip",
        "session": "regular",
        "delay_minutes": 15,
    }
    row = {
        "as_of": NOW,
        "last": 201.0,
        "prev_close": 199.0,
        "source": "Alpaca:iex",
        "session": "regular",
        "delay_minutes": 0,
        "alt": sip,
    }
    html = _intra_line(row)
    assert "IEX 实时" in html and "Alpaca IEX" in html and "延迟 SIP" in html


def test_intra_line_sip_label():
    from inves_cog.web.investor_html import _intra_line

    row = {
        "as_of": NOW,
        "last": 202.0,
        "prev_close": 199.0,
        "source": "Alpaca:delayed_sip",
        "session": "regular",
        "delay_minutes": 15,
    }
    html = _intra_line(row)
    assert "延迟 15 分" in html


def test_intra_line_yahoo_keeps_session():
    from inves_cog.web.investor_html import _intra_line

    row = {"as_of": NOW, "last": 200.0, "prev_close": 199.0, "source": "Yahoo", "session": "pre", "delay_minutes": 15}
    html = _intra_line(row)
    assert "盘前" in html and "截至" in html
