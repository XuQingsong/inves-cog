"""Production M1 tasks using the same parsers exercised by the offline harness."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import yaml

from inves_cog.ingest.adapters import (Embedding, Trends, Websites, alpaca_splits,
    cboe_statistics, cik_mapping, frames_shares)
from inves_cog.ingest.deadline import check
from inves_cog.ingest.http import HTTPClient, RateLimiter, SourceError
from inves_cog.ingest.info import enrich, make_item
from inves_cog.ingest.jobs import HealthBook
from inves_cog.ingest.market import (MarketCollector, NY, exchange, local_at, post_close, split_factors, trading_day)
from inves_cog.ingest.providers import (Alpaca, FRED, alpha_calendar, apple_chart,
    finra_short_interest, sec_atom, sec_daily_index)
from inves_cog.ingest.repository import identity
from inves_cog.ingest.runtime import Runtime, complete_adv20
from inves_cog.ingest.sec import collect_submissions, earnings_event, earnings_fallback, parse_form4
from inves_cog.ingest.signals import rank_jumps, trend_event
from inves_cog.ingest.sources import macro_items, parse_finra, website_change
from inves_cog.ingest.universe import build_universe, daily_liquidity

ROOT = Path(__file__).resolve().parents[3]


def select_membership(candidates, previous, adv, day, *, monthly):
    """K18: first observed close is a labelled baseline, never a backdated run."""
    if monthly or not previous:
        rows = build_universe(candidates, day)
        if not monthly:
            for row in rows:
                row['notes'].append('startup_baseline')
        return rows
    return daily_liquidity(previous, adv, day)


class Pipeline:
    def __init__(self, *, clock, repository, values, llm, sec, alpaca=None, fred=None,
                 embed=None, websites=None, trends=None):
        self.clock, self.repo, self.values, self.llm, self.sec = clock, repository, values, llm, sec
        self.alpaca, self.fred = alpaca, fred
        self.embed = embed or Embedding(values)
        self.websites, self.trends = websites or Websites(), trends or Trends(clock=clock)
        self.universe = yaml.safe_load((ROOT / 'config/universe.yaml').read_text())
        self.stocks = [row['ticker'] for row in self.universe['stocks']]
        self.codes = self.stocks + self.universe['etfs']
        fallback = yaml.safe_load((ROOT / 'config/monitored_entities.yaml').read_text())['entities']
        self.monitored = self.repo.monitored_entities(fallback)
        self.entities = self.repo.graph_entities(self.monitored)
        self.day_override = None

    @property
    def day(self):
        return self.day_override or self.clock.today_trade_date()

    def require(self, value, source):
        if value is None:
            raise SourceError(source + ' configuration missing: 等待 R5', confirmed_unavailable=True)
        return value

    def info(self, items):
        count = 0
        for item in items:
            check()
            previous = self.repo.info_signature(item['info_id'])
            if previous != (item['headline'], item['body']):
                # The durable pending row is the queue. Collection never waits
                # for dialogue/embedding, and restart resumes from this row.
                self.repo.put_info(item)
            else:
                self.repo.count_duplicate()
            count += 1
        return {'processed_count': count}

    def enrich_pending(self, limit=32):
        counts = Counter()
        try:
            for item in self.repo.pending_info(limit):
                check()
                result=enrich(item,llm=self.llm,embed=self.embed,entities=self.entities,clock=self.clock)
                if self.repo.apply_enrichment(result):
                    counts['processed_count'] += 1
                    counts['tagging_failed'] += 'entity_tagging_failed' in result['flags']
                    counts['embedding_failed'] += 'embedding_failed' in result['flags']
        except Exception as exc:
            exc.processed_count=counts['processed_count']
            raise
        counts.setdefault('processed_count',0)
        report=dict(counts)
        report['status']='degraded' if counts['tagging_failed'] or counts['embedding_failed'] else 'ok'
        report['note']=f"tagging_failed={counts['tagging_failed']}; embedding_failed={counts['embedding_failed']}"
        return report

    def bars(self, *, prefill=False):
        if not trading_day(self.day):
            return {'processed_count': 0, 'note': 'XNYS closed'}
        alpaca = self.require(self.alpaca, 'Alpaca')
        collector = MarketCollector(alpaca.http, clock=self.clock, headers=alpaca.headers)
        result = collector.minute_bars(self.codes, self.day, end=local_at(self.day, 8) if prefill else None)
        for row in result.rows:
            self.repo.write('bars_minute', row, update=('open', 'high', 'low', 'close', 'volume', 'session'))
        if prefill:
            return {'processed_count': len(result.rows), 'missing_codes': result.missing_codes,
                    'exhausted': result.exhausted, 'status': result.status}
        first = self.repo.first_bar_date() or self.day - timedelta(days=60)
        daily = alpaca.daily_bars(self.codes, first, self.day)
        split_gap = None
        try:
            splits = alpaca_splits(alpaca, self.codes, first, self.day)
        except SourceError as exc:
            splits, split_gap = {}, str(exc)
        grouped = defaultdict(list)
        for row in daily: grouped[row['ticker']].append(row)
        for ticker, rows in grouped.items():
            factors = split_factors([r['trade_date'] for r in rows], splits.get(ticker, []))
            for row, factor in zip(rows, factors):
                check()
                row['adj_factor'] = factor if split_gap is None or row['trade_date'] == self.day else None
                if row['trade_date'] == self.day: row['post_close'] = post_close(result.rows, self.day, ticker=ticker)
                else: row['post_close'] = self.repo.post_close(ticker, row['trade_date'])
                self.repo.write('bars_daily', row, update=('open', 'high', 'low', 'close', 'volume', 'post_close', 'adj_factor'))
        actual = {row['ticker'] for row in daily if row['trade_date'] == self.day}
        unavailable = [ticker for ticker in self.codes if ticker not in actual]
        for ticker in unavailable:
            self.repo.set_cursor('no_bar:' + ticker, {'day': self.day.isoformat(), 'reason': 'Alpaca SIP returned no daily bar'}, self.clock.now_utc())
        available_coverage = [result.coverage[t] for t in actual if result.coverage[t] is not None]
        coverage_ok = bool(available_coverage) and min(available_coverage) >= .95 and sum(available_coverage) / len(available_coverage) >= .99
        late = self.clock.now_utc() > local_at(self.day, 20, 45)
        report = {'processed_count': len(result.rows) + len(daily), 'daily_codes': len(actual),
                  'requested_codes': len(self.codes), 'unavailable_codes': unavailable,
                  'coverage': result.coverage, 'exhausted': result.exhausted,
                  'completed_at': self.clock.now_utc().isoformat(), 'deadline_met': not late,
                  'status': 'ok' if coverage_ok and not split_gap and not late else 'degraded',
                  'note': split_gap or ('minute coverage below threshold' if not coverage_ok else 'past 20:45 ET deadline' if late else None)}
        self.repo.set_cursor('bars-report:' + self.day.isoformat(), report, self.clock.now_utc())
        return report

    def news(self):
        alpaca = self.require(self.alpaca, 'Alpaca')
        previous = self.repo.get_cursor('news')
        first = datetime.fromisoformat(previous['through']) - timedelta(days=1) if previous else self.clock.now_utc() - timedelta(days=90)
        count, before = 0, dict(self.repo.counts)
        for item in alpaca.news(first=first, last=self.clock.now_utc()):
            self.info([item]); count += 1
            # Each durable insert moves the resumable bootstrap cursor.
            if item['published_at']:
                self.repo.set_cursor('news', {'through': item['published_at'].isoformat()}, self.clock.now_utc())
        self.repo.set_cursor('news', {'through': self.clock.now_utc().isoformat(), 'bootstrap_complete': True}, self.clock.now_utc())
        return {'processed_count': count, **{key: self.repo.counts[key] - before[key] for key in before}}

    def wide(self):
        alpaca = self.require(self.alpaca, 'Alpaca')
        assets = alpaca.assets()
        eligible = [a for a in assets if a.get('exchange', '').upper() in {'NYSE','NASDAQ','AMEX','ARCA','BATS','CBOE','NYSEAMERICAN','NYSEARCA'}]
        mapping, shares = cik_mapping(self.require(self.sec, 'SEC')), frames_shares(self.sec, self.day)
        sessions = [d.date() for d in exchange(self.day.year).sessions_in_range(str(self.day - timedelta(days=50)), str(self.day))][-20:]
        codes = [a['ticker'] for a in eligible]
        history = defaultdict(list)
        for start in range(0, len(codes), 200):
            check()
            for row in alpaca.daily_bars(codes[start:start+200], sessions[0], self.day):
                history[row['ticker']].append(row)
                self.repo.write('bars_daily', row, update=('open','high','low','close','volume'))
        counts = Counter(mapping.get(a['ticker']) for a in eligible if mapping.get(a['ticker']))
        candidates, adv = [], {}
        for asset in eligible:
            ticker, rows = asset['ticker'], history[asset['ticker']]
            cik = mapping.get(ticker)
            latest = next((r['close'] for r in rows if r['trade_date'] == self.day), None)
            value = complete_adv20(rows, sessions)
            adv[ticker] = value
            candidates.append({**asset, 'cik': cik, 'shares': shares.get(cik, {}).get('shares'),
                'close': latest, 'history': rows if value is not None else [], 'multi_class': counts[cik] > 1})
        previous = self.repo.latest_wide()
        first_session = exchange(self.day.year).sessions_in_range(f'{self.day:%Y-%m}-01', str(self.day))[0].date()
        monthly = self.day == first_session
        rows = select_membership(candidates, previous, adv, self.day, monthly=monthly)
        for row in rows:
            self.repo.write('wide_universe', row, update=('mktcap','adv20','included','exclude_reason','notes'))
        report = {'processed_count': len(rows), 'included': sum(r['included'] for r in rows),
                  'exclusions': dict(Counter(r['exclude_reason'] for r in rows if not r['included'])), 'monthly': monthly, 'startup_baseline': not monthly and not previous}
        self.repo.set_cursor('wide-report:' + self.day.isoformat(), report, self.clock.now_utc())
        return report

    def submissions(self):
        sec = self.require(self.sec, 'SEC'); mapping = cik_mapping(sec)
        count, gaps, unavailable = 0, [], []
        calendar = None
        for ticker in self.stocks:
            check()
            cik = mapping.get(ticker)
            if not cik:
                unavailable.append(ticker + ': no SEC CIK'); continue
            try:
                rows = collect_submissions(sec, cik=cik, ticker=ticker, clock=self.clock,
                    existing=self.repo.filings(ticker), persist=lambda r: self.repo.write('sec_filings', r, update=tuple(k for k in r if k != 'accession')),
                    verify_limit=20)
            except SourceError:
                if calendar is None:
                    calendar = alpha_calendar(HTTPClient(), key=self.values.get('ALPHA_VANTAGE_API_KEY'))
                for event in calendar:
                    if event.get('symbol') == ticker and event['reportDate'] >= self.day.isoformat():
                        row = earnings_fallback(ticker, event, clock=self.clock)
                        row['event_id'] = 'fallback:' + ticker + ':' + event['reportDate']
                        self.repo.write('earnings_events', row)
                continue
            closes = self.repo.closes(ticker)
            for row in rows:
                check(); count += 1
                if row['form'] == '8-K' and '2.02' in row['items']:
                    if row['accepted_at'] is None:
                        gaps.append(row['accession']); continue
                    event = earnings_event(row, closes=closes, clock=self.clock)
                    event['event_id'] = 'SEC:' + row['accession']
                    if event['ref_close'] is None: event['flags'].append('ref_close_missing')
                    future_periods = [f for f in rows if f['form'] in {'10-Q','10-K'} and f['report_date']
                                      and row['filing_date'] <= f['filing_date'] <= row['filing_date'] + timedelta(days=60)]
                    if future_periods: event['fiscal_period'] = min(future_periods, key=lambda f: f['filing_date'])['report_date'].isoformat()
                    self.repo.write('earnings_events', event, update=('ref_close','fiscal_period','flags'))
                    self.repo.supersede_fallback(ticker, row['accepted_at'].astimezone(NY).date(), self.clock.now_utc())
                    if not self.repo.info_signature('sec_8k:SEC:' + row['accession']):
                        body = sec.get(self.document_url(row))
                        self.info([make_item('sec_8k','SEC',row['accession'], headline=ticker + ' 8-K', body=body,
                            url=self.document_url(row), tickers=[ticker], published_at=row['accepted_at'], clock=self.clock, payload=row['raw'])])
                if row['form'] in {'4','4/A'} and row['accepted_at'] is not None and not self.repo.get_cursor('form4:' + row['accession']):
                    document = sec.get(self.document_url(row, raw_xml=True))
                    events = parse_form4(document, accession=row['accession'], filed_at=row['accepted_at'])
                    for event in events:
                        event.update(event_id=row['accession'] + ':' + str(event['transaction_index']), source='SEC', raw={'xml': document})
                        self.repo.write('form4_events', event)
                        self.info([make_item('form4','SEC',event['event_id'],headline=ticker + ' Form 4',body=document,
                            tickers=[ticker], published_at=row['accepted_at'], clock=self.clock, payload=event)])
                    self.repo.set_cursor('form4:' + row['accession'], {'parsed': True}, self.clock.now_utc())
        return {'processed_count': count, 'status': 'degraded' if gaps or unavailable else 'ok',
                'note': f'Unverified earnings accessions: {len(gaps)}; ' + '; '.join(unavailable), 'acceptance_gaps': gaps}

    @staticmethod
    def document_url(row, raw_xml=False):
        document = row['primary_document']
        if not document or '..' in document or document.startswith('/'):
            raise SourceError('Missing or unsafe SEC primary document')
        if raw_xml: document = document.rsplit('/', 1)[-1]
        return f'https://www.sec.gov/Archives/edgar/data/{int(row["cik"])}/{row["accession"].replace("-", "")}/{document}'

    def atom(self):
        return self.info(sec_atom(self.require(self.sec, 'SEC'), clock=self.clock))

    def index(self):
        previous = self.day - timedelta(days=1)
        while previous.weekday() >= 5: previous -= timedelta(days=1)
        items = sec_daily_index(self.require(self.sec, 'SEC'), previous, clock=self.clock)
        for item in items:
            item['body'] = self.sec.get(item['url'])
        return self.info(items)

    def apps(self, chart):
        rows = apple_chart(HTTPClient(), chart=chart, clock=self.clock)
        if len(rows) < 100: raise SourceError('Apple chart incomplete', confirmed_unavailable=True)
        previous = self.repo.latest_app_ranks(chart)
        for row in rows: self.repo.write('app_rank_snapshots', row)
        monitored = {str(app) for entity in self.monitored for app in entity.get('app_ids', [])}
        current = {r['app_id']: r['rank'] for r in rows if r['app_id'] in monitored}
        events = rank_jumps(previous, current, chart=chart, clock=self.clock)
        self.info(events)
        return {'processed_count': len(rows), 'events': len(events)}

    def trends_task(self):
        count, short = 0, []
        for entity in self.monitored:
            for keyword in entity.get('trends_keywords', []):
                check(); payload = self.trends.get(keyword)
                today = self.clock.now_utc().astimezone(NY).date()
                valid = [r for r in payload['history'] if today-timedelta(days=90) <= r['date'] < today]
                if len(valid) < 60: short.append(keyword + ': trend_window_short')
                event = trend_event(keyword, payload['history'], payload['today'], clock=self.clock)
                if event: self.info([event])
                self.repo.set_cursor('trends:' + keyword, payload, self.clock.now_utc()); count += 1
        return {'processed_count': count, 'note': '; '.join(short), 'status': 'degraded' if short else 'ok'}

    def websites_task(self):
        count = 0
        for entity in self.monitored:
            for url in entity.get('urls', []):
                check(); current = self.websites.get(url); previous = self.repo.latest_website(url)
                if previous is not None:
                    event = website_change(url, previous, current, clock=self.clock)
                    if event: self.info([event])
                self.repo.write('website_snapshots', {'url':url,'captured_at':self.clock.now_utc(),'body':current}); count += 1
        return {'processed_count': count}

    def fred_task(self):
        fred, count = self.require(self.fred, 'FRED'), 0
        for series in yaml.safe_load((ROOT / 'config/params/p-2026.10/m1.yaml').read_text())['m1']['fred_series']:
            try: observations=fred.collect(series)
            except SourceError as exc:
                raise SourceError(f'FRED {series}: {exc}',status_code=exc.status_code) from exc
            for row in observations:
                check(); self.repo.write('macro_observations', row)
                self.info(macro_items([row], clock=self.clock)); count += 1
        return {'processed_count': count}

    def finra(self):
        raw = finra_short_interest(HTTPClient(limiter=RateLimiter(60,60)), tickers=self.stocks)
        shares = frames_shares(self.require(self.sec,'SEC'), self.day); mapping = cik_mapping(self.sec)
        rows = parse_finra(raw, allowed_tickers=set(self.stocks), shares_by_ticker={t:shares.get(mapping.get(t),{}).get('shares') for t in self.stocks})
        for row in rows:
            row.update(observation_id=identity(row), raw=next((r for r in raw if r.get('symbolCode') == row['ticker'] and r.get('settlementDate') == row['settlement_date']), {}))
            self.repo.write('short_interest', row)
            published = datetime.combine(date.fromisoformat(row['publish_date']), datetime.min.time(), timezone.utc) if row['publish_date'] else None
            item = make_item('short_interest','FINRA',row['observation_id'], headline=row['ticker']+' short interest',body=str(row['short_interest']),
                             tickers=[row['ticker']],clock=self.clock,published_at=published,payload=row)
            if published: item['flags'].append('published_at_date_only')
            self.info([item])
        return {'processed_count': len(rows)}

    def cboe(self):
        rows = cboe_statistics(HTTPClient(), self.day)
        for row in rows:
            self.repo.write('options_stats', row)
            item = make_item('options_stats','CBOE',f'{self.day}:{row["category"]}',headline='CBOE '+row['category'],body=str(row),
                published_at=datetime.combine(self.day,datetime.min.time(),timezone.utc),clock=self.clock,payload=row)
            item['flags'].append('published_at_date_only'); self.info([item])
        return {'processed_count': len(rows)}

    def runtime(self):
        health = HealthBook(clock=self.clock, rows=self.repo.health_rows(), persist=self.repo.write_health)
        tasks = {'bars_full':('Alpaca',self.bars),'bars_prefill':('Alpaca',lambda:self.bars(prefill=True)),
            'wide_universe':('AlpacaWide',self.wide),'news_full':('AlpacaNews',self.news),'news_prefill':('AlpacaNews',self.news),
            'sec_submissions':('SEC',self.submissions),'sec_index':('SECDailyIndex',self.index),'sec_atom':('SECAtom',self.atom),
            'app_free':('AppStoreFree',lambda:self.apps('free')),'app_grossing':('AppStoreGrossing',lambda:self.apps('grossing')),
            'trends':('GoogleTrends',self.trends_task),'websites':('CompanyIR',self.websites_task),'fred':('FRED',self.fred_task),
            'finra':('FINRA',self.finra),'cboe':('CBOE',self.cboe)}
        for source in ('FederalReserveNews','EIANews'):
            health.record(source,success=False,configured=False,note='First phase excludes this source')
        def guarded(operation):
            def execute():
                before = self.repo.processed
                try:
                    return operation()
                except Exception as exc:
                    exc.processed_count = self.repo.processed - before
                    raise
            return execute
        tasks = {name:(source,guarded(operation)) for name,(source,operation) in tasks.items()}
        return Runtime(clock=self.clock,health=health,persist_job=self.repo.write_job,tasks=tasks)
