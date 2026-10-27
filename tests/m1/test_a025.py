"""A025 minute/overnight observations: injected clocks, recorded quotes, no network."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.ingest.runtime import due_tasks

pytestmark = pytest.mark.phase1_blocking


@pytest.mark.parametrize('moment,stock,macro,wide', [
    ('2026-10-27T04:01:00-04:00', True, True, False),
    ('2026-10-27T09:35:00-04:00', True, True, True),
    ('2026-10-27T16:01:00-04:00', True, True, False),
    ('2026-10-27T20:15:00-04:00', False, True, False),
    ('2026-10-28T03:15:00-04:00', False, True, False),
    ('2026-10-24T20:15:00-04:00', False, True, False),
    ('2026-11-02T04:01:00-05:00', True, True, False),
])
def test_schedule_each_minute_and_overnight_quarter_hour(moment, stock, macro, wide):
    c = FrozenClock(datetime.fromisoformat(moment))
    last = {n: c.now_utc() - timedelta(minutes=1) for n in ('intraday_snapshots','yahoo_intraday','wide_snapshots')}
    tasks = due_tasks(c, last)
    assert ('intraday_snapshots' in tasks) == stock
    assert ('yahoo_intraday' in tasks) == macro
    assert ('wide_snapshots' in tasks) == wide
    assert not set(last) & set(due_tasks(c, dict.fromkeys(last, c.now_utc())))


def test_overnight_symbols_weekends_and_original_session():
    from inves_cog.ingest.intraday import yahoo_symbols, parse_yahoo_snapshot, YAHOO_TICKERS
    from tests.m1.test_a024_yahoo import sample
    c = FrozenClock(datetime.fromisoformat('2026-10-27T01:15:00-04:00'))
    assert yahoo_symbols(c.now_utc()) == YAHOO_TICKERS
    assert yahoo_symbols(datetime.fromisoformat('2026-10-24T21:00:00-04:00')) == ('BTC-USD',)
    assert yahoo_symbols(datetime.fromisoformat('2026-10-25T18:15:00-04:00')) == YAHOO_TICKERS
    raw = sample('ES=F')
    raw['chart']['result'][0]['meta']['regularMarketTime'] = (c.now_utc()-timedelta(minutes=16)).timestamp()
    r = parse_yahoo_snapshot(raw,'ES=F',c)
    assert r['session'] == 'overnight' and r['delay_minutes'] == 16
    assert r['as_of'] != r['fetched_at']


def test_persisted_failure_backoff_recovery_and_quarter_hour_health():
    from inves_cog.ingest.snapshot_poll import SnapshotPoll
    state, health = {}, Mock()
    repo = Mock()
    repo.get_cursor.side_effect = lambda k: state.get(k)
    repo.set_cursor.side_effect = lambda k,v,t: state.update({k:v})
    t = datetime.fromisoformat('2026-10-27T10:00:00-04:00')
    def poll(at, good=False):
        op = Mock(return_value={'processed_count': 1 if good else 0, 'source_success':good,
                                'status':'ok' if good else 'degraded'})
        return SnapshotPoll(repo, FrozenClock(at), health).run('yahoo_intraday','YahooIntraday',op), op
    poll(t)
    for minutes, delay in [(1,2),(3,4),(7,8),(15,15)]:
        poll(t+timedelta(minutes=minutes))
        s = state['snapshot-poll:yahoo_intraday']
        assert datetime.fromisoformat(s['retry_at']) == t+timedelta(minutes=minutes+delay)
    _, op = poll(t+timedelta(minutes=16))
    op.assert_not_called()
    poll(t+timedelta(minutes=30), True)
    assert state['snapshot-poll:yahoo_intraday']['failures'] == 0
    assert health.record.call_count == 3  # first observation, +15, +30
    assert 'backoff_seconds=0' in health.record.call_args.kwargs['note']


def test_wide_scope_and_duplicate_insert_contract():
    from inves_cog.ingest.intraday import collect_wide
    from tests.m1.test_a024 import sample
    c = FrozenClock(datetime.fromisoformat('2026-10-26T10:00:00-04:00'))
    repo, http = Mock(), Mock()
    repo.latest_wide.return_value = [{'ticker':'SPY','included':True}, {'ticker':'BAD','included':False}]
    http.get.side_effect = [sample('spy_snapshot.json'), sample('spy_previous_all.json')]
    p = SimpleNamespace(clock=c,repo=repo,alpaca=SimpleNamespace(headers={}))
    result = collect_wide(p,http=http)
    assert result['processed_count'] == 1
    assert http.get.call_args_list[0].kwargs['params']['symbols'] == 'SPY'
    assert repo.write.call_args.args[0] == 'wide_snapshots'
    assert not repo.write.call_args.kwargs.get('update')


def test_alpaca_429_persists_halt_and_never_auto_retries():
    from inves_cog.ingest.snapshot_poll import SnapshotPoll
    state, repo = {}, Mock()
    repo.get_cursor.side_effect = lambda k: state.get(k)
    repo.set_cursor.side_effect = lambda k,v,t: state.update({k:v})
    c = FrozenClock(datetime.fromisoformat('2026-10-27T10:00:00-04:00'))
    op = Mock(return_value={'processed_count':0,'source_success':False,'rate_limited':True})
    poll = SnapshotPoll(repo,c,Mock())
    poll.run('intraday_snapshots','AlpacaIntraday',op)
    poll.run('wide_snapshots','AlpacaWideSnapshots',op)
    poll.run('intraday_snapshots','AlpacaIntraday',op)
    assert op.call_count == 1
