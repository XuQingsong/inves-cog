import pytest


@pytest.mark.phase1_live
def test_ingest_live_smoke(clock):
    from inves_cog.ingest.live import run_smoke
    report = run_smoke(clock=clock)
    assert report['daily_codes'] + len(report['unavailable_codes']) == 73
    assert report['daily_codes'] > 0 and report['news_count'] > 0
    assert report['exhausted']
    assert report['source_health']
