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


def test_prev_session_post_close_news_is_not_early():
    """A cite from the previous session's post-close (e.g. a 17:00 ET earnings
    print) is fresh context, not 早前消息; before 16:00 ET prev-session is."""
    from inves_cog.web.brief import citation_stale_note

    day = date(2026, 11, 6)  # Friday; prev session Thursday 11-05
    # Thursday 17:00 ET post-close -> not tagged
    assert citation_stale_note("2026-11-05T22:00:00+00:00", day) is None
    # Thursday 15:00 ET (before the close) -> tagged
    assert citation_stale_note("2026-11-05T20:00:00+00:00", day) == "早前消息（11-05）"


def test_highlights_card_renders_peak_text_without_double_escape():
    """Regression: _pct() returns an HTML span — embedding it inside _text()
    double-escaped it and the card literally showed '<span class="num up">'."""
    from inves_cog.web.investor_html import _highlights_module

    payload = {
        "hl_groups": [
            {
                "scope": "stock",
                "subject": "STX",
                "basket_name": None,
                "ret": 0.092,
                "session": "pre",
                "cur_ret": -0.012,
                "last_px": 460.77,
                "why": "单股异常",
                "cause": None,
                "members": [{"severity": "watch", "scope": "stock"}],
            }
        ],
        "state": {},
    }
    html = _highlights_module(payload)
    assert "&lt;span" not in html and "&quot;" not in html
    assert "盘前异动 +9.2%（峰值）" in html
    assert "$460.77" in html and "-1.2%" in html
