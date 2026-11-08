from datetime import date

import pytest

from inves_cog.dataguard.finra import parse_daily

pytestmark = pytest.mark.phase1_blocking
DAY = date(2026, 11, 5)
FILE = (
    "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n"
    "20261105|SPY|120|5|300|B,Q,N\n20261105|QQQ|80|1|200|Q,N\n2\n"
)


def test_only_monitored_symbols_and_short_exempt_is_already_in_short_volume():
    assert parse_daily(FILE, DAY, {"SPY"}) == [dict(date=DAY, ticker="SPY", short_volume=120, total_volume=300)]


@pytest.mark.parametrize(
    "text",
    [
        FILE.replace("20261105", "20261104"),
        FILE.replace("\n2\n", "\n3\n"),
        FILE.replace("|120|", "|-1|"),
        FILE.replace("|120|", "|301|"),
        FILE.replace("|5|", "|121|"),
        "<html>rate limited</html>",
    ],
)
def test_wrong_day_truncated_or_bad_quantity_is_rejected_before_any_write(text):
    with pytest.raises(ValueError):
        parse_daily(text, DAY, {"SPY"})


def test_empty_official_file_is_no_data_not_fake_zero_rows():
    assert parse_daily(FILE.splitlines()[0] + "\n0\n", DAY, {"SPY"}) == []


def test_fractional_share_volumes_are_bounds_checked_then_rounded():
    text = FILE.replace("|SPY|120|5|300|", "|SPY|562765.465412|502|1110680.408842|")
    assert parse_daily(text, DAY, {"SPY"}) == [dict(date=DAY, ticker="SPY", short_volume=562765, total_volume=1110680)]


@pytest.mark.parametrize("text", [FILE.replace("|120|", "|-0.5|"), FILE.replace("|120|", "|300.5|")])
def test_fractional_bounds_violations_still_rejected(text):
    with pytest.raises(ValueError):
        parse_daily(text, DAY, {"SPY"})
