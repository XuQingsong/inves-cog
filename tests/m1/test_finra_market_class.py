import pytest

from inves_cog.ingest.sources import parse_finra


def _record(ticker, code):
    return {
        "symbolCode": ticker,
        "marketClassCode": code,
        "settlementDate": "2026-10-15",
        "currentShortPositionQuantity": 1000,
        "averageDailyVolumeQuantity": 100,
    }


@pytest.mark.phase1_blocking
def test_parse_finra_passes_listed_exchanges_drops_otc():
    rows = parse_finra(
        [
            _record("NMS_T", "NMS"),
            _record("NGM_T", "NGM"),
            _record("NCM_T", "NCM"),
            _record("ARCA_T", "ARCA"),
            _record("NNM_T", "NNM"),
            _record("SC_T", "SC"),
            _record("OTC_T", "OTC"),
            _record("OTCBB_T", "OTCBB"),
        ],
        allowed_tickers={"NMS_T", "NGM_T", "NCM_T", "ARCA_T", "NNM_T", "SC_T", "OTC_T", "OTCBB_T"},
    )
    assert {r["ticker"] for r in rows} == {"NMS_T", "NGM_T", "NCM_T", "ARCA_T", "NNM_T", "SC_T"}
