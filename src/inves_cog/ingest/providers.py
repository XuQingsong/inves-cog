"""Approved source endpoints behind injectable, bounded HTTP clients."""
import csv
from datetime import date, datetime, timedelta, timezone
from io import StringIO
import json
import re
from xml.etree import ElementTree

from inves_cog.ingest.http import HTTPClient, RateLimiter, SourceError, require_mapping
from inves_cog.ingest.info import make_item
from inves_cog.ingest.market import NY, market_window, trading_day
from inves_cog.ingest.sec import parse_acceptance_et
from inves_cog.ingest.sources import fred_observations, parse_cboe


def stamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise SourceError('Source timestamp lacks timezone')
    return result.astimezone(timezone.utc)


class Alpaca:
    def __init__(self, *, clock, key, secret, http=None, assets_base_url='https://paper-api.alpaca.markets'):
        if not key or not secret:
            raise SourceError('Alpaca credentials absent: 等待 R5', confirmed_unavailable=True)
        if assets_base_url not in {'https://paper-api.alpaca.markets','https://api.alpaca.markets'}:
            raise ValueError('Official Alpaca asset endpoint required')
        self.assets_base_url=assets_base_url
        self.clock = clock
        self.headers = {'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': secret}
        self.http = http or HTTPClient(limiter=RateLimiter(120, 60),pool=True)

    def assets(self):
        rows = self.http.get(self.assets_base_url+'/v2/assets', params={'status': 'active', 'asset_class': 'us_equity'}, headers=self.headers)
        if not isinstance(rows, list):
            raise SourceError('Malformed Alpaca assets')
        return [{**row, 'ticker': row['symbol'], 'asset_class': row.get('class')} for row in rows]

    def daily_bars(self, tickers, first, last, *, feed='sip'):
        params = {'symbols': ','.join(tickers), 'timeframe': '1Day', 'feed': feed, 'adjustment': 'raw',
                  'start': datetime.combine(first, datetime.min.time(), NY).isoformat(),
                  'end': datetime.combine(last + timedelta(days=1), datetime.min.time(), NY).isoformat(), 'limit': 10000}
        seen_tokens, seen_rows, rows = set(), set(), []
        while True:
            data = require_mapping(self.http.get('https://data.alpaca.markets/v2/stocks/bars', params=dict(params), headers=self.headers))
            if not isinstance(data.get('bars'), dict):
                raise SourceError('Daily bars mapping missing')
            for ticker, bars in data['bars'].items():
                for bar in bars:
                    day = stamp(bar['t']).astimezone(NY).date()
                    if ticker not in tickers or not first <= day <= last or (ticker, day) in seen_rows:
                        continue
                    seen_rows.add((ticker, day))
                    rows.append({'ticker': ticker, 'trade_date': day, 'open': bar.get('o'), 'high': bar.get('h'),
                                 'low': bar.get('l'), 'close': bar.get('c'), 'volume': bar.get('v'),
                                 'post_close': None, 'adj_factor': None, 'source': 'Alpaca'})
            token = data.get('next_page_token')
            if not token:
                return rows
            if token in seen_tokens:
                raise SourceError('Repeated daily pagination token')
            seen_tokens.add(token)
            params['page_token'] = token

    def news(self, *, first, last):
        params = {'start': first.isoformat(), 'end': last.isoformat(), 'include_content': True, 'limit': 50, 'sort': 'asc'}
        seen_tokens = set()
        while True:
            data = require_mapping(self.http.get('https://data.alpaca.markets/v1beta1/news', params=dict(params), headers=self.headers))
            if not isinstance(data.get('news'), list):
                raise SourceError('News list missing')
            for record in data['news']:
                item = make_item('news', record.get('source') or 'Alpaca', record['id'], headline=record['headline'],
                                 body=record.get('content'), url=record.get('url'), tickers=record.get('symbols', []),
                                 published_at=stamp(record['created_at']) if record.get('created_at') else None,
                                 clock=self.clock, payload=record, upstream_provider=record.get('upstream_provider'), upstream_id=record.get('upstream_id'))
                yield item
            token = data.get('next_page_token')
            if not token:
                return
            if token in seen_tokens:
                raise SourceError('Repeated news pagination token')
            seen_tokens.add(token)
            params['page_token'] = token


