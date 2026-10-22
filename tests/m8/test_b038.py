"""B-038: each affected ticker is its own record with a scalar ticker."""

import json

import pytest

from inves_cog.perception.attribution.snapshot import capture_if_ready, read_snapshot
from tests.m8.test_b036 import BEFORE, CUTOFF, DAY, EARLIER, Memory, _clock, _entry, _jobs

pytestmark = pytest.mark.phase1_blocking


def _row(**changes):
    row = {
        "event_id": "evt-1",
        "anomaly_id": "anom-1",
        "history": [_entry(EARLIER, "假设中", ["info-1"])],
        "generated_at": EARLIER,
        "mechanism": "供给",
        "deadline_outcome": "未到",
        "tickers": [
            {"ticker": "NVDA", "exposure": "直接"},
            {"ticker": "AMD", "exposure": "间接"},
        ],
        "candidates": [],
        "tracks": [{"trade_date": DAY, "emotion": "初现", "capital": "观望", "fundamental": "未证"}],
        "claims": [{"direction": "不利"}],
        "report": {"divergence_label": "情绪性折价", "next_filing_at": "2026-11-01"},
        "systemic_event_tag": "无",
    }
    row.update(changes)
    return row


def _capture(row):
    pages = Memory(_jobs(), [row])
    capture_if_ready(pages, DAY, _clock(CUTOFF))
    found = read_snapshot(pages, DAY, CUTOFF)
    return pages.snapshots[0], found


def _by_ticker(found):
    affected = found["events"][0]["affected"]
    mapped = {}
    for item in affected:
        assert isinstance(item["ticker"], str)
        hash(item["ticker"])
        mapped[item["ticker"]] = item
    return mapped


def test_two_tickers_keep_their_own_exposure():
    stored, found = _capture(_row())
    assert found["complete"] is True
    mapped = _by_ticker(found)
    assert list(mapped) == ["NVDA", "AMD"]
    assert mapped["NVDA"]["exposure"] == "直接"
    assert mapped["AMD"]["exposure"] == "间接"
    assert mapped["NVDA"]["divergence_tag"] == "情绪性折价"
    assert mapped["AMD"]["divergence_tag"] == "情绪性折价"
    assert mapped["NVDA"]["next_filing_at"] == "2026-11-01"
    assert mapped["AMD"]["next_filing_at"] == "2026-11-01"
    assert "ticker=[" not in json.dumps(found["events"], ensure_ascii=False)
    assert stored["events"][0]["fields"]["lifecycle"]["value"] == "假设中"


def test_a_missing_or_conflicting_exposure_stays_on_that_ticker():
    missing, found = _capture(
        _row(tickers=[{"ticker": "NVDA", "exposure": "直接"}, {"ticker": "AMD", "exposure": None}])
    )
    assert found["complete"] is True
    assert found["source_events_asof"] == BEFORE.isoformat()
    mapped = _by_ticker(found)
    assert mapped["NVDA"]["exposure"] == "直接"
    assert "AMD" not in mapped
    text = json.dumps(missing["missing"], ensure_ascii=False)
    assert "AMD" in text
    assert "NVDA" not in text or "直接" in json.dumps(found["events"], ensure_ascii=False)

    conflict, hidden = _capture(
        _row(
            tickers=[
                {"ticker": "NVDA", "exposure": "直接"},
                {"ticker": "NVDA", "exposure": "间接"},
                {"ticker": "AMD", "exposure": "直接"},
            ]
        )
    )
    assert hidden["complete"] is True
    mapped = _by_ticker(hidden)
    assert mapped["AMD"]["exposure"] == "直接"
    assert "NVDA" not in mapped
    assert "不一致" in json.dumps(conflict["missing"], ensure_ascii=False)
    assert "间接" not in json.dumps(hidden["events"], ensure_ascii=False)


def test_candidate_tickers_stay_separate_when_status_is_empty():
    row = _row(
        tickers=[],
        candidates=[{"affected": [{"ticker": "NVDA", "exposure": "直接"}, {"ticker": "AMD", "exposure": "间接"}]}],
    )
    _stored, found = _capture(row)
    mapped = _by_ticker(found)
    assert mapped["NVDA"]["exposure"] == "直接"
    assert mapped["AMD"]["exposure"] == "间接"
    assert found["complete"] is True


def test_one_ticker_stays_a_single_record():
    _stored, found = _capture(_row(tickers=[{"ticker": "NVDA", "exposure": "直接"}]))
    assert found["complete"] is True
    assert found["events"][0]["affected"] == [
        {
            "ticker": "NVDA",
            "exposure": "直接",
            "divergence_tag": "情绪性折价",
            "next_filing_at": "2026-11-01",
        }
    ]
    hash(found["events"][0]["affected"][0]["ticker"])


def test_no_ticker_does_not_invent_an_affected_row():
    _stored, found = _capture(_row(tickers=[], candidates=[]))
    assert found["complete"] is True
    assert found["events"][0]["affected"] == []
    assert found["source_events_asof"] == BEFORE.isoformat()
    assert "ticker" in found["missing"]["fields"]["evt-1"]


def test_m9_can_key_each_ticker():
    _stored, found = _capture(_row())
    tickers = {}
    for event in found["events"]:
        for affected in event["affected"]:
            ticker = affected["ticker"]
            assert isinstance(ticker, str)
            tickers.setdefault(
                ticker,
                {"exposure": affected["exposure"], "divergence_tag": affected["divergence_tag"]},
            )
    assert tickers["NVDA"]["exposure"] == "直接"
    assert tickers["AMD"]["exposure"] == "间接"
    assert "ticker=[" not in json.dumps(found["events"], ensure_ascii=False)
