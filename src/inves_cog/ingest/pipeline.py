"""Production M1 tasks using the same parsers exercised by the offline harness."""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.etree.ElementTree import ParseError

import yaml

from inves_cog.ingest.adapters import (
    Embedding,
    Trends,
    Websites,
    alpaca_splits,
    cboe_statistics,
    cik_mapping,
    frames_shares,
)
from inves_cog.ingest.deadline import check
from inves_cog.ingest.http import HTTPClient, RateLimiter, SourceError
from inves_cog.ingest.info import make_item
from inves_cog.ingest.jobs import HealthBook
from inves_cog.ingest.market import NY, MarketCollector, exchange, local_at, post_close, split_factors, trading_day
from inves_cog.ingest.providers import (
    alpha_calendar,
    apple_chart,
    finra_short_interest,
    sec_atom,
    sec_daily_index,
)
from inves_cog.ingest.repository import identity
from inves_cog.ingest.runtime import Runtime, complete_adv20
from inves_cog.ingest.sec import collect_submissions, earnings_event, earnings_fallback, parse_form4
from inves_cog.ingest.sec_progress import SECProgress
from inves_cog.ingest.signals import rank_jumps, trend_event
from inves_cog.ingest.sources import macro_items, parse_finra, website_change
from inves_cog.ingest.triage import NewsTriage
from inves_cog.ingest.universe import build_universe, daily_liquidity

ROOT = Path(__file__).resolve().parents[3]
# The free Alpaca subscription rejects SIP data newer than 15 minutes (HTTP 403).
SIP_DELAY = timedelta(minutes=16)


def prefill_end(clock, day):
    """Premarket cutoff: 08:00 ET, or the newest SIP minute the subscription may query."""
    first = local_at(day, 4)
    return max(first, min(local_at(day, 8), clock.now_utc() - SIP_DELAY))


def bar_run_mode(clock, day):
    observed_day = clock.now_utc().astimezone(NY).date()
    if day > observed_day:
        raise ValueError("Cannot collect future trading day")
    return "historical_backfill" if day < observed_day else "current_day"


def wide_bar_adjustments(alpaca, batch, first, last):
    """Verified split factors for one wide-universe batch. Unknown stays NULL."""
    rows = list(alpaca.daily_bars(batch, first, last))
    gap = None
    try:
        splits = alpaca_splits(alpaca, batch, first, last)
    except SourceError as exc:
        splits, gap = None, str(exc)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["ticker"]].append(row)
    counts = {"split": 0, "unity": 0, "null": 0}
    stamped = []
    for ticker, ticker_rows in grouped.items():
        ticker_rows.sort(key=lambda item: item["trade_date"])
        if splits is None:
            for row in ticker_rows:
                row["adj_factor"] = None
                counts["null"] += 1
        else:
            factors = split_factors([row["trade_date"] for row in ticker_rows], splits.get(ticker, []))
            bucket = "split" if splits.get(ticker) else "unity"
            for row, factor in zip(ticker_rows, factors, strict=True):
                row["adj_factor"] = factor
                counts[bucket] += 1
        stamped.extend(ticker_rows)
    return stamped, counts, gap


def select_membership(candidates, previous, adv, day, *, monthly):
    """K18: first observed close is a labelled baseline, never a backdated run."""
    if monthly or not previous:
        rows = build_universe(candidates, day)
        if not monthly:
            for row in rows:
                row["notes"].append("startup_baseline")
        return rows
    return daily_liquidity(previous, adv, day)


def rule_only_news(item, clock):
    result = dict(item)
    old = item.get("extraction_source", {})
    result["extraction_status"] = "ok"
    result["extraction_source"] = {
        **old,
        "news_triage": {
            "layer": "rules_only",
            "reason": "rules_only",
            "llm_full": False,
            "embedding_attempted": False,
            "marked_at": clock.now_utc().isoformat(),
        },
        "a023_previous_triage": old.get("news_triage"),
    }
    return result


