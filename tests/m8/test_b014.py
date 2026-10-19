"""B-014 name records. Muse, R1, and Toshiba are no longer required to be empty lists."""

from datetime import datetime, timedelta, timezone

import pytest

from inves_cog.perception.attribution.news_records import NewsRecords

T0 = datetime(2026, 10, 14, 13, 30, tzinfo=timezone.utc)


def _read(records, news_id, text, *, published_at=None, ingested_at=None):
    return records.ingest(
        news_id,
        text,
        ingested_at=ingested_at or T0 - timedelta(hours=5),
        published_at=published_at or T0 - timedelta(hours=6),
        level="已经细读",
    )


@pytest.mark.phase1_blocking
def test_coreweave_headline_marks_only_crwv():
    records = NewsRecords()
    row = _read(records, "coreweave", "CoreWeave Bond Yield Hits 15%")
    assert row["公司"] == [{"代码": "CRWV", "标明": "正文写了"}]
    assert "NVDA" not in [item["代码"] for item in row["公司"]]
    assert row["判断"] == ""
    stored = records.ingest(
        "coreweave-stored",
        "CoreWeave Bond Yield Hits 15%",
        ingested_at=T0 - timedelta(hours=5),
        published_at=T0 - timedelta(hours=6),
        level="只入库",
    )
    assert stored["处理级别"] == "只入库"
    assert stored["公司"] == []
    price = records.price("NVDA", T0)
    assert price["当时已经知道"] == ["coreweave", "coreweave-stored"]
    assert price["标记"] == "已看到新闻，正文没有这家公司"
    assert "公司" not in price
    assert records.price("CRWV", T0)["标记"] == "正文写了"


@pytest.mark.phase1_blocking
def test_dell_headline_marks_only_dell():
    row = _read(NewsRecords(), "dell", "Barclays Downgrades Dell Technologies to Equal-Weight")
    assert row["公司"] == [{"代码": "DELL", "标明": "正文写了"}]
    assert "SMCI" not in [item["代码"] for item in row["公司"]]


@pytest.mark.phase1_blocking
def test_hewlett_packard_and_netapp_headlines_list_nobody():
    records = NewsRecords()
    hewlett = _read(records, "hpe", "Barclays Downgrades Hewlett Packard")
    netapp = _read(records, "ntap", "Barclays Downgrades NetApp")
    assert hewlett["公司"] == []
    assert netapp["公司"] == []
    assert hewlett["判断"] == ""
    assert netapp["判断"] == ""


@pytest.mark.phase1_blocking
def test_close_reading_keeps_at_most_three_named_companies():
    text = "NVIDIA, Advanced Micro Devices, Broadcom and Marvell Technology reported together."
    row = _read(NewsRecords(), "four", text)
    assert [item["代码"] for item in row["公司"]] == ["NVDA", "AMD", "AVGO"]
    assert all(item["标明"] == "正文写了" for item in row["公司"])
    assert row["判断"] == ""


@pytest.mark.phase1_blocking
def test_move_with_no_earlier_news_is_complete():
    price = NewsRecords().price("META", T0)
    assert price["标记"] == "已入库新闻对不上"
    assert price["当时已经知道"] == []
    assert "公司" not in price


@pytest.mark.phase1_blocking
def test_news_published_after_the_move_is_not_already_known():
    records = NewsRecords()
    _read(records, "early", "DeepSeek R1 was released that day, with weights open-sourced.")
    records.ingest(
        "late",
        "Barclays Downgrades Dell Technologies to Equal-Weight",
        ingested_at=T0 - timedelta(minutes=30),
        published_at=T0 + timedelta(minutes=1),
        level="已经细读",
    )
    price = records.price("META", T0)
    assert price["当时已经知道"] == ["early"]
    assert "late" not in price["当时已经知道"]
    assert price["标记"] == "已看到新闻，正文没有这家公司"
    assert records.price("DELL", T0)["标记"] == "已看到新闻，正文没有这家公司"
