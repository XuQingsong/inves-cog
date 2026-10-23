"""A016: ET windows, real upstream completion and explicit input gaps."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.trading.execution import cli

NY = ZoneInfo('America/New_York')


def clock(day, hour, minute):
    return FrozenClock(datetime.fromisoformat(day).replace(hour=hour, minute=minute, tzinfo=NY))


@pytest.mark.parametrize('day', ['2026-07-13', '2026-01-12'])
def test_e1_et_window_and_restart(day):
    for hour, minute, expected in [(8, 34, False), (8, 35, True), (9, 4, True), (9, 5, False)]:
        c = clock(day, hour, minute)
        assert cli.due(c) is expected
        assert not cli.due(c, last=c.now_utc())
    assert not cli.due(FrozenClock(datetime.fromisoformat(day).replace(hour=20, tzinfo=ZoneInfo('Asia/Shanghai'))))


def test_e2_only_real_success_before_now_is_ready():
    c = clock('2026-07-13', 8, 51)
    ended = clock('2026-07-13', 8, 50).now_utc()
    from inves_cog.trading.execution.cli import scores_ready
    assert scores_ready([{'status': 'ok', 'ended_at': ended}], c.now_utc())
    assert not scores_ready([{'status': 'ok', 'ended_at': ended}], clock('2026-07-13', 8, 49).now_utc())
    assert not scores_ready([{'status': 'failed', 'ended_at': ended}], c.now_utc())
    assert not scores_ready([{'status': 'ok', 'ended_at': None}], c.now_utc())


def test_e5_seven_sources_no_empty_insider_proof():
    from inves_cog.trading.execution.completeness import describe_inputs
    c = clock('2026-07-13', 8, 40)
    day = date(2026, 7, 10)
    inputs = {'bars': {'AAA': {day: {'open': 10, 'close': 11}}},
              'signals': {'AAA': {day: {}}}, 'vix': {}, 'first_trade_dates': {'AAA': day}}
    plan = {'missing_scores': [], 'missing_tickers': [], 'overlay': {'status': 'missing', 'version': None}}
    result = describe_inputs(plan, inputs, [{'ticker': 'AAA'}], signal_day=day,
                             cutoff=c.now_utc(), insiders={}, ledger=None, ledger_checked=True)
    assert set(result['sources']) == {'scores', 'bars', 'vix', 'membership', 'insiders', 'overlay', 'ledger'}
    for source in result['sources'].values():
        assert {'status', 'visible_at', 'coverage', 'missing', 'fallback', 'impact'} <= source.keys()
    assert result['sources']['vix']['status'] == 'missing'
    assert result['sources']['vix']['fallback'] == '按非恐慌'
    assert result['sources']['insiders']['status'] == 'unknown'
    assert result['sources']['membership']['status'] == 'unknown'
    assert result['sources']['overlay']['impact'] == '冷静期未生效'
    assert result['sources']['ledger']['status'] == 'missing'
