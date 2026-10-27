"""B-067: IEX realtime vs SIP delayed labeling."""

from datetime import date, datetime, timedelta

import pytest

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
