from urllib.error import HTTPError

import pytest

from inves_cog.dataguard.trace import SourceTrace, reason

pytestmark = pytest.mark.phase1_blocking


def test_source_evidence_keeps_status_but_never_url_key_or_message():
    trace = SourceTrace()
    trace.record(HTTPError("https://fixture.test?key=secret-fixture", 429, "private-fixture", {}, None))
    assert trace.errors == [{"error_type": "HTTPError", "http_status": 429}]
    assert "429" in reason({"source_errors": trace.errors})
    assert "secret-fixture" not in str(trace.errors) and "private-fixture" not in str(trace.errors)
