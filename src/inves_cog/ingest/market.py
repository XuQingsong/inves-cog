"""Exchange-local bar windows and complete SIP pagination, without gap filling."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from inves_cog.ingest.http import SourceError, require_mapping

NY = ZoneInfo('America/New_York')


@lru_cache(maxsize=16)
def exchange(year):
    import exchange_calendars
    return exchange_calendars.get_calendar('XNYS', start=f'{year-1}-01-01', end=f'{year+1}-12-31')


def trading_day(day):
    return exchange(day.year).is_session(str(day))


def next_trading_day(day):
    candidate = day + timedelta(days=1)
    while not trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate


def regular_bounds(day):
    cal = exchange(day.year)
    if not cal.is_session(str(day)):
        return None
    return (cal.session_open(str(day)).to_pydatetime(), cal.session_close(str(day)).to_pydatetime())


def local_at(day, hour, minute=0):
    return datetime.combine(day, time(hour, minute), NY).astimezone(timezone.utc)


def market_window(day):
    return local_at(day, 4), local_at(day, 20)


def schedule_times(day):
    return {'full_start': local_at(day, 20, 20), 'full_deadline': local_at(day, 20, 45),
            'prefill': local_at(day, 8)}


def bar_session(stamp):
    if stamp.tzinfo is None:
        raise ValueError('Bar timestamps must include timezone')
    day = stamp.astimezone(NY).date()
    bounds = regular_bounds(day)
    if bounds is None:
        return None
    first, last = market_window(day)
    if not first <= stamp < last:
        return None
    return 'pre' if stamp < bounds[0] else 'intraday' if stamp < bounds[1] else 'post'


def post_close(bars, day, *, ticker=None):
    candidates = [row for row in bars if (ticker is None or row.get('ticker') == ticker) and row['ts_utc'].astimezone(NY).date() == day
                  and bar_session(row['ts_utc']) == 'post' and row.get('volume') is not None
                  and row['volume'] > 0 and row.get('close') is not None]
    return max(candidates, key=lambda row: row['ts_utc'])['close'] if candidates else None


def split_factors(days, splits):
    result = []
    for day in days:
        factor = 1.0
        for split in splits:
            if split['ratio'] <= 0:
                raise ValueError('Split ratio must be positive')
            if day < split['date']:
                factor /= split['ratio']
        result.append(factor)
    return result


@dataclass
class BarResult:
    rows: list
    exhausted: bool
    coverage: dict
    status: str
    missing_codes: list


class MarketCollector:
    def __init__(self, http, *, clock, feed='sip', headers=None):
        self.http, self.clock, self.feed = http, clock, feed
        self.headers = headers or {}

    def minute_bars(self, tickers, day, *, end=None):
        first, last = market_window(day)
        if end is not None:
            if end.tzinfo is None or not first <= end <= last:
                raise ValueError('Invalid prefill end')
            last = end
        params = {'symbols': ','.join(tickers), 'timeframe': '1Min', 'feed': self.feed,
                  'adjustment': 'raw', 'start': first.isoformat(), 'end': last.isoformat(), 'limit': 10000}
        seen, rows, tokens = set(), [], set()
        while True:
            data = require_mapping(self.http.get('https://data.alpaca.markets/v2/stocks/bars', params=dict(params), headers=self.headers))
            grouped = data.get('bars')
            if not isinstance(grouped, dict):
                raise SourceError('Alpaca bars mapping missing')
            for ticker, values in grouped.items():
                if ticker not in tickers or not isinstance(values, list):
                    raise SourceError('Unexpected bar symbol or shape')
                for value in values:
                    stamp = datetime.fromisoformat(value['t'].replace('Z', '+00:00')).astimezone(timezone.utc)
                    session = bar_session(stamp)
                    identity = (ticker, stamp)
                    if not first <= stamp < last or session is None or identity in seen:
                        continue
                    seen.add(identity)
                    rows.append({'ticker': ticker, 'ts_utc': stamp, 'open': value.get('o'), 'high': value.get('h'),
                                 'low': value.get('l'), 'close': value.get('c'), 'volume': value.get('v'),
                                 'session': session, 'source': 'Alpaca'})
            token = data.get('next_page_token')
            if not token:
                break
            if token in tokens:
                raise SourceError('Repeated Alpaca pagination token')
            tokens.add(token)
            params['page_token'] = token
        bounds = regular_bounds(day)
        denominator = int((bounds[1] - bounds[0]).total_seconds() / 60) if bounds else None
        coverage = {ticker: sum(r['ticker'] == ticker and r['session'] == 'intraday' for r in rows) / denominator
                    if denominator else None for ticker in tickers}
        missing = [ticker for ticker in tickers if not any(r['ticker'] == ticker for r in rows)]
        return BarResult(rows, True, coverage, 'ok' if self.feed == 'sip' else 'degraded', missing)
