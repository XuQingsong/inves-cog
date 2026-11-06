from copy import deepcopy

import pytest

from inves_cog.trading.execution.service import annotate_ceiling

pytestmark = pytest.mark.phase1_blocking


def test_ceiling_annotation_changes_only_buy_reason_text():
    original = {
        "orders": [
            {"ticker": "V", "side": "buy", "reason_zh": "基本条件满足", "shares": 10, "limit_price": 100},
            {"ticker": "MU", "side": "sell", "reason_zh": "减仓", "shares": 4, "limit_price": 200},
        ],
        "risk_count": 2,
        "cash": 1000,
    }
    plan = deepcopy(original)
    annotate_ceiling(plan, {"V": {"m": 5.1, "r": 0.08, "method": "growth", "band": "严重透支"}})
    assert "5.1" in plan["orders"][0]["reason_zh"]
    plan["orders"][0]["reason_zh"] = original["orders"][0]["reason_zh"]
    assert plan == original


def test_carried_pending_order_does_not_accumulate_daily_valuation_sentences():
    plan = {"orders": [{"ticker": "V", "side": "buy", "reason_zh": "原始理由", "shares": 10}]}
    annotate_ceiling(plan, {"V": {"m": 5.1, "band": "偏高"}})
    annotate_ceiling(plan, {"V": {"m": 6.1, "band": "严重透支"}})
    assert plan["orders"][0]["reason_zh"].count("隐含利润倍数") == 1
    assert "6.1" in plan["orders"][0]["reason_zh"]
