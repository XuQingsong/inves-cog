"""Clock fixtures shared with every test through the root plugin."""
from datetime import datetime, timezone
import pytest
from inves_cog.clock import FrozenClock, SystemClock


@pytest.fixture
def clock(pytestconfig, request):
    if (request.node.get_closest_marker('phase1_live') and
            pytestconfig.option.markexpr.strip() == 'phase1_live'):
        return SystemClock()
    return FrozenClock(datetime(2026, 10, 13, tzinfo=timezone.utc))
