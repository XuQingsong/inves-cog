"""A027 earnings cadence, durable rate fallback and zero-model news, offline."""
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
import yaml

from inves_cog.clock import FrozenClock
from inves_cog.ingest.runtime import due_tasks

pytestmark = pytest.mark.phase1_blocking
NY = ZoneInfo('America/New_York')


def clock(day='2026-10-30', hour=16, minute=1):
    return FrozenClock(datetime.fromisoformat(f'{day}T{hour:02}:{minute:02}:00').replace(tzinfo=NY))


@pytest.mark.parametrize('slot,hour,minute,expected', [
    ('pre',6,29,10),('pre',6,30,1),('pre',9,35,1),('pre',9,36,10),
    ('post',15,54,10),('post',15,55,1),('post',18,30,1),('post',18,31,10),
    ('unknown',6,30,1),('unknown',15,55,1),('pre',16,1,10),('post',8,1,10),
])
def test_window_boundaries(slot,hour,minute,expected):
    from inves_cog.ingest.earnings_news import news_interval
    c=clock(hour=hour,minute=minute)
    rows=[{'ticker':'NVDA','report_date':date(2026,10,30),'time':slot}]
    assert news_interval(c,rows)==expected


@pytest.mark.parametrize('day', ['2026-11-01','2026-03-08'])
def test_dst_local_window_and_utc_persisted_start(day):
    c=clock(day,6,31)
    rows=[{'ticker':'INTC','report_date':date.fromisoformat(day),'time':'unknown'}]
    last=c.now_utc()-timedelta(minutes=1)
    assert 'news_poll' in due_tasks(c,{'news_poll':last},earnings=rows)


def test_core_date_only_and_durable_backoff():
    from inves_cog.ingest.earnings_news import news_interval
    c=clock()
    row={'ticker':'INTC','report_date':date(2026,10,30),'time':'post'}
    assert news_interval(c,[dict(row,ticker='AAPL')])==10
    assert news_interval(c,[dict(row,report_date=date(2026,10,29))])==10
    assert news_interval(c,[])==10
    assert news_interval(c,[row],backoff_until=c.now_utc()+timedelta(minutes=5))==10
    assert news_interval(c,[row],backoff_until=c.now_utc())==1


def test_config_and_fallback_match_approved_table(tmp_path):
    from inves_cog.ingest.earnings_news import CORE_FALLBACK, core_tickers
    doc=Path('docs/phase1/design/anomaly-first-2026-10-30.md').read_text()
    table=doc.split('## 核心公司')[1].split('## 主线叙事')[0]
    assert len(CORE_FALLBACK)==29 and all(t in table for t in CORE_FALLBACK)
    assert core_tickers(tmp_path/'absent.yaml')==CORE_FALLBACK
    cfg=Path('config/core_companies.yaml')
    if cfg.exists():
        assert core_tickers(cfg)==CORE_FALLBACK
    cfg=tmp_path/'core.yaml'
    cfg.write_text(yaml.safe_dump({'companies':[{'ticker':'NVDA'}]}))
    assert core_tickers(cfg)=={'NVDA'}


def test_poll_rate_failure_persists_ten_minute_fallback():
    from inves_cog.ingest.earnings_news import poll_news
    from inves_cog.ingest.http import SourceError
    from inves_cog.ingest.jobs import HealthBook, JobRunner
    c=clock(); repo=Mock(); repo.core_earnings.return_value=[{'ticker':'NVDA','report_date':date(2026,10,30),'time':'post'}]
    repo.get_cursor.return_value=None
    p=SimpleNamespace(clock=c,repo=repo,news=Mock(side_effect=SourceError('HTTP status 429',status_code=429)))
    health=HealthBook(clock=c)
    runner=JobRunner(clock=c,health=health,persist=Mock())
    assert runner.run('news_poll','AlpacaNews',lambda:poll_news(p))['status']=='failed'
    saved=repo.set_cursor.call_args.args[1]
    assert datetime.fromisoformat(saved['until'])>c.now_utc()
    assert health.rows['AlpacaNews']['status']=='degraded'
    assert '10 minutes' in health.rows['AlpacaNews']['note']
    repo.get_cursor.return_value=saved
    p.news.side_effect=None;p.news.return_value={'processed_count':0}
    poll_news(p)
    p.news.assert_called_with(accelerated=False)


def test_accelerated_news_budget_and_no_model():
    from inves_cog.ingest.http import HTTPClient, Response, SourceError
    from inves_cog.ingest.providers import Alpaca
    send=Mock(return_value=Response(200,{'news':[], 'next_page_token':'again'}))
    a=Alpaca(clock=clock(),key='fixture',secret='fixture',http=HTTPClient(send=send))
    with pytest.raises(SourceError):
        list(a.news(first=clock().now_utc(),last=clock().now_utc(),max_pages=1))
    assert send.call_count==1
    send.reset_mock();send.return_value=Response(429,{})
    with pytest.raises(SourceError):
        list(a.news(first=clock().now_utc(),last=clock().now_utc(),max_pages=30))
    assert send.call_count==1


def test_poll_calls_existing_rules_only_ingestion():
    from inves_cog.ingest.pipeline import Pipeline
    from inves_cog.ingest.info import make_item
    p=Pipeline.__new__(Pipeline);p.clock=clock();p.news_llm_enabled=False;p.triage=Mock()
    p.repo=Mock();p.repo.counts={};p.repo.get_cursor.return_value={'through':p.clock.now_utc().isoformat()}
    p.repo.info_signature.return_value=None;p.repo.latest_news_at.return_value=p.clock.now_utc()
    p.alpaca=Mock();p.alpaca.news.return_value=[make_item('news','Benzinga','test',headline='NVDA reports quarterly earnings',tickers=['NVDA'],clock=p.clock,published_at=p.clock.now_utc())]
    p.news(accelerated=True)
    assert p.repo.put_info.call_count==1
    assert p.triage.mock_calls==[]
    assert p.alpaca.news.call_args.kwargs['max_pages']==30
