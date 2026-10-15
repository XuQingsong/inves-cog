"""Restartable SEC original collection and evidence-bound candidate drafting."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from inves_cog.perception.graph.drafting import DraftService
from inves_cog.perception.graph.seeds import initial_baskets, monitored_seed
from inves_cog.perception.graph.texts import extract_sections


class GraphService:
    def __init__(self, *, repository, sec, llm, clock, universe):
        self.repo, self.sec, self.llm, self.clock, self.universe = repository, sec, llm, clock, universe

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
            chosen = sorted(sources, key=lambda r: ("note" in r["section"], r["section"]))[:6]
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

    def draft_all(self, tickers=None, *, workers=3):
        selected = tickers or [row["ticker"] for row in self.universe]
        with ThreadPoolExecutor(max_workers=workers) as executor:
            rows = list(executor.map(self.draft_ticker, selected))
        return {
            "processed_count": sum(row["relations"] + row["exposures"] for row in rows),
            "coverage": rows,
            "status": "degraded" if any(row["status"] != "ok" or row["relations"] < 3 for row in rows) else "ok",
        }
