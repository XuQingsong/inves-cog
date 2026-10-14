"""Approved source adapters; no synthetic values are produced on failure."""
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlparse
from collections import defaultdict
from inves_cog.ingest.http import HTTPClient, RateLimiter, SourceError, require_mapping
from inves_cog.ingest.market import NY
from inves_cog.ingest.sources import optional_number


class Embedding:
    def __init__(self, values, http=None):
        self.key, self.base = values.get('DASHSCOPE_API_KEY'), values.get('DASHSCOPE_BASE_URL', '')
        self.http = http or HTTPClient()
    def __call__(self, text, *, model, dimensions):
        if model != 'text-embedding-v3' or dimensions != 1024:
            raise ValueError('Unsupported embedding contract')
        if not self.key or urlparse(self.base).scheme != 'https':
            raise SourceError('DashScope embedding endpoint/key missing: 等待 R5', confirmed_unavailable=True)
        data = require_mapping(self.http.request('POST', self.base.rstrip('/') + '/embeddings',
            headers={'Authorization': 'Bearer ' + self.key},
            json={'model': model, 'input': text, 'dimensions': dimensions}))
        try:
            return data['data'][0]['embedding']
        except (KeyError, IndexError, TypeError):
            raise SourceError('Embedding response lacks data[0].embedding') from None


def cik_mapping(sec):
    data = require_mapping(sec.get('https://www.sec.gov/files/company_tickers_exchange.json'))
    if not isinstance(data.get('fields'), list) or not isinstance(data.get('data'), list):
        raise SourceError('SEC ticker/CIK mapping malformed')
    rows = [dict(zip(data['fields'], row)) for row in data['data']]
    return {row['ticker']: str(row['cik']).zfill(10) for row in rows}


def frames_shares(sec, day):
    year, quarter = day.year, (day.month - 1) // 3
    result = {}
    for _ in range(2):
        if quarter == 0:
            year, quarter = year - 1, 4
        frame = f'CY{year}Q{quarter}I'
        data = require_mapping(sec.get(f'https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/{frame}.json'))
        if not isinstance(data.get('data'), list):
            raise SourceError('SEC shares frame malformed')
        for row in data['data']:
            if row.get('val') is not None:
                result.setdefault(str(row['cik']).zfill(10), {'shares': row['val'], 'frame': frame, 'end': row.get('end')})
        quarter -= 1
    return result


def alpaca_splits(alpaca, tickers, first, last):
    params = {'symbols': ','.join(tickers), 'types': 'forward_split,reverse_split',
              'start': first.isoformat(), 'end': last.isoformat(), 'limit': 1000, 'sort': 'asc'}
    output, seen = defaultdict(list), set()
    while True:
        data = require_mapping(alpaca.http.get('https://data.alpaca.markets/v1/corporate-actions',
                                              params=dict(params), headers=alpaca.headers))
        actions = data.get('corporate_actions')
        if not isinstance(actions, dict):
            raise SourceError('Alpaca corporate actions mapping missing')
        for category in ('forward_splits', 'reverse_splits'):
            for row in actions.get(category, []):
                old, new = optional_number(row.get('old_rate')), optional_number(row.get('new_rate'))
                if old is None or new is None or old <= 0 or new <= 0 or not row.get('ex_date'):
                    raise SourceError('Split lacks positive old/new rate or effective date')
                ticker = row.get('symbol')
                if ticker in tickers:
                    output[ticker].append({'date': date.fromisoformat(row['ex_date']), 'ratio': new / old, 'raw': row})
        token = data.get('next_page_token')
        if not token:
            return dict(output)
        if token in seen:
            raise SourceError('Repeated corporate actions pagination token')
        seen.add(token)
        params['page_token'] = token


class Websites:
    def __init__(self, http=None):
        self.http = http or HTTPClient()
        self.limits = {}
    def get(self, url):
        parts = urlparse(url)
        if parts.scheme != 'https' or not parts.hostname or parts.username:
            raise ValueError('Website URL must be public HTTPS')
        limiter = self.limits.setdefault(parts.hostname, RateLimiter(1, 2))
        value = self.http.get(url, limiter=limiter)
        if not isinstance(value, str):
            raise SourceError('Website response is not text')
        return value


