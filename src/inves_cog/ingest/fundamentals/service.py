"""Injected M1 clients, PIT state builds and daily financial profiles."""

from copy import deepcopy
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from inves_cog.ingest.fundamentals.consensus import ConsensusStore, derive_consensus
from inves_cog.ingest.fundamentals.extractors import day, extract_state
from inves_cog.ingest.fundamentals.fx import FXGap
from inves_cog.ingest.fundamentals.health import health_row
from inves_cog.ingest.fundamentals.mapping import MappingQueue
from inves_cog.ingest.fundamentals.profile import ProfileBook
from inves_cog.ingest.fundamentals.providers import fiscal_years
from inves_cog.ingest.fundamentals.segments import PARSE_CONTRACT, apply_recast
from inves_cog.ingest.fundamentals.state import StateStore

RELEVANT = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "NetIncomeLoss",
    "EarningsPerShareDiluted",
    "NetCashProvidedByUsedInOperatingActivities",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "GrossProfit",
)


class MemoryRepository(StateStore):
    """Deterministic own-table substitute; never creates a shared client/table."""

    def __init__(self):
        super().__init__()
        self.shared_filings = {}
        self.health = {}
        self.profiles = {}
        self.segments = []
        self.mappings = {}
        self.snapshots = ConsensusStore()
        self.derived = {}
        self.guidance = {}
        self.missing_bars = set()

    def put_state(self, state):
        self.put(state)

    def read_shared_filings(self, ticker):
        return self.shared_filings.get(ticker, [])

    def bars_available(self, ticker, as_of):
        return ticker not in self.missing_bars

    def put_health(self, row):
        self.health[row["ticker"]] = row

    def health_rows(self):
        return self.health

    def put_profile(self, row):
        self.profiles[row["ticker"]] = row

    def profile_rows(self):
        return list(self.profiles.values())

    def put_snapshot(self, row):
        self.snapshots.put(row)

    def snapshot_rows(self, ticker):
        return [r for r in self.snapshots.rows.values() if r["ticker"] == ticker]

    def put_derived(self, row):
        self.derived[(row["ticker"], row["as_of"])] = row

    def put_segments(self, rows):
        keys = {(r["ticker"], r["accession"], r.get("period_end"), r.get("axis"), r.get("segment_raw")) for r in rows}
        self.segments = [
            r
            for r in self.segments
            if (r["ticker"], r["accession"], r.get("period_end"), r.get("axis"), r.get("segment_raw")) not in keys
        ] + deepcopy(rows)

    def replace_segments(self, ticker, accession, rows):
        self.segments = [r for r in self.segments if (r["ticker"], r["accession"]) != (ticker, accession)]
        self.put_segments(rows)

    def segment_rows(self, ticker):
        return [r for r in self.segments if r["ticker"] == ticker]

    def mapping_rows(self):
        return list(self.mappings.values())

    def put_mapping(self, row):
        self.mappings[row["id"]] = deepcopy(row)

    def graph_nodes(self):
        return []

    def guidance_rows(self, ticker, as_of):
        return self.guidance.get(ticker, [])

    def latest_earnings(self, ticker, as_of):
        return None


