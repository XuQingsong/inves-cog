from datetime import datetime, timedelta, timezone

import pytest


@pytest.mark.phase1_blocking
def test_analyst_summary_uses_av_not_muse():
    """_analyst_summary must query valuation_v1.consensus_snapshots (AV),
    never fundamentals.consensus_snapshot (which hosts muse_import)."""
    import inspect

    from inves_cog.web import stock_brief

    src = inspect.getsource(stock_brief._analyst_summary)
    assert "valuation_v1.consensus_snapshots" in src
    assert "fundamentals.consensus_snapshot" not in src
    src2 = inspect.getsource(stock_brief._earnings_hist)
    assert "source<>'muse_import'" in src2 or "source <> 'muse_import'" in src2


@pytest.mark.phase1_blocking
def test_consensus_revision_up_down_and_insufficient():
    from inves_cog.web.stock_brief import _consensus_revision

    t0 = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    rows = [
        {"fetched_at": t0, "fiscal_end": None, "horizon": "fiscal year", "eps_avg": 5.0},
        {"fetched_at": t0 - timedelta(days=8), "fiscal_end": None, "horizon": "fiscal year", "eps_avg": 4.0},
    ]
    rev = _consensus_revision(rows)
    assert rev["d7"] == {"up": 1, "down": 0, "since": str(t0 - timedelta(days=8))[:10]}
    assert rev["d30"] == "历史不足"
    assert "本系统快照" in rev["note"]


@pytest.mark.phase1_blocking
def test_repository_consensus_reads_av_table():
    import inspect

    from inves_cog.valuation_v1 import repository

    src = inspect.getsource(repository)
    assert "valuation_v1.consensus_snapshots" in src


@pytest.mark.phase1_blocking
def test_earnings_hist_excludes_muse_source():
    import inspect

    from inves_cog.web.stock_brief import _earnings_hist

    assert "muse_import" in inspect.getsource(_earnings_hist)


@pytest.mark.phase1_blocking
def test_pit_cutoff_uses_fetched_at():
    """Repository consensus query filters by fetched_at (PIT), not as_of."""
    import inspect

    from inves_cog.valuation_v1 import repository

    src = inspect.getsource(repository)
    assert "fetched_at::date<=%s" in src
