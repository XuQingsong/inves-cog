"""Append-only Alpha Vantage snapshots. These are not valuation formula inputs."""

import json
import math
import time as timer
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4

from psycopg.types.json import Jsonb

DAILY_LIMIT = 24


@dataclass
class Response:
    raw: object
    status_code: int = 200


class Client:
    def __init__(self, key):
        if not key:
            raise ValueError("Alpha Vantage key missing")
        self.key = key

    def fetch(self, ticker):
        import httpx

        # No automatic retries or redirects: one reservation is one HTTP call.
        chunks, size, started = [], 0, timer.monotonic()
        with httpx.stream(
            "GET",
            "https://www.alphavantage.co/query",
            params={"function": "EARNINGS_ESTIMATES", "symbol": ticker, "apikey": self.key},
            timeout=20,
            follow_redirects=False,
        ) as response:
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > 2 * 1024 * 1024 or timer.monotonic() - started > 20:
                    raise TimeoutError("consensus response exceeded bounded read")
                chunks.append(chunk)
            status = response.status_code
        body = b"".join(chunks).decode("utf-8")
        try:
            raw = json.loads(body)
        except ValueError:
            raw = body
        return Response(raw, status)


def number(value, *, count=False):
    if value in (None, "", "None", "N/A", "-", "null"):
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not an estimate")
    n = float(value)
    if not math.isfinite(n) or count and (n < 0 or not n.is_integer()):
        raise ValueError("invalid estimate number")
    return int(n) if count else n


def parse_estimates(ticker, raw, fetched_at):
    """Provider flat response verified against the coordinator fixture; no inferred estimates."""
    if raw.get("symbol") != ticker or not isinstance(raw.get("estimates"), list):
        raise ValueError("unrecognized earnings estimates response")
    annual, quarterly = [], []
    for row in raw["estimates"]:
        end = date.fromisoformat(row["date"])
        if end < fetched_at.date():
            continue
        horizon = row["horizon"].lower()
        values = dict(
            fiscal_end=end,
            eps_avg=number(row.get("eps_estimate_average")),
            eps_count=number(row.get("eps_estimate_analyst_count"), count=True),
            revenue_avg=number(row.get("revenue_estimate_average")),
        )
        if "fiscal year" in horizon:
            annual.append(values)
        elif "fiscal quarter" in horizon:
            quarterly.append(values)
        else:
            raise ValueError("unknown estimate horizon")
    result = []
    for prefix, rows in (("FY", annual), ("Q", quarterly)):
        rows.sort(key=lambda r: r["fiscal_end"])
        if len({r["fiscal_end"] for r in rows}) != len(rows):
            raise ValueError("duplicate estimate period")
        result.extend({**r, "horizon": prefix + str(i)} for i, r in enumerate(rows, 1))
    return result


def rotation(tickers, latest):
    ancient = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(set(tickers), key=lambda t: (latest.get(t, ancient), t))


def collect(*, clock, repository, tickers, fetch, pause):
    requested = successful = 0
    degraded = False
    reason = None
    for ticker in rotation(tickers, repository.latest()):
        request_id = repository.reserve(ticker, clock.now_utc())
        if request_id is None:
            continue
        requested += 1
        try:
            raw = fetch(ticker)
        except Exception as exc:
            raw = {"transport_error_type": type(exc).__name__}
            status, rows = "error", []
        else:
            code = 200
            if isinstance(raw, Response):
                raw, code = raw.raw, raw.status_code
            if isinstance(raw, dict) and ("Note" in raw or "Information" in raw):
                status, rows = "throttled", []
            elif code != 200 or not isinstance(raw, dict):
                status, rows = "error", []
            else:
                try:
                    rows = parse_estimates(ticker, raw, clock.now_utc())
                    status = "ok" if rows else "empty"
                except (ValueError, TypeError, KeyError, OverflowError):
                    status, rows = "error", []
        repository.finish(request_id, ticker, clock.now_utc(), raw, rows, status)
        successful += status == "ok"
        degraded |= status != "ok"
        if status == "throttled":
            reason = "provider quota message; stopped for the UTC day"
            break
        if requested >= DAILY_LIMIT:
            break
        pause()
    return {
        "status": "degraded" if degraded else "ok",
        "processed_count": successful,
        "request_count": requested,
        "note": reason,
    }


