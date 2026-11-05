import pytest

from inves_cog.web.brief import valuation_card
from inves_cog.web.investor_html import _valuation


def test_ceiling_survives_unvalued_range_and_explains_missing_inputs():
    ceiling = {
        "method": "growth",
        "m": 5.1,
        "r": 0.08,
        "band": "严重透支",
        "m_r_minus_1": 4.1,
        "m_r_plus_1": 6.2,
        "fcf_m": 8.4,
        "quality": "低",
        "missing": ["FY1_consensus"],
        "evidence": {"rev_growth": 12},
    }
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


pytestmark = pytest.mark.phase1_blocking


def test_stock_page_explanation_no_longer_promotes_historical_pe_percentiles():
    from inves_cog.web.investor_html import render_brief

    html = render_brief(
        {
            "page": "/s/NVDA",
            "symbol": "NVDA",
            "date": "2026-11-04",
            "trend": {},
            "position": {},
            "valuation": {"ceiling": {"method": "growth", "m": 3.2, "r": 0.08, "band": "偏高"}},
        }
    )
    assert "历史分位" not in html
    assert "隐含" in html


def test_institution_module_keeps_ratings_without_price_targets():
    from inves_cog.web.investor_html import _actions_body

    html = _actions_body(
        {
            "analyst_actions": [
                {
                    "firm": "Fixture Research",
                    "action_date": "2026-11-04",
                    "from_grade": "Hold",
                    "to_grade": "Buy",
                    "action": "up",
                    "prior_pt": 99999,
                    "current_pt": 88888,
                }
            ]
        }
    )
    assert "Fixture Research" in html and "Buy" in html
    assert "目标价" not in html and "99999" not in html and "88888" not in html


def test_price_bar_formats_earnings_date_without_exposing_source_dictionary():
    from inves_cog.web.investor_html import _price_bar

    payload = {
        "price_now": {"px": 100},
        "bar_stats": {"next_earnings": {"report_date": "2026-11-17", "time": "post", "eps_forecast": 2.49}},
        "next_report": {"report_date": "2026-11-17", "time": "post"},
    }
    text = _price_bar(payload)
    assert "2026-11-17" in text and "盘后" in text
    assert "eps_forecast" not in text and "report_date" not in text


def test_inapplicable_method_still_displays_its_discount_rate():
    from inves_cog.web.ceiling import ceiling_text

    for method in ['cyclical','loss']:
        assert '10%' in ceiling_text({'method':method,'r':.10},full=True)
