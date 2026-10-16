"""Read-only replay. Basket math uses the same price history as file mode.

Stored marketstate.baskets begins later than the bar history, so a z-score
taken from that short window does not match the 120-session file calculation.
This reader rebuilds the snapshot from ingest.bars_daily. Wide names that are
only present in marketstate.daily stay out of the pool.
"""

import os
from datetime import date, timedelta

from inves_cog.perception.anomaly.detect import detect_snapshot
from inves_cog.perception.anomaly.panel import PricePanel
from inves_cog.perception.anomaly.universe import pool_names, rotation_names


class DatabasePanel:
    def __init__(self, panel, wide_daily=None):
        self.panel = panel
        self.sessions = panel.sessions
        self.membership_note = panel.membership_note
        self.wide_daily = list(wide_daily or [])

    @classmethod
    def from_frames(cls, bars, baskets, macro_rows=None, short_rows=None, wide_daily=None):
        panel = PricePanel.from_records(bars, baskets, macro_rows, short_rows)
        return cls(panel, wide_daily)

    @classmethod
    def from_env(cls):
        url = os.environ.get("INVES_COG_DATABASE_URL")
        if not url:
            raise SystemExit("只读复跑需要调用方提供 INVES_COG_DATABASE_URL，仓库里不保存连接串")
        import psycopg
        from psycopg.rows import dict_row

        connection = psycopg.connect(url, row_factory=dict_row)
        return cls.from_connection(connection)

    @classmethod
    def from_connection(cls, connection, start=None, end=None):
        start = start or date(2017, 1, 1)
        end = end or date(2026, 10, 14)
        baskets = connection.execute(
            "SELECT basket_id, level, name, members, factor_basis FROM graph.baskets"
        ).fetchall()
        pool = sorted(pool_names(baskets))
        bar_names = sorted(set(pool) | rotation_names())
        bars = connection.execute(
            """
            SELECT ticker, trade_date, open, high, low, close, volume, post_close, adj_factor, source
            FROM ingest.bars_daily
            WHERE ticker = ANY(%s) AND trade_date BETWEEN %s AND %s
            """,
            (bar_names, start, end),
        ).fetchall()
        macro = connection.execute(
            """
            SELECT series_id, observation_date, value, realtime_start
            FROM ingest.macro_observations
            WHERE series_id IN ('VIX_CBOE', 'VIXCLS', 'DGS2', 'DTWEXBGS', 'DCOILWTICO', 'VIX3M_CBOE')
              AND observation_date BETWEEN %s AND %s
            """,
            (start - timedelta(days=40), end),
        ).fetchall()
        shorts = connection.execute(
            """
            SELECT ticker, settlement_date, publish_date, days_to_cover, si_pct_shares_outstanding
            FROM ingest.short_interest
            WHERE ticker = ANY(%s)
            """,
            (pool,),
        ).fetchall()
        wide = connection.execute(
            """
            SELECT trade_date, ticker, ret, resid, resid_z, sigma, primary_basket
            FROM marketstate.daily
            WHERE session = 'close' AND trade_date BETWEEN %s AND %s
              AND NOT (ticker = ANY(%s))
            """,
            (start, end, bar_names),
        ).fetchall()
        return cls.from_frames(bars, baskets, macro, shorts, wide)

    def detect(self, day, session="close"):
        rows = self.panel.detect(day, session)
        if session != "close":
            return rows
        return rows + self._wide(day)

    def snapshot(self, day, session="close"):
        return self.panel.snapshot(day, session)

    def _wide(self, day):
        day = date.fromisoformat(str(day)[:10])
        daily = []
        for row in self.wide_daily:
            trade_date = row["trade_date"]
            if not isinstance(trade_date, date):
                trade_date = date.fromisoformat(str(trade_date)[:10])
            if trade_date != day:
                continue
            daily.append(
                {
                    "ticker": row["ticker"],
                    "ret": row["ret"],
                    "resid": row["resid"],
                    "resid_z": row["resid_z"],
                    "sigma": row["sigma"],
                    "l3_ex_ret": None,
                    "primary_basket": row.get("primary_basket"),
                }
            )
        if not daily:
            return []
        snapshot = {
            "trade_date": day.isoformat(),
            "session": "close",
            "baskets": [],
            "basket_history": {},
            "member_returns": {},
            "daily": daily,
            "daily_history": {},
            "rotation": [],
            "macro": {},
            "bars": {},
            "calendar": {"index_rebalance": False, "option_expiry": False, "index_rebalance_connected": False},
            "shorts": {},
            "clusters": [],
            "levels": {},
            "names": {},
            "pool": sorted(self.panel.classified),
        }
        return detect_snapshot(snapshot)
