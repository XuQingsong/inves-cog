"""Official event parsing preserves action, effective dates and the target index."""

import pytest

pytestmark = pytest.mark.phase1_blocking


def test_official_rows_do_not_leak_other_index_additions():
    from inves_cog.backtest.membership import parse_announcement

    html = """<p>ABIOMED Inc. (NASD: ABMD) will replace Wyndham Worldwide Corp. (NYSE: WYN).</p>
    <table><tr><td colspan="4">S&amp;P 500 INDEX – MAY 31, 2018</td></tr>
    <tr><td>ADDED</td><td>ABIOMED</td><td>Health Care</td><td>Health Care Equipment</td></tr>
    <tr><td>DELETED</td><td>Wyndham Worldwide</td><td>Consumer Discretionary</td><td>Hotels</td></tr>
    <tr><td colspan="4">S&amp;P MIDCAP 400 INDEX – MAY 31, 2018</td></tr>
    <tr><td>ADDED</td><td>Other</td><td>Energy</td><td>Equipment</td></tr></table>"""
    rows = parse_announcement(html, "https://press.spglobal.com/2018-05-25-example")
    assert [(r["ticker"], r["action"], r["effective"]) for r in rows] == [
        ("ABMD", "added", "2018-05-31"),
        ("WYN", "deleted", "2018-05-31"),
    ]


def test_membership_uses_entry_inclusive_exit_exclusive_and_supports_reentry():
    from inves_cog.backtest.membership import is_member

    events = [
        {"effective": "2018-05-31", "action": "added"},
        {"effective": "2020-01-02", "action": "deleted"},
        {"effective": "2021-01-04", "action": "added"},
    ]
    assert not is_member(events, "2018-05-30")
    assert is_member(events, "2018-05-31")
    assert not is_member(events, "2020-01-02")
    assert is_member(events, "2021-01-04")


def test_official_midcap500_typo_still_identifies_500_not_400():
    from inves_cog.backtest.membership import parse_announcement

    html = """<p>Twitter Inc. (NYSE: TWTR) replaces Monsanto (NYSE: MON) in the S&amp;P 500.</p>
    <table><tr><td>S&amp;P MIDCAP 500 INDEX – JUNE 7, 2018</td></tr>
    <tr><td>ADDED</td><td>Twitter</td><td>Information Technology</td><td>Software</td></tr></table>"""
    rows = parse_announcement(html, "https://press.spglobal.com/2018-06-04-example")
    assert rows[0]["ticker"] == "TWTR"
    assert rows[0]["effective"] == "2018-06-07"


def test_modern_official_table_expands_effective_date_and_index_rowspans():
    from inves_cog.backtest.membership import parse_announcement
    html='''<table><tr><td>Effective Date</td><td>Index Name</td><td>Action</td><td>Company Name</td><td>Ticker</td><td>GICS Sector</td></tr>
    <tr><td rowspan="2">December 21, 2020</td><td rowspan="2">S&amp;P 500</td><td>Addition</td><td>Tesla</td><td>TSLA</td><td>Consumer Discretionary</td></tr>
    <tr><td>Deletion</td><td>Apartment Investment</td><td>AIV</td><td>Real Estate</td></tr></table>'''
    rows=parse_announcement(html,'https://press.spglobal.com/2020-12-11-example')
    assert [(r['ticker'],r['action'],r['effective']) for r in rows]==[
        ('TSLA','added','2020-12-21'),('AIV','deleted','2020-12-21')]
