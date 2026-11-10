import inspect

import pytest


@pytest.mark.phase1_blocking
def test_congress_block_present_and_not_in_summary():
    """国会 block: listed-not-counted, lag note, excluded from chips/summary."""
    from inves_cog.web import investor_html

    src = inspect.getsource(investor_html)
    assert "国会（只列不计）" in src
    assert "众议院 · 申报最长滞后 45 天 · 参议院暂未接入" in src
    assert "cong_html" in src
    # congress data must not feed chips (summary line built from 'chips' only)
    chips_src = src[src.index("chips") - 400 : src.index("chips") + 400]
    assert "cong" not in chips_src


@pytest.mark.phase1_blocking
def test_congress_summary_shape():
    """smartmoney.congress output carries member/buy/sell counts + note."""
    from inves_cog.perception import smartmoney

    src = inspect.getsource(smartmoney.congress)
    for key in ("member_count", "buy_count", "sell_count", "scanned_count", "as_of_note"):
        assert key in src
    assert "interval '180 days'" in src


@pytest.mark.phase1_blocking
def test_congress_card_renders_counts():
    """Render path: a populated congress dict produces count + row markup."""
    from inves_cog.web import investor_html

    src = inspect.getsource(investor_html)
    assert "议员" in src and "买入" in src and "卖出" in src and "扫描件未解析" in src