class Trends:
    def __init__(self, *, clock):
        self.clock, self.limiter = clock, RateLimiter(1, 10)
    def get(self, keyword):
        from pytrends.request import TrendReq
        from inves_cog.ingest.deadline import check
        limiter = self.limiter
        class LimitedTrendReq(TrendReq):
            def GetGoogleCookie(self):
                check()
                limiter.acquire()
                return super().GetGoogleCookie()
            def _get_data(self, *args, **kwargs):
                check()
                limiter.acquire()
                return super()._get_data(*args, **kwargs)
        try:
            client = LimitedTrendReq(hl='en-US', tz=300, timeout=(10, 30), retries=0)
            client.build_payload([keyword], timeframe='today 3-m', geo='US')
            data = client.interest_over_time()
        except Exception as exc:
            status = getattr(getattr(exc, 'response', None), 'status_code', None)
            raise SourceError(f'Google Trends {keyword}: {type(exc).__name__}: {exc}', status_code=status,
                              confirmed_unavailable=status in {401, 403}) from exc
        today, rows, value = self.clock.now_utc().astimezone(NY).date(), [], None
        for instant, row in data.iterrows():
            day, number = instant.date(), float(row[keyword])
            if day == today:
                value = number
            elif day < today and not row.get('isPartial', False):
                rows.append({'date': day, 'value': number})
        return {'history': rows, 'today': value}


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.rows, self.cells, self.text = [], None, None, None
    def handle_starttag(self, tag, attrs):
        if tag == 'table': self.rows = []
        elif tag == 'tr' and self.rows is not None: self.cells = []
        elif tag in {'td', 'th'} and self.cells is not None: self.text = []
    def handle_data(self, value):
        if self.text is not None: self.text.append(value)
    def handle_endtag(self, tag):
        if tag in {'td', 'th'} and self.text is not None:
            self.cells.append(' '.join(''.join(self.text).split())); self.text = None
        elif tag == 'tr' and self.cells is not None:
            self.rows.append(self.cells); self.cells = None
        elif tag == 'table' and self.rows is not None:
            self.tables.append(self.rows); self.rows = None


def cboe_statistics(http, day):
    html=http.get('https://www.cboe.com/markets/us/options/market-statistics/daily',params={'dt':day.isoformat()})
    if not isinstance(html,str): raise SourceError('CBOE daily response is not HTML')
    import re
    decoded=html.replace('\\"','"')
    observed=re.search(r'["\']selectedDate["\']\s*:\s*["\'](\d{4}-\d{2}-\d{2})',decoded)
    if observed is None:
        observed=re.search(r'<input\b[^>]*value=["\'](\d{4}[/-]\d{2}[/-]\d{2})',html)
    if observed is None or observed.group(1).replace('/','-')!=day.isoformat():
        raise SourceError('CBOE statistics date missing or differs from requested date')
    parser=_Tables();parser.feed(html)
    categories={'SUM OF ALL PRODUCTS':'total','INDEX OPTIONS':'index',
        'EXCHANGE TRADED PRODUCTS':'etf','EQUITY OPTIONS':'equity'}
    ratios={row[0].upper():optional_number(row[1]) for table in parser.tables for row in table if len(row)==2 and 'PUT/CALL RATIO' in row[0].upper()}
    output=[]
    for rows in parser.tables:
        heading=next((r[0] for r in rows if len(r)==1),None)
        volume=next((r for r in rows if r and r[0].upper()=='VOLUME'),None)
        interest=next((r for r in rows if r and r[0].upper()=='OPEN INTEREST'),None)
        if not heading or not volume or len(volume)<3: continue
        category=categories.get(heading.upper()) or re.sub(r'[^a-z0-9]+','_',heading.lower()).strip('_')
        call,put=optional_number(volume[1]),optional_number(volume[2])
        ratio_name={'total':'TOTAL','index':'INDEX','equity':'EQUITY'}.get(category,heading.upper())+' PUT/CALL RATIO'
        ratio=ratios.get(ratio_name)
        if ratio is None: ratio=put/call if call and put is not None else None
        output.append({'trade_date':day,'category':category,'category_label':heading,'call_volume':call,
            'put_volume':put,'put_call_ratio':ratio,
            'open_interest':optional_number(interest[3]) if interest and len(interest)>3 else None,'source':'CBOE'})
    if not output: raise SourceError('CBOE daily market tables absent; no substitute produced')
    return output