class Repository:
    def __init__(self, connection):
        self.connection = connection

    def latest(self):
        return {
            r["ticker"]: r["latest"]
            for r in self.connection.execute(
                "SELECT ticker,max(fetched_at) AS latest FROM valuation_v1.consensus_snapshots "
                "WHERE kind='response' AND status='ok' GROUP BY ticker"
            ).fetchall()
        }

    def available(self, now):
        start = datetime.combine(now.date(), time(), timezone.utc)
        rows = self.connection.execute(
            "SELECT request_id,kind,status,fetched_at FROM valuation_v1.consensus_snapshots "
            "WHERE fetched_at>=%s AND kind IN ('request','response')",
            (now - timedelta(days=1),),
        ).fetchall()
        responses = {r["request_id"] for r in rows if r["kind"] == "response"}
        return (
            not any(r["kind"] == "request" and r["request_id"] not in responses for r in rows)
            and sum(r["kind"] == "request" for r in rows) < DAILY_LIMIT
            and not any(r["status"] == "throttled" and r["fetched_at"] >= start for r in rows)
        )

    def reserve(self, ticker, now):
        """Commit before HTTP; failed/interrupted attempts consume the quota too."""
        start = datetime.combine(now.date(), time(), timezone.utc)
        with self.connection.transaction():
            self.connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('A020:alpha:quota',0))")
            rows = self.connection.execute(
                "SELECT request_id,kind,status,ticker,fetched_at FROM valuation_v1.consensus_snapshots "
                "WHERE fetched_at>=%s AND kind IN ('request','response')",
                (now - timedelta(days=1),),
            ).fetchall()
            requests = [r for r in rows if r["kind"] == "request"]
            responses = {r["request_id"] for r in rows if r["kind"] == "response"}
            if any(r["request_id"] not in responses for r in requests):
                return None  # Unknown in-flight outcome: fail closed across restarts.
            if len(requests) >= DAILY_LIMIT:
                return None
            today = [r for r in rows if r["fetched_at"] >= start]
            if any(r["status"] == "throttled" for r in today):
                return None
            if any(r["kind"] == "request" and r["ticker"] == ticker for r in today):
                return None
            request_id = str(uuid4())
            self.connection.execute(
                "INSERT INTO valuation_v1.consensus_snapshots "
                "(id,request_id,kind,ticker,fetched_at,status,raw) VALUES (%s,%s,'request',%s,%s,'reserved','{}')",
                (request_id, request_id, ticker, now),
            )
            return request_id

    def finish(self, request_id, ticker, now, raw, rows, status):
        with self.connection.transaction():
            self.connection.execute(
                "INSERT INTO valuation_v1.consensus_snapshots "
                "(id,request_id,kind,ticker,fetched_at,status,raw) VALUES (%s,%s,'response',%s,%s,%s,%s)",
                (str(uuid4()), request_id, ticker, now, status, Jsonb(raw)),
            )
            for row in rows:
                self.connection.execute(
                    "INSERT INTO valuation_v1.consensus_snapshots "
                    "(id,request_id,kind,ticker,fetched_at,status,fiscal_end,horizon,"
                    "eps_avg,eps_count,revenue_avg,raw) "
                    "VALUES (%s,%s,'estimate',%s,%s,'ok',%s,%s,%s,%s,%s,%s)",
                    (
                        str(uuid4()),
                        request_id,
                        ticker,
                        now,
                        row["fiscal_end"],
                        row["horizon"],
                        row["eps_avg"],
                        row["eps_count"],
                        row["revenue_avg"],
                        Jsonb(raw),
                    ),
                )

    def pit(self, ticker, cutoff):
        if cutoff.tzinfo is None or cutoff.utcoffset() is None:
            raise ValueError("PIT cutoff must include timezone")
        snapshot = self.connection.execute(
            "SELECT request_id,fetched_at,status,raw FROM valuation_v1.consensus_snapshots "
            "WHERE ticker=%s AND kind='response' AND fetched_at<=%s ORDER BY fetched_at DESC,id DESC LIMIT 1",
            (ticker, cutoff),
        ).fetchone()
        if snapshot is None:
            return None
        rows = self.connection.execute(
            "SELECT fiscal_end,horizon,eps_avg,eps_count,revenue_avg FROM valuation_v1.consensus_snapshots "
            "WHERE request_id=%s AND kind='estimate' ORDER BY horizon,fiscal_end",
            (snapshot["request_id"],),
        ).fetchall()
        return {**snapshot, "estimates": rows}
