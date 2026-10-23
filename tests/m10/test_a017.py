"""A017 public boundary: no production database, sources or model calls."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.phase1_blocking


def client_for(*, timer=None, failing=False, host='203.0.113.1'):
    from inves_cog.web.public import protect

    app = FastAPI()

    @app.get('/api/pages/home')
    def home():
        if failing:
            raise RuntimeError('postgresql://private-user:private-pass@private-host/db traceback detail')
        return {'counts': {'anomaly_count': 3}}

    return TestClient(protect(app, monotonic=timer or (lambda: 0)), client=(host, 123))


def test_a017_only_get_no_docs_or_other_paths():
    with client_for() as client:
        for method in ('post', 'put', 'patch', 'delete', 'options', 'head'):
            response = getattr(client, method)('/api/pages/home')
            assert response.status_code == 405
            assert response.headers['allow'] == 'GET'
        for path in ('/docs', '/redoc', '/openapi.json', '/anything'):
            assert client.get(path).status_code == 404


def test_a017_exact_home_alias_and_upstream_payload():
    with client_for() as client:
        assert client.get('/api/pages/?date=2031-04-17').json() == {'counts': {'anomaly_count': 3}}
        assert client.get('/api/pages/home').json() == {'counts': {'anomaly_count': 3}}


def test_a017_per_ip_60_per_minute_ignores_forwarded_headers():
    now = [0.0]
    with client_for(timer=lambda: now[0]) as client:
        for i in range(60):
            assert client.get('/api/pages/home', headers={'X-Forwarded-For': f'198.51.100.{i}'}).status_code == 200
        response = client.get('/api/pages/home')
        assert response.status_code == 429 and int(response.headers['retry-after']) == 60
        now[0] = 60.0
        assert client.get('/api/pages/home').status_code == 200


def test_a017_error_hides_exception_and_connection_string():
    with client_for(failing=True) as client:
        response = client.get('/api/pages/home')
        assert response.status_code == 503
        assert response.json() == {'detail': '页面暂不可用'}
        assert all(x not in response.text for x in ('postgresql', 'private-', 'traceback', 'RuntimeError'))


def test_a017_service_only_web_single_worker_and_no_secret():
    from pathlib import Path

    from scripts.serve_pages import configuration

    config = configuration(Path('/srv/inves-cog'), Path('/srv/inves-cog/.venv/bin/python'))
    assert config.count('[program:') == 1 and '[program:pages]' in config
    assert 'serve_pages.py' in config and 'DATABASE_URL' not in config and 'password' not in config
    assert 'autostart=true' in config


def test_a017_rate_limit_is_separate_for_socket_ips():
    from inves_cog.web.public import protect
    app = FastAPI()
    @app.get('/api/pages/home')
    def home():
        return {'ok': True}
    guarded = protect(app, monotonic=lambda: 0)
    with TestClient(guarded, client=('203.0.113.1', 1)) as first:
        for _ in range(60):
            assert first.get('/api/pages/home').status_code == 200
        assert first.get('/api/pages/home').status_code == 429
    with TestClient(guarded, client=('203.0.113.2', 2)) as second:
        assert second.get('/api/pages/home').status_code == 200


@pytest.fixture(scope='module')
def public_pages():
    from tests.m10.test_b048 import pages

    yield from pages.__wrapped__()


def test_a017_public_market_is_original_payload_without_trading_fields(public_pages):
    from inves_cog.web.api import create_app as original
    from inves_cog.web.public import create_app as public
    from tests.m10.test_b048 import AFTER, DAY, FORBIDDEN_FIELDS, MARKET_PATHS, _keys

    with TestClient(original(dsn=public_pages['dsn'], clock=AFTER)) as before:
        with TestClient(public(dsn=public_pages['dsn'], clock=AFTER)) as after:
            for path, _ in MARKET_PATHS:
                expected = before.get(path, params={'date': DAY.isoformat()})
                actual = after.get(path, params={'date': DAY.isoformat()})
                assert actual.status_code == expected.status_code == 200
                assert actual.json() == expected.json()
                assert not (_keys(actual.json()) & FORBIDDEN_FIELDS)


def test_a017_uvicorn_single_worker_direct_ip_and_no_access_logging(monkeypatch):
    import sys
    from types import SimpleNamespace

    from scripts.serve_pages import main

    seen = {}
    monkeypatch.setattr(
        'inves_cog.ingest.settings.read_environment',
        lambda *a, **kw: {'INVES_COG_WEB_DATABASE_URL': 'offline'},
    )
    monkeypatch.setattr('inves_cog.web.public.create_app', lambda **kw: 'app')
    monkeypatch.setitem(sys.modules, 'uvicorn', SimpleNamespace(run=lambda app, **kw: seen.update(app=app, **kw)))
    main()
    assert seen == {'app': 'app', 'host': '0.0.0.0', 'port': 8080, 'workers': 1,
                    'proxy_headers': False, 'server_header': False, 'access_log': False, 'log_level': 'critical'}
