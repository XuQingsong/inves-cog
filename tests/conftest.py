import pytest

pytest_plugins = ["tests.harness.plugin"]


# A-026: tests must never make a real LLM transport network request.


# A-026: tests must never make a real LLM transport network request.
@pytest.fixture(autouse=True)
def _no_real_llm_transport(monkeypatch):
    # A real transport (send=None) would hit the network; force a forbidden send.
    from inves_cog.llm.transport import OpenAICompatibleTransport

    real_init = OpenAICompatibleTransport.__init__

    def _guarded_init(self, configuration, *, send=None):
        real_init(self, configuration, send=send or _forbidden_send)

    def _forbidden_send(*args, **kwargs):
        raise AssertionError("real LLM transport request in tests is forbidden")

    monkeypatch.setattr(OpenAICompatibleTransport, "__init__", _guarded_init)
    yield
