import pytest

from tests.m10.test_b054 import _clear, _get, _json, _roles, _seed


@pytest.fixture(scope="module")
def pages():
    import psycopg
    from psycopg.rows import dict_row

    from tests.m8.test_attribution import _disposable_database

    host = _disposable_database()
    admin = psycopg.connect(
        host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row, autocommit=True
    )
    _roles(admin)
    _seed(admin)
    yield {"admin": admin, "dsn": f"postgresql://b054_web@{host}/inves_cog"}
    _clear(admin)
    admin.close()


def test_diag_market3_fixture(pages):
    market = _json(pages, "/api/pages/brief/market")
    m3 = market.get("market3") or {}
    print("\nM3 groups:", list((m3.get("groups") or {}).keys()))
    for tab, items in (m3.get("groups") or {}).items():
        print("TAB", tab, [(i.get("sym"), i.get("ret"), i.get("px")) for i in items[:5]])
    print("daily syms:", list((m3.get("daily") or {}).keys())[:6])
    html = _get(pages, "/").text
    print("m3table:", "m3table" in html, "| minus:", "−1.18%" in html, "| len:", len(html))
