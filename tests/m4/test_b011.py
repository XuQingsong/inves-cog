"""B-011: exact drawdown thresholds use the written operators."""

import pytest

pytestmark = pytest.mark.phase1_blocking

PEAK = 1_000_000


def _book(peak=PEAK, dd8=False, dd12=False):
    return type(
        "Book",
        (),
        {
            "peak_equity": peak,
            "dd8": dd8,
            "dd12": dd12,
            "positions": {"ATK": {"tier_now": "attack"}, "NRM": {"tier_now": "normal"}},
            "index": 0,
            "last_swan": -100,
        },
    )()


def _step(equity, *, dd8=False, dd12=False):
    from inves_cog.trading.execution.risk import update_risk

    book = _book(dd8=dd8, dd12=dd12)
    intents = update_risk(book, equity, (0, 0), False)
    sold = [item for item in intents if item[0] == "ATK" and item[1] == "M-62"]
    return book, sold


def test_exact_minus_eight_sells_one_third_of_each_attack_name():
    from inves_cog.trading.execution.state import PARAMS

    book, sold = _step(920_000)
    assert book.dd8 is True
    assert sold == [("ATK", "M-62", PARAMS["risk"]["dd8_sell_fraction"], "回撤刹车减仓")]


def test_exact_minus_six_releases_the_deep_brake():
    book, sold = _step(940_000, dd12=True)
    assert book.dd12 is False
    assert sold == []


def test_neighboring_amounts_keep_each_operator():
    from inves_cog.trading.execution.state import PARAMS

    fraction = PARAMS["risk"]["dd8_sell_fraction"]
    sell = [("ATK", "M-62", fraction, "回撤刹车减仓")]
    cases = (
        (920_000.01, {}, False, False, []),
        (919_999.99, {}, True, False, sell),
        (939_999.99, {"dd12": True}, False, True, []),
        (940_000.01, {"dd12": True}, False, False, []),
        (880_000, {}, True, True, sell),
        (880_000.01, {}, True, False, sell),
        (879_999.99, {}, True, True, sell),
        (960_000, {"dd8": True}, True, False, []),
        (960_000.01, {"dd8": True}, False, False, []),
        (959_999.99, {"dd8": True}, True, False, []),
    )
    for equity, flags, dd8, dd12, expected in cases:
        book, sold = _step(equity, **flags)
        assert (book.dd8, book.dd12, sold) == (dd8, dd12, expected)
