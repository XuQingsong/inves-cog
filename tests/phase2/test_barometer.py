def test_api_shape_and_today_selection():
    """api_payload returns today+label+history; missing list propagates."""
    from datetime import date
    from unittest.mock import MagicMock

    from inves_cog.web.barometer import _row, render_page

    row = {
        "date": date(2026, 10, 30),
        "fear": 18.9,
        "greed": 4.0,
        "fear_level": 1.5,
        "greed_level": 0.3,
        "stage": "谨慎",
        "pendulum": -0.5,
        "short_heat": 10.0,
        "accumulation": 20.0,
        "nature": "",
        "dims": {"fear": {"去杠杆": 30}, "greed": {}},
        "inputs": {"VIX": 18.2},
        "missing": ["MOVE"],
    }
    rec = _row(row)
    assert rec["st"] == -1 and rec["missing"] == ["MOVE"]
    html = render_page([rec])
    assert "市场情绪钟摆" in html and "缺" in html


def test_page_rules_no_banned_words():
    from datetime import date

    from inves_cog.web.barometer import _row, render_page

    row = {
        "date": date(2026, 10, 30),
        "fear": 10.0,
        "greed": 5.0,
        "fear_level": 1.0,
        "greed_level": 0.5,
        "stage": "理性",
        "pendulum": 0.0,
        "short_heat": 5.0,
        "accumulation": 10.0,
        "nature": "",
        "dims": {"fear": {}, "greed": {}},
        "inputs": {},
        "missing": [],
    }
    html = render_page([_row(row)])
    for banned in ("下单", "目标价", "实时", "dev50", "M9"):
        assert banned not in html


def test_no_noqa_leak_in_rendered_html():
    """Rendered /barometer must not contain Python noqa comments (JS syntax)."""
    from datetime import date

    from inves_cog.web.barometer import _row, render_page

    row = {"date": date(2026, 10, 30), "fear": 10.0, "greed": 5.0,
           "fear_level": 1.0, "greed_level": 0.5, "stage": "理性",
           "pendulum": 0.0, "short_heat": 5.0, "accumulation": 10.0,
           "nature": "", "dims": {"fear": {}, "greed": {}},
           "inputs": {}, "missing": []}
    html = render_page([_row(row)])
    assert "noqa" not in html
    assert "# " not in html.split("<script", 1)[-1]  # no Python comment tokens in script
    assert 'svg id="pend"' in html
    assert "const R=[{" in html


def test_script_identifiers_defined():
    """All JS identifiers the page needs must be defined in the inline script."""
    from datetime import date

    from inves_cog.web.barometer import _row, render_page

    row = {"date": date(2026, 10, 30), "fear": 10.0, "greed": 5.0,
           "fear_level": 1.0, "greed_level": 0.5, "stage": "理性",
           "pendulum": 0.0, "short_heat": 5.0, "accumulation": 10.0,
           "nature": "", "dims": {"fear": {}, "greed": {}},
           "inputs": {}, "missing": []}
    html = render_page([_row(row)])
    for ident in ("TN", "HN", "ST", "SC", "DIM", "FMT", "PH", "RING"):
        assert f"const {ident}=" in html or f"{ident}=" in html
    assert "P=[640" in html and "L=330" in html and "RING=[" in html
