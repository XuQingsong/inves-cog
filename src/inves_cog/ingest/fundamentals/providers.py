"""yfinance's approved estimates API mapped to the project snapshot contract."""

import json
import math
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

from inves_cog.ingest.fundamentals.consensus import FIELDS


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, str):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def fiscal_years(latest_annual_end):
    if latest_annual_end is None:
        return None, None
    if isinstance(latest_annual_end, str):
        latest_annual_end = date.fromisoformat(latest_annual_end)
    import calendar

    def following(n):
        year = latest_annual_end.year + n
        return date(
            year,
            latest_annual_end.month,
            min(latest_annual_end.day, calendar.monthrange(year, latest_annual_end.month)[1]),
        )

    return following(1), following(2)


def snapshot_from_tables(tables, *, ticker, clock, fy_cy, fy_ny):
    tables = clean(tables)
    row = {
        "as_of": clock.now_utc().astimezone(ZoneInfo("Asia/Shanghai")).date(),
        "ticker": ticker,
        "source": "yfinance",
        "captured_at": clock.now_utc(),
        **{key: None for key in FIELDS},
        "raw": tables,
    }
    row.update(fy_cy=fy_cy, fy_ny=fy_ny)
    earnings = tables.get("earnings_estimate", {})
    revenue = tables.get("revenue_estimate", {})
    revisions = tables.get("eps_revisions", {})
    for period, key in (("0q", "eps_cq"), ("+1q", "eps_nq"), ("0y", "eps_cy"), ("+1y", "eps_ny")):
        row[key] = earnings.get(period, {}).get("avg")
    for period, key in (("0y", "rev_cy"), ("+1y", "rev_ny")):
        row[key] = revenue.get(period, {}).get("avg")
    row.update(
        coverage=earnings.get("0y", {}).get("numberOfAnalysts"),
        eps_high_cy=earnings.get("0y", {}).get("high"),
        eps_low_cy=earnings.get("0y", {}).get("low"),
    )
    for dest, src in (
        ("up_7d", "upLast7days"),
        ("down_7d", "downLast7days"),
        ("up_30d", "upLast30days"),
        ("down_30d", "downLast30days"),
    ):
        row[dest] = revisions.get("0y", {}).get(src)
    targets = tables.get("analyst_price_targets", {}) or {}
    row.update(pt_mean=targets.get("mean"), pt_median=targets.get("median"))
    history = []
    for original in tables.get("earnings_history", []):
        history.append(
            {
                "quarter_date": str(original["quarter_date"])[:10],
                "eps_actual": original.get("epsActual", original.get("eps_actual")),
                "eps_est": original.get("epsEstimate", original.get("eps_est")),
                "surprise_pct": original["surprisePercent"] * 100
                if original.get("surprisePercent") is not None
                else original.get("surprise_pct"),
                "captured_at": clock.now_utc().isoformat(),
            }
        )
    row["raw"]["earnings_history"] = history
    return row


class YFinance:
    def __init__(self, *, clock, ticker_factory=None, http=None):
        self.clock, self.ticker_factory = clock, ticker_factory
        from inves_cog.ingest.http import HTTPClient, RateLimiter

        self.http = http or HTTPClient(retries=0)
        self.page_limiter = RateLimiter(1, 5)
        self.api_limited = False

    def collect(self, ticker, *, fy_cy, fy_ny):
        if self.ticker_factory is None:
            return self.collect_api_or_page(ticker, fy_cy=fy_cy, fy_ny=fy_ny)
        else:
            factory = self.ticker_factory
        client = factory(ticker)
        tables = {}
        for name in ("earnings_estimate", "revenue_estimate", "eps_revisions", "eps_trend"):
            frame = getattr(client, "get_" + name)()
            tables[name] = frame.to_dict(orient="index") if frame is not None else {}
        tables["analyst_price_targets"] = client.get_analyst_price_targets() or {}
        frame = client.get_earnings_history()
        tables["earnings_history"] = (
            [{"quarter_date": index.date(), **row.to_dict()} for index, row in frame.iterrows()]
            if frame is not None
            else []
        )
        if not tables["earnings_estimate"]:
            raise RuntimeError("yfinance returned no earnings estimates; snapshot not fabricated")
        return snapshot_from_tables(tables, ticker=ticker, clock=self.clock, fy_cy=fy_cy, fy_ny=fy_ny)

    def collect_api_or_page(self, ticker, *, fy_cy, fy_ny):
        from inves_cog.ingest.http import SourceError

        if not self.api_limited:
            try:
                data = self.http.get(
                    f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}",
                    params={
                        "modules": "earningsTrend,financialData,earningsHistory,"
                        "upgradeDowngradeHistory,recommendationTrend"
                    },
                )
                tables = tables_from_yahoo_json(data)
                return snapshot_from_tables(tables, ticker=ticker, clock=self.clock, fy_cy=fy_cy, fy_ny=fy_ny)
            except SourceError as exc:
                if exc.status_code not in {401, 403, 429}:
                    raise
                self.api_limited = True
        html = self.http.get(
            f"https://finance.yahoo.com/quote/{ticker}/analysis/",
            headers={"User-Agent": "Mozilla/5.0"},
            limiter=self.page_limiter,
        )
        tables = tables_from_yahoo_page(html)
        result = snapshot_from_tables(tables, ticker=ticker, clock=self.clock, fy_cy=fy_cy, fy_ny=fy_ny)
        result["source"] = "yahoo_page"
        return result


