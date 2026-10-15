"""Graph-owned persistence, evidence retention and audited batch review."""

import hashlib
import json
import re
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from inves_cog.perception.graph.review import ReviewQueue


def entity_id(name):
    normalized = name.casefold().strip()
    if not normalized:
        raise ValueError("Entity name must be nonempty")
    slug = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    return slug or "entity_" + hashlib.sha256(normalized.encode()).hexdigest()[:24]


class Repository:
    def __init__(self, connection):
        self.connection = connection

    def put_entity(self, row):
        fields = "entity_id kind name aliases ticker app_store_ids trend_keywords official_urls".split()
        self.connection.execute(
            "INSERT INTO graph.entities ("
            + ",".join(fields)
            + ") VALUES ("
            + ",".join(["%s"] * len(fields))
            + ") ON CONFLICT (entity_id) DO NOTHING",
            [
                row.get(key, [])
                if key in {"aliases", "app_store_ids", "trend_keywords", "official_urls"}
                else row.get(key)
                for key in fields
            ],
        )

    def put_basket(self, row):
        self.connection.execute(
            "INSERT INTO graph.baskets (basket_id,level,name,benchmark,members,factor_basis) "
            "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (basket_id) DO NOTHING",
            (
                row["basket_id"],
                row["level"],
                row["name"],
                row["benchmark"],
                Jsonb(row["members"]),
                Jsonb(row["factor_basis"]),
            ),
        )

    def baskets(self):
        return self.connection.execute("SELECT * FROM graph.baskets ORDER BY level,basket_id").fetchall()

    def sources(self, ticker, accession):
        return self.connection.execute(
            "SELECT * FROM graph.source_texts WHERE ticker=%s AND accession=%s ORDER BY section,char_start",
            (ticker, accession),
        ).fetchall()

    def save_source(self, row):
        keys = "ticker accession section text char_start char_end fetched_at source_url source_sha256".split()
        self.connection.execute(
            "INSERT INTO graph.source_texts ("
            + ",".join(keys)
            + ") VALUES ("
            + ",".join(["%s"] * len(keys))
            + ") ON CONFLICT DO NOTHING",
            [row[k] for k in keys],
        )

    def annual_filing(self, ticker):
        return self.connection.execute(
            "SELECT * FROM ingest.sec_filings WHERE ticker=%s AND form IN ('10-K','20-F','40-F') "
            "ORDER BY filing_date DESC LIMIT 1",
            (ticker,),
        ).fetchone()

    def put_relation(self, row, *, ticker, baskets):
        for side in ("from_entity", "to_entity"):
            name = row[side]
            identifier = "ticker:" + name if name == ticker else entity_id(name)
            self.put_entity(
                {
                    "entity_id": identifier,
                    "kind": "company"
                    if name == ticker
                    else row.get(side + "_kind", "private_company")
                    if row.get(side + "_kind", "private_company")
                    in {"company", "private_company", "product", "app", "model", "workload", "segment", "theme"}
                    else "private_company",
                    "name": name,
                    "ticker": ticker if name == ticker else None,
                }
            )
            row[side] = identifier
        citation = row.get("citation")
        if citation is None and not row.get("structured_source"):
            raise ValueError("A prose citation or validated M2 source is required")
        evidence = {
            "citation": citation,
            "source_ticker": ticker,
            "structured_source": row.get("structured_source"),
            "flags": row.get("flags", []),
        }
        if row.get("exposure_usd") is not None and not row.get("structured_source"):
            metadata = self.connection.execute(
                "SELECT filing_date FROM ingest.sec_filings WHERE accession=%s LIMIT 1", (citation["accession"],)
            ).fetchone()
            if metadata:
                row["exposure_asof"] = metadata["filing_date"]
            else:
                metadata = self.connection.execute(
                    "SELECT published_at FROM ingest.info_items WHERE info_id=%s",
                    (row.get("info_id") or citation["accession"],),
                ).fetchone()
                row["exposure_asof"] = (
                    metadata["published_at"].astimezone(ZoneInfo("America/New_York")).date()
                    if metadata and metadata["published_at"]
                    else None
                )
            evidence["asof_basis"] = "source disclosure date; not a model-inferred contract date"
        self.connection.execute(
            """INSERT INTO graph.relations
         (relation_id,from_entity,to_entity,connection_type,mechanism,direction,strength,lag,exposure_usd,
          exposure_basis,exposure_asof,source_info_ids,evidence,first_discovered_at,last_evidence_at,status,drafted_by,basket_ids)
         VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'候选',%s,%s) ON CONFLICT DO NOTHING""",
            (
                row["relation_id"],
                row["from_entity"],
                row["to_entity"],
                row.get("connection_type", "业务关系"),
                row.get("mechanism", "需求"),
                row.get("direction"),
                row.get("strength"),
                str(row.get("lag") or "") or None,
                row.get("exposure_usd"),
                row.get("exposure_basis"),
                row.get("exposure_asof"),
                [row.get("info_id") or row.get("accession") or citation["accession"]],
                Jsonb(evidence),
                row["drafted_at"],
                row["drafted_at"],
                row["drafted_by"],
                baskets,
            ),
        )

    def candidates(self, basket=None):
        return self.connection.execute(
            "SELECT * FROM graph.relations WHERE status='候选' AND "
            "(%s::text IS NULL OR %s=ANY(basket_ids)) ORDER BY from_entity,relation_id",
            (basket, basket),
        ).fetchall()

    def refresh_monitored(self):
        self.connection.execute(
            "UPDATE graph.entities e SET trend_keywords=ARRAY[e.name] WHERE e.kind IN "
            "('private_company','product','app','model') AND cardinality(e.trend_keywords)=0 "
            "AND EXISTS(SELECT 1 FROM graph.relations r WHERE r.to_entity=e.entity_id)"
        )
        result = self.connection.execute(
            "INSERT INTO graph.monitored_entities (entity_id,reason,channels) "
            "SELECT DISTINCT e.entity_id,'basket upstream',ARRAY['trend']::text[] "
            "FROM graph.entities e JOIN graph.relations r ON r.to_entity=e.entity_id "
            "WHERE e.kind IN ('private_company','product','app','model') AND cardinality(e.trend_keywords)>0 "
            "AND cardinality(r.basket_ids)>0 ON CONFLICT DO NOTHING RETURNING entity_id"
        ).fetchall()
        return {"processed_count": len(result)}

    def review(self, ids, *, action, clock, edits=None, expected_revisions=None):
        with self.connection.transaction():
            rows = self.connection.execute(
                "SELECT * FROM graph.relations WHERE relation_id=ANY(%s) FOR UPDATE", (ids,)
            ).fetchall()
            if len(rows) != len(set(ids)):
                raise ValueError("Review identifiers are missing")
            for row in rows:
                expected = (expected_revisions or {}).get(row["relation_id"])
                if expected is not None and expected != row["revision"]:
                    raise ValueError("Review revision conflict")
            queue = ReviewQueue(clock=clock, rows=rows)
            changed = queue.review(ids, action=action, edits=edits)
            for before, after in zip(
                sorted(rows, key=lambda r: r["relation_id"]),
                sorted(changed, key=lambda r: r["relation_id"]),
                strict=True,
            ):
                self.connection.execute(
                    "UPDATE graph.relations SET status=%s,reviewed_at=%s,direction=%s,strength=%s,"
                    "lag=%s,exposure_usd=%s,exposure_basis=%s,exposure_asof=%s,basket_ids=%s,"
                    "revision=revision+1 WHERE relation_id=%s",
                    (
                        after["status"],
                        after.get("reviewed_at"),
                        after.get("direction"),
                        after.get("strength"),
                        after.get("lag"),
                        after.get("exposure_usd"),
                        after.get("exposure_basis"),
                        after.get("exposure_asof"),
                        after.get("basket_ids", []),
                        after["relation_id"],
                    ),
                )
                self.connection.execute(
                    "INSERT INTO graph.review_log (relation_id,action,before_row,after_row,reviewed_at) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (
                        after["relation_id"],
                        action,
                        Jsonb(json.loads(json.dumps(before, default=str))),
                        Jsonb(json.loads(json.dumps(after, default=str))),
                        clock.now_utc(),
                    ),
                )
            return changed
