"""Restartable SEC original collection and evidence-bound candidate drafting."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from inves_cog.perception.graph.drafting import DraftService
from inves_cog.perception.graph.seeds import initial_baskets, monitored_seed
from inves_cog.perception.graph.texts import extract_sections


class GraphService:
    def __init__(self, *, repository, sec, llm, clock, universe, connection_factory=None):
        self.repo, self.sec, self.llm, self.clock, self.universe = repository, sec, llm, clock, universe
        self.connection_factory = connection_factory

    def seed_config(self):
        baskets = initial_baskets(self.universe)
        names = yaml.safe_load((Path(__file__).resolve().parents[4] / "config/news_entities.yaml").read_text())[
            "companies"
        ]
        for row in self.universe:
            company = names[row["ticker"]]
            self.repo.put_entity(
                {
                    "entity_id": "ticker:" + row["ticker"],
                    "kind": "company",
                    "name": company["name"],
                    "aliases": company["aliases"],
                    "ticker": row["ticker"],
                }
            )
        for row in baskets:
            self.repo.put_basket(row)
        for row in monitored_seed():
            entity = {
                **row,
                "kind": row.get("kind", "private_company"),
                "app_store_ids": row.get("app_store_ids", row.get("app_ids", [])),
                "trend_keywords": row.get("trend_keywords", row.get("trends_keywords", [])),
                "official_urls": row.get("official_urls", row.get("urls", [])),
            }
            self.repo.put_entity(entity)
            channels = [
                name
                for name, key in [("app", "app_store_ids"), ("trend", "trend_keywords"), ("site", "official_urls")]
                if entity[key]
            ]
            self.repo.connection.execute(
                "INSERT INTO graph.monitored_entities (entity_id,reason,channels) "
                "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                (row["entity_id"], "seed", channels),
            )
        return {"processed_count": len(baskets), "basket_count": len(baskets)}

    def collect_sources(self, ticker):
        filing = self.repo.annual_filing(ticker)
        if filing is None:
            return []
        cached = self.repo.sources(ticker, filing["accession"])
        if cached:
            return cached
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(filing['cik'])}/"
            f"{filing['accession'].replace('-', '')}/{filing['primary_document']}"
        )
        raw = self.sec.get(url)
        result = extract_sections(raw, filing=filing, clock=self.clock, source_url=url)
        for row in result:
            self.repo.save_source(row)
        return result

    def draft_ticker(self, ticker):
        try:
            sources = self.collect_sources(ticker)
            if not sources:
                return {
                    "ticker": ticker,
                    "status": "degraded",
                    "reason": "annual_source_unavailable",
                    "relations": 0,
                    "exposures": 0,
                }
            existing = self.repo.connection.execute(
                "SELECT count(*) AS n FROM graph.relations WHERE evidence->>'source_ticker'=%s "
                "AND evidence->'citation'->>'accession'=%s",
                (ticker, sources[0]["accession"]),
            ).fetchone()["n"]
            if existing >= 3:
                return {"ticker": ticker, "status": "ok", "relations": existing, "exposures": 0, "reused": True}
            # Full originals remain in source_texts; bounded excerpts retain exact original offsets.
            chosen = sorted(
                [r for r in sources if r["section"].startswith("item:")]
                or [r for r in sources if r["section"] not in {"full_filing", "canonical_full"}]
                or sources,
                key=lambda r: ("note" in r["section"], r["section"]),
            )[:6]
            payload = []
            for row in chosen:
                payload.append(
                    {
                        "ticker": ticker,
                        "accession": row["accession"],
                        "section": row["section"],
                        "text": row["text"][:12000],
                        "char_start": row["char_start"],
                    }
                )
            draft = DraftService(llm=self.llm, clock=self.clock).draft(payload)
            baskets = [b["basket_id"] for b in self.repo.baskets() if any(m["ticker"] == ticker for m in b["members"])]
            for row in draft["relations"] + draft["exposures"]:
                self.repo.put_relation(row, ticker=ticker, baskets=baskets)
            return {
                "ticker": ticker,
                "status": "ok",
                "relations": len(draft["relations"]),
                "exposures": len(draft["exposures"]),
            }
        except Exception as exc:
            return {
                "ticker": ticker,
                "status": "degraded",
                "reason": type(exc).__name__ + ": " + str(exc),
                "relations": 0,
                "exposures": 0,
            }

    def _draft_on_own_connection(self, ticker):
        with self.connection_factory() as connection:
            worker = type(self)(
                repository=type(self.repo)(connection),
                sec=self.sec,
                llm=self.llm,
                clock=self.clock,
                universe=self.universe,
            )
            return worker.draft_ticker(ticker)

    def draft_all(self, tickers=None, *, workers=3):
        selected = tickers or [row["ticker"] for row in self.universe]
        if self.connection_factory is None or workers <= 1 or len(selected) <= 1:
            rows = [self.draft_ticker(ticker) for ticker in selected]
        else:
            with ThreadPoolExecutor(max_workers=min(workers, len(selected))) as executor:
                rows = list(executor.map(self._draft_on_own_connection, selected))
        return {
            "processed_count": sum(row["relations"] + row["exposures"] for row in rows),
            "coverage": rows,
            "status": "degraded" if any(row["status"] != "ok" or row["relations"] < 3 for row in rows) else "ok",
        }

    def draft_structured(self):
        from inves_cog.ingest.fundamentals.fx import FXBook
        from inves_cog.perception.graph.segments import draft_segments
        from inves_cog.perception.graph.source_exposures import quarterly_ttm_source, single_business_hdd

        as_of = self.clock.today_trade_date()
        stx = single_business_hdd(self.repo.financial_state("STX", as_of=as_of), as_of=as_of)
        skhy = quarterly_ttm_source(
            self.repo.interim_rows("SKHY", as_of=as_of), as_of=as_of, fx=FXBook(self.repo.fx_rates())
        )
        sources = [row for row in (stx, skhy["source"]) if row is not None]
        drafts = draft_segments(self.llm, sources, clock=self.clock) if sources else []
        for row in drafts:
            ticker = row["from_entity"]
            baskets = [b["basket_id"] for b in self.repo.baskets() if any(m["ticker"] == ticker for m in b["members"])]
            self.repo.put_relation(row, ticker=ticker, baskets=baskets)
        return {
            "processed_count": len(drafts),
            "sources": sources,
            "drafts": drafts,
            "SKHY": skhy,
            "status": "degraded" if skhy["status"] != "ok" or len(drafts) != len(sources) else "ok",
        }
