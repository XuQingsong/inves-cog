from inves_cog.valuation.ceiling import dyn_pe, implied_m, cap_multiplier


def test_dyn_pe_book_values():
    for m, want in ((1, 10.0), (2, 15.3), (3, 20.1), (5, 28.8), (10, 48.6)):
        assert abs(dyn_pe(m, 0.10, 10) - want) < 0.1


def test_implied_m_inverse():
    for m in (1.5, 3, 8, 30):
        got = implied_m(dyn_pe(m, 0.08, 10), 0.08, 10)
        assert abs(got - m) < 0.05


def test_cap_multiplier_book():
    assert abs(cap_multiplier(5, 0.10) - 8.3) < 0.15
    assert abs(cap_multiplier(10, 0.10) - 6.8) < 0.15
