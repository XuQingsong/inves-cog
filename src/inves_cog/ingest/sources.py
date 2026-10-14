"""Structured-source parsers, preserving missing values and original releases."""
import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import difflib
from io import StringIO

from inves_cog.ingest.info import make_item, normalized_body
from inves_cog.ingest.http import SourceError


def optional_number(value):
    if value is None or str(value).strip() in {'', '.', '\\N'}:
        return None
    return float(Decimal(str(value).replace(',', '')))


def fred_observations(series_id, response, *, units, clock):
    rows = []
    for observation in response['observations']:
        rows.append({'series_id': series_id, 'observation_date': date.fromisoformat(observation['date']),
                     'value': optional_number(observation.get('value')), 'units': units,
                     'realtime_start': date.fromisoformat(observation['realtime_start']), 'fetched_at': clock.now_utc()})
    return rows


def macro_items(rows, *, clock):
    result = []
    for row in rows:
        published = datetime.combine(row['realtime_start'], datetime.min.time(), timezone.utc)
        item = make_item('macro', 'FRED', f"{row['series_id']}:{row['observation_date']}:{row['realtime_start']}",
                         headline=f"{row['series_id']} observation {row['observation_date']}",
                         body=f"{row['value']} {row['units']}", clock=clock, published_at=published,
                         payload={key: str(value) if isinstance(value, date) else value for key, value in row.items() if key != 'fetched_at'})
        item['flags'].append('published_at_date_only')
        result.append(item)
    return result


def parse_finra(response, *, allowed_tickers, shares_by_ticker=None):
    rows = []
    shares_by_ticker = shares_by_ticker or {}
    for record in response:
        ticker = record.get('symbolCode')
        exchange = str(record.get('issueExchange', '')).upper()
        if ticker not in allowed_tickers or exchange not in {'NYSE', 'NASDAQ', 'N', 'Q'}:
            continue
        short = optional_number(record.get('currentShortPositionQuantity'))
        volume = optional_number(record.get('averageDailyVolumeQuantity'))
        shares = shares_by_ticker.get(ticker)
        rows.append({'ticker': ticker, 'settlement_date': record.get('settlementDate'),
                     'publish_date': record.get('publicationDate'), 'short_interest': short,
                     'avg_daily_volume': volume, 'days_to_cover': short / volume if short is not None and volume is not None and volume > 0 else None,
                     'si_pct_shares_outstanding': 100 * short / shares if short is not None and shares is not None and shares > 0 else None,
                     'source': 'FINRA'})
    return rows


def parse_cboe(text, trade_date):
    reader = csv.DictReader(StringIO(text))
    rows = []
    for record in reader:
        def value(*names):
            return next((record[name] for name in names if name in record), None)
        category = value('category', 'Type', 'Category')
        if not category:
            raise SourceError('CBOE category field missing')
        calls = optional_number(value('call_volume', 'Call Volume', 'Calls'))
        puts = optional_number(value('put_volume', 'Put Volume', 'Puts'))
        if calls is None and puts is None:
            raise SourceError('CBOE market-volume fields absent')
        ratio = optional_number(value('put_call_ratio', 'P/C Ratio'))
        rows.append({'trade_date': trade_date, 'category': category.lower(), 'call_volume': calls, 'put_volume': puts,
                     'put_call_ratio': ratio if ratio is not None else puts / calls if puts is not None and calls is not None and calls > 0 else None,
                     'open_interest': optional_number(value('open_interest', 'Open Interest')), 'source': 'CBOE'})
    if not rows:
        raise SourceError('Empty or malformed CBOE market statistics')
    return rows


def website_change(url, previous, current, *, clock):
    old, new = normalized_body(previous), normalized_body(current)
    if old == new:
        return None
    import hashlib
    digest = hashlib.sha256(new.encode()).hexdigest()
    difference = '\n'.join(difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile='previous', tofile='current', lineterm=''))
    return make_item('site_change', 'CompanyIR', url + ':' + digest, headline='Website content changed: ' + url,
                     body=difference, url=url, clock=clock, published_at=None,
                     payload={'content_sha256': digest})
