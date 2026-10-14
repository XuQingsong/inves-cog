"""The single SEC client shared by M1 and M2, with one process-wide budget."""
import os
import time
from urllib.parse import urlparse

from inves_cog.ingest.http import HTTPClient, RateLimiter

_SEC_BUDGET = RateLimiter(5, 1)


class SECClient:
    def __init__(self, http=None, *, user_agent=None, monotonic=None, sleep=None):
        self.user_agent = os.environ.get('SEC_USER_AGENT', '') if user_agent is None else user_agent
        if not self.user_agent.strip():
            raise ValueError('SEC_USER_AGENT is required (等待 R5)')
        self.http = http or HTTPClient()
        # Every production instance uses the same budget; deterministic test clocks
        # get an isolated injected budget so they cannot contaminate the process clock.
        self.budget = _SEC_BUDGET if monotonic is None and sleep is None else RateLimiter(
            5, 1, monotonic=monotonic or time.monotonic, sleep=sleep or time.sleep)

    def get(self, url, *, params=None):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname not in {'data.sec.gov', 'www.sec.gov'}:
            raise ValueError('SEC client accepts only official HTTPS SEC endpoints')
        # Acquire for each HTTP attempt, including retries.
        return self.http.get(url, params=params, limiter=self.budget,
                             headers={'User-Agent': self.user_agent,
                                      'Accept': 'application/json, application/xml, text/html'})

    def submissions(self, cik):
        return self.get(f'https://data.sec.gov/submissions/CIK{int(cik):010d}.json')

    def companyfacts(self, cik):
        return self.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json')
