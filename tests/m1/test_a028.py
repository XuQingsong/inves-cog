"""A028 real-shaped source contracts and deterministic pre-earnings sampling."""
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from inves_cog.clock import FrozenClock

pytestmark = pytest.mark.phase1_blocking
NY = ZoneInfo('America/New_York')

def clock(day='2026-11-16', hour=15, minute=50):
    return FrozenClock(datetime.combine(date.fromisoformat(day), datetime.min.time(), NY).replace(hour=hour, minute=minute))

def test_consensus_scope_and_raw_quarter_currency():
    from inves_cog.ingest.earnings_data import consensus_fields, target_tickers
    assert target_tickers(['AAPL'], ['IBM'], ['NVDA']) == ['AAPL', 'IBM', 'NVDA']
    assert consensus_fields({'raw': {'revenue_estimate': {'0q': {'avg': 123, 'revenueCurrency': 'USD'}}}}) == {'rev_cq': 123, 'rev_cq_currency': 'USD'}
    assert consensus_fields({'rev_cy': 999, 'raw': {}}) == {'rev_cq': None, 'rev_cq_currency': None}

def test_calendar_horizon_includes_45_days_and_holidays():
    from inves_cog.ingest.resilience import calendar_days
    days = calendar_days(date(2026, 10, 30))
    assert max(days) >= date(2026, 12, 14)
    assert date(2026, 11, 17) in days

def test_implied_capture_pre_post_weekend_and_dedupe():
    from inves_cog.ingest.implied_moves import capture_targets
    rows = [{'ticker': 'NVDA', 'report_date': date(2026, 11, 17), 'time': 'post'}, {'ticker': 'INTC', 'report_date': date(2026, 11, 16), 'time': 'pre'}]
    assert [r['ticker'] for r in capture_targets(clock('2026-11-13'), rows, {'NVDA', 'INTC'})] == ['INTC', 'NVDA']
    assert capture_targets(clock('2026-11-14'), rows, {'NVDA', 'INTC'}) == []
    assert capture_targets(clock('2026-11-16', 15, 49), rows, {'NVDA', 'INTC'}) == []
    assert [r['ticker'] for r in capture_targets(clock(), rows * 2, {'NVDA', 'INTC'})] == ['NVDA']

def snapshots():
    out = {}
    for expiry in ['261117', '261120']:
        for strike in [210, 212.5, 215]:
            for side, bid, ask in [('C', 9.8, 10.0), ('P', 8.1, 8.3)]:
                out[f'NVDA{expiry}{side}{int(strike * 1000):08d}'] = {'latestQuote': {'t': '2026-11-16T20:49:59Z', 'bp': bid, 'ap': ask}, 'greeks': {'delta': .5}}
    return {'snapshots': out, 'next_page_token': None}

@pytest.mark.parametrize('slot,expiry', [('pre', date(2026, 11, 17)), ('post', date(2026, 11, 20)), ('unknown', date(2026, 11, 20))])
def test_expiry_strike_missing_iv_and_aligned_spot(slot, expiry):
    from inves_cog.ingest.implied_moves import select_move
    row = select_move('NVDA', date(2026, 11, 17), slot, snapshots()['snapshots'], clock().now_utc(), lambda at: {'last': 213.7, 'as_of': at, 'source': 'AlpacaIEX'})
    assert row['expiry'] == expiry and row['strike'] == 212.5
    assert row['spot_source'] == 'IEX' and row['iv_call'] is None and row['iv_put'] is None
    assert row['straddle_pct'] == pytest.approx(18.1 / 213.7)
    assert row['feed'] == 'indicative'

def test_mismatched_session_or_stale_quotes_not_fabricated():
    from inves_cog.ingest.implied_moves import select_move
    def spot(at): return {'last': 213.7, 'as_of': at - timedelta(minutes=16), 'source': 'AlpacaIEX'}
    assert select_move('NVDA', date(2026, 11, 17), 'post', snapshots()['snapshots'], clock().now_utc(), spot) is None
    assert select_move('NVDA', date(2026, 11, 17), 'post', snapshots()['snapshots'], clock('2026-11-17').now_utc(), lambda at: {'last': 213.7, 'as_of': at, 'source': 'AlpacaIEX'}) is None

def test_consensus_daily_no_models_and_retry_only_next_day():
    from inves_cog.ingest.earnings_data import collect_consensus
    repo = SimpleNamespace(snapshot_today=Mock(return_value=False), annual_years=Mock(return_value=(None, None)), put_snapshot=Mock())
    provider = SimpleNamespace(collect=Mock(return_value={'ticker': 'NVDA', 'raw': {'earnings_estimate': {'0q': {'avg': 2}}}}))
    llm = Mock()
    result = collect_consensus(clock=clock(), repository=repo, tickers=['NVDA'], provider=provider)
    assert result['processed_count'] == 1
    repo.put_snapshot.assert_called_once()
    repo.snapshot_today.return_value = True
    assert collect_consensus(clock=clock(), repository=repo, tickers=['NVDA'], provider=provider)['processed_count'] == 0
    assert provider.collect.call_count == 1 and llm.mock_calls == []
