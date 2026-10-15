from pathlib import Path

import pytest


@pytest.mark.phase1_replay
def test_legacy_matches_muse_state():
    from inves_cog.ingest.fundamentals.oracle import compare_muse_export

    report = compare_muse_export(Path(__file__).resolve().parents[1] / "fixtures/phase1/m2/muse")
    assert report["tickers"] == 30 and report["dates"] == 3 and report["mismatches"] == []


@pytest.mark.phase1_live
def test_fundamentals_live_smoke(clock):
    from inves_cog.ingest.fundamentals.live import run_smoke

    report = run_smoke(clock=clock)
    assert len(report["health"]) == 59
    assert all(
        "stale_fundamentals" not in report["health"][ticker]["health_codes"] for ticker in ("LITE", "BE", "COHR")
    )