def sec_atom(client, *, clock):
    xml = client.get('https://www.sec.gov/cgi-bin/browse-edgar', params={'action': 'getcurrent', 'type': '8-K', 'owner': 'include', 'count': 100, 'output': 'atom'})
    root = ElementTree.fromstring(xml)
    namespace = {'atom': 'http://www.w3.org/2005/Atom'}
    rows = []
    for entry in root.findall('atom:entry', namespace):
        identifier = entry.findtext('atom:id', '', namespace)
        match = re.search(r'\d{10}-\d{2}-\d{6}', identifier)
        if not match:
            raise SourceError('Atom accession missing')
        links = entry.findall('atom:link', namespace)
        url = links[0].attrib.get('href') if links else None
        updated = entry.findtext('atom:updated', None, namespace)
        rows.append(make_item('sec_8k', 'SEC', match.group(), headline=entry.findtext('atom:title', '', namespace),
                              body=entry.findtext('atom:summary', None, namespace), url=url,
                              published_at=stamp(updated) if updated else None, clock=clock,
                              payload={'atom_id': identifier, 'updated': updated}))
    return rows


def sec_daily_index(client, day, *, clock):
    quarter = (day.month - 1) // 3 + 1
    url = f'https://www.sec.gov/Archives/edgar/daily-index/{day.year}/QTR{quarter}/form.{day:%Y%m%d}.idx'
    text = client.get(url)
    result = []
    for line in text.splitlines():
        match = re.match(r'^8-K\s+(.+?)\s+(\d+)\s+(\d{4}-\d{2}-\d{2})\s+(edgar/data/\S+)', line)
        if not match:
            continue
        company, cik, filed, filename = match.groups()
        accession = re.search(r'\d{10}-\d{2}-\d{6}', filename)
        if accession is None:
            raise SourceError('Daily-index accession absent')
        item = make_item('sec_8k', 'SEC', accession.group(), headline=f'{company} 8-K', body=None,
                         url='https://www.sec.gov/Archives/' + filename, clock=clock,
                         published_at=datetime.combine(date.fromisoformat(filed), datetime.min.time(), timezone.utc),
                         payload={'cik': cik, 'filing_date': filed, 'index_url': url})
        item['flags'].append('published_at_date_only')
        result.append(item)
    return result


def apple_chart(http, *, chart, clock):
    if chart == 'free':
        url = 'https://rss.marketingtools.apple.com/api/v2/us/apps/top-free/100/apps.json'
        data = require_mapping(http.get(url))
        values = data.get('feed', {}).get('results')
        if not isinstance(values, list):
            raise SourceError('Apple free chart unavailable', confirmed_unavailable=True)
        return [{'ts_utc': clock.now_utc(), 'chart': chart, 'rank': index + 1, 'app_id': str(row['id']),
                 'app_name': row.get('name'), 'developer': row.get('artistName')} for index, row in enumerate(values[:100])]
    if chart != 'grossing':
        raise ValueError('Unknown Apple chart')
    data = require_mapping(http.get('https://itunes.apple.com/us/rss/topgrossingapplications/limit=100/json'))
    values = data.get('feed', {}).get('entry')
    if not isinstance(values, list):
        raise SourceError('Apple grossing chart unavailable', confirmed_unavailable=True)
    return [{'ts_utc': clock.now_utc(), 'chart': chart, 'rank': index + 1,
             'app_id': str(row['id']['attributes']['im:id']), 'app_name': row.get('im:name', {}).get('label'),
             'developer': row.get('im:artist', {}).get('label')} for index, row in enumerate(values[:100])]


