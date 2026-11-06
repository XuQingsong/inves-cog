import pytest

from scripts.a030_redacted_account_preview import redact_html

pytestmark = pytest.mark.phase1_blocking


def test_account_redaction_drops_private_text_attributes_scripts_and_prices():
    private = """<html><head><style>.card{color:black}</style></head><body>
    <h2>持仓与关键价位</h2><div class="card hi" id="SECRET" data-shares="1234" title="private cost">
    SECRET 1234 $9876.54 50% 买入订单</div><a href="/s/SECRET">SECRET</a>
    <script type="application/json">{"holdings":["SECRET",1234]}</script>
    <span>现价隐含利润约涨到现在的 6.0 倍（折现率 8%），严重透支；长期回报大概率偏低</span>
    <div style="width:78%">9876</div></body></html>"""
    out = redact_html(private)
    for value in (
        "SECRET",
        "1234",
        "9876",
        "50%",
        "78%",
        "private cost",
        "买入订单",
        "data-shares",
        "<script",
        "6.0",
        "8%",
    ):
        assert value not in out
    assert "持仓与关键价位" in out
    assert "长期回报大概率偏低" in out and "严重透支" in out
    assert "已遮盖" in out and ".card{color:black}" in out
