import pytest

pytest_plugins = ["tests.harness.plugin"]


# A-026: tests must never make a real LLM transport network request.
@pytest.fixture(autouse=True)
def _no_real_llm_transport(monkeypatch):
    # Real network happens via httpx when the transport's send is not injected.
    try:
        import httpx

        _real = httpx.request
        _real_client = httpx.Client.request

        def _forbid(*args, **kwargs):
            url = args[1] if len(args) > 1 else kwargs.get("url", "")
            if "testserver" in str(url):
                return _real(*args, **kwargs)
            raise AssertionError("real LLM transport request in tests is forbidden")

        def _forbid_client(self, *args, **kwargs):
            url = args[0] if args else kwargs.get("url", "")
            if "testserver" in str(url):
                return _real_client(self, *args, **kwargs)
            raise AssertionError("real LLM transport request in tests is forbidden")

        monkeypatch.setattr(httpx, "request", _forbid)
        monkeypatch.setattr(httpx.Client, "request", _forbid_client)
    except Exception:
        pass
    yield
