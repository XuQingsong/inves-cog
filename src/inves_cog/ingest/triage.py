"""Rule-first news routing with replayable batches and a persisted usage budget."""

import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from copy import deepcopy
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from inves_cog.ingest.info import enrich, extraction_body, record_extraction_error
from inves_cog.llm.usage import usage_context

INDUSTRIES = [
    "semiconductors",
    "AI",
    "software",
    "retail",
    "healthcare",
    "finance",
    "energy",
    "industrial",
    "macroeconomic policy",
]
KEYWORDS = {
    "guidance": r"guidance|outlook",
    "rating": r"upgrade|downgrade|rating|price target",
    "merger": r"merger|acquisition|takeover",
    "capacity": r"capacity|expansion|production",
    "policy": r"export control|tariff|regulation|sanction",
    "risk": r"recall|lawsuit|litigation",
}
MACRO_PATTERN = re.compile(
    r"(?<!\w)(fed|fomc|cpi|pce|payrolls?|employment|jobs?|tariffs?|export controls?|sanctions?)(?!\w)",
    re.I,
)
REUSED_FIELDS = ["entities", "is_guidance", "guidance_direction", "is_rating_change"]
NEWS_DAILY_TOKEN_LIMIT = 5_500_000


def contains(text, term):
    return bool(term and re.search(r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)", text.casefold()))


class NewsTriage:
    def __init__(
        self,
        *,
        llm,
        embed,
        entities,
        monitored_ids,
        pool_tickers,
        clock,
        pool_ciks=None,
        daily_budget=NEWS_DAILY_TOKEN_LIMIT,
        usage_today=None,
        cached_root=None,
        workers=1,
        full_daily_limit=1_500,
        screen_daily_limit=120,
    ):
        self.llm, self.embed, self.entities, self.clock = llm, embed, entities, clock
        self.pool_ciks = {str(c).zfill(10) for c in (pool_ciks or set()) if c}
        self.workers = workers
        self.monitored_ids, self.pool = set(monitored_ids), set(pool_tickers)
        # Pipeline still passes the frozen 1.5M configuration. A-022's reviewed
        # fallback supersedes it without changing configuration or test injection.
        self.daily_budget = NEWS_DAILY_TOKEN_LIMIT if daily_budget == 1_500_000 else daily_budget
        self.full_daily_limit = full_daily_limit
        self.screen_daily_limit = screen_daily_limit
        self.usage_today = usage_today or (lambda: {"tokens": 0, "missing": 0})
        self.cached_root = cached_root or (lambda root: None)
        self.entity_map = {e["entity_id"]: e for e in entities}
        self.context = [{k: e.get(k, []) for k in ("entity_id", "name", "aliases", "tickers")} for e in entities]

    def rules(self, item):
        result = deepcopy(item)
        # A-026: structured non-news items never reach the model.
        if item["kind"] in {"short_interest", "macro"}:
            meta = {"rule_entities": [], "llm_full": False, "reason": "rules_only_structured"}
            result.setdefault("extraction_source", {})["news_triage"] = meta
            return result
        text = result["headline"] + " " + extraction_body(result["body"])
        identifiers = set(result["entities"])
        for entity in self.entities:
            if set(entity.get("tickers", [])) & set(result["tickers"]) or any(
                contains(text, term) for term in [entity["name"], *entity.get("aliases", [])]
            ):
                identifiers.add(entity["entity_id"])
        # A ticker in prose must retain its case; short tickers require "$".
        for ticker in self.pool:
            pattern = r"(?<!\w)" + (r"\$" if len(ticker) < 3 else r"\$?") + re.escape(ticker) + r"(?!\w)"
            if re.search(pattern, text):
                identifiers.update(e["entity_id"] for e in self.entities if ticker in e.get("tickers", []))
        result["entities"] = sorted(identifiers)
        meta = {
            "rule_entities": result["entities"],
            "source_level": result["source_level"],
            "keyword_tags": [key for key, pattern in KEYWORDS.items() if re.search(pattern, text, re.I)],
            "llm_full": False,
        }
        result.setdefault("extraction_source", {})["news_triage"] = meta
        return result

    @staticmethod
    def meta(item):
        return item["extraction_source"]["news_triage"]

    def tracked(self, item):
        return bool(
            set(item["tickers"]) & self.pool
            or any(
                set(self.entity_map.get(identifier, {}).get("tickers", [])) & self.pool
                for identifier in item["entities"]
            )
        )

    @staticmethod
    def holding(item):
        return bool(item.get("extraction_source", {}).get("news_queue", {}).get("holding_related"))

    def primary(self, item):
        return (
            self.holding(item)
            or self.tracked(item)
            or bool(set(item["entities"]) & self.monitored_ids)
            or (item["kind"] in {"sec_8k", "form4"} and self._filing_relevant(item))
            or item["source_level"] == 1
            or item["source"].casefold() == "benzinga"
            and bool(MACRO_PATTERN.search(item["headline"] + " " + extraction_body(item["body"])))
        )

    def _filing_relevant(self, item):
        """Filing issuer must be in the pool or current holdings (CIK/ticker)."""
        import re as _re

        for match in _re.findall(r"\((\d{10})\)", item["headline"]):
            if match in self.pool_ciks:
                return True
        pool = {t.upper() for e in self.entities for t in e.get("tickers", [])}
        return bool({t.upper() for t in item["tickers"]} & pool)

    def over_budget(self):
        stats = self.usage_today()
        return bool(stats["missing"]) or stats["tokens"] >= self.daily_budget

    def defer(self, item, reason):
        now = self.clock.now_utc()
        if reason in {"daily_budget", "full_daily_limit", "screen_daily_limit"}:
            zone = ZoneInfo("America/New_York")
            retry = datetime.combine(now.astimezone(zone).date() + timedelta(days=1), time(), zone)
        else:
            retry = now + timedelta(minutes=5)
        self.meta(item).update(reason=reason, retry_at=retry.astimezone(timezone.utc).isoformat())
        item["extraction_status"] = "pending"

    def map_work(self, operation, values):
        if self.workers == 1:
            return [operation(value) for value in values]
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = [executor.submit(copy_context().run, operation, value) for value in values]
            return [future.result() for future in futures]

    def screen(self, items):
        batches = [items[start : start + 25] for start in range(0, len(items), 25)]
        stats = self.usage_today()
        if bool(stats.get("missing")) or stats.get("tokens", 0) >= self.daily_budget:
            for item in items:
                self.defer(item, "daily_budget")
            return
        remaining = max(0, self.screen_daily_limit - stats.get("screen_calls", 0))
        self.map_work(self.screen_batch, batches[:remaining])
        for batch in batches[remaining:]:
            for item in batch:
                self.defer(item, "screen_daily_limit")

    def screen_batch(self, batch):
        if self.over_budget():
            for item in batch:
                self.defer(item, "daily_budget")
            return
        payload = {
            "items": [
                {
                    "info_id": item["info_id"],
                    "headline": item["headline"],
                    "body": extraction_body(item["body"])[:200],
                }
                for item in batch
            ],
            "known_entities": self.context,
            "industry_scope": INDUSTRIES,
        }
        try:
            with usage_context(purpose="M1:layer1", info_ids=[item["info_id"] for item in batch]):
                reply = self.llm.call("entity_tagging", payload)
            entries = reply.get("items")
            if not isinstance(entries, list):
                raise ValueError("Screening reply requires an items array")
            by_id = {entry["info_id"]: entry for entry in entries if isinstance(entry, dict) and "info_id" in entry}
            if len(by_id) != len(entries):
                raise ValueError("Duplicate or malformed screening identifiers")
        except Exception as exc:
            for item in batch:
                record_extraction_error(item, "news_screening", exc)
                self.defer(item, "screening_failed")
            return
        for item in batch:
            try:
                entry = by_id[item["info_id"]]
                if (
                    not isinstance(entry.get("material"), bool)
                    or not isinstance(entry.get("entities"), list)
                    or not all(isinstance(e, str) for e in entry["entities"])
                ):
                    raise ValueError("Invalid material/entity screening output")
                item["entities"] = sorted(set(item["entities"]) | (set(entry["entities"]) & self.entity_map.keys()))
                self.meta(item).update(
                    screened=True,
                    material=entry["material"],
                    layer=2 if entry["material"] or self.primary(item) else 3,
                    tier="A" if entry["material"] or self.primary(item) else "B",
                    reason="screening_material" if entry["material"] else "screening_not_material",
                )
            except Exception as exc:
                record_extraction_error(item, "news_screening", exc)
                self.defer(item, "screening_failed")

    def full(self, item):
        item["flags"] = [f for f in item["flags"] if f != "entity_tagging_failed"]
        with usage_context(purpose="M1:layer2", info_ids=[item["info_id"]]):
            result = enrich(item, llm=self.llm, embed=None, entities=self.entities, clock=self.clock, close_read=True)
        self.meta(result).update(layer=2, llm_full=True)
        return result

    def embed_item(self, item):
        if self.meta(item).get("tier") == "C" or self.meta(item).get("retry_at"):
            return item
        self.meta(item)["embedding_attempted"] = True
        if item["embedding"] is not None:
            item["flags"] = [f for f in item["flags"] if f != "embedding_failed"]
            return item
        try:
            if self.embed is None:
                raise RuntimeError("Embedding is unavailable")
            vector = self.embed(
                item["headline"] + "\n" + extraction_body(item["body"])[:2000],
                model="text-embedding-v3",
                dimensions=1024,
            )
            if (
                not isinstance(vector, list)
                or len(vector) != 1024
                or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in vector)
            ):
                raise ValueError("Invalid embedding dimension or value")
            item["embedding"] = vector
            item["flags"] = [f for f in item["flags"] if f != "embedding_failed"]
        except Exception as exc:
            record_extraction_error(item, "embedding", exc)
            if "embedding_failed" not in item["flags"]:
                item["flags"].append("embedding_failed")
        return item

    def reuse(self, item, previous):
        for key in REUSED_FIELDS:
            item[key] = deepcopy(previous[key])
        item["entities"] = sorted(set(item["entities"]) | set(self.meta(item)["rule_entities"]))
        meta = deepcopy(self.meta(previous))
        meta.update(reused_from=previous["info_id"], rule_entities=self.meta(item)["rule_entities"])
        item["extraction_source"] = deepcopy(previous["extraction_source"])
        item["extraction_source"]["news_triage"] = meta
        item["extraction_status"] = previous["extraction_status"]
        for flag in previous["flags"]:
            if flag == "entity_tagging_failed" and flag not in item["flags"]:
                item["flags"].append(flag)
        return item

    def finish(self, item):
        meta = self.meta(item)
        try:
            if not meta.get("retry_at") and not meta.get("reused_from"):
                if meta["layer"] == 2:
                    return self.full(item)
                item["extraction_status"] = "ok"
        except Exception as exc:
            record_extraction_error(item, "news_processing", exc)
            self.defer(item, "processing_failed")
        return item

    def process(self, items, *, on_demand=False, persist=None):
        planned, representatives, copies, screening = [], {}, {}, []
        for original in items:
            item = self.rules(original)
            root = item["source_root"] or item["info_id"]
            planned.append(item)
            if root in representatives:
                copies[item["info_id"]] = root
                continue
            previous = (
                original
                if original["extraction_status"] == "ok" and "news_triage" in original["extraction_source"]
                else None
            )
            if previous is None and item["source_root"]:
                previous = self.cached_root(root)
            if previous and previous["extraction_status"] == "ok":
                representatives[root] = self.reuse(item, previous)
                self.meta(representatives[root]).update(tier="C", layer=3, reason="rules_only_low_value")
                continue
            representatives[root] = item
            meta = self.meta(item)
            stamp = item["published_at"] or item["first_seen_at"]
            # A-026: structured items and non-relevant filings never reach any model.
            if item["kind"] in {"short_interest", "macro"}:
                meta.update(tier="C", layer=3, reason="rules_only_structured")
            elif item["kind"] in {"sec_8k", "form4"} and not (
                self.holding(item) or self.tracked(item) or self._filing_relevant(item)
            ):
                meta.update(tier="C", layer=3, reason="filing_not_in_pool")
            elif not on_demand and stamp < self.clock.now_utc() - timedelta(days=30):
                meta.update(tier="C", layer=3, reason="historical_rules_only")
            elif on_demand or self.primary(item):
                meta.update(tier="A", layer=2, reason="on_demand" if on_demand else "rule_hit")
            elif original.get("extraction_source", {}).get("news_triage", {}).get("screened"):
                screen = original["extraction_source"]["news_triage"]
                meta.update(
                    screened=True,
                    material=screen["material"],
                    layer=2 if screen["material"] else 3,
                    tier="A" if screen["material"] else "B",
                    reason="screening_cached",
                )
            elif item["source"].casefold() == "fiscal.ai":
                meta.update(tier="C", layer=3, reason="rules_only_low_value")
            else:
                meta.update(tier="B", layer=1, reason="screening")
                screening.append(item)
        self.screen(screening)
        ordered = sorted(
            representatives.items(),
            key=lambda pair: (
                self.meta(pair[1]).get("tier") != "A",
                not self.holding(pair[1]),
                not self.tracked(pair[1]),
            ),
        )
        stats = self.usage_today()
        full = [
            item for _, item in ordered if self.meta(item).get("layer") == 2 and not self.meta(item).get("retry_at")
        ]
        if bool(stats.get("missing")) or stats.get("tokens", 0) >= self.daily_budget:
            for item in full:
                self.defer(item, "daily_budget")
        else:
            remaining = max(0, self.full_daily_limit - stats.get("full_items", 0))
            for item in full[remaining:]:
                self.defer(item, "full_daily_limit")
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(copy_context().run, self.finish, item): root for root, item in ordered}
            for future in as_completed(futures):
                root = futures[future]
                result = self.embed_item(future.result())
                representatives[root] = result
                if persist is not None:
                    persist(result)
        output = []
        for item in planned:
            root = item["source_root"] or item["info_id"]
            result = self.reuse(item, representatives[root]) if item["info_id"] in copies else representatives[root]
            if item["info_id"] in copies:
                self.meta(result).update(tier="C", layer=3, reason="rules_only_low_value")
                result = self.embed_item(result)
                if persist is not None:
                    persist(result)
            output.append(result)
        return output