class FRED:
    def __init__(self, *, key, clock, http=None):
        if not key:
            raise SourceError('FRED key absent: 等待 R5', confirmed_unavailable=True)
        self.key, self.clock = key, clock
        self.http = http or HTTPClient(limiter=RateLimiter(30, 60))

    def collect(self, series_id):
        params = {'api_key': self.key, 'file_type': 'json', 'series_id': series_id}
        series = require_mapping(self.http.get('https://api.stlouisfed.org/fred/series', params=params))
        units = series['seriess'][0]['units']
        try:
            server_day = date.fromisoformat(series['realtime_end'])
        except (KeyError, TypeError, ValueError):
            raise SourceError('FRED metadata lacks a valid server realtime_end') from None
        # UTC can already be tomorrow at FRED. Use the reported API date rather
        # than guessing its timezone, and never cross the injected as-of date.
        visible = min(server_day, self.clock.now_utc().date()).isoformat()
        offset, rows, seen = 0, [], set()
        while True:
            try:
                data = require_mapping(self.http.get('https://api.stlouisfed.org/fred/series/observations',
                    params={**params, 'realtime_start': '1776-07-04', 'realtime_end': visible,
                            'output_type': 1, 'offset': offset, 'limit': 100000}))
            except SourceError as exc:
                if offset == 0 and exc.status_code == 400:
                    return self.collect_vintages(series_id,units,visible)
                raise
            batch = data.get('observations')
            count = data.get('count')
            if not isinstance(batch, list) or not isinstance(count, int) or count < 0:
                raise SourceError('Malformed FRED observations pagination')
            parsed = fred_observations(series_id, data, units=units, clock=self.clock)
            for row in parsed:
                key = (row['observation_date'], row['realtime_start'])
                if key in seen:
                    raise SourceError('FRED returned repeated vintage rows')
                seen.add(key)
                rows.append(row)
            offset += len(batch)
            if offset >= count:
                return rows
            if not batch:
                raise SourceError('FRED pagination ended before declared count')


    def collect_vintages(self,series_id,units,visible):
        """Bound each real-time range using official vintage dates.

        Type 1 retains realtime_start. Later ranges overlap the preceding
        vintage; rows clipped to that anchor are ignored, since the earlier
        range already stored them. Old values never gain a fake release date.
        """
        base={'api_key':self.key,'file_type':'json','series_id':series_id}
        vintages=[]; offset=0
        while True:
            data=require_mapping(self.http.get('https://api.stlouisfed.org/fred/series/vintagedates',
                params={**base,'realtime_end':visible,'offset':offset,'limit':1000,'sort_order':'asc'}))
            batch=data.get('vintage_dates'); count=data.get('count')
            if not isinstance(batch,list) or not isinstance(count,int): raise SourceError('Malformed FRED vintage-date pagination')
            vintages.extend(day for day in batch if date.fromisoformat(day)<=date.fromisoformat(visible))
            offset+=len(batch)
            if offset>=count: break
            if not batch: raise SourceError('FRED vintage dates ended before count')
        vintages=sorted(set(vintages)); result=[]; seen=set()
        if not vintages: raise SourceError('FRED supplied no visible historical vintage dates')
        size=getattr(self,'vintage_batch_size',1000)
        for start in range(0,len(vintages),size):
            anchor=vintages[start-1] if start else None
            first=anchor or '1776-07-04'; last=vintages[min(start+size,len(vintages))-1]
            offset=0
            while True:
                data=require_mapping(self.http.get('https://api.stlouisfed.org/fred/series/observations',
                    params={**base,'realtime_start':first,'realtime_end':last,'output_type':1,'offset':offset,'limit':10000}))
                batch=data.get('observations'); count=data.get('count')
                if not isinstance(batch,list) or not isinstance(count,int): raise SourceError('Malformed FRED vintage observations')
                for row in fred_observations(series_id,data,units=units,clock=self.clock):
                    vintage=row['realtime_start'].isoformat()
                    if anchor and vintage<=anchor: continue
                    if vintage>last: raise SourceError('FRED observation version crosses requested range')
                    key=(row['observation_date'],row['realtime_start'])
                    if key in seen: raise SourceError('Repeated FRED vintage observation')
                    seen.add(key);result.append(row)
                offset+=len(batch)
                if offset>=count: break
                if not batch: raise SourceError('FRED vintage observations ended before count')
        return result


def alpha_calendar(http, *, key):
    if not key:
        raise SourceError('Alpha Vantage key absent: 等待 R5', confirmed_unavailable=True)
    text = http.get('https://www.alphavantage.co/query', params={'function': 'EARNINGS_CALENDAR', 'horizon': '3month', 'apikey': key})
    if not isinstance(text, str) or 'reportDate' not in text.splitlines()[0]:
        raise SourceError('Alpha Vantage calendar unavailable')
    return list(csv.DictReader(StringIO(text)))


def finra_short_interest(http, *, tickers):
    rows=[]; offset=0; signatures=set()
    while True:
        batch=http.request('POST','https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest',
            headers={'Accept':'application/json'},json={'limit':1000,'offset':offset,
                'domainFilters':[{'fieldName':'symbolCode','values':list(tickers)}]})
        if not isinstance(batch,list): raise SourceError('FINRA response format not a list',confirmed_unavailable=True)
        if not batch: break
        signature=json.dumps(batch,sort_keys=True)
        if signature in signatures: raise SourceError('Repeated FINRA page')
        signatures.add(signature);rows.extend(batch);offset+=len(batch)
        if len(batch)<1000: break
    if not any(str(row.get('marketClassCode',row.get('issueExchange',''))).upper() in {'NYSE','NASDAQ','N','Q'} for row in rows):
        raise SourceError('FINRA dataset does not establish NYSE/Nasdaq coverage',confirmed_unavailable=True)
    return rows
