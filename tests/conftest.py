import pytest

pytest_plugins = ["tests.harness.plugin"]


# A-026: tests must never make a real LLM transport network request.
@pytest.fixture(autouse=True)
def _no_real_llm_transport(monkeypatch):
    # Real network happens via httpx when the transport's send is not injected.
    def _forbid(*args, **kwargs):
        raise AssertionError("real LLM transport request in tests is forbidden")

    try:
        import httpx

        monkeypatch.setattr(httpx, "request", _forbid)
        monkeypatch.setattr(httpx.Client, "request", _forbid)
    except Exception:
        pass
    yield
