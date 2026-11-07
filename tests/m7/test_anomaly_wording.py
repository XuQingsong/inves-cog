"""PR anomaly-display-truth: single-ticker titles, residual-direction wording,
pre-date citation tagging."""

from datetime import date

import pytest

pytestmark = pytest.mark.phase1_blocking

CATALOG = {"rows": [], "sectors": {}, "by_id": {}}


def test_single_ticker_title_has_no_collective_wording():
    from inves_cog.web.brief import _event_title

    members = [{"ticker": "LITE", "ret": 0.057, "resid": -0.02}]
    title = _event_title([], members, "down", CATALOG)
    assert "集体" not in title and "LITE" in title


def test_residual_opposite_direction_phrasing():
    from inves_cog.web.brief import _event_title

    weaker = _event_title([], [{"ticker": "LITE", "ret": 0.057, "resid": -0.02}], "down", CATALOG)
    assert "相对同组走弱" in weaker and "+5.7%" in weaker
    stronger = _event_title([], [{"ticker": "MU", "ret": -0.03, "resid": 0.01}], "down", CATALOG)
    assert "相对同组走强" in stronger and "-3.0%" in stronger


def test_aligned_single_ticker_shows_direction_and_ret():
    from inves_cog.web.brief import _event_title

    title = _event_title([], [{"ticker": "NVDA", "ret": 0.082, "resid": 0.05}], "up", CATALOG)
    assert "上涨" in title and "+8.2%" in title and "集体" not in title


def test_citation_from_prior_day_tagged_early_news():
    from inves_cog.web.brief import citation_stale_note

    note = citation_stale_note("2026-11-03T18:00:00+00:00", date(2026, 11, 6))
    assert note == "早前消息（11-03）"
    assert citation_stale_note("2026-11-06T18:00:00+00:00", date(2026, 11, 6)) is None