def tables_from_yahoo_json(data):
    def raw(value):
        if isinstance(value, dict):
            if "raw" in value:
                return value["raw"]
            return {k: raw(v) for k, v in value.items()}
        if isinstance(value, list):
            return [raw(v) for v in value]
        return value

    found = {}

    def walk(value):
        if isinstance(value, str) and value.lstrip().startswith(("{", "[")):
            try:
                walk(json.loads(value))
            except (ValueError, RecursionError):
                pass
        elif isinstance(value, dict):
            for key in (
                "earningsTrend",
                "financialData",
                "earningsHistory",
                "upgradeDowngradeHistory",
                "recommendationTrend",
            ):
                if isinstance(value.get(key), dict):
                    found[key] = raw(value[key])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    trends = found.get("earningsTrend", {}).get("trend", [])
    if not trends:
        raise ValueError("Yahoo response has no earningsTrend; snapshot not fabricated")
    tables = {name: {} for name in ("earnings_estimate", "revenue_estimate", "eps_revisions", "eps_trend")}
    for row in trends:
        period = row.get("period")
        if period not in {"0q", "+1q", "0y", "+1y"}:
            continue
        for target, key in [
            ("earnings_estimate", "earningsEstimate"),
            ("revenue_estimate", "revenueEstimate"),
            ("eps_revisions", "epsRevisions"),
            ("eps_trend", "epsTrend"),
        ]:
            tables[target][period] = row.get(key, {})
    financial = found.get("financialData", {})
    tables["analyst"] = {
        "targetLowPrice": financial.get("targetLowPrice"),
        "targetHighPrice": financial.get("targetHighPrice"),
        "targetMeanPrice": financial.get("targetMeanPrice"),
        "targetMedianPrice": financial.get("targetMedianPrice"),
        "numberOfAnalystOpinions": financial.get("numberOfAnalystOpinions"),
        "recommendationTrend": found.get("recommendationTrend", {}),
        "marketCap": financial.get("marketCap"),
        "forwardPE": financial.get("forwardPE"),
    }
    tables["upgrade_history"] = [
        r for r in found.get("upgradeDowngradeHistory", {}).get("history", []) if r.get("epochGradeDate")
    ]
    tables["analyst_price_targets"] = {
        "mean": financial.get("targetMeanPrice"),
        "median": financial.get("targetMedianPrice"),
    }
    tables["earnings_history"] = [
        {
            **r,
            "quarter_date": r.get("quarter", {}).get("fmt")
            if isinstance(r.get("quarter"), dict)
            else datetime.fromtimestamp(r["quarter"], timezone.utc).date().isoformat(),
        }
        for r in found.get("earningsHistory", {}).get("history", [])
        if r.get("quarter")
    ]
    return tables


def tables_from_yahoo_page(html):
    class Scripts(HTMLParser):
        def __init__(self):
            super().__init__()
            self.active = False
            self.data = []
            self.current = []

        def handle_starttag(self, tag, attrs):
            if tag == "script":
                self.active = True
                self.current = []

        def handle_data(self, data):
            if self.active:
                self.current.append(data)

        def handle_endtag(self, tag):
            if tag == "script" and self.active:
                self.data.append("".join(self.current))
                self.active = False

    parser = Scripts()
    parser.feed(html)
    for script in parser.data:
        try:
            data = json.loads(script)
        except ValueError:
            continue
        try:
            return tables_from_yahoo_json(data)
        except ValueError:
            continue
    raise ValueError("Yahoo analysis page has no embedded earningsTrend; snapshot not fabricated")
