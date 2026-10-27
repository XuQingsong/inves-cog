import pytest

pytest_plugins = ["tests.harness.plugin"]


# A-026: tests must never make a real LLM transport network request.
@pytest.fixture(autouse=True)
def _no_real_llm_transport(monkeypatch):
    def _forbid(*args, **kwargs):
        raise AssertionError("real LLM transport request in tests is forbidden")

    try:
        monkeypatch.setattr("inves_cog.llm.transport.OpenAICompatibleTransport.__call__", _forbid)
    except Exception:
        pass
    yield
