"""Read-only marketstate snapshot. The connection string stays outside this repository."""

import os
from datetime import date, timedelta

from inves_cog.perception.anomaly.detect import detect_snapshot


class DatabasePanel:
    def __init__(self, connection, sessions, baskets, daily, basket_rows, rotation, macro, bars, shorts):
        self.connection = connection
        self.sessions = sessions
        self.membership_note = None
        self.baskets = baskets
        self.daily = daily
        self.basket_rows = basket_rows
        self.rotation = rotation
        self.macro = macro
        self.bars = bars
        self.shorts = shorts
        self.levels = {row["basket_id"]: row["level"] for row in baskets}
        self.names = {row["basket_id"]: row["name"] for row in baskets}
        self.members = {row["basket_id"]: _members(row) for row in baskets}

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
        sessions = [
            row["trade_date"]
            for row in connection.execute(
                "SELECT DISTINCT trade_date FROM marketstate.market WHERE trade_date BETWEEN %s AND %s ORDER BY 1",
                (start, end),
            ).fetchall()
        ]
        baskets = connection.execute(
            "SELECT basket_id, level, name, members, factor_basis FROM graph.baskets"
        ).fetchall()
        daily = connection.execute(
            """
            SELECT trade_date, ticker, ret, resid, resid_z, sigma, primary_basket
            FROM marketstate.daily
            WHERE session = 'close' AND trade_date BETWEEN %s AND %s
            """,
            (start, end),
        ).fetchall()
        basket_rows = connection.execute(
            """
            SELECT trade_date, basket_id, ret_ew, resid_z
            FROM marketstate.baskets
            WHERE session = 'close' AND trade_date BETWEEN %s AND %s
            """,
            (start, end),
        ).fetchall()
        rotation = connection.execute(
            """
            SELECT trade_date, group_kind, group_id, ret, z
            FROM marketstate.rotation
            WHERE session = 'close' AND trade_date BETWEEN %s AND %s
            """,
            (start, end),
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
        bars = connection.execute(
            """
            SELECT ticker, trade_date, close, volume, adj_factor, source
            FROM ingest.bars_daily
            WHERE trade_date BETWEEN %s AND %s
            """,
            (end - timedelta(days=10), end),
        ).fetchall()
        shorts = connection.execute(
            """
            SELECT ticker, settlement_date, publish_date, days_to_cover, si_pct_shares_outstanding
            FROM ingest.short_interest
            """
        ).fetchall()
        return cls(connection, sessions, baskets, daily, basket_rows, rotation, macro, bars, shorts)

    def detect(self, day, session="close"):
        if session != "close":
            return []
        day = date.fromisoformat(str(day)[:10])
        return detect_snapshot(self.snapshot(day))

    def snapshot(self, day):
        history_days = [item for item in self.sessions if item <= day][-121:]
        by_day = {}
        for row in self.basket_rows:
            by_day.setdefault(row["trade_date"], {}).setdefault(row["basket_id"], row)
        baskets, history, member_returns = [], {}, {}
        daily = [row for row in self.daily if row["trade_date"] == day]
        returns = {row["ticker"]: row["ret"] for row in daily}
        for basket in self.baskets:
            identifier = basket["basket_id"]
            current = by_day.get(day, {}).get(identifier)
            if current is None or current["ret_ew"] is None:
                continue
            baskets.append({"basket_id": identifier, "ret_ew": current["ret_ew"], "resid_z": current["resid_z"]})
            history[identifier] = [(by_day.get(item, {}).get(identifier) or {}).get("ret_ew") for item in history_days]
            member_returns[identifier] = {
                ticker: returns[ticker] for ticker in self.members[identifier] if returns.get(ticker) is not None
            }
        return {
            "trade_date": day.isoformat(),
            "session": "close",
            "baskets": baskets,
            "basket_history": history,
            "member_returns": member_returns,
            "daily": [
                {
                    "ticker": row["ticker"],
                    "ret": row["ret"],
                    "resid": row["resid"],
                    "resid_z": row["resid_z"],
                    "sigma": row["sigma"],
                    "l3_ex_ret": None,
                    "primary_basket": row["primary_basket"],
                }
                for row in daily
            ],
            "daily_history": {},
            "rotation": [
                {"group_kind": row["group_kind"], "group_id": row["group_id"], "ret": row["ret"], "z": row["z"]}
                for row in self.rotation
                if row["trade_date"] == day
            ],
            "macro": _macro_on(self.macro, day),
            "bars": {},
            "calendar": {"index_rebalance": False, "option_expiry": False, "index_rebalance_connected": False},
            "shorts": {},
            "clusters": [],
            "levels": self.levels,
            "names": self.names,
        }


def _members(basket):
    names = []
    for member in basket["members"]:
        names.append(member["ticker"] if isinstance(member, dict) else member)
    return names


def _macro_on(rows, day):
    payload = {}
    for key, series_ids in {
        "VIX": ("VIX_CBOE", "VIXCLS"),
        "DGS2": ("DGS2",),
        "DTWEXBGS": ("DTWEXBGS",),
        "DCOILWTICO": ("DCOILWTICO",),
    }.items():
        visible = [
            row
            for row in rows
            if row["series_id"] in series_ids and row["observation_date"] <= day and row["realtime_start"] <= day
        ]
        if key == "VIX":
            preferred = [row for row in visible if row["series_id"] == "VIX_CBOE"]
            visible = preferred or visible
        visible.sort(key=lambda row: row["observation_date"])
        current = visible[-1]["value"] if visible else None
        previous = visible[-2]["value"] if len(visible) > 1 else None
        payload[key] = {"z": None, "level": current, "prev": previous, "change": None}
    return payload
