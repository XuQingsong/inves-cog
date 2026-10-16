"""Read accepted upstream inputs; persist only M4 ledger and plan snapshots."""

import json
from collections import defaultdict
from datetime import date, timedelta

from psycopg.types.json import Jsonb

from inves_cog.ingest.fundamentals.repository import state_from_row
from inves_cog.ingest.fundamentals.state import StateStore
from inves_cog.trading.execution.signals import enrich
from inves_cog.trading.scoring import score_history


def jsonb(value):
    return Jsonb(value, dumps=lambda v: json.dumps(v, default=str, ensure_ascii=False, allow_nan=False))


class Repository:
    def __init__(self, connection):
        self.connection = connection

    def inputs(self, through, tickers, *, historical=False):
        bars = defaultdict(dict)
        for row in self.connection.execute(
            "SELECT * FROM ingest.bars_daily WHERE trade_date BETWEEN %s AND %s "
            "AND ticker=ANY(%s) ORDER BY ticker,trade_date",
            (through - timedelta(days=1100), through, tickers + ["SPY"]),
        ).fetchall():
            adjusted = dict(row)
            for field in ("open", "close"):
                adjusted[field] = (
                    row[field] * row["adj_factor"] if row[field] is not None and row["adj_factor"] is not None else None
                )
            bars[row["ticker"]][row["trade_date"]] = adjusted
        states = StateStore(
            [
                state_from_row(r)
                for r in self.connection.execute(
                    "SELECT * FROM fundamentals.fin_state WHERE ticker=ANY(%s) "
                    "AND extractor='fixed' AND filed<=%s ORDER BY filed",
                    (tickers, through),
                ).fetchall()
            ]
        )
        signals = {}
        stored = defaultdict(dict)
        if not historical:
            for row in self.connection.execute(
                "SELECT * FROM trading.daily_scores WHERE ticker=ANY(%s) AND extractor='fixed' "
                "AND rule_set='A' AND params_version='p-2026.10' AND signal_date<=%s ORDER BY signal_date",
                (tickers, through),
            ).fetchall():
                stored[row["ticker"]][row["signal_date"]] = row
        for ticker in tickers:
            source = list(bars[ticker].values())
            if not source:
                signals[ticker] = {}
                continue
            # Historical acceptance replays invoke the accepted M3 pure function, with M2 PIT lookup.
            # Production decisions consume published daily_scores; no M3 table is written here.
            snapshots = score_history(
                ticker,
                source,
                state_asof=states.state_asof,
                extractor="fixed",
                start=date(through.year, 1, 1),
                end=through,
            )
            if not historical:
                accepted = []
                for snapshot in snapshots:
                    row = stored[ticker].get(snapshot["signal_date"])
                    if row:
                        accepted.append(
                            {
                                **snapshot,
                                **row,
                                "books": {k: row[k] for k in ("quality", "growth", "valuation", "timing")},
                            }
                        )
                snapshots = accepted
            signals[ticker] = enrich(snapshots, states.state_asof, ticker, "fixed")
        macro = self.connection.execute(
            "SELECT series_id,observation_date,realtime_start,value FROM ingest.macro_observations "
            "WHERE series_id IN ('VIX_CBOE','VIXCLS') AND observation_date<=%s AND realtime_start<=%s "
            "ORDER BY observation_date,series_id,realtime_start",
            (through, through),
        ).fetchall()
        vix, source = {}, {}
        for row in macro:
            day = row["observation_date"]
            if row["value"] is not None and (
                day not in vix or row["series_id"] == "VIX_CBOE" or source[day] != "VIX_CBOE"
            ):
                vix[day], source[day] = row["value"], row["series_id"]
        return {
            "bars": bars,
            "signals": signals,
            "vix": vix,
            "vix_sources": source,
            "score_source": "M3 pure historical replay" if historical else "trading.daily_scores",
        }

    def insider_events(self, through):
        rows = self.connection.execute(
            "SELECT ticker,filed_at,transaction_code,is_officer FROM ingest.form4_events "
            "WHERE filed_at < (%s::date+1) AT TIME ZONE 'America/New_York' "
            "AND transaction_code='P'",
            (through,),
        ).fetchall()
        from inves_cog.ingest.market import NY

        result = defaultdict(list)
        for row in rows:
            result[row["ticker"]].append(
                {"filed": row["filed_at"].astimezone(NY).date(), "code": "P", "officer": row["is_officer"]}
            )
        return dict(result)

    def restore(self, portfolio_id, through):
        return self.connection.execute(
            "SELECT state FROM trading.ledger WHERE portfolio_id=%s AND trade_date<=%s "
            "AND extractor='fixed' AND rule_set='A' AND params_version='p-2026.10' "
            "ORDER BY trade_date DESC,observed_at DESC LIMIT 1",
            (portfolio_id, through),
        ).fetchone()

    def save(self, engine, plan):
        stamp = engine.clock.now_utc()
        self.connection.execute(
            "INSERT INTO trading.ledger (portfolio_id,trade_date,phase,extractor,rule_set,params_version,"
            "cash,equity,peak_equity,state,observed_at) VALUES (%s,%s,'plan','fixed','A','p-2026.10',%s,%s,%s,%s,%s) "
            "ON CONFLICT (portfolio_id,trade_date,phase,extractor,rule_set,params_version) "
            "DO UPDATE SET cash=EXCLUDED.cash,equity=EXCLUDED.equity,peak_equity=EXCLUDED.peak_equity,"
            "state=EXCLUDED.state,observed_at=EXCLUDED.observed_at",
            (
                engine.portfolio_id,
                plan["trade_date"],
                engine.cash,
                engine.last_equity,
                engine.peak_equity,
                jsonb(engine.snapshot()),
                stamp,
            ),
        )
        self.connection.execute(
            "INSERT INTO trading.plan (portfolio_id,trade_date,signal_date,extractor,rule_set,params_version,"
            "published,generated_at,payload) VALUES (%s,%s,%s,'fixed','A','p-2026.10',%s,%s,%s) "
            "ON CONFLICT (portfolio_id,trade_date,extractor,rule_set,params_version) DO UPDATE SET "
            "published=EXCLUDED.published,generated_at=EXCLUDED.generated_at,payload=EXCLUDED.payload",
            (engine.portfolio_id, plan["trade_date"], plan["signal_date"], plan["published"], stamp, jsonb(plan)),
        )
