from datetime import date

import pytest

from inves_cog.web.data_status import banner, render_status

pytestmark = pytest.mark.phase1_blocking


def sample():
    return {
        "available": True,
        "fresh": True,
        "mail_status": "邮件未配置",
        "detect_only": True,
        "gaps": [
            dict(
                dataset="波动率",
                data_date=date(2026, 11, 5),
                kind="stale",
                status="open",
                impact="晴雨表情绪可能被低估",
            )
        ],
        "checked_at": "2026-11-06 08:00",
    }


def test_missing_is_visible_with_affected_date_and_email_configuration():
    payload = sample()
    text = render_status(payload)
    assert "波动率" in text and "2026-11-05" in text and "邮件未配置" in text
    assert "晴雨表情绪可能被低估" in text
    assert "只检测" in text
    assert "部分数据缺失" in banner(payload)
    assert "该读数受数据缺失影响" in banner(payload, barometer=True)


def test_unknown_or_stale_guard_never_renders_healthy():
    payload = sample()
    payload.update(available=False, fresh=False, gaps=[])
    assert "尚未" in render_status(payload)
    assert banner(payload)
    payload.update(available=True, fresh=False)
    assert "未更新" in render_status(payload)


def test_escape_upstream_labels_instead_of_executing_html():
    payload = sample()
    payload["gaps"][0]["dataset"] = "<script>alert(1)</script>"
    assert "<script>alert(1)</script>" not in render_status(payload)
    assert "<script>alert(1)</script>" not in banner(payload)


def test_status_page_is_accessible_through_the_actual_public_read_only_boundary():
    from fastapi import FastAPI
    from starlette.testclient import TestClient
    from starlette.responses import HTMLResponse

    from inves_cog.web.public import protect

    app = FastAPI()

    @app.get('/data-status')
    def status_page():
        return HTMLResponse(render_status(sample()))

    client = TestClient(protect(app))
    response = client.get('/data-status')
    assert response.status_code == 200
    assert '波动率' in response.text and '邮件未配置' in response.text
    assert response.headers['Cache-Control'] == 'no-store'
    assert client.post('/data-status').status_code == 405
    assert client.get('/not-a-public-page').status_code == 404
