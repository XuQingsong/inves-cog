"""A023 uses recorded public-source responses and an injected clock, offline."""
import json
from pathlib import Path
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from inves_cog.clock import FrozenClock

pytestmark = pytest.mark.phase1_blocking
FIXTURES = Path(__file__).parent / 'fixtures/a023'
CLOCK = FrozenClock(datetime(2026, 10, 26, 14, tzinfo=timezone.utc))


def sample(name):
    return json.loads((FIXTURES / name).read_text())


def test_a023_real_calendar_shapes_and_missing_numbers():
    from inves_cog.ingest.resilience import parse_earnings, parse_econ
    rows = parse_earnings(sample('earnings_2026-10-28.json'), date(2026,10,28), CLOCK)
    googl = next(r for r in rows if r['ticker']=='GOOGL')
    assert googl['time']=='post' and googl['eps_forecast']==2.94 and googl['n_estimates']==14
    assert googl['market_cap']==3965210590000 and rows[-1]['time']=='pre'
    raw=sample('earnings_2026-10-28.json'); raw['data']['rows'][0]['epsForecast']='N/A'
    assert parse_earnings(raw,date(2026,10,28),CLOCK)[0]['eps_forecast'] is None
    econ=parse_econ(sample('econ_2026-10-28.json'),date(2026,10,28),CLOCK)
    assert econ and all(r['country']=='United States' for r in econ)
    assert all(r['actual'] is None for r in econ)
    assert econ[-1]['event_time_et']=='08:30'


def test_a023_yahoo_close_date_and_no_current_unclosed_daily_bar():
    from inves_cog.ingest.resilience import parse_yahoo_vix
    rows=parse_yahoo_vix(sample('vix.json'),'VIX_YAHOO',CLOCK)
    assert next(r for r in rows if r['observation_date']==date(2026,10,23))['value']==pytest.approx(19.45)
    assert all(r['fetched_at']==CLOCK.now_utc() for r in rows)
    raw=sample('vix.json'); raw['chart']['result'][0]['timestamp']=[int(CLOCK.now_utc().timestamp())]
    raw['chart']['result'][0]['indicators']['quote'][0]['close']=[99]
    assert parse_yahoo_vix(raw,'VIX_YAHOO',CLOCK)==[]


def test_a023_vix_priority_and_v18_cboe_unchanged():
    from inves_cog.trading.execution.repository import select_vix
    d=date(2026,10,23)
    rows=[{'series_id':s,'observation_date':d,'value':v} for s,v in [('VIXCLS',17),('VIX_YAHOO',19.45),('VIX_CBOE',20)]]
    assert select_vix(rows)==({d:20},{d:'VIX_CBOE'})
    assert select_vix(list(reversed(rows)))==select_vix(rows)
    assert select_vix(rows[:2])==({d:19.45},{d:'VIX_YAHOO'})
    assert select_vix(rows[:1])==({d:17},{d:'VIXCLS'})
    for row in rows[:2]: row['value']=None
    assert select_vix(rows)==({d:20},{d:'VIX_CBOE'})


def test_a023_cboe_failure_still_collects_both_yahoo_series_and_health():
    from inves_cog.ingest.resilience import collect_vix
    repo=Mock(); repo.health_rows.return_value={}
    def get(url,**kw):
        if 'cboe.com' in url: raise RuntimeError('blocked')
        return sample('vix.json')
    http=SimpleNamespace(get=get)
    result=collect_vix(SimpleNamespace(repo=repo,clock=CLOCK),http=http)
    assert result['processed_count']>0
    assert {c.args[1]['series_id'] for c in repo.write.call_args_list}=={'VIX_YAHOO','VIX3M_YAHOO'}
    health={c.args[0]['source']:c.args[0] for c in repo.write_health.call_args_list}
    assert health['VIX_CBOE']['consecutive_failures']==1
    assert health['VIX_YAHOO']['items_last_run']>0
    assert '2026-10-23' in health['VIX_YAHOO']['note']


def test_a023_rule_only_news_preserves_content_and_never_calls_models():
    from inves_cog.ingest.pipeline import Pipeline
    from inves_cog.ingest.info import make_item
    p=Pipeline.__new__(Pipeline); p.news_llm_enabled=False; p.clock=CLOCK; p.repo=Mock(); p.triage=Mock()
    p.repo.info_signature.return_value=None
    row=make_item('news','benzinga','1',headline='Company raises outlook',body='original',clock=CLOCK,published_at=CLOCK.now_utc(),tickers=['AAPL'])
    p.info([row]); saved=p.repo.put_info.call_args.args[0]
    assert saved['extraction_status']=='ok' and saved['extraction_source']['news_triage']['reason']=='rules_only'
    assert saved['body']=='original' and saved['first_seen_at']==row['first_seen_at'] and saved['tickers']==['AAPL']
    p.repo.finish_pending_news.return_value=2; p.repo.pending_info.return_value=[]
    assert p.enrich_pending()['rules_only']==2
    p.triage.process.assert_not_called()


def test_a023_schedule_calendar_and_news_monitor_independent():
    from inves_cog.ingest.runtime import due_tasks
    tasks=due_tasks(CLOCK,{})
    assert {'earnings_calendar','econ_calendar','news_poll','news_watchdog'}<=set(tasks)
    sunday=FrozenClock(datetime(2026,10,25,14,tzinfo=timezone.utc))
    assert 'news_watchdog' not in due_tasks(sunday,{})