class Pipeline:
    def __init__(
        self, *, clock, repository, values, llm, sec, alpaca=None, fred=None, embed=None, websites=None, trends=None
    ):
        self.clock, self.repo, self.values, self.llm, self.sec = clock, repository, values, llm, sec
        self.alpaca, self.fred = alpaca, fred
        self.embed = embed or Embedding(values, clock=clock)
        self.websites, self.trends = websites or Websites(), trends or Trends(clock=clock)
        self.universe = yaml.safe_load((ROOT / "config/universe.yaml").read_text())
        self.stocks = [row["ticker"] for row in self.universe["stocks"]]
        self.codes = self.stocks + self.universe["etfs"]
        fallback = yaml.safe_load((ROOT / "config/monitored_entities.yaml").read_text())["entities"]
        self.monitored = self.repo.monitored_entities(fallback)
        self.entities = self.repo.graph_entities(self.monitored)
        aliases = yaml.safe_load((ROOT / "config/news_entities.yaml").read_text())["companies"]
        for ticker in self.stocks:
            company = aliases[ticker]
            existing = next(
                (
                    e
                    for e in self.entities
                    if ticker in e.get("tickers", []) and e["name"].casefold() == company["name"].casefold()
                ),
                None,
            )
            if existing:
                existing["aliases"] = sorted(set(existing.get("aliases", [])) | set(company["aliases"]))
            else:
                self.entities.append({"entity_id": "ticker:" + ticker, "tickers": [ticker], **company})
        params = yaml.safe_load((ROOT / "config/params/p-2026.10/m1.yaml").read_text())["m1"]
        self.news_llm_enabled = params.get("news_llm_enabled", False)
        pool_ciks = set()
        try:
            mapping = cik_mapping(self.sec)
            relevant = set(self.stocks) | set(self.repo.holding_tickers())
            pool_ciks = {mapping[t] for t in relevant if t in mapping}
        except Exception:
            pool_ciks = set()
        self.triage = NewsTriage(
            llm=self.llm,
            pool_ciks=pool_ciks,
            embed=self.embed,
            entities=self.entities,
            monitored_ids={e["entity_id"] for e in self.monitored},
            pool_tickers=self.stocks,
            clock=self.clock,
            daily_budget=params["llm_daily_token_budget"],
            usage_today=lambda: self.repo.llm_usage(self.clock.now_utc()),
            cached_root=self.repo.enriched_root,
            workers=4,
        )
        self.day_override = None

    @property
    def day(self):
        return self.day_override or self.clock.today_trade_date()

    def require(self, value, source):
        if value is None:
            raise SourceError(source + " configuration missing: 等待 R5", confirmed_unavailable=True)
        return value

    def _pending_relevant_filings(self):
        """info_ids of pending filings whose issuer is in pool/holdings — kept
        pending so news_card still runs for them."""
        try:
            rows = self.repo.connection.execute(
                "SELECT info_id, headline, tickers, extraction_source FROM ingest.info_items"
                " WHERE extraction_status='pending' AND kind IN ('sec_8k','form4')"
            ).fetchall()
        except Exception:
            return set()
        keep = set()
        for row in rows:
            item = {
                "headline": row["headline"],
                "tickers": row["tickers"] or [],
                "entities": [],
                "extraction_source": row["extraction_source"] or {},
            }
            if self.triage.holding(item) or self.triage.tracked(item) or self.triage._filing_relevant(item):
                keep.add(row["info_id"])
        return keep

    def info(self, items):
        count = 0
        for item in items:
            check()
            if item["kind"] == "news" and not getattr(self, "news_llm_enabled", True):
                item = rule_only_news(item, self.clock)
            previous = self.repo.info_signature(item["info_id"])
            if previous != (item["headline"], item["body"]):
                # The durable pending row is the queue. Collection never waits
                # for dialogue/embedding, and restart resumes from this row.
                self.repo.put_info(item)
            else:
                self.repo.count_duplicate()
            count += 1
        return {"processed_count": count}

    def enrich_pending(self, limit=32):
        counts = Counter()
        try:
            converted = None
            if hasattr(self.repo, "finish_pending_rules_only"):
                converted = self.repo.finish_pending_rules_only(
                    max(limit, 512),
                    as_of=self.clock.now_utc(),
                    exclude_ids=self._pending_relevant_filings(),
                )
            counts["rules_only_structured"] = converted if isinstance(converted, int) else 0
            counts["processed_count"] += counts["rules_only_structured"]
            if not getattr(self, "news_llm_enabled", True):
                counts["rules_only"] = self.repo.finish_pending_news(max(limit, 512), as_of=self.clock.now_utc())
                counts["processed_count"] += counts["rules_only"]
                items = self.repo.pending_info(limit, as_of=self.clock.now_utc(), include_news=False)
            else:
                items = self.repo.pending_info(limit, as_of=self.clock.now_utc())
            for result in self.triage.process(items) if items else []:
                check()
                if self.repo.apply_enrichment(result):
                    counts["processed_count"] += 1
                    counts["tagging_failed"] += "entity_tagging_failed" in result["flags"]
                    counts["embedding_failed"] += "embedding_failed" in result["flags"]
                    counts["deferred"] += result["extraction_status"] == "pending"
        except Exception as exc:
            exc.processed_count = counts["processed_count"]
            raise
        counts.setdefault("processed_count", 0)
        report = dict(counts)
        report["status"] = (
            "degraded" if counts["tagging_failed"] or counts["embedding_failed"] or counts["deferred"] else "ok"
        )
        report["note"] = (
            f"tagging_failed={counts['tagging_failed']}; embedding_failed={counts['embedding_failed']}; "
            f"deferred={counts['deferred']}"
        )
        return report

    def enrich_on_demand(self, items):
        if not getattr(self, "news_llm_enabled", True):
            news = [rule_only_news(item, self.clock) for item in items if item["kind"] == "news"]
            other = [item for item in items if item["kind"] != "news"]
            results = news + (self.triage.process(other, on_demand=True) if other else [])
        else:
            results = self.triage.process(items, on_demand=True)
        for result in results:
            self.repo.apply_enrichment(result)
        return results

    def bars(self, *, prefill=False):
        mode = bar_run_mode(self.clock, self.day)
        if not trading_day(self.day):
            return {"processed_count": 0, "note": "XNYS closed"}
        alpaca = self.require(self.alpaca, "Alpaca")
        collector = MarketCollector(alpaca.http, clock=self.clock, headers=alpaca.headers)
        end = prefill_end(self.clock, self.day) if prefill else None
        result = collector.minute_bars(self.codes, self.day, end=end)
        for row in result.rows:
            self.repo.write("bars_minute", row, update=("open", "high", "low", "close", "volume", "session"))
        if prefill:
            return {
                "processed_count": len(result.rows),
                "missing_codes": result.missing_codes,
                "exhausted": result.exhausted,
                "status": result.status,
                "data_through": end.isoformat(),
            }
        first = self.repo.first_bar_date() or self.day - timedelta(days=60)
        daily = alpaca.daily_bars(self.codes, first, self.day)
        split_gap = None
        try:
            splits = alpaca_splits(alpaca, self.codes, first, self.day)
        except SourceError as exc:
            splits, split_gap = {}, str(exc)
        grouped = defaultdict(list)
        for row in daily:
            grouped[row["ticker"]].append(row)
        for ticker, rows in grouped.items():
            factors = split_factors([r["trade_date"] for r in rows], splits.get(ticker, []))
            for row, factor in zip(rows, factors, strict=True):
                check()
                row["adj_factor"] = factor if split_gap is None or row["trade_date"] == self.day else None
                if row["trade_date"] == self.day:
                    row["post_close"] = post_close(result.rows, self.day, ticker=ticker)
                else:
                    row["post_close"] = self.repo.post_close(ticker, row["trade_date"])
                self.repo.write(
                    "bars_daily", row, update=("open", "high", "low", "close", "volume", "post_close", "adj_factor")
                )
        actual = {row["ticker"] for row in daily if row["trade_date"] == self.day}
        unavailable = [ticker for ticker in self.codes if ticker not in actual]
        for ticker in unavailable:
            self.repo.set_cursor(
                "no_bar:" + ticker,
                {"day": self.day.isoformat(), "reason": "Alpaca SIP returned no daily bar"},
                self.clock.now_utc(),
            )
        available_coverage = [result.coverage[t] for t in actual if result.coverage[t] is not None]
        coverage_ok = (
            bool(available_coverage)
            and min(available_coverage) >= 0.95
            and sum(available_coverage) / len(available_coverage) >= 0.99
        )
        late = mode == "current_day" and self.clock.now_utc() > local_at(self.day, 20, 45)
        report = {
            "processed_count": len(result.rows) + len(daily),
            "daily_codes": len(actual),
            "requested_codes": len(self.codes),
            "unavailable_codes": unavailable,
            "coverage": result.coverage,
            "exhausted": result.exhausted,
            "completed_at": self.clock.now_utc().isoformat(),
            "run_mode": mode,
            "deadline_met": not late if mode == "current_day" else None,
            "status": "ok" if coverage_ok and not split_gap and not late else "degraded",
            "note": split_gap
            or ("minute coverage below threshold" if not coverage_ok else "past 20:45 ET deadline" if late else None),
        }
        self.repo.set_cursor("bars-report:" + self.day.isoformat(), report, self.clock.now_utc())
        return report

    def news(self):
        alpaca = self.require(self.alpaca, "Alpaca")
        previous = self.repo.get_cursor("news")
        first = (
            datetime.fromisoformat(previous["through"]) - timedelta(days=1)
            if previous
            else self.clock.now_utc() - timedelta(days=90)
        )
        count, before = 0, dict(self.repo.counts)
        for item in alpaca.news(first=first, last=self.clock.now_utc()):
            self.info([item])
            count += 1
            # Each durable insert moves the resumable bootstrap cursor.
            if item["published_at"]:
                self.repo.set_cursor("news", {"through": item["published_at"].isoformat()}, self.clock.now_utc())
        self.repo.set_cursor(
            "news", {"through": self.clock.now_utc().isoformat(), "bootstrap_complete": True}, self.clock.now_utc()
        )
        from inves_cog.ingest.service import check_news_gap

        latest = self.repo.latest_news_at()
        gap = check_news_gap(self.repo, self.clock)
        return {
            "processed_count": count,
            **{key: self.repo.counts[key] - before[key] for key in before},
            "source_success": gap["healthy"],
            "status": "ok" if gap["healthy"] else "degraded",
            "note": "latest_data_at=" + (latest.isoformat() if latest else "none"),
        }

    def wide(self):
        alpaca = self.require(self.alpaca, "Alpaca")
        assets = alpaca.assets()
        eligible = [
            a
            for a in assets
            if a.get("exchange", "").upper()
            in {"NYSE", "NASDAQ", "AMEX", "ARCA", "BATS", "CBOE", "NYSEAMERICAN", "NYSEARCA"}
        ]
        mapping, shares = cik_mapping(self.require(self.sec, "SEC")), frames_shares(self.sec, self.day)
        sessions = [
            d.date()
            for d in exchange(self.day.year).sessions_in_range(str(self.day - timedelta(days=50)), str(self.day))
        ][-20:]
        codes = [a["ticker"] for a in eligible]
        history = defaultdict(list)
        factors = {"split": 0, "unity": 0, "null": 0}
        gaps = []
        for start in range(0, len(codes), 200):
            check()
            batch = codes[start : start + 200]
            stamped, batch_counts, gap = wide_bar_adjustments(alpaca, batch, sessions[0], self.day)
            for key in factors:
                factors[key] += batch_counts[key]
            if gap:
                gaps.append(gap)
            for row in stamped:
                history[row["ticker"]].append(row)
                self.repo.write(
                    "bars_daily",
                    row,
                    update=("open", "high", "low", "close", "volume", "adj_factor"),
                )
        counts = Counter(mapping.get(a["ticker"]) for a in eligible if mapping.get(a["ticker"]))
        candidates, adv = [], {}
        for asset in eligible:
            ticker, rows = asset["ticker"], history[asset["ticker"]]
            cik = mapping.get(ticker)
            latest = next((r["close"] for r in rows if r["trade_date"] == self.day), None)
            value = complete_adv20(rows, sessions)
            adv[ticker] = value
            candidates.append(
                {
                    **asset,
                    "cik": cik,
                    "shares": shares.get(cik, {}).get("shares"),
                    "close": latest,
                    "history": rows if value is not None else [],
                    "multi_class": counts[cik] > 1,
                }
            )
        previous = self.repo.latest_wide()
        first_session = exchange(self.day.year).sessions_in_range(f"{self.day:%Y-%m}-01", str(self.day))[0].date()
        monthly = self.day == first_session
        rows = select_membership(candidates, previous, adv, self.day, monthly=monthly)
        for row in rows:
            self.repo.write("wide_universe", row, update=("mktcap", "adv20", "included", "exclude_reason", "notes"))
        report = {
            "processed_count": len(rows),
            "included": sum(r["included"] for r in rows),
            "exclusions": dict(Counter(r["exclude_reason"] for r in rows if not r["included"])),
            "monthly": monthly,
            "startup_baseline": not monthly and not previous,
            "status": "degraded" if gaps else "ok",
            "note": "; ".join(gaps) if gaps else None,
            "adj_factor_split": factors["split"],
            "adj_factor_unity": factors["unity"],
            "adj_factor_null": factors["null"],
        }
        self.repo.set_cursor("wide-report:" + self.day.isoformat(), report, self.clock.now_utc())
        return report

    def submissions(self):
        sec = self.require(self.sec, "SEC")
        progress = SECProgress(self.repo, self.clock, self.day, self.stocks)
        mapping = cik_mapping(sec)
        count = 0
        for ticker in progress.pending:
            check()
            progress.start(ticker)
            try:
                cik = mapping.get(ticker)
                if not cik:
                    raise SourceError("No SEC CIK for " + ticker)
                rows = collect_submissions(
                    sec,
                    cik=cik,
                    ticker=ticker,
                    clock=self.clock,
                    existing=self.repo.filings(ticker),
                    persist=lambda r: self.repo.write("sec_filings", r, update=tuple(k for k in r if k != "accession")),
                    verify_limit=20,
                )
                count += len(rows)
                gaps = self._submission_rows(sec, ticker, rows)
            except (SourceError, ValueError, ParseError) as exc:
                progress.fail(ticker, exc)
                # Persist the issuer cursor before propagating an expired slot.
                check()
                self._submission_fallback(ticker)
                continue
            progress.complete(ticker, gaps)
        return progress.result(count)

    def _submission_fallback(self, ticker):
        key = self.values.get("ALPHA_VANTAGE_API_KEY")
        if not key:
            return
        try:
            calendar = alpha_calendar(HTTPClient(), key=key)
        except SourceError:
            return
        for event in calendar:
            if event.get("symbol") == ticker and event["reportDate"] >= self.day.isoformat():
                row = earnings_fallback(ticker, event, clock=self.clock)
                row["event_id"] = "fallback:" + ticker + ":" + event["reportDate"]
                self.repo.write("earnings_events", row)

    def _submission_rows(self, sec, ticker, rows):
        gaps = []
        closes = self.repo.closes(ticker)
        for row in rows:
            check()
            if row["form"] == "8-K" and "2.02" in row["items"]:
                if row["accepted_at"] is None:
                    gaps.append(row["accession"])
                    continue
                event = earnings_event(row, closes=closes, clock=self.clock)
                event["event_id"] = "SEC:" + row["accession"]
                if event["ref_close"] is None:
                    event["flags"].append("ref_close_missing")
                future_periods = [
                    f
                    for f in rows
                    if f["form"] in {"10-Q", "10-K"}
                    and f["report_date"]
                    and row["filing_date"] <= f["filing_date"] <= row["filing_date"] + timedelta(days=60)
                ]
                if future_periods:
                    event["fiscal_period"] = min(future_periods, key=lambda f: f["filing_date"])[
                        "report_date"
                    ].isoformat()
                self.repo.write("earnings_events", event, update=("ref_close", "fiscal_period", "flags"))
                self.repo.supersede_fallback(ticker, row["accepted_at"].astimezone(NY).date(), self.clock.now_utc())
                if not self.repo.info_signature("sec_8k:SEC:" + row["accession"]):
                    body = sec.get(self.document_url(row))
                    self.info(
                        [
                            make_item(
                                "sec_8k",
                                "SEC",
                                row["accession"],
                                headline=ticker + " 8-K",
                                body=body,
                                url=self.document_url(row),
                                tickers=[ticker],
                                published_at=row["accepted_at"],
                                clock=self.clock,
                                payload=row["raw"],
                            )
                        ]
                    )
            if (
                row["form"] in {"4", "4/A"}
                and row["accepted_at"] is not None
                and not self.repo.get_cursor("form4:" + row["accession"])
            ):
                document = sec.get(self.document_url(row, raw_xml=True))
                events = parse_form4(document, accession=row["accession"], filed_at=row["accepted_at"])
                for event in events:
                    event.update(
                        event_id=row["accession"] + ":" + str(event["transaction_index"]),
                        source="SEC",
                        raw={"xml": document},
                    )
                    self.repo.write("form4_events", event)
                    self.info(
                        [
                            make_item(
                                "form4",
                                "SEC",
                                event["event_id"],
                                headline=ticker + " Form 4",
                                body=document,
                                tickers=[ticker],
                                published_at=row["accepted_at"],
                                clock=self.clock,
                                payload=event,
                            )
                        ]
                    )
                self.repo.set_cursor("form4:" + row["accession"], {"parsed": True}, self.clock.now_utc())
        return gaps

    @staticmethod
    def document_url(row, raw_xml=False):
        document = row["primary_document"]
        if not document or ".." in document or document.startswith("/"):
            raise SourceError("Missing or unsafe SEC primary document")
        if raw_xml:
            document = document.rsplit("/", 1)[-1]
        return (
            f"https://www.sec.gov/Archives/edgar/data/{int(row['cik'])}/{row['accession'].replace('-', '')}/{document}"
        )

    def atom(self):
        return self.info(sec_atom(self.require(self.sec, "SEC"), clock=self.clock))

    def index(self):
        previous = self.day - timedelta(days=1)
        while previous.weekday() >= 5:
            previous -= timedelta(days=1)
        items = sec_daily_index(self.require(self.sec, "SEC"), previous, clock=self.clock)
        for item in items:
            item["body"] = self.sec.get(item["url"])
        return self.info(items)

    def apps(self, chart):
        rows = apple_chart(HTTPClient(), chart=chart, clock=self.clock)
        if len(rows) < 100:
            raise SourceError("Apple chart incomplete", confirmed_unavailable=True)
        previous = self.repo.latest_app_ranks(chart)
        for row in rows:
            self.repo.write("app_rank_snapshots", row)
        monitored = {str(app) for entity in self.monitored for app in entity.get("app_ids", [])}
        current = {r["app_id"]: r["rank"] for r in rows if r["app_id"] in monitored}
        events = rank_jumps(previous, current, chart=chart, clock=self.clock)
        self.info(events)
        return {"processed_count": len(rows), "events": len(events)}

    def trends_task(self):
        count, short, failures = 0, [], []
        for entity in self.monitored:
            for keyword in entity.get("trends_keywords", []):
                try:
                    check()
                    payload = self.trends.get(keyword)
                    today = self.clock.now_utc().astimezone(NY).date()
                    valid = [r for r in payload["history"] if today - timedelta(days=90) <= r["date"] < today]
                    if len(valid) < 60:
                        short.append(keyword + ": trend_window_short")
                    event = trend_event(keyword, payload["history"], payload["today"], clock=self.clock)
                    if event:
                        self.info([event])
                    self.repo.set_cursor("trends:" + keyword, payload, self.clock.now_utc())
                    count += 1
                except Exception as exc:
                    failures.append(
                        {
                            "keyword": keyword,
                            "type": type(exc).__name__,
                            "message": str(exc),
                            "confirmed_unavailable": getattr(exc, "confirmed_unavailable", False),
                        }
                    )
        notes = short + [f"{f['keyword']}: {f['type']}: {f['message']}" for f in failures]
        return {
            "processed_count": count,
            "failures": failures,
            "source_success": count > 0,
            "confirmed_unavailable": count == 0
            and bool(failures)
            and all(f["confirmed_unavailable"] for f in failures),
            "note": "; ".join(notes),
            "status": "degraded" if short or failures else "ok",
        }

    def websites_task(self):
        count, failures = 0, []
        health = HealthBook(clock=self.clock, rows=self.repo.health_rows(), persist=self.repo.write_health)
        for entity in self.monitored:
            for url in entity.get("urls", []):
                source = "EntitySites:" + url
                try:
                    check()
                    current = self.websites.get(url)
                    previous = self.repo.latest_website(url)
                    event = website_change(url, previous or "", current, clock=self.clock)
                    if event:
                        if previous is None:
                            event["flags"].append("site_baseline")
                        self.info([event])
                    self.repo.write(
                        "website_snapshots", {"url": url, "captured_at": self.clock.now_utc(), "body": current}
                    )
                    count += 1
                    health.record(source, success=True, count=1)
                except Exception as exc:
                    note = f"{type(exc).__name__}: {exc}"
                    failures.append(
                        {
                            "url": url,
                            "error": note,
                            "confirmed_unavailable": getattr(exc, "confirmed_unavailable", False),
                        }
                    )
                    health.record(
                        source,
                        success=False,
                        note=note,
                        degraded=True,
                        confirmed_unavailable=getattr(exc, "confirmed_unavailable", False),
                    )
        return {
            "processed_count": count,
            "failures": failures,
            "source_success": count > 0,
            "confirmed_unavailable": count == 0
            and bool(failures)
            and all(f["confirmed_unavailable"] for f in failures),
            "status": "degraded" if failures else "ok",
            "note": "; ".join(f"{f['url']}: {f['error']}" for f in failures),
        }

    def rss_task(self, source):
        from inves_cog.ingest.rss import PUBLIC_FEEDS, parse_rss

        rows = parse_rss(HTTPClient().get(PUBLIC_FEEDS[source]), source=source, clock=self.clock)
        return self.info(rows)

    def fred_task(self):
        fred, count = self.require(self.fred, "FRED"), 0
        for series in yaml.safe_load((ROOT / "config/params/p-2026.10/m1.yaml").read_text())["m1"]["fred_series"]:
            try:
                observations = fred.collect(series)
            except SourceError as exc:
                raise SourceError(f"FRED {series}: {exc}", status_code=exc.status_code) from exc
            for row in observations:
                check()
                self.repo.write("macro_observations", row)
                self.info(macro_items([row], clock=self.clock))
                count += 1
        return {"processed_count": count}

    def finra(self):
        raw = finra_short_interest(HTTPClient(limiter=RateLimiter(60, 60)), tickers=self.stocks)
        shares = frames_shares(self.require(self.sec, "SEC"), self.day)
        mapping = cik_mapping(self.sec)
        rows = parse_finra(
            raw,
            allowed_tickers=set(self.stocks),
            shares_by_ticker={t: shares.get(mapping.get(t), {}).get("shares") for t in self.stocks},
        )
        for row in rows:
            row.update(
                observation_id=identity(row),
                raw=next(
                    (
                        r
                        for r in raw
                        if r.get("symbolCode") == row["ticker"] and r.get("settlementDate") == row["settlement_date"]
                    ),
                    {},
                ),
            )
            self.repo.write("short_interest", row)
            published = (
                datetime.combine(date.fromisoformat(row["publish_date"]), datetime.min.time(), timezone.utc)
                if row["publish_date"]
                else None
            )
            item = make_item(
                "short_interest",
                "FINRA",
                row["observation_id"],
                headline=row["ticker"] + " short interest",
                body=str(row["short_interest"]),
                tickers=[row["ticker"]],
                clock=self.clock,
                published_at=published,
                payload=row,
            )
            if published:
                item["flags"].append("published_at_date_only")
            self.info([item])
        return {"processed_count": len(rows)}

    def cboe(self):
        rows = cboe_statistics(HTTPClient(), self.day)
        for row in rows:
            self.repo.write("options_stats", row)
            item = make_item(
                "options_stats",
                "CBOE",
                f"{self.day}:{row['category']}",
                headline="CBOE " + row["category"],
                body=str(row),
                published_at=datetime.combine(self.day, datetime.min.time(), timezone.utc),
                clock=self.clock,
                payload=row,
            )
            item["flags"].append("published_at_date_only")
            self.info([item])
        return {"processed_count": len(rows)}

    def runtime(self):
        from inves_cog.ingest.intraday import (
            collect_iex_intraday,
            collect_intraday,
            collect_wide,
            collect_yahoo_intraday,
        )
        from inves_cog.ingest.market_structure import collect_issuer_profiles, collect_market_inputs
        from inves_cog.ingest.resilience import collect_calendars, collect_vix
        from inves_cog.ingest.service import check_news_gap

        health = HealthBook(clock=self.clock, rows=self.repo.health_rows(), persist=self.repo.write_health)
        tasks = {
            "bars_full": ("Alpaca", self.bars),
            "bars_prefill": ("Alpaca", lambda: self.bars(prefill=True)),
            "wide_universe": ("AlpacaWide", self.wide),
            "news_full": ("AlpacaNews", self.news),
            "news_poll": ("AlpacaNews", self.news),
            "wide_snapshots": ("AlpacaWideSnapshots", lambda: collect_wide(self)),
            "iex_intraday": ("AlpacaIEX", lambda: collect_iex_intraday(self)),
            "intraday_snapshots": ("AlpacaIntraday", lambda: collect_intraday(self)),
            "yahoo_intraday": ("YahooIntraday", lambda: collect_yahoo_intraday(self)),
            "news_watchdog": ("Scheduler:news_watchdog", lambda: check_news_gap(self.repo, self.clock)),
            "vix_daily": ("VolatilitySources", lambda: collect_vix(self)),
            "earnings_calendar": ("EarningsCalendar", lambda: collect_calendars(self, "earnings")),
            "econ_calendar": ("EconomicCalendar", lambda: collect_calendars(self, "econ")),
            "news_prefill": ("AlpacaNews", self.news),
            "sec_submissions": ("SEC", self.submissions),
            "sec_index": ("SECDailyIndex", self.index),
            "sec_atom": ("SECAtom", self.atom),
            "app_free": ("AppStoreFree", lambda: self.apps("free")),
            "app_grossing": ("AppStoreGrossing", lambda: self.apps("grossing")),
            "trends": ("GoogleTrends", self.trends_task),
            "websites": ("EntitySites", self.websites_task),
            "fred": ("FRED", self.fred_task),
            "finra": ("FINRA", self.finra),
            "cboe": ("CBOE", self.cboe),
        }
        tasks.update(
            {
                "m6_market_inputs": ("MarketStructureInputs", lambda: collect_market_inputs(self)),
                "issuer_profiles": ("SECIssuerProfiles", lambda: collect_issuer_profiles(self)),
                "fed_news": ("FederalReserveNews", lambda: self.rss_task("FederalReserveNews")),
                "eia_press": ("EIANews", lambda: self.rss_task("EIANews")),
                "eia_energy": ("EIATodayInEnergy", lambda: self.rss_task("EIATodayInEnergy")),
            }
        )

        def guarded(operation):
            def execute():
                before = self.repo.processed
                try:
                    return operation()
                except Exception as exc:
                    exc.processed_count = self.repo.processed - before
                    raise

            return execute

        tasks = {name: (source, guarded(operation)) for name, (source, operation) in tasks.items()}
        return Runtime(
            snapshot_repo=self.repo,
            trade_date=lambda: self.day,
            clock=self.clock,
            health=health,
            persist_job=self.repo.write_job,
            persist_start=self.repo.write_job,
            tasks=tasks,
        )
