"""Public read-only HTTP boundary; business page payloads stay upstream-owned."""

import math
import time
from collections import deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from inves_cog.web.api import create_app as page_app


class PageBoundary(BaseHTTPMiddleware):
    def __init__(self, app, *, monotonic=time.monotonic):
        super().__init__(app)
        self.monotonic = monotonic
        self.clients = {}
        self.lock = Lock()

    def allow(self, host):
        now = self.monotonic()
        with self.lock:
            # Expire inactive clients and bound memory without evicting active limits.
            self.clients = {ip: hits for ip, hits in self.clients.items() if hits and hits[-1] > now - 60}
            if host not in self.clients and len(self.clients) >= 10000:
                return False, 60
            hits = self.clients.setdefault(host, deque())
            while hits and hits[0] <= now - 60:
                hits.popleft()
            if len(hits) >= 60:
                return False, max(1, math.ceil(60 - (now - hits[0])))
            hits.append(now)
            return True, 0

    async def dispatch(self, request, call_next):
        if request.method != "GET":
            return JSONResponse({"detail": "Method Not Allowed"}, status_code=405, headers={"Allow": "GET"})
        path = request.scope["path"]
        if not path.startswith("/api/pages/") and not _html_page(path):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        host = request.client.host if request.client else "unknown"
        allowed, retry = self.allow(host)
        if not allowed:
            return JSONResponse({"detail": "请求过于频繁"}, status_code=429, headers={"Retry-After": str(retry)})
        if path == "/api/pages/":
            request.scope["path"] = "/api/pages/home"
            request.scope["raw_path"] = b"/api/pages/home"
        try:
            response = await call_next(request)
        except Exception:
            # No exception detail, DSN, SQL or private page content reaches HTTP/log output.
            return JSONResponse({"detail": "页面暂不可用"}, status_code=503)
        if response.status_code >= 500:
            return JSONResponse({"detail": "页面暂不可用"}, status_code=503)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


def _html_page(path):
    if path in {
        "/",
        "/log",
        "/stocks",
        "/account",
        "/trust",
        "/market",
        "/graph",
        "/settings/data",
        "/paper/plan",
        "/paper/portfolio",
        "/paper/universe",
        "/paper/health",
        "/paper/ledger",
        "/review",
        "/search",
        "/investor.js",
        "/lightweight-charts.js",
        "/barometer",
    }:
        return True
    for prefix in ("/linkage/", "/s/", "/stock/", "/paper/stock/"):
        rest = path[len(prefix) :] if path.startswith(prefix) else ""
        if rest and "/" not in rest:
            return True
    return False


def protect(app, *, monotonic=time.monotonic):
    app.debug = False
    # Disable built-in documentation routes even if the underlying app keeps defaults.
    app.router.routes = [
        r
        for r in app.router.routes
        if getattr(r, "path", "") not in {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}
    ]
    app.add_middleware(PageBoundary, monotonic=monotonic)
    return app


def create_app(*, dsn=None, clock=None, monotonic=None):
    app = page_app(dsn=dsn, clock=clock)
    if monotonic is None:
        return protect(app)
    return protect(app, monotonic=monotonic)
