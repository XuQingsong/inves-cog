"""Narrow price-table queries; graph relations and news never enter this layer."""

import re

TABLES = {
    "ingest.bars_daily",
    "ingest.bars_minute",
    "graph.baskets",
    "ingest.macro_observations",
    "ingest.issuer_profiles",
    "marketstate.daily",
    "marketstate.baskets",
    "marketstate.market",
    "marketstate.rotation",
}


def assert_price_query(query):
    tables = re.findall(r"\b(?:FROM|JOIN|INTO|UPDATE)\s+([a-z_]+\.[a-z_]+)", query, re.I)
    if not tables or any(table.lower() not in TABLES for table in tables):
        raise ValueError("marketstate input/output table is outside the price-only contract")


class Repository:
    def __init__(self, connection):
        self.connection = connection

    def query(self, sql, args=()):
        assert_price_query(sql)
        return self.connection.execute(sql, args)

    def vix(self):
        return self.query(
            "SELECT * FROM ingest.macro_observations WHERE series_id = ANY(%s)", (["VIX_CBOE", "VIX_YAHOO", "VIXCLS", "VIX3M_CBOE", "VIX3M_YAHOO"],)
        ).fetchall()
