"""Point-in-time data loader for backtests — prod DB only, no test-module imports."""

import logging
from datetime import date

import yaml

from inves_cog.ingest.fundamentals.repository import Repository as FinancialRepository

log = logging.getLogger(__name__)

ROOT_UNIVERSE = "config/universe.yaml"


class BacktestLoader:
    """Loads bars/fundamentals/VIX from ingest + fundamentals schemas.

    state_asof is the SAME PIT lookup production uses (fundamentals.fin_state
    WHERE filed <= as_of ORDER BY filed DESC) — historical as-of by filing date.
    The audit wraps it and records (ticker, as_of, filed) for every lookup.
    """

    def __init__(self, connection):
        self.connection = connection
        self.fundamentals = FinancialRepository(connection)
        self.audit = {"state_lookups": [], "bar_violations": []}

    # ---------- PIT-audited fundamentals ----------

    def state_asof(self, ticker, as_of_date, extractor):
        state = self.fundamentals.state_asof(ticker, as_of_date, extractor)
        filed = getattr(state, "filed", None) if state is not None else None
        self.audit["state_lookups"].append({"ticker": ticker, "as_of": as_of_date, "filed": filed})
        if state is not None and filed is not None and filed > as_of_date:
            raise ValueError(f"PIT violation: {ticker} state filed {filed} used for {as_of_date}")
        return state

    # ---------- bars ----------

    def bars(self, ticker, start=None, end=None):
        """ingest.bars_daily rows like the golden price_rows shape."""
        rows = self.connection.execute(
            "SELECT trade_date, open, close, volume, adj_factor "
            "FROM ingest.bars_daily WHERE ticker=%s AND trade_date <= %s "
            "ORDER BY trade_date",
            (ticker, end or date(9999, 12, 31)),
        ).fetchall()
        out = []
        for r in rows:
            factor = float(r["adj_factor"]) if r.get("adj_factor") else 1.0
            out.append(
                {
                    "trade_date": r["trade_date"],
                    # one split-adjusted series: engine/scoring see adjusted prices
                    # with adj_factor=1 so technical.py's own adjustment is a no-op
                    "open": float(r["open"]) * factor if r["open"] is not None else None,
                    "close": float(r["close"]) * factor if r["close"] is not None else None,
                    "volume": int(r["volume"] / factor) if r["volume"] is not None else None,
                    "adj_factor": 1.0,
                }
            )
        return out

    def vix(self, end):
        """ingest.macro_observations VIX_CBOE → {date: close}."""
        rows = self.connection.execute(
            "SELECT observation_date, value FROM ingest.macro_observations "
            "WHERE series_id=%s AND observation_date <= %s ORDER BY observation_date",
            ("VIXCLS", end),
        ).fetchall()
        return {r["observation_date"]: float(r["value"]) for r in rows if r["value"] is not None}

    # ---------- universe ----------

    @staticmethod
    def universe(name, v18_tickers):
        if name == "v18":
            return list(v18_tickers)
        data = yaml.safe_load(open(ROOT_UNIVERSE).read())
        return [x["ticker"] for x in data["stocks"]]

    def coverage(self, tickers, start):
        """tickers enter the universe on their first bar date (IPO) → return first-bar map."""
        rows = self.connection.execute(
            "SELECT ticker, min(trade_date) AS first, max(trade_date) AS last "
            "FROM ingest.bars_daily WHERE ticker = ANY(%s) GROUP BY ticker",
            (list(tickers),),
        ).fetchall()
        return {r["ticker"]: {"first": r["first"], "last": r["last"]} for r in rows}
