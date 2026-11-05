from inves_cog.web.brief import valuation_card
from inves_cog.web.investor_html import _valuation


def test_ceiling_survives_unvalued_range_and_explains_missing_inputs():
    ceiling = {"method": "growth", "m": 5.1, "r": .08, "band": "严重透支",
               "m_r_minus_1": 4.1, "m_r_plus_1": 6.2, "fcf_m": 8.4,
               "quality": "低", "missing": ["FY1_consensus"], "evidence": {"rev_growth": 12}}
    card = valuation_card({"status": "unvalued", "payload": {"reason": "历史不足", "ceiling": ceiling}}, 30, 40)
    text = _valuation(card, full=True)
    assert "5.1" in text and "严重透支" in text and "8%" in text
    assert "现金" in text and "缺失" in text
    assert "长期回报大概率偏低" in text
    assert "None" not in text and "FY1_consensus" not in text


def test_cyclical_and_loss_are_explicitly_inapplicable():
    for method, phrase in [("cyclical", "周期股"), ("financial", "金融股"), ("loss", "亏损")]:
        card = valuation_card({"status": "unvalued", "payload": {"ceiling": {"method": method}}}, None, 40)
        assert phrase in _valuation(card, full=True)
