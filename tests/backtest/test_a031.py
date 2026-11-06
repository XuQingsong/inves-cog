"""A031 keeps research exits opt-in and removes the technical fallback."""
from datetime import datetime, timezone

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.backtest.policies import BacktestEngine
from inves_cog.trading.execution.state import new_position

pytestmark = pytest.mark.phase1_blocking


@pytest.mark.parametrize('flag,fear,quality,expected', [
    ('breakdown_v2', 0, 80, None),
    ('breakdown_v2', 2, 80, None),
    ('breakdown_v2', 3, 80, .8),
    ('breakdown_v2', 0, 70, .8),
    ('breakdown_v2b', 3, 80, 1/3),
    ('breakdown_v2b', 3, 70, .8),
    ('breakdown_v2b', 0, 70, .8),
])
def test_r2_exit_requires_fundamental_or_market_risk(flag, fear, quality, expected):
    engine = BacktestEngine(clock=FrozenClock(datetime(2026, 10, 30, tzinfo=timezone.utc)), flags={flag: True})
    engine.signal_date = engine.clock.today_trade_date()
    engine.positions['NVDA'] = new_position(shares=30, price=100, tier='normal', index=0, state_version='',
                                          entry_books={'quality': 80, 'growth': 80})
    engine.scores = {'NVDA': {'tier': 'normal', 'books': {'quality': quality, 'growth': 80},
                            'red_lines': ['趋势破位'], 'fear_level': fear,
                            'breakdown_below_days': 20, 'breakdown_depth_atr': 5}}
    engine.queue('NVDA', 'sell_frac', 'M-55', '破位减仓', fraction=.8)
    actual = engine.pending[0]['fraction'] if engine.pending else None
    assert actual == expected


def test_r2_runner_selects_optional_engine():
    from inves_cog.backtest.runner import research_policy_enabled
    assert research_policy_enabled({'breakdown_v2': True})
    assert research_policy_enabled({'breakdown_v2b': True})
    assert not research_policy_enabled({})
