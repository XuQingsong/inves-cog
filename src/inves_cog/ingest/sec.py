"""SEC submissions, earnings-event calendar and non-derivative Form 4 parsing."""
from datetime import date, datetime, timezone
from xml.etree import ElementTree

from inves_cog.ingest.market import NY, regular_bounds, next_trading_day, trading_day
from inves_cog.ingest.http import SourceError, require_mapping


def parse_acceptance_et(value):
    """Q-M1-8 contract: SEC wall time is Eastern despite its literal Z suffix."""
    stamp = datetime.fromisoformat(value.removesuffix('Z'))
    if stamp.tzinfo is not None:
        raise ValueError('Unexpected offset: SEC acceptance format needs verification')
    return stamp.replace(tzinfo=NY).astimezone(timezone.utc)


def earnings_event(filing, *, closes, clock):
    if filing.get('form') != '8-K' or '2.02' not in filing.get('items', []):
        return None
    accepted = filing.get('accepted_at')
    if accepted is None:
        raise SourceError('Earnings filing has no verified acceptance time')
    day = accepted.astimezone(NY).date()
    bounds = regular_bounds(day)
    if bounds is None:
        session, reaction = 'closed', next_trading_day(day)
    elif accepted < bounds[0]:
        session, reaction = 'pre', day
    elif accepted < bounds[1]:
        session, reaction = 'intraday', day
    else:
        session, reaction = 'post', next_trading_day(day)
    prior = [d for d in closes if d < reaction]
    return {'ticker': filing['ticker'], 'accession': filing['accession'], 'item': '2.02',
            'accepted_at': accepted, 'session': session, 'reaction_day': reaction,
            'ref_close': closes[max(prior)] if prior else None, 'fiscal_period': filing.get('fiscal_period'),
            'fallback': False, 'flags': [], 'fetched_at': clock.now_utc()}


def earnings_fallback(ticker, data, *, clock):
    day = date.fromisoformat(data['reportDate'])
    session = data.get('session')
    if session not in {None, 'pre', 'post'}:
        raise SourceError('Unsupported earnings-calendar session')
    reaction = None
    flags = ['earnings_event_fallback']
    if session is None:
        flags.append('earnings_event_time_unknown')
    else:
        reaction = day if session == 'pre' and trading_day(day) else next_trading_day(day)
    return {'ticker': ticker, 'accession': None, 'item': None, 'accepted_at': None, 'session': session,
            'reaction_day': reaction, 'ref_close': None, 'fiscal_period': None, 'fallback': True,
            'flags': flags, 'reported_date': day, 'fetched_at': clock.now_utc()}


def submissions_rows(data, *, ticker, clock):
    data = require_mapping(data)
    rows = data.get('filings', {}).get('recent', data)
    numbers = rows.get('accessionNumber')
    if not isinstance(numbers, list):
        raise SourceError('Malformed submissions: accessionNumber array absent')
    results = []
    for index, accession in enumerate(numbers):
        def value(key):
            values = rows.get(key, [])
            return values[index] if index < len(values) else None
        filed = value('filingDate')
        if not filed or filed < '2015-01-01':
            continue
        accepted = value('acceptanceDateTime')
        results.append({'ticker': ticker, 'cik': str(data.get('cik', '')), 'accession': accession,
                        'form': value('form'), 'filing_date': date.fromisoformat(filed),
                        'report_date': date.fromisoformat(value('reportDate')) if value('reportDate') else None,
                        'accepted_at': parse_acceptance_et(accepted) if accepted else None,
                        'items': [part.strip() for part in (value('items') or '').split(',') if part.strip()],
                        'primary_document': value('primaryDocument'), 'is_xbrl': bool(value('isXBRL')),
                        'is_inline_xbrl': bool(value('isInlineXBRL')), 'fetched_at': clock.now_utc(),
                        'raw': {key: values[index] for key, values in rows.items() if isinstance(values, list) and index < len(values)}})
    return results


def collect_submissions(client, *, cik, ticker, clock):
    data = client.submissions(cik)
    rows = submissions_rows(data, ticker=ticker, clock=clock)
    for historical in data.get('filings', {}).get('files', []):
        if historical.get('filingTo', '9999-12-31') < '2015-01-01':
            continue
        name = historical['name']
        if '/' in name or '..' in name:
            raise SourceError('Unsafe historical submissions filename')
        older = client.get('https://data.sec.gov/submissions/' + name)
        for row in submissions_rows(older, ticker=ticker, clock=clock):
            row['cik'] = str(cik)
            rows.append(row)
    return list({row['accession']: row for row in rows}.values())


def parse_form4(xml, *, accession, filed_at):
    root = ElementTree.fromstring(xml)
    def content(path, parent=root):
        found = parent.find(path)
        return found.text.strip() if found is not None and found.text else None
    owner = content('.//rptOwnerName')
    officer = content('.//isOfficer')
    rows = []
    for index, transaction in enumerate(root.findall('.//nonDerivativeTable/nonDerivativeTransaction')):
        def number(path):
            text = content(path, transaction)
            return float(text) if text is not None else None
        rows.append({'ticker': content('.//issuerTradingSymbol'), 'filed_at': filed_at,
                     'insider_name': owner, 'is_officer': None if officer is None else officer.lower() in {'1', 'true'},
                     'transaction_code': content('./transactionCoding/transactionCode', transaction),
                     'shares': number('./transactionAmounts/transactionShares/value'),
                     'price': number('./transactionAmounts/transactionPricePerShare/value'),
                     'accession': accession, 'transaction_index': index})
    return rows
