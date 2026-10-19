"""Read only upstream contracts; restrict every write to M5's own three tables."""

import json
from collections import defaultdict
from datetime import timedelta

from psycopg.types.json import Jsonb

from inves_cog.ingest.fundamentals.repository import state_from_row
from inves_cog.ingest.fundamentals.state import StateStore
from inves_cog.valuation_v1.calculations import settings
from inves_cog.valuation_v1.lifecycle import TypeHistory, ValuationBook

WRITE_TABLES = {"ranges", "position_panel", "shadow_rules"}


def jsonb(row):
    return Jsonb(row, dumps=lambda x: json.dumps(x, default=str, ensure_ascii=False, allow_nan=False))


class Repository:
    def __init__(self, connection):
        self.connection = connection

    def exists(self, schema, table):
        return self.connection.execute(
            "SELECT to_regclass(%s) IS NOT NULL AS exists", (schema + "." + table,)
        ).fetchone()["exists"]

    def inputs(self, through, tickers):
        states = [
            state_from_row(r)
            for r in self.connection.execute(
                "SELECT * FROM fundamentals.fin_state WHERE extractor='fixed' "
                "AND ticker=ANY(%s) AND filed<=%s ORDER BY ticker,filed",
                (tickers, through),
            ).fetchall()
        ]
        grouped = defaultdict(list)
        for s in states:
            grouped[s.ticker].append(s)
        bars = defaultdict(list)
        for r in self.connection.execute(
            "SELECT ticker,trade_date,close FROM ingest.bars_daily WHERE ticker=ANY(%s) "
            "AND trade_date BETWEEN %s AND %s ORDER BY ticker,trade_date",
            (tickers, through - timedelta(days=366 * settings()["pe"]["lookback_years"]), through),
        ).fetchall():
            bars[r["ticker"]].append(r)
        snapshots = defaultdict(list)
        for r in self.connection.execute(
            "SELECT * FROM fundamentals.consensus_snapshot WHERE ticker=ANY(%s) "
            "AND as_of<=%s ORDER BY as_of,captured_at",
            (tickers, through),
        ).fetchall():
            snapshots[r["ticker"]].append(r)
        baskets = (
            self.connection.execute("SELECT * FROM graph.baskets ORDER BY level,basket_id").fetchall()
            if self.exists("graph", "baskets")
            else []
        )
        profiles = (
            self.connection.execute("SELECT ticker,sic FROM ingest.issuer_profiles").fetchall()
            if self.exists("ingest", "issuer_profiles")
            else []
        )
        return {
            "sic": {r["ticker"]: r["sic"] for r in profiles},
            "store": StateStore(states),
            "states": dict(grouped),
            "bars": dict(bars),
            "consensus": dict(snapshots),
            "baskets": baskets,
        }

    def restore(self, through):
        book = ValuationBook()
        if not self.exists("valuation_v1", "ranges"):
            return book
        rows = self.connection.execute(
            "SELECT DISTINCT ON(ticker) ticker,payload FROM valuation_v1.ranges "
            "WHERE trade_date<=%s AND params_version=%s ORDER BY ticker,trade_date DESC",
            (through, settings()["params_version"]),
        ).fetchall()
        for row in rows:
            p = row["payload"]
            ticker = row["ticker"]
            book.published[ticker] = {k: v for k, v in p.items() if k not in {"proposed", "review_reason"}}
            if p.get("proposed"):
                book.pending[ticker] = p["proposed"]
            h = TypeHistory()
            state = p.get("type_state", {})
            h.current = state.get("current", p["type"])
            h.observations = state.get("observations", {})
            h.audit = state.get("audit", [])
            book.types[ticker] = h
        return book

    def shadow_history(self, through):
        seen = defaultdict(set)
        past = {}
        if self.exists("valuation_v1", "shadow_rules"):
            for r in self.connection.execute(
                "SELECT ticker,version FROM valuation_v1.shadow_rules "
                "WHERE trade_date<%s AND v3_trim_flag IS TRUE AND params_version=%s",
                (through, settings()["params_version"]),
            ).fetchall():
                seen[r["ticker"]].add(r["version"])
        if self.exists("valuation_v1", "ranges"):
            for r in self.connection.execute(
                "SELECT DISTINCT ON(ticker) ticker,bear FROM valuation_v1.ranges "
                "WHERE trade_date<=%s AND params_version=%s ORDER BY ticker,trade_date DESC",
                (through - timedelta(days=settings()["shadow"]["bear_lookback_days"]), settings()["params_version"]),
            ).fetchall():
                past[r["ticker"]] = r["bear"]
        return dict(seen), past

    def holdings(self, through, *, portfolio=None, cutoff=None):
        if not self.exists("trading", "ledger") or not self.exists("trading", "plan"):
            return {"holdings": [], "candidates": [], "reason": "M4持仓/计划表未部署，不能判断实际仓位"}
        portfolio = portfolio or settings()["inputs"]["portfolio_id"]
        ledger = self.connection.execute(
            "SELECT * FROM trading.ledger WHERE portfolio_id=%s AND trade_date<=%s "
            "AND extractor='fixed' AND rule_set='A' AND (%s::timestamptz IS NULL OR observed_at<=%s) "
            "ORDER BY trade_date DESC,observed_at DESC LIMIT 1",
            (portfolio, through, cutoff, cutoff),
        ).fetchone()
        plan = self.connection.execute(
            "SELECT * FROM trading.plan WHERE portfolio_id=%s AND signal_date<=%s "
            "AND extractor='fixed' AND rule_set='A' AND published "
            "AND (%s::timestamptz IS NULL OR generated_at<=%s) ORDER BY signal_date DESC,generated_at DESC LIMIT 1",
            (portfolio, through, cutoff, cutoff),
        ).fetchone()
        if not ledger:
            return {"holdings": [], "candidates": [], "reason": "M4未发布实际持仓快照"}
        state = ledger["state"]
        positions = state.get("positions", {})
        equity = ledger["equity"]
        holdings = []
        for ticker, p in positions.items():
            holdings.append({"ticker": ticker, "shares": p["shares"], "equity": equity})
        return {
            "holdings": holdings,
            "candidates": plan["payload"].get("orders", []) if plan else [],
            "equity": equity,
            "ledger_date": ledger["trade_date"],
            "cash": ledger["cash"],
            "reason": None,
        }

    def write(self, table, day, row, observed_at):
        if table not in WRITE_TABLES:
            raise ValueError("M5只允许写valuation_v1的三张表")
        base = {
            "trade_date": day,
            "ticker": row["ticker"],
            "params_version": settings()["params_version"],
            "payload": jsonb(row),
            "observed_at": observed_at,
        }
        if table == "ranges":
            base.update(
                {
                    k: row[k]
                    for k in (
                        "method_version",
                        "version",
                        "type",
                        "status",
                        "bear",
                        "neutral",
                        "bull",
                        "pending_review",
                    )
                }
            )
        if table == "shadow_rules":
            base.update({k: row[k] for k in ("version", "vt1", "vt2", "v1_score", "v2_coef", "v3_trim_flag")})
        keys = list(base)
        columns = ",".join(keys)
        placeholders = ",".join(["%s"] * len(keys))
        updates = ",".join(k + "=EXCLUDED." + k for k in keys if k not in {"trade_date", "ticker", "params_version"})
        self.connection.execute(
            f"INSERT INTO valuation_v1.{table} ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(trade_date,ticker,params_version) DO UPDATE SET {updates}",
            list(base.values()),
        )

    def save(self, day, result, observed_at):
        with self.connection.transaction():
            for table, rows in [
                ("ranges", result["ranges"]),
                ("position_panel", result["panel"] + [result["summary"]]),
                ("shadow_rules", result["shadows"]),
            ]:
                for row in rows:
                    self.write(table, day, row, observed_at)
