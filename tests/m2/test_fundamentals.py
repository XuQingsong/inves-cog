"""M2 v2 deterministic contracts; no Muse implementation is executed."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import gzip
import json
from pathlib import Path

import pytest
import yaml

from inves_cog.clock import FrozenClock
from tests.harness.tools.golden import load_golden

pytestmark = pytest.mark.phase1_blocking
ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures/phase1/m2'
ASOF = date(2026, 10, 13)


def input_facts():
    return json.loads((FIXTURES / 'companyfacts_synthetic.json').read_text())


def extract(data=None, *, extractor='fixed', switches=None, as_of=ASOF, sic=3571, foreign=False, filings=(), instance_facts=None):
    from inves_cog.ingest.fundamentals.extractors import extract_state
    return extract_state(data or input_facts(), ticker='FIXTURE', as_of=as_of, extractor=extractor, switches=switches, sic=sic, foreign=foreign, filings=filings, instance_facts=instance_facts)


def test_revenue_tag_gap():
    facts = input_facts()
    gaap = facts['facts']['us-gaap']
    gaap['RevenueFromContractWithCustomerIncludingAssessedTax'] = gaap.pop('RevenueFromContractWithCustomerExcludingAssessedTax')
    legacy = extract(facts, extractor='legacy')
    fixed = extract(facts)
    assert 'revenue_tag_gap' in legacy.health_codes and legacy.values['rev_ttm'] is None
    assert fixed.values['rev_ttm'] == 400 and 'revenue_tag_gap' not in fixed.health_codes
    assert 'revenue_tag_gap' not in extract().health_codes
    assert fixed.values['op_margin_ttm'] == pytest.approx(20)
    assert fixed.values['fcf_margin_change_pp'] == pytest.approx(0)


def test_q4_derived_from_annual():
    from inves_cog.ingest.fundamentals.extractors import derive_quarters
    case = load_golden('m2_fundamentals.json')['q4_derivation']
    rows = derive_quarters(case['fy_total'], q1=case['q1'], q2=case['q2'], q3=case['q3'])
    assert rows['q4'] == case['expected_q4'] and rows['sources']['q4'] == 'q4_derived'
    assert derive_quarters(400, q1=90, q2=None, q3=95)['q4'] is None
    assert 'q4_missing' in derive_quarters(400, q1=90, q2=None, q3=95)['health_codes']
    cumulative = derive_quarters(400, q1=90, ytd6=190, ytd9=285)
    assert [cumulative[k] for k in ('q1', 'q2', 'q3', 'q4')] == [90, 100, 95, 115]
    assert cumulative['sources']['q2'] == 'ytd_derived'
    facts = input_facts()
    for name in ('RevenueFromContractWithCustomerExcludingAssessedTax', 'GrossProfit', 'OperatingIncomeLoss', 'NetIncomeLoss', 'NetCashProvidedByUsedInOperatingActivities', 'PaymentsToAcquirePropertyPlantAndEquipment'):
        rows = facts['facts']['us-gaap'][name]['units']['USD']
        rows[:] = [r for r in rows if r.get('fp') != 'Q4']
    assert extract(facts).values['rev_ttm'] == 400
    assert 'q4_derived' in str(extract(facts).field_sources)


def test_companyfacts_lag():
    filings = [{'accession': 'latest', 'form': '10-Q', 'filing_date': '2026-10-10', 'report_date': '2026-09-30'}]
    plain = extract(filings=filings, as_of=date(2026, 10, 12))
    assert 'companyfacts_lag' in plain.health_codes
    parsed = input_facts()
    for tag in parsed['facts']['us-gaap'].values():
        for rows in tag['units'].values():
            for row in rows:
                row['accn'] = 'latest'
    repaired = extract(filings=filings, instance_facts=parsed)
    assert 'companyfacts_lag' not in repaired.health_codes
    assert 'instance_parsed' in str(repaired.field_sources)
    assert extract(filings=filings, instance_facts=parsed, as_of=date(2026, 10, 12)).values == plain.values
    assert 'companyfacts_lag' not in extract(filings=[{'accession': 'q8', 'form': '10-Q', 'filing_date': '2026-08-01', 'report_date': '2026-06-30'}]).health_codes


def test_stale_fundamentals_code():
    period = date(2026, 6, 30)
    assert 'stale_fundamentals' not in extract(as_of=period + timedelta(days=180)).health_codes
    assert 'stale_fundamentals' in extract(as_of=period + timedelta(days=181)).health_codes


def test_gross_margin_derived():
    facts = input_facts()
    facts['facts']['us-gaap'].pop('GrossProfit')
    state = extract(facts)
    assert state.values['gross_margin'] == pytest.approx(40)
    assert 'gross_margin_derived' in state.health_codes
    assert 'gross_margin_derived' not in extract().health_codes
    assert extract(facts, switches={'D4': False}).values['gross_margin'] is None


def test_ni_tag_fallback():
    facts = input_facts()
    gaap = facts['facts']['us-gaap']
    gaap['NetIncomeLossAvailableToCommonStockholdersBasic'] = gaap.pop('NetIncomeLoss')
    assert extract(facts).values['ni_ttm'] == 40
    assert 'ni_tag_fallback' in extract(facts).health_codes
    assert extract(facts, switches={'D5': False}).values['ni_ttm'] is None
    assert 'ni_tag_fallback' not in extract().health_codes


def test_industry_basis_na():
    from inves_cog.ingest.fundamentals.health import health_row
    state = extract(sic=4911)
    health = health_row(state, foreign=False)
    assert 'industry_basis_na' in state.health_codes and health['can_score']
    assert 'industry_basis_na' not in extract(sic=3571).health_codes
    assert not health_row(state, foreign=True)['can_trade']


def test_fin_state_pit():
    from inves_cog.ingest.fundamentals.service import FinancialService, MemoryRepository
    calls = []
    class SEC:
        def companyfacts(self,cik):
            calls.append(cik)
            return input_facts()
    clock = FrozenClock(datetime(2026,10,13,1,tzinfo=timezone.utc))
    repository = MemoryRepository()
    repository.shared_filings['FIXTURE'] = [{'accession':'q8','form':'10-Q','filing_date':date(2026,8,1),'report_date':date(2026,6,30)}]
    service = FinancialService(clock=clock,repository=repository,sec=SEC(),llm=None,
        universe=[{'ticker':'FIXTURE','foreign':False,'sector':'fixture'}],ciks={'FIXTURE':'1'})
    report = service.collect_financials()
    assert report['processed_count']==1 and repository.health['FIXTURE']['can_score']
    assert repository.state_asof('FIXTURE',date(2026,7,31),'fixed') is None
    assert repository.state_asof('FIXTURE',date(2026,8,1),'fixed').accession=='q8'
    assert calls==['1'] and 'FIXTURE' in repository.profiles
    from inves_cog.ingest.fundamentals.state import StateStore
    before, after = extract(), extract()
    before.filed, after.filed = date(2026, 8, 1), date(2026, 10, 14)
    before.accession, after.accession = 'old', 'new'
    store = StateStore([after, before])
    assert store.state_asof('FIXTURE', date(2026, 7, 31), 'fixed') is None
    assert store.state_asof('FIXTURE', ASOF, 'fixed').accession == 'old'
    assert store.state_asof('FIXTURE', date(2026, 10, 14), 'fixed').accession == 'new'
    facts = input_facts()
    for rows in facts['facts']['us-gaap']['RevenueFromContractWithCustomerExcludingAssessedTax']['units'].values():
        rows.append({'start': '2026-04-01', 'end': '2026-06-30', 'filed': '2026-10-14', 'val': 99999, 'accn': 'future', 'form': '10-Q'})
    assert extract(facts).values['rev_ttm'] == 400


def test_extractor_fixed_toggles():
    settings = yaml.safe_load((ROOT / 'config/params/p-2026.10/m2.yaml').read_text())['m2']
    assert settings['repair_order'] == ['D3', 'D1', 'D2', 'D4', 'D5', 'D8']
    base = input_facts()
    base['facts']['us-gaap'].pop('CashAndCashEquivalentsAtCarryingValue')
    plain = extract(base, switches={key: False for key in settings['repair_order']})
    for switch, matrix in settings['impact_matrix'].items():
        enabled = extract(base, switches={key: key == switch for key in settings['repair_order']})
        allowed = set(matrix['direct']) | set(matrix['derived'])
        for name, value in plain.values.items():
            if name not in allowed:
                assert enabled.values[name] == value, (switch, name)
    legacy = extract(base, extractor='legacy')
    fixed = extract(base)
    assert legacy.values['net_debt'] == 30 and 'cash_missing_as_zero' in str(legacy.field_sources)
    assert fixed.values['net_debt'] is None and fixed.values['net_debt_fcf'] is None
    assert 'cash_missing' in str(fixed.field_sources)
    assert extract().values['net_debt'] == 10


def test_segment_extraction(tmp_path):
    import shutil
    from inves_cog.ingest.fundamentals.segments import parse_segments
    for path in (FIXTURES/'xbrl').iterdir(): shutil.copyfile(path,tmp_path/path.name)
    instance=tmp_path/'instance.xml'
    instance.write_text(instance.read_text().replace('iso4217:USD','iso4217:EUR'))
    class Rates:
        def convert(self,value,**kwargs): return value*2,{'currency':kwargs['currency'],'factor':2}
    foreign=parse_segments(instance,ticker='ASML',accession='foreign-fixture',filed=date(2026,8,1),fx=Rates())
    business=[row for row in foreign if row['axis']=='business']
    assert sum(row['revenue'] for row in business)==204
    assert all('segment_sum_mismatch' not in row['health_codes'] for row in business)
    assert sorted(row['share_pct'] for row in business)==[50,52]

    from inves_cog.ingest.fundamentals.segments import parse_segments, segment_sum_ok
    for case in load_golden('m2_fundamentals.json')['segment_sum_tolerance']:
        assert segment_sum_ok(case['segments'], case['eliminations'], case['consolidated']) == case['expected_pass']
    rows = parse_segments(FIXTURES / 'xbrl/instance.xml', ticker='AMD', accession='fixture', filed=date(2026, 8, 1))
    business = [row for row in rows if row['axis'] == 'business']
    assert {row['segment_raw'] for row in business} == {'ClientMember', 'DataCenterMember'}
    assert sum(row['revenue'] for row in business) == 102
    assert next(row for row in rows if row['axis'] == 'elimination')['revenue'] == -2
    assert next(row for row in rows if row['axis'] == 'product')['revenue'] == 999
    assert all('segment_sum_mismatch' not in row['health_codes'] for row in business)
    assert next(row for row in business if row['segment_raw'] == 'ClientMember')['segment_profit'] == 10


    # Authorized K15: an exact operating-segment auxiliary axis is valid;
    # geography/product mixes and lookalike namespaces remain invalid.
    from lxml import etree
    folder=tmp_path/'auxiliary'; folder.mkdir()
    for fixture in (FIXTURES/'xbrl').iterdir():
        text=fixture.read_text().replace('http://example.invalid/us-gaap','http://fasb.org/us-gaap/2026')
        if fixture.name=='company.xsd':
            text=text.replace('</xs:schema>','<xs:import namespace="http://fasb.org/srt/2026" schemaLocation="srt.xsd"/></xs:schema>')
        if fixture.name=='us-gaap.xsd':
            text=text.replace('</xs:schema>','<xs:element name="OperatingSegmentsMember" type="xs:string"/></xs:schema>')
        if fixture.name=='instance.xml':
            text=text.replace('<xbrli:xbrl ','<xbrli:xbrl xmlns:srt="http://fasb.org/srt/2026" ')
        (folder/fixture.name).write_text(text)
    (folder/'srt.xsd').write_text('<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="http://fasb.org/srt/2026"><xs:element name="ConsolidationItemsAxis" type="xs:string"/><xs:element name="StatementGeographicalAxis" type="xs:string"/></xs:schema>')
    baseline=(folder/'instance.xml').read_text()
    ns={'x':'http://www.xbrl.org/2003/instance','d':'http://xbrl.org/2006/xbrldi'}
    def auxiliary(axis,member,*,namespace='http://fasb.org/srt/2026',third=None):
        document=etree.fromstring(baseline.replace('http://fasb.org/srt/2026',namespace).encode())
        for context in document.findall('x:context',ns):
            if context.get('id') not in {'client','datacenter'}: continue
            segment=context.find('x:entity/x:segment',ns)
            added=etree.SubElement(segment,'{'+ns['d']+'}explicitMember',dimension=axis); added.text=member
            if third:
                added=etree.SubElement(segment,'{'+ns['d']+'}explicitMember',dimension=third[0]);added.text=third[1]
        (folder/'instance.xml').write_bytes(etree.tostring(document))
        return [row for row in parse_segments(folder/'instance.xml',ticker='NVDA',accession='aux-fixture',filed=date(2026,8,1)) if row['axis']=='business']
    accepted=auxiliary('srt:ConsolidationItemsAxis','us-gaap:OperatingSegmentsMember')
    assert {row['segment_raw'] for row in accepted}=={'ClientMember','DataCenterMember'}
    assert sum(row['revenue'] for row in accepted)==102
    assert sorted(row['segment_profit'] for row in accepted)==[10,15]
    assert all('segment_sum_mismatch' not in row['health_codes'] for row in accepted)
    assert not auxiliary('srt:ConsolidationItemsAxis','us-gaap:IntersegmentEliminationMember')
    assert not auxiliary('srt:StatementGeographicalAxis','fixture:ProductMember')
    assert not auxiliary('us-gaap:ProductOrServiceAxis','fixture:ProductMember')
    assert not auxiliary('srt:ConsolidationItemsAxis','us-gaap:OperatingSegmentsMember',namespace='http://example.invalid/impostor')
    assert not auxiliary('srt:ConsolidationItemsAxis','us-gaap:OperatingSegmentsMember',third=('us-gaap:ProductOrServiceAxis','fixture:ProductMember'))


    # A context that discloses only assets is not a revenue/profit segment row.
    metrics=tmp_path/'metrics';metrics.mkdir()
    for fixture in (FIXTURES/'xbrl').iterdir():shutil.copyfile(fixture,metrics/fixture.name)
    schema=metrics/'company.xsd'
    schema.write_text(schema.read_text().replace('</xs:schema>','<xs:element name="AssetsOnlyMember" type="xs:string"/><xs:element name="Assets" type="xbrli:monetaryItemType" substitutionGroup="xbrli:item" xbrli:periodType="duration"/></xs:schema>'))
    document=etree.fromstring((metrics/'instance.xml').read_bytes())
    context=deepcopy(document.find("x:context[@id='client']",ns));context.set('id','assets-only')
    context.find('.//d:explicitMember',ns).text='fixture:AssetsOnlyMember';document.append(context)
    fact=etree.SubElement(document,'{http://example.invalid/company}Assets',contextRef='assets-only',unitRef='usd',decimals='0');fact.text='123'
    (metrics/'instance.xml').write_bytes(etree.tostring(document))
    metrics_rows=parse_segments(metrics/'instance.xml',ticker='AMD',accession='metrics-fixture',filed=date(2026,8,1))
    assert {r['segment_raw'] for r in metrics_rows if r['axis']=='business'}=={'ClientMember','DataCenterMember'}


def test_segment_recast():
    from inves_cog.ingest.fundamentals.segments import apply_recast
    previous = [{'segment_raw': 'A', 'revenue': 50, 'axis': 'business', 'recast_group': 'old', 'period_end': date(2025, 6, 30)}]
    current = [{'segment_raw': 'B', 'revenue': 60, 'axis': 'business', 'period_end': date(2026, 6, 30)}]
    changed = apply_recast(current, previous, comparative=[])
    assert changed[0]['recast_group'] != 'old' and changed[0]['yoy_pct'] is None
    assert 'segment_recast' in changed[0]['health_codes']
    stable = apply_recast([dict(current[0], segment_raw='A')], previous, comparative=[dict(previous[0], revenue=50.5)])
    assert stable[0]['recast_group'] == 'old' and stable[0]['yoy_pct'] == pytest.approx(20)
    assert apply_recast([dict(current[0], segment_raw='A')], previous, comparative=[dict(previous[0], revenue=51)])[0]['yoy_pct'] is None


def test_segment_mapping_pending():
    from inves_cog.ingest.fundamentals.mapping import MappingQueue
    class RecordedLLM:
        def __init__(self):
            self.calls = []
        def call(self, task, payload):
            self.calls.append((task, payload))
            return json.loads((FIXTURES / 'mapping_recording.json').read_text())['result']
    llm = RecordedLLM()
    queue = MappingQueue(llm=llm, clock=FrozenClock(datetime(2026, 10, 13, tzinfo=timezone.utc)), sectors={'AMD': 'chips'})
    draft = queue.draft('AMD', 'DataCenterMember', graph_nodes=[{'id': 'datacenter', 'name': 'Data center'}])
    assert draft['status'] == '待审核' and draft['segment_std'] is None
    assert queue.draft('AMD', 'DataCenterMember', graph_nodes=[])['id'] == draft['id'] and len(llm.calls) == 1
    assert llm.calls[0][0] == 'segment_mapping_draft'
    assert queue.list_pending_mappings('chips') == [draft]
    with pytest.raises(ValueError):
        queue.confirm_mappings([draft['id']], reviewer='', decision='已确认')
    queue.confirm_mappings([draft['id']], reviewer='fixture-reviewer', decision='已确认')
    assert queue.list_pending_mappings('chips') == []
    assert draft['segment_std'] == ['datacenter'] and draft['reviewed_at'].tzinfo is not None
    shared=MappingQueue(llm=RecordedLLM(),clock=FrozenClock(datetime(2026,10,13,tzinfo=timezone.utc)),sectors={})
    accepted=shared.draft('AMD','ClientMember',graph_nodes=[{'entity_id':'datacenter','name':'Data center'}])
    assert accepted['graph_node_ids']==['datacenter']
    from inves_cog.ingest.fundamentals.service import FinancialService,MemoryRepository
    repo=MemoryRepository()
    repo.mappings[draft['id']]=dict(draft)
    repo.segments=[{'ticker':'AMD','accession':'cached','filed':date(2026,10,1),
        'period_end':date(2026,6,30),'axis':'business','segment_raw':'DataCenterMember',
        'segment_std':None,'health_codes':['segment_unmapped'],'evidence':{'parse_contract':'operating-aux-v1'}}]
    repo.segments.append(dict(repo.segments[0],period_end=date(2025,6,30)))
    class CachedLoader:
        def segments(self,*args,**kwargs): raise AssertionError('Cached instance must not be parsed again')
    def service(): return FinancialService(clock=FrozenClock(datetime(2026,10,13,tzinfo=timezone.utc)),
        repository=repo,sec=None,llm=RecordedLLM(),universe=[{'ticker':'AMD','sector':'chips'}],ciks={'AMD':'1'},instance_loader=CachedLoader())
    filings=[{'accession':'cached','filing_date':date(2026,10,1)}]
    mapped=service().collect_segments('AMD',filings)
    assert len(mapped)==1 and mapped[0]['segment_std']==['datacenter'] and 'segment_unmapped' not in mapped[0]['health_codes']
    repo.mappings[draft['id']].update(status='驳回',segment_std=None,health_codes=['segment_unmapped'])
    rejected=service().collect_segments('AMD',filings)
    assert rejected[0]['segment_std'] is None and 'segment_unmapped' in rejected[0]['health_codes']

    # Old parsed rows must not hide the newly authorized auxiliary dimensions.
    for row in repo.segments: row['evidence'].pop('parse_contract',None)
    class RefreshLoader:
        calls=0
        def segments(self,*args,**kwargs):
            self.calls+=1
            return [{'ticker':'AMD','accession':'cached','filed':date(2026,10,1),
                'period_start':date(2026,4,1),'period_end':date(2026,6,30),'axis':'business',
                'segment_raw':'DataCenterMember','revenue':52,'health_codes':[],
                'evidence':{'parse_contract':'operating-aux-v1'}}]
    loader=RefreshLoader(); refreshed=service();refreshed.instance_loader=loader
    assert refreshed.collect_segments('AMD',filings)[0]['revenue']==52
    assert loader.calls==1
    refreshed.collect_segments('AMD',filings)
    assert loader.calls==1

    empty=MappingQueue(llm=RecordedLLM(),clock=FrozenClock(datetime(2026,10,13,tzinfo=timezone.utc)),sectors={})
    with pytest.raises(ValueError): empty.draft('AMD','Other',graph_nodes=[])



def test_consensus_derived_pit():
    from inves_cog.ingest.fundamentals.consensus import derive_consensus
    case = load_golden('m2_fundamentals.json')['consensus_derived']
    snapshots = [dict(row, ticker='FIXTURE', source='yfinance', fy_cy='2026-12-31', fy_ny='2027-12-31', captured_at=row['as_of'] + 'T01:00:00Z') for row in case['snapshots']]
    for expected in case['expected']:
        result = derive_consensus(snapshots, ticker='FIXTURE', as_of=date.fromisoformat(expected['as_of']))
        for key, value in expected.items():
            if key == 'as_of':
                continue
            actual = result['window_status'][key.removesuffix('_status')] if key.endswith('_status') else result[key]
            assert actual == pytest.approx(value) if isinstance(value, float) else actual == value
    rich = dict(snapshots[0], coverage=4, up_7d=3, down_7d=1, eps_high_cy=5, eps_low_cy=3, raw={'ago7': 999})
    result = derive_consensus([rich], ticker='FIXTURE', as_of=date(2026, 10, 8))
    assert result['breadth_7d'] == 0.5 and result['dispersion'] == 0.5
    assert result['chg_7d_pct'] is None
    zero = derive_consensus([dict(rich, coverage=0, eps_cy=0.001)], ticker='FIXTURE', as_of=date(2026, 10, 8))
    assert zero['breadth_7d'] is None and zero['dispersion'] is None
    future = dict(snapshots[0], captured_at='2026-10-09T01:00:00Z')
    assert derive_consensus([future], ticker='FIXTURE', as_of=date(2026, 10, 8))['eps_cy'] is None
    rolled = dict(snapshots[1], fy_cy='2027-12-31')
    assert derive_consensus([snapshots[0], rolled], ticker='FIXTURE', as_of=date(2026, 10, 15))['window_status']['chg_7d_pct'] == '财年切换'


def test_consensus_import_idempotent(tmp_path):
    from inves_cog.ingest.fundamentals.providers import snapshot_from_tables
    captured = FrozenClock(datetime(2026,10,13,2,tzinfo=timezone.utc))
    tables = {'earnings_estimate': {'0y': {'avg':4,'high':5,'low':3,'numberOfAnalysts':4}},
              'revenue_estimate': {'0y': {'avg':100}},
              'eps_revisions': {'0y': {'upLast7days':3,'downLast7days':1}},
              'analyst_price_targets': {'mean':10,'median':9}, 'earnings_history': [{'quarter_date':'2026-06-30','epsActual':1.2,'epsEstimate':1,'surprisePercent':0.2}]}
    snapshot = snapshot_from_tables(tables,ticker='FIXTURE',clock=captured,fy_cy=date(2026,12,31),fy_ny=date(2027,12,31))
    assert snapshot['coverage']==4 and snapshot['rev_cy']==100 and snapshot['up_7d']==3
    assert snapshot['raw']['earnings_history'][0]['surprise_pct']==20
    assert snapshot['as_of']==date(2026,10,13) and snapshot['captured_at']==captured.now_utc()
    from inves_cog.ingest.fundamentals.consensus import ConsensusStore, import_muse_exports, read_copy_blocks
    store = ConsensusStore()
    folder = FIXTURES / 'muse_export_synthetic'
    import_muse_exports(folder, store=store)
    # Imported target years must use the snapshot's PIT annual filing.
    resolved=ConsensusStore();lookups=[]
    def annual_end(ticker,as_of):
        lookups.append((ticker,as_of))
        return date(2025,12,31)
    import_muse_exports(folder,store=resolved,annual_end_asof=annual_end)
    assert len(lookups)==len(resolved.rows)
    for historical in resolved.rows.values():
        assert historical['fy_cy']==date(2026,12,31) and historical['fy_ny']==date(2027,12,31)
        assert historical['raw']['fiscal_year_source']['as_of']==historical['as_of'].isoformat()
        assert historical['captured_at'] is None
    unknown=ConsensusStore()
    import_muse_exports(folder,store=unknown,annual_end_asof=lambda ticker,as_of:None)
    assert all(row['fy_cy'] is None and row['raw']['fiscal_year_source']['reason']=='PIT annual filing unavailable' for row in unknown.rows.values())

    count = len(store.rows)
    assert count > 0
    import_muse_exports(folder, store=store)
    assert len(store.rows) == count
    row = next(iter(store.rows.values()))
    assert row['source'] == 'muse_import' and row['as_of'] == date(2026, 10, 8)
    assert row['captured_at'] is None and row['coverage'] is None and row['rev_cy'] is None
    parsed = read_copy_blocks("CREATE TABLE forbidden ();\nCOPY data.estimates_trend (ticker, cur) FROM stdin;\nAAPL\t4.1\n\\.\nDROP DATABASE quant;\n")
    assert parsed == {'data.estimates_trend': [{'ticker': 'AAPL', 'cur': '4.1'}]}
    assert not list(tmp_path.iterdir())


def test_health_contract(monkeypatch):
    from inves_cog.ingest.fundamentals.fx import FXBook, FXGap
    from inves_cog.ingest.fundamentals.fx import fetch_fred_rates
    seen = []
    class FRED:
        def get(self,url,params):
            if url.endswith('/series'): return {'realtime_end':'2026-01-06'}
            seen.append(params)
            assert params['output_type']==1
            return {'count':1,'observations':[{'date':'2025-12-30','realtime_start':'2025-12-31','realtime_end':'9999-12-31','value':'1.2'}]}
    rows = fetch_fred_rates(FRED(),key='fixture-not-a-key',currency='EUR',first=date(2025,12,29),last=date(2025,12,31),as_of=date(2026,1,6),clock=FrozenClock(datetime(2026,1,6,tzinfo=timezone.utc)))
    assert rows[0]['realtime_start']=='2025-12-31' and seen
    rates = FXBook(json.loads((FIXTURES / 'fx_synthetic.json').read_text())['records'])
    value, evidence = rates.convert(100, currency='EUR', start=date(2025,12,29),
        end=date(2025,12,31), as_of=date(2026,1,6), field='revenue')
    assert value == pytest.approx(115)
    assert evidence['original_currency'] == 'EUR' and evidence['quotes'][-1]['observation_date'] == '2025-12-30'
    value, evidence = rates.convert(100, currency='EUR', start=None,
        end=date(2025,12,31), as_of=date(2026,1,6), field='cash')
    assert value == pytest.approx(120) and evidence['effective_quote_date'] == '2025-12-30'
    assert rates.convert(320, currency='TWD', start=None, end=date(2025,12,31), as_of=date(2026,1,6),field='cash')[0] == 10
    with pytest.raises(FXGap, match='EUR.*revenue.*2025-12-29'):
        rates.convert(100,currency='EUR',start=date(2025,12,29),end=date(2025,12,31),as_of=date(2025,12,29),field='revenue')
    with pytest.raises(FXGap, match='unsupported'):
        rates.convert(100,currency='XXX',start=None,end=date(2025,12,31),as_of=date(2026,1,6),field='cash')
    # Large history must not exhaust a bounded lookup budget for one balance.
    from inves_cog.ingest.fundamentals import fx as fx_module
    history=[{'currency':'EUR','observation_date':str(date(2009,1,1)+timedelta(days=i)),
              'realtime_start':str(date(2009,1,1)+timedelta(days=i+1)),'value':1.2} for i in range(5000)]
    indexed=FXBook(history); parses=[]; parse_day=fx_module.as_date
    def bounded_date(value):
        parses.append(value)
        if len(parses)>60:raise RuntimeError('FX lookup exhausted processing budget')
        return parse_day(value)
    with monkeypatch.context() as patch:
        patch.setattr(fx_module,'as_date',bounded_date)
        end=date(2009,1,1)+timedelta(days=4999)
        assert indexed.convert(100,currency='EUR',start=None,end=end,as_of=end+timedelta(days=2),field='cash')[0]==pytest.approx(120)
    # Q-M2-17(4): seven calendar days is inclusive, including year boundary.
    seven = FXBook([{'currency':'EUR','observation_date':'2025-12-25','realtime_start':'2025-12-26','value':1.2}])
    converted, quote = seven.convert(100,currency='EUR',start=None,end=date(2026,1,1),as_of=date(2026,1,6),field='cash')
    assert converted == pytest.approx(120) and quote['effective_quote_date']=='2025-12-25'
    assert quote['lookback_days']==7
    stale = FXBook([{'currency':'EUR','observation_date':'2025-12-23','realtime_start':'2025-12-24','value':1.2}])
    with pytest.raises(FXGap,match='7.*calendar') as expired:
        stale.convert(100,currency='EUR',start=None,end=date(2025,12,31),as_of=date(2026,1,6),field='cash')
    assert expired.value.detail['field']=='cash' and expired.value.detail['series']=='DEXUSEU'
    # Flow averaging is unchanged; a future quote cannot satisfy a balance.
    assert stale.convert(100,currency='EUR',start=date(2025,12,1),end=date(2025,12,31),as_of=date(2026,1,6),field='revenue')[0]==pytest.approx(120)
    same = FXBook([{'currency':'EUR','observation_date':'2025-12-31','realtime_start':'2026-01-02','value':1.3}])
    assert same.convert(100,currency='EUR',start=None,end=date(2025,12,31),as_of=date(2026,1,6),field='cash')[1]['lookback_days']==0
    from inves_cog.ingest.fundamentals.health import health_row
    from inves_cog.ingest.fundamentals.profile import ProfileBook
    good = extract()
    row = health_row(good, foreign=False)
    assert {'ticker', 'latest_period_end', 'latest_filed', 'latest_8k_202', 'health_codes', 'can_score', 'can_trade', 'reason'} <= row.keys()
    assert row['can_score'] and row['can_trade']
    missing = deepcopy(good)
    missing.values['shares'] = None
    health = health_row(missing, foreign=False)
    assert not health['can_score'] and health['reason'] and 'core_field_missing' in health['health_codes']
    book = ProfileBook(clock=FrozenClock(datetime(2026, 10, 13, tzinfo=timezone.utc)))
    profile = book.generate(good, segments=[], consensus=None, guidance=[])
    book.generate(good,segments=[],consensus={'eps_cy':4,'fy_cy':'2026-12-31'},guidance=[])
    guide = book.generate(good,segments=[],consensus=None,guidance=[{'is_guidance':True,'info_id':'sec_8k:SEC:fixture-guidance','payload':{'items':'2.02,7.01'}}])
    assert any(row['kind']=='业绩指引' for row in guide['changes'])
    boundary = book.generate(good,segments=[],consensus={'eps_cy':4.12,'fy_cy':'2026-12-31'},guidance=[])
    assert not any(row['kind']=='一致预期变化' for row in boundary['changes'])
    changed = book.generate(good,segments=[],consensus={'eps_cy':4.124,'fy_cy':'2026-12-31'},guidance=[])
    assert sum(row['kind']=='一致预期变化' for row in changed['changes'])==1
    from inves_cog.ingest.fundamentals.service import FinancialService,MemoryRepository
    universe = [{'ticker':f'F{i:02}','foreign':i>=54,'sector':'handwritten fixture'} for i in range(59)]
    memory = MemoryRepository()
    for entity in universe:
        memory.shared_filings[entity['ticker']]=[{'accession':'q8','form':'10-Q','filing_date':date(2026,8,1),'report_date':date(2026,6,30)}]
    class SEC:
        def companyfacts(self,cik): return input_facts()
    service = FinancialService(clock=FrozenClock(datetime(2026,10,13,1,tzinfo=timezone.utc)),repository=memory,
        sec=SEC(),llm=None,universe=universe,ciks={row['ticker']:'1' for row in universe})
    partial=MemoryRepository()
    partial.shared_filings={key:value for key,value in memory.shared_filings.items()}
    class LimitedService(FinancialService):
        def _budget(self):
            if partial.health: raise RuntimeError('fixture task budget exhausted')
    limited=LimitedService(clock=service.clock,repository=partial,sec=SEC(),llm=None,
        universe=universe[:2],ciks=service.ciks)
    with pytest.raises(RuntimeError,match='budget exhausted') as expired_run:
        limited.collect_financials()
    assert expired_run.value.processed_count==1
    assert len(partial.health)==1 and len(partial.profiles)==1

    assert service.collect_financials()['processed_count']==59
    assert len(memory.health)==59 and len(memory.profiles)==59
    for entity in universe:
        health=memory.health[entity['ticker']]
        if entity['foreign']: assert not health['can_trade']
        if health['can_trade']:
            state=memory.state_asof(entity['ticker'],ASOF,'fixed')
            assert all(state.values[key] is not None for key in ('rev_ttm','eps_ttm','shares'))
    assert all(profile[key]['data'] is not None or profile[key]['reason'] for key in ('business', 'financials', 'consensus'))
