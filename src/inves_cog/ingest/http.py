"""Injectable HTTP transport, bounded retries and process-local rate limits."""
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
import time
from typing import Any, Callable


class SourceError(RuntimeError):
    def __init__(self, message, *, status_code=None, confirmed_unavailable=False):
        super().__init__(message)
        self.status_code = status_code
        self.confirmed_unavailable = confirmed_unavailable


@dataclass
class Response:
    status_code: int
    data: Any
    headers: dict = field(default_factory=dict)


class RateLimiter:
    """Rolling window; callers can supply a monotonic timer and wait function."""
    def __init__(self, count, seconds, *, monotonic=time.monotonic, sleep=time.sleep):
        if count < 1 or seconds <= 0:
            raise ValueError('Invalid rate budget')
        self.count, self.seconds = count, seconds
        self.monotonic, self.sleep = monotonic, sleep
        self.arrivals = deque()
        self.lock = Lock()

    def acquire(self):
        with self.lock:
            while True:
                now = self.monotonic()
                while self.arrivals and self.arrivals[0] <= now - self.seconds:
                    self.arrivals.popleft()
                if len(self.arrivals) < self.count:
                    self.arrivals.append(now)
                    return
                self.sleep(max(0, self.arrivals[0] + self.seconds - now))


class HTTPClient:
    def __init__(self, send: Callable | None = None, *, retries=3, timeout=30,
                 sleep=time.sleep, limiter=None):
        self.send = send
        self.retries, self.timeout, self.sleep = retries, timeout, sleep
        self.limiter = limiter

    def request(self, method, url, *, params=None, headers=None, json=None, limiter=None):
        from inves_cog.ingest.deadline import remaining
        for attempt in range(self.retries + 1):
            seconds = remaining()
            request_timeout = min(self.timeout, seconds) if seconds is not None else self.timeout
            budget = limiter or self.limiter
            if budget:
                budget.acquire()
                seconds = remaining()
                request_timeout = min(self.timeout, seconds) if seconds is not None else self.timeout
            try:
                if self.send is None:
                    import httpx
                    result = httpx.request(method, url, params=params, headers=headers,
                                           json=json, timeout=request_timeout, follow_redirects=True)
                    try:
                        data = result.json()
                    except ValueError:
                        data = result.text
                    response = Response(result.status_code, data, dict(result.headers))
                else:
                    response = self.send(method, url, params=params, headers=headers,
                                         json=json, timeout=request_timeout)
            except (TimeoutError, ConnectionError) as exc:
                if attempt == self.retries:
                    raise SourceError('HTTP transport failed after bounded retries') from exc
                self.sleep(min(60, 2 ** attempt))
                continue
            except Exception as exc:
                # httpx exceptions must also work with no optional transport imports.
                if type(exc).__module__.startswith('httpx') and any(
                        base.__name__ in {'TimeoutException', 'NetworkError'}
                        for base in type(exc).__mro__):
                    if attempt < self.retries:
                        self.sleep(min(60, 2 ** attempt))
                        continue
                    raise SourceError('HTTP transport failed after bounded retries') from exc
                raise
            if 200 <= response.status_code < 300:
                return response.data
            retryable = response.status_code == 429 or 500 <= response.status_code < 600
            if retryable and attempt < self.retries:
                self.sleep(min(60, 2 ** attempt))
                continue
            raise SourceError(f'HTTP status {response.status_code}', status_code=response.status_code)
        raise AssertionError('Unreachable request state')

    def get(self, url, **kwargs):
        return self.request('GET', url, **kwargs)


def require_mapping(payload):
    if not isinstance(payload, dict):
        raise SourceError('Expected a JSON object; malformed responses are not retried')
    return payload