class FinancialService:
    def __init__(
        self, *, clock, repository, sec, llm, universe, ciks, consensus_provider=None, fx=None, instance_loader=None
    ):
        self.clock, self.repo, self.sec, self.llm = clock, repository, sec, llm
        self.universe, self.ciks, self.provider, self.fx, self.instance_loader = (
            universe,
            ciks,
            consensus_provider,
            fx,
            instance_loader,
        )
        self.profiles = ProfileBook(clock=clock, previous=repository.profile_rows())
        self.queue = MappingQueue(
            llm=llm,
            clock=clock,
            sectors={r["ticker"]: r["sector"] for r in universe},
            rows=repository.mapping_rows(),
            persist=repository.put_mapping,
        )

    @property
    def as_of(self):
        return self.clock.now_utc().astimezone(ZoneInfo("Asia/Shanghai")).date()

    def _budget(self):
        # The pure offline service also works before M1 is merged. Production
        # runs supply M1's budget through the caller; no second client is built.
        try:
            from inves_cog.ingest.deadline import check
        except ImportError:
            return
        check()

    def _checked_budget(self, processed):
        try:
            self._budget()
        except Exception as exc:
            exc.processed_count = processed
            raise

    def collect_financials(self):
        failures = []
        processed = 0
        for entity in self.universe:
            self._checked_budget(processed)
            ticker = entity["ticker"]
            filings = self.repo.read_shared_filings(ticker)
            try:
                cik = self.ciks.get(ticker)
                if not cik:
                    raise ValueError("SEC CIK missing for " + ticker)
                data = self.sec.companyfacts(cik)
                sic = data.get("sic", entity.get("sic"))
                foreign = entity.get("foreign", False)
                relevant = [
                    f
                    for f in filings
                    if str(f["form"]).removesuffix("/A") in {"10-Q", "10-K", "20-F", "40-F", "6-K"}
                    and day(f["filing_date"]) <= self.as_of
                ]
                d9_facts = self.d9_facts(ticker, relevant)
                fixed_dates = sorted(
                    {day(f["filing_date"]) for f in relevant if day(f["filing_date"]) >= date(2015, 1, 1)}
                )
                if not fixed_dates:
                    raise ValueError("No M1 effective filings available for " + ticker)
                legacy_dates = {date(2025, 12, 31)}
                for tag in RELEVANT:
                    for rows in data.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {}).values():
                        for row in rows:
                            if (
                                row.get("filed")
                                and str(row.get("form", "")).startswith(("10-Q", "10-K", "20-F", "6-K"))
                                and date(2026, 1, 1) <= day(row["filed"]) <= self.as_of
                            ):
                                legacy_dates.add(day(row["filed"]))
                for extractor, dates in (("legacy", sorted(legacy_dates)), ("fixed", fixed_dates)):
                    for cutoff in dates:
                        self._budget()
                        parsed = None
                        latest = max(
                            (f for f in relevant if day(f["filing_date"]) <= cutoff),
                            key=lambda f: (day(f["filing_date"]), str(f.get("accepted_at") or ""), f["accession"]),
                            default=None,
                        )
                        accessions = {
                            r.get("accn")
                            for tax in data.get("facts", {}).values()
                            for node in tax.values()
                            for rows in node.get("units", {}).values()
                            for r in rows
                            if r.get("filed") and day(r["filed"]) <= cutoff
                        }
                        if (
                            extractor == "fixed"
                            and latest
                            and latest["accession"] not in accessions
                            and self.as_of >= day(latest["filing_date"]) + timedelta(days=3)
                            and self.instance_loader
                        ):
                            try:
                                parsed = self.instance_loader.facts(latest)
                            except Exception as exc:
                                failures.append(
                                    {
                                        "ticker": ticker,
                                        "instance": latest["accession"],
                                        "reason": type(exc).__name__ + ": " + str(exc),
                                    }
                                )
                        state = extract_state(
                            data,
                            ticker=ticker,
                            as_of=cutoff,
                            extractor=extractor,
                            sic=sic,
                            foreign=foreign,
                            filings=filings,
                            instance_facts=self.merge_d9(parsed, d9_facts) if extractor == "fixed" else parsed,
                            fx=self.fx,
                            available_as_of=self.as_of,
                        )
                        state.filed = cutoff
                        self.repo.put_state(state)
                current = self.repo.state_asof(ticker, self.as_of, "fixed")
                if current is None:
                    raise ValueError("No fixed state after extraction")
                codes = set(current.health_codes) - {"ok"}
                if current.period_end and (self.as_of - current.period_end).days > 180:
                    codes.add("stale_fundamentals")
                if not self.repo.bars_available(ticker, self.as_of):
                    codes.add("no_bar")
                segments = self.collect_segments(ticker, relevant)
                codes.update(code for row in segments for code in row.get("health_codes", []))
                display = deepcopy(current)
                display.health_codes = sorted(codes) or ["ok"]
                accepted = self.repo.latest_earnings(ticker, self.clock.now_utc())
                if accepted is None:
                    display.health_codes.append("earnings_event_missing")
                health = health_row(display, foreign=foreign, latest_8k_202=accepted)
                self.repo.put_health(health)
                snapshots = self.repo.snapshot_rows(ticker)
                derived = derive_consensus(snapshots, ticker=ticker, as_of=self.as_of) if snapshots else None
                profile = self.profiles.generate(
                    display,
                    segments=segments,
                    consensus=derived,
                    guidance=self.repo.guidance_rows(ticker, self.clock.now_utc()),
                )
                self.repo.put_profile(profile)
                processed += 1
            except Exception as exc:
                reason = type(exc).__name__ + ": " + str(exc)
                failures.append({"ticker": ticker, "reason": reason})
                existing = self.repo.state_asof(ticker, self.as_of, "fixed")
                if existing and not isinstance(exc, FXGap):
                    display = deepcopy(existing)
                    if display.period_end and (self.as_of - display.period_end).days > 180:
                        display.health_codes.append("stale_fundamentals")
                    if any(
                        day(f["filing_date"]) > display.filed
                        for f in filings
                        if str(f["form"]).startswith(("10-Q", "10-K"))
                    ):
                        display.health_codes.append("companyfacts_lag")
                    health = health_row(display, foreign=entity.get("foreign", False))
                    health["reason"] = "; ".join(filter(None, [health["reason"], reason]))
                    self.repo.put_health(health)
                else:
                    # FX errors stop the amount write. They are not disguised as
                    # a normal financial row full of NULL converted amounts.
                    self.repo.put_health(
                        {
                            "ticker": ticker,
                            "latest_period_end": existing.period_end if existing else None,
                            "latest_filed": existing.filed if existing else None,
                            "latest_8k_202": None,
                            "health_codes": ["core_field_missing"],
                            "can_score": False,
                            "can_trade": False,
                            "reason": reason,
                        }
                    )
                self.repo.put_profile(
                    {
                        "as_of": self.as_of,
                        "ticker": ticker,
                        "changes": [],
                        **{name: {"data": None, "reason": reason} for name in ("business", "financials", "consensus")},
                    }
                )
        return {
            "processed_count": processed,
            "status": "degraded" if failures else "ok",
            "failures": failures,
            "health_rows": len(self.repo.health_rows()),
            "note": str(len(failures)) + " issuer/source gaps",
        }

    def merge_d9(self, parsed, extra):
        from inves_cog.ingest.fundamentals.repairs import merge_facts

        return merge_facts(extra, parsed or {}) if extra else parsed

    def d9_facts(self, ticker, filings):
        from inves_cog.ingest.fundamentals.repairs import merge_facts, settings

        rules = settings().get("d9", {})
        extra = {}
        for cik in rules.get("predecessor_ciks", {}).get(ticker, []):
            evidence = self.sec.companyfacts(cik)
            for tags in evidence.get("facts", {}).values():
                for node in tags.values():
                    for rows in node.get("units", {}).values():
                        for row in rows:
                            row["origin"] = "predecessor_companyfacts:" + cik
                            row["d9_only"] = True
            extra = merge_facts(extra, evidence)
        if ticker in rules.get("dimensional_facts", {}) and self.instance_loader:
            financials = [f for f in filings if str(f["form"]).removesuffix("/A") in {"10-Q", "10-K"}]
            for filing in sorted(financials, key=lambda f: day(f["filing_date"]))[-10:]:
                self._budget()
                extra = merge_facts(extra, self.instance_loader.facts(dict(filing, ticker=ticker)))
        return extra

    def collect_segments(self, ticker, filings):
        existing = self.repo.segment_rows(ticker)
        if self.instance_loader is None:
            return (
                self.apply_mappings(ticker, existing)
                if existing
                else [
                    {
                        "ticker": ticker,
                        "axis": "evidence",
                        "health_codes": ["segment_missing"],
                        "reason": "XBRL instance not supplied",
                    }
                ]
            )
        latest = max(filings, key=lambda f: day(f["filing_date"]), default=None)
        if latest is None:
            return existing
        cached = [r for r in existing if r["accession"] == latest["accession"]]
        last = max((r["period_end"] for r in cached if r.get("period_end")), default=None)
        current_cached = [r for r in cached if r.get("period_end") == last] if last else cached
        if current_cached and all(
            r.get("evidence", {}).get("parse_contract") == PARSE_CONTRACT for r in current_cached
        ):
            last = max((r["period_end"] for r in cached if r.get("period_end")), default=None)
            current = self.apply_mappings(
                ticker, [r for r in cached if r.get("period_end") == last] if last else cached
            )
            self.repo.put_segments(current)
            return current
        try:
            rows = self.instance_loader.segments(latest, ticker=ticker, fx=self.fx)
        except FXGap:
            raise
        except Exception as exc:
            return [
                {
                    "ticker": ticker,
                    "axis": "evidence",
                    "health_codes": ["segment_missing"],
                    "reason": type(exc).__name__ + ": " + str(exc),
                }
            ]
        latest_end = max((r["period_end"] for r in rows if r.get("period_end")), default=None)
        current = [r for r in rows if r.get("period_end") == latest_end]
        comparative = [r for r in rows if r.get("period_end") != latest_end]
        prior = [r for r in existing if any(c.get("period_end") == r.get("period_end") for c in comparative)]
        current = apply_recast(current, prior, comparative=comparative)
        current = self.apply_mappings(ticker, current)
        self.repo.replace_segments(ticker, latest["accession"], current + comparative)
        return current

    def apply_mappings(self, ticker, rows):
        # Review may happen in a different process while this service stays alive.
        self.queue.rows.update({row["id"]: row for row in self.repo.mapping_rows()})
        result = deepcopy(rows)
        for row in result:
            if row.get("axis") != "business":
                continue
            row["segment_std"] = None
            try:
                mapping = self.queue.draft(ticker, row["segment_raw"], graph_nodes=self.repo.graph_nodes())
                row["segment_std"] = mapping["graph_node_ids"] if mapping["status"] == "已确认" else None
            except Exception as exc:
                row.setdefault("evidence", {})["mapping_gap"] = type(exc).__name__ + ": " + str(exc)
            codes = [code for code in row.get("health_codes", []) if code != "segment_unmapped"]
            if row["segment_std"] is None:
                codes.append("segment_unmapped")
            row["health_codes"] = codes
        return result

    def collect_consensus(self):
        if self.provider is None:
            raise RuntimeError("yfinance provider not configured")
        failures = []
        count = 0
        for entity in self.universe:
            self._checked_budget(count)
            ticker = entity["ticker"]
            annual = [
                r
                for r in self.repo.read_shared_filings(ticker)
                if str(r["form"]).removesuffix("/A") in {"10-K", "20-F", "40-F"}
                and day(r["filing_date"]) <= self.as_of
                and r.get("report_date")
            ]
            latest = max(annual, key=lambda r: day(r["filing_date"]), default=None)
            years = fiscal_years(day(latest["report_date"]) if latest else None)
            try:
                snapshot = self.provider.collect(ticker, fy_cy=years[0], fy_ny=years[1])
                self.repo.put_snapshot(snapshot)
                derived = derive_consensus(self.repo.snapshot_rows(ticker), ticker=ticker, as_of=self.as_of)
                self.repo.put_derived(derived)
                count += 1
                state = self.repo.state_asof(ticker, self.as_of, "fixed")
                if state:
                    self.repo.put_profile(
                        self.profiles.generate(
                            state,
                            segments=self.repo.segment_rows(ticker),
                            consensus=derived,
                            guidance=self.repo.guidance_rows(ticker, self.clock.now_utc()),
                        )
                    )
            except Exception as exc:
                failures.append({"ticker": ticker, "reason": type(exc).__name__ + ": " + str(exc)})
                derived = derive_consensus(self.repo.snapshot_rows(ticker), ticker=ticker, as_of=self.as_of)
                derived["window_status"]["source"] = "当日采集失败: " + str(exc)
                self.repo.put_derived(derived)
        now = self.clock.now_utc().astimezone(ZoneInfo("Asia/Shanghai"))
        late = (now.hour, now.minute) > (10, 30)
        return {
            "processed_count": count,
            "status": "degraded" if failures or late else "ok",
            "failures": failures,
            "note": "past 10:30 Beijing deadline" if late else str(len(failures)) + " source gaps",
            "deadline_met": not late,
        }
