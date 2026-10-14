"""M1 v2 contracts: both boundary rejection and valid-input preservation."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path

import pytest
import yaml

from inves_cog.clock import FrozenClock
from tests.harness.tools.golden import load_golden

pytestmark = pytest.mark.phase1_blocking
ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures/phase1'


def instant(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00'))


def frozen(text='2026-10-29T00:30:00Z'):
    return FrozenClock(instant(text))


class FakeTime:
    def __init__(self):
        self.value = 0.0
        self.waits = []

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        assert seconds >= 0
        self.waits.append(seconds)
        self.value += seconds


def test_bar_window_to_20et():
    from inves_cog.ingest.market import MarketCollector, market_window, schedule_times
    from inves_cog.ingest.http import HTTPClient, Response
    from inves_cog.ingest.sec_client import SECClient
    from inves_cog.llm.client import Client, LLMUnavailable
    settings = yaml.safe_load((ROOT / 'config/params/p-2026.10/m1.yaml').read_text())['m1']
    assert settings['minute_window'] == {'start': '04:00', 'end': '20:00', 'timezone': 'America/New_York'}
    assert market_window(date(2026, 10, 28))[1] == instant('2026-10-29T00:00:00Z')
    assert market_window(date(2026, 11, 2))[1] == instant('2026-11-03T01:00:00Z')
    assert schedule_times(date(2026, 10, 28))['full_start'] == instant('2026-10-29T00:20:00Z')
    assert schedule_times(date(2026, 11, 2))['full_deadline'] == instant('2026-11-03T01:45:00Z')
    pages = [Response(200, {'bars': {'AAPL': [{'t': '2026-10-28T13:30:00Z', 'o': 100, 'h': 101, 'l': 99, 'c': 100, 'v': 3}]}, 'next_page_token': 'next'}), Response(200, {'bars': {}, 'next_page_token': None})]
    calls = []
    def send(method, url, **kwargs):
        calls.append(kwargs)
        return pages.pop(0)
    collector = MarketCollector(HTTPClient(send), clock=frozen())
    result = collector.minute_bars(['AAPL'], date(2026, 10, 28))
    assert result.exhausted and len(result.rows) == 1
    assert all(call['params']['feed'] == 'sip' for call in calls)
    assert calls[1]['params']['page_token'] == 'next'
    assert result.coverage['AAPL'] == pytest.approx(1 / 390)
    iex = MarketCollector(HTTPClient(lambda *a, **k: Response(200, {'bars': {}, 'next_page_token': None})), clock=frozen(), feed='iex')
    assert iex.minute_bars(['AAPL'], date(2026, 10, 28)).status == 'degraded'
    timer, requests = FakeTime(), []
    def sec_send(method, url, **kwargs):
        requests.append((timer.value, kwargs))
        return Response(200, {'ok': True})
    client = SECClient(HTTPClient(sec_send), user_agent='fixture-contact.invalid', monotonic=timer.monotonic, sleep=timer.sleep)
    for _ in range(6):
        client.get('https://data.sec.gov/submissions/CIK0000320193.json')
    assert requests[5][0] - requests[0][0] >= 1
    assert all(req[1]['headers']['User-Agent'] == 'fixture-contact.invalid' for req in requests)
    with pytest.raises(ValueError, match='SEC_USER_AGENT'):
        SECClient(HTTPClient(sec_send), user_agent='')
    registry = ROOT / 'config/llm_tasks.yaml'
    llm = Client(registry=registry, recordings=FIXTURES / 'recordings')
    assert llm.call('entity_tagging', {'headline': 'Apple introduces a product', 'body': 'AAPL'}) == {'entities': ['apple']}
    with pytest.raises(ValueError, match='unregistered'):
        llm.call('unknown', {})
    with pytest.raises(LLMUnavailable):
        llm.call('entity_tagging', {'unrecorded': True})


def test_bar_window_from_04et():
    from inves_cog.ingest.market import market_window, bar_session, schedule_times
    assert market_window(date(2026, 10, 28))[0] == instant('2026-10-28T08:00:00Z')
    assert schedule_times(date(2026, 11, 2))['prefill'] == instant('2026-11-02T13:00:00Z')
    assert bar_session(instant('2026-11-27T17:59:00Z')) == 'intraday'
    assert bar_session(instant('2026-11-27T18:00:00Z')) == 'post'
    assert bar_session(instant('2026-10-28T13:30:00Z')) == 'intraday'
    assert bar_session(instant('2026-10-28T07:59:00Z')) is None
    assert bar_session(instant('2026-10-29T00:00:00Z')) is None
    assert bar_session(instant('2026-11-26T15:00:00Z')) is None


def test_post_close_null_when_no_trade():
    from inves_cog.ingest.market import post_close, split_factors
    bars = [{'ts_utc': instant('2026-10-28T19:59:00Z'), 'close': 100, 'volume': 3}]
    assert post_close(bars, date(2026, 10, 28)) is None
    bars += [{'ts_utc': instant('2026-10-29T00:00:00Z'), 'close': 130, 'volume': 5}, {'ts_utc': instant('2026-10-28T22:00:00Z'), 'close': 110, 'volume': 0}]
    assert post_close(bars, date(2026, 10, 28)) is None
    bars += [{'ts_utc': instant('2026-10-28T21:00:00Z'), 'close': 105, 'volume': 2}]
    assert post_close(bars, date(2026, 10, 28)) == 105
    assert split_factors([date(2026, 10, 27), date(2026, 10, 28)], [{'date': date(2026, 10, 28), 'ratio': 2}]) == [0.5, 1.0]


def test_wide_universe_rules():
    from inves_cog.ingest.universe import build_universe, daily_liquidity
    candidates = json.loads((FIXTURES / 'm1/wide_candidates.json').read_text())
    rows = build_universe(candidates, date(2026, 10, 1))
    by_name = {r['ticker']: r for r in rows}
    assert by_name['GOOD']['included']
    for ticker, reason in {'ETF': 'non_common', 'ADR': 'non_common', 'SMALL': 'below_mktcap', 'THIN': 'below_adv', 'MISSING': 'no_shares', 'NOCIK': 'no_cik', 'NOPRICE': 'no_price', 'SHORT': 'insufficient_history'}.items():
        assert by_name[ticker]['exclude_reason'] == reason
        assert not by_name[ticker]['included']
    assert 'multi_class_approx' in by_name['CLASS.A']['notes']
    assert by_name['ETF']['notes']
    first = daily_liquidity(rows, {'GOOD': 19_999_999}, date(2026, 10, 2))
    second = daily_liquidity(first, {'GOOD': 100_000_000}, date(2026, 10, 5))
    assert not next(r for r in second if r['ticker'] == 'GOOD')['included']
    assert next(r for r in rows if r['ticker'] == 'GOOD')['included']


def test_news_dedupe_and_times():
    from inves_cog.ingest.info import InfoStore, make_item, source_root
    clock = frozen()
    store = InfoStore()
    item = make_item('news', 'Reuters', 'a', headline='Growth', body='<p>Sales 10, not 20.</p>', clock=clock, published_at=instant('2026-10-28T17:00:00Z'))
    assert store.put(item) == 'inserted'
    assert store.put(deepcopy(item)) == 'deduped'
    changed = deepcopy(item)
    changed.update(body='Sales 11, not 20.', published_at=instant('2026-10-28T18:00:00Z'))
    assert store.put(changed) == 'deduped'
    assert len(store.items) == 1 and len(store.versions) == 1
    saved = store.items[item['info_id']]
    assert saved['published_at'] == item['published_at'] and saved['first_seen_at'] == clock.now_utc()
    assert saved['source_root'] == item['source_root']
    assert saved['body'] == changed['body']
    assert source_root('<p>ＡＢＣ\n Sales 10, not 20.</p>') == source_root('ABC Sales 10, not 20.')
    assert source_root('Sales 10') != source_root('Sales 20')
    assert source_root('not increased') != source_root('increased')
    assert source_root('x', provider='Reuters', upstream_id='1') == 'Reuters:1'
    assert source_root('different', provider='Reuters', upstream_id='1') == 'Reuters:1'
    store.compact(instant('2027-02-01T00:00:00Z'))
    assert saved['body'] is None and saved['summary'] == changed['body'][:500]
    assert store.counts == {'collected': 3, 'inserted': 1, 'deduped': 2}


def test_earnings_reaction_day():
    from inves_cog.ingest.sec import earnings_event, parse_acceptance_et
    for case in load_golden('m1_earnings_sessions.json')['cases']:
        accepted = parse_acceptance_et(case['accepted_at_et'] + 'Z')
        assert accepted == instant(case['accepted_at_utc'])
        event = earnings_event({'ticker': 'AAPL', 'accession': 'fixture', 'form': '8-K', 'items': ['2.02'], 'accepted_at': accepted}, closes={}, clock=frozen())
        assert event['session'] == case['session']
        assert event['reaction_day'] == date.fromisoformat(case['reaction_day'])
    assert earnings_event({'form': '10-Q', 'items': ['2.02']}, closes={}, clock=frozen()) is None
    assert earnings_event({'form': '8-K', 'items': ['7.01']}, closes={}, clock=frozen()) is None


def test_earnings_fallback_flag():
    from inves_cog.ingest.sec import earnings_fallback
    uncertain = earnings_fallback('AAPL', {'reportDate': '2026-10-29'}, clock=frozen())
    assert uncertain['fallback'] and uncertain['session'] is None and uncertain['reaction_day'] is None
    assert {'earnings_event_fallback', 'earnings_event_time_unknown'} <= set(uncertain['flags'])
    assert earnings_fallback('AAPL', {'reportDate': '2026-10-30', 'session': 'post'}, clock=frozen())['reaction_day'] == date(2026, 11, 2)


def test_form4_parse_code_p():
    from inves_cog.ingest.sec import parse_form4
    text = (FIXTURES / 'm1/form4_synthetic.xml').read_text()
    rows = parse_form4(text, accession='fixture-form4', filed_at=instant('2026-10-28T15:00:00Z'))
    assert len(rows) == 2
    assert rows[0]['transaction_code'] == 'P' and rows[0]['is_officer'] is True
    assert rows[0]['shares'] == 100 and rows[0]['price'] == 10.5
    assert rows[0]['filed_at'] == instant('2026-10-28T15:00:00Z')
    assert rows[1]['price'] is None and rows[1]['transaction_code'] == 'S'


def test_app_rank_jump():
    from inves_cog.ingest.signals import rank_jumps
    rows = rank_jumps({'app': 45}, {'app': 24}, chart='free', clock=frozen())
    assert len(rows) == 1 and rows[0]['kind'] == 'app_rank'
    assert rank_jumps({'app': 45}, {'app': 25}, chart='free', clock=frozen()) == []
    assert len(rank_jumps({}, {'app': 80}, chart='grossing', clock=frozen())) == 1
    assert rank_jumps({}, {'app': 81}, chart='grossing', clock=frozen()) == []


def test_trends_unavailable_marked():
    from inves_cog.ingest.signals import trend_event, collect_trends
    from inves_cog.ingest.jobs import HealthBook
    health = HealthBook(clock=frozen())
    def broken(*args):
        raise ValueError('confirmed source unusable')
    rows = collect_trends(['fixture'], fetch=broken, health=health, clock=frozen())
    assert rows == [] and health.rows['GoogleTrends']['status'] == '未接通'
    days = [{'date': date(2026, 10, 28) - timedelta(days=i), 'value': 10} for i in range(1, 91)]
    assert trend_event('fixture', days, 31, clock=frozen('2026-10-28T15:00:00Z'))['kind'] == 'trend'
    assert trend_event('fixture', days, 30, clock=frozen('2026-10-28T15:00:00Z')) is None
    assert trend_event('fixture', days[:59], 100, clock=frozen('2026-10-28T15:00:00Z')) is None
    assert trend_event('fixture', [dict(day, value=0) for day in days], 1, clock=frozen('2026-10-28T15:00:00Z')) is None
    health.record('source', success=True, count=3)
    assert health.rows['source']['status'] == 'ok'
    health.record('source', success=False)
    assert health.rows['source']['status'] == 'ok'
    health.record('source', success=False)
    assert health.rows['source']['status'] == 'degraded'
    health.clock = frozen('2026-10-31T00:30:00Z')
    health.record('source', success=False)
    assert health.rows['source']['status'] == 'unavailable'
    health.record('source', success=True)
    assert health.rows['source']['status'] == 'ok'


def test_source_level_mapping():
    from inves_cog.ingest.info import source_level
    for source in ('SEC', 'CompanyIR', 'Government', 'CentralBank'):
        assert source_level(source) == 1
    for source in ('Reuters', 'Bloomberg', 'WSJ', 'FT', 'CNBC', 'AP'):
        assert source_level(source) == 2
    assert source_level('SellSide') == 3 and source_level('unknown') == 4
    entities = yaml.safe_load((ROOT / 'config/monitored_entities.yaml').read_text())['entities']
    assert entities and all({'entity_id', 'name', 'aliases', 'tickers', 'app_ids', 'trends_keywords', 'urls'} <= row.keys() for row in entities)
    universe = yaml.safe_load((ROOT / 'config/universe.yaml').read_text())
    assert len(universe['stocks']) == 59 and len(universe['etfs']) == 14


def test_info_item_contract(tmp_path):
    from inves_cog.ingest.info import make_item, InfoStore, enrich
    from inves_cog.ingest.sources import fred_observations, parse_cboe, parse_finra, website_change
    item = make_item('news', 'unknown', '1', headline='Unimportant update', body='x' * 600, clock=frozen())
    assert item['info_id'] == 'news:unknown:1'
    assert item['published_at'] is None and 'published_at_missing' in item['flags']
    assert item['summary'] == 'x' * 500 and item['embedding'] is None and item['extraction_status'] == 'pending'
    assert item['first_seen_at'].utcoffset().total_seconds() == 0
    with pytest.raises(ValueError):
        make_item('not-a-kind', 'unknown', '1', headline='x', body='x', clock=frozen())
    data = {'observations': [{'date': '2026-10-01', 'realtime_start': '2026-10-02', 'value': '.'}, {'date': '2026-10-01', 'realtime_start': '2026-10-03', 'value': '2.5'}]}
    observations = fred_observations('DGS2', data, units='Percent', clock=frozen())
    assert observations[0]['value'] is None and observations[1]['value'] == 2.5
    assert observations[0]['realtime_start'] != observations[1]['realtime_start']
    assert parse_finra([{'symbolCode': 'AAPL', 'issueExchange': 'OTC', 'currentShortPositionQuantity': 10}], allowed_tickers={'AAPL'}) == []
    assert parse_finra([{'symbolCode': 'AAPL', 'issueExchange': 'NASDAQ', 'currentShortPositionQuantity': 10, 'averageDailyVolumeQuantity': 0}], allowed_tickers={'AAPL'})[0]['days_to_cover'] is None
    assert parse_cboe('category,call_volume,put_volume,open_interest\nequity,100,50,\n', date(2026, 10, 28))[0]['open_interest'] is None
    assert website_change('https://example.invalid', '<p>unchanged</p>', '<p>unchanged</p>', clock=frozen()) is None
    assert website_change('https://example.invalid', '<p>old 1</p>', '<p>new 2</p>', clock=frozen())['kind'] == 'site_change'
    calls = []
    class Embed:
        def __call__(self, text, **kwargs):
            calls.append((text, kwargs))
            return [0.1] * 1024
    class LLM:
        def call(self, task, payload):
            return {'entities': []} if task == 'entity_tagging' else {'is_guidance': False, 'is_rating_change': False}
    enriched = enrich(item, llm=LLM(), embed=Embed(), entities=[], clock=frozen())
    assert len(enriched['embedding']) == 1024 and calls[0][1]['dimensions'] == 1024
    assert calls[0][1]['model'] == 'text-embedding-v3'
    assert enriched['is_guidance'] is False and enriched['is_rating_change'] is False
    store = InfoStore()
    assert store.put(enriched) == 'inserted'
    from inves_cog.ingest.settings import read_environment, source_configuration
    configuration = tmp_path / 'credentials.env'
    configuration.write_text('ALPACA_API_KEY_ID=fixture-key\n'
                             'ALPACA_API_SECRET_KEY="fixture-secret"\n'
                             'SEC_EDGAR_USER_AGENT="fixture contact@example.invalid"\n'
                             'ALPACA_DATA_FEED=iex\n'
                             'FRED_API_KEY=fixture-fred # local comment\n'
                             'LLM_STANDARD_API_KEY="$(not-executed)"\n')
    values = read_environment(configuration, environ={})
    assert values['APCA_API_KEY_ID'] == 'fixture-key'
    assert values['APCA_API_SECRET_KEY'] == 'fixture-secret'
    assert values['SEC_USER_AGENT'] == 'fixture contact@example.invalid'
    assert values['FRED_API_KEY'] == 'fixture-fred'
    assert values['LLM_STANDARD_API_KEY'] == '$(not-executed)'
    report = source_configuration(values)
    assert report['Alpaca']['configured'] and report['Alpaca']['feed'] == 'sip'
    assert report['SEC']['configured']
    assert not report['DashScope']['configured']
    assert report['DashScope']['missing'] == ['DASHSCOPE_API_KEY', 'DASHSCOPE_BASE_URL']
    assert 'fixture-secret' not in json.dumps(report)
    assert 'fixture-key' not in json.dumps(report)
    from inves_cog.ingest.providers import FRED
    from inves_cog.ingest.http import HTTPClient, Response
    requests = []
    def fred_response(method, url, **kwargs):
        requests.append(kwargs['params'])
        if url.endswith('/series'):
            return Response(200, {'realtime_end': '2026-10-13', 'seriess': [{'units': 'Percent'}]})
        offset = kwargs['params'].get('offset', 0)
        return Response(200, {'count': 2, 'observations': [
            {'date': '2026-10-01', 'realtime_start': f'2026-10-{12+offset}', 'value': '2.5'}]})
    fred = FRED(key='fixture-key', clock=frozen('2026-10-14T04:03:00Z'), http=HTTPClient(fred_response))
    records = fred.collect('DGS2')
    assert all(request['realtime_end'] == '2026-10-13' for request in requests[1:])
    assert len(records) == 2 and records[0]['realtime_start'] != records[1]['realtime_start']
    assert requests[-1]['offset'] == 1
    requests.clear()
    fred.clock = frozen('2026-10-10T12:00:00Z')
    fred.collect('DGS2')
    assert all(request['realtime_end'] == '2026-10-10' for request in requests[1:])
    configuration.write_text('APCA_API_KEY_ID=a\nALPACA_API_KEY_ID=b\n')
    with pytest.raises(ValueError, match='conflicting.*APCA_API_KEY_ID'):
        read_environment(configuration, environ={})
    configuration.write_text('not an assignment\n')
    with pytest.raises(ValueError, match='line 1'):
        read_environment(configuration, environ={})


def test_info_fields_extraction():
    from inves_cog.ingest.info import enrich, make_item
    from inves_cog.llm.client import Client
    llm = Client(registry=ROOT / 'config/llm_tasks.yaml', recordings=FIXTURES / 'recordings')
    item = make_item('news', 'Reuters', 'fixture', headline='Apple raises guidance', body='AAPL raises guidance; a broker raises its rating. Published 2026-10-28T16:00:00Z.', clock=frozen())
    result = enrich(item, llm=llm, embed=None, entities=[], clock=frozen())
    assert result['is_guidance'] is True and result['guidance_direction'] == 'up' and result['is_rating_change'] is True
    assert result['published_at'] == instant('2026-10-28T16:00:00Z')
    assert 'published_at_extracted' in result['flags'] and 'published_at_missing' not in result['flags']
    assert result['extraction_source']['is_guidance'] == 'llm'
    assert result['entities'] == ['apple']


def test_llm_extraction_failure_degrades():
    from inves_cog.ingest.info import enrich, make_item, InfoStore
    from inves_cog.llm.client import Client, LLMUnavailable
    item = make_item('news', 'Reuters', 'failure', headline='Fixture failure', body='Retain all information', clock=frozen())
    llm = Client(registry=ROOT / 'config/llm_tasks.yaml', recordings=FIXTURES / 'recordings')
    result = enrich(item, llm=llm, embed=lambda *a, **k: None, entities=[], clock=frozen())
    assert result['extraction_status'] == 'failed'
    assert result['is_guidance'] is None and result['is_rating_change'] is None
    assert result['embedding'] is None and 'embedding_failed' in result['flags']
    store = InfoStore()
    assert store.put(result) == 'inserted' and result['body'] == item['body']
    calls = []
    def fails(spec, payload):
        calls.append(spec)
        raise LLMUnavailable('fixture timeout')
    client = Client(registry=ROOT / 'config/llm_tasks.yaml', transport=fails)
    with pytest.raises(LLMUnavailable):
        client.call('entity_tagging', {})
    assert len(calls) == 3 and calls[0].timeout_seconds == 120
    assert calls[0].task == 'entity_tagging'
    calls.clear()
    with pytest.raises(LLMUnavailable):
        client.call('segment_mapping_draft', {})
    assert len(calls) == 1 and calls[0].timeout_seconds == 900
    assert calls[0].task == 'segment_mapping_draft'
    from inves_cog.ingest.settings import source_configuration
    configuration = {}
    for prefix in ('LLM_HARD', 'LLM_STANDARD'):
        configuration.update({prefix + '_PROVIDER': 'aliyun',
                              prefix + '_BASE_URL': 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1',
                              prefix + '_API_STYLE': 'openai-compatible',
                              prefix + '_API_KEY': 'fixture-not-a-key'})
    assert source_configuration(configuration)['LLM_hard']['configured']
    assert source_configuration(configuration)['LLM_standard']['configured']
    from inves_cog.llm.transport import OpenAICompatibleTransport
    from inves_cog.ingest.http import Response
    recorded_payload = {'headline': 'Apple introduces a product', 'body': 'AAPL'}
    recorded = llm.call('entity_tagging', recorded_payload)
    requests = []
    def recorded_response(method, url, **kwargs):
        requests.append((method, url, kwargs))
        return Response(200, {'choices': [{'message': {'content': json.dumps(recorded)}}]})
    connected = Client(transport=OpenAICompatibleTransport(configuration, send=recorded_response))
    assert connected.call('entity_tagging', recorded_payload) == recorded
    assert connected.call('segment_mapping_draft', recorded_payload) == recorded
    assert [row[2]['json']['model'] for row in requests] == ['deepseek-v4.1-flash', 'glm-5.3']
    assert [row[2]['timeout'] for row in requests] == [120, 900]
    assert all(row[1].endswith('/compatible-mode/v1/chat/completions') for row in requests)
    assert all('fixture-not-a-key' not in json.dumps(row[2]['json']) for row in requests)
    requests.clear()
    def rate_limited(method, url, **kwargs):
        requests.append((method, url, kwargs))
        return Response(429, {'error': {'message': 'recorded rate limit'}})
    connected = Client(transport=OpenAICompatibleTransport(configuration, send=rate_limited))
    with pytest.raises(LLMUnavailable):
        connected.call('entity_tagging', recorded_payload)
    assert len(requests) == 3
    requests.clear()
    with pytest.raises(LLMUnavailable):
        connected.call('segment_mapping_draft', recorded_payload)
    assert len(requests) == 1


