"""Price task persistence and coverage, without news or graph relations."""

import json
import math
from datetime import timedelta

from psycopg.types.json import Jsonb

from inves_cog.marketstate.engine import calculate
from inves_cog.marketstate.sic import load_sic, sector_etf

FIELDS = {
    "daily": "trade_date ticker session ret resid resid_z sigma beta_m beta_s beta_t primary_basket "
    "resid_5d resid_5d_z beta_share_5d factor_set health_codes null_reason",
    "baskets": "trade_date basket_id session ret_ew resid resid_z same_sign_share "
    "member_resid_std health_codes null_reason",
    "rotation": "trade_date session group_kind group_id ret z ret_5d z_5d rank rank_5d health_codes null_reason",
    "market": "trade_date spy_5d_pct vix vix_pctile_252 down_share_5d_pct shock_flag l1_state vix3m "
    "vix_term_inverted spy_drawdown_252_pct null_reason sector_spread_z style_spread_z",
}
KEYS = {
    "daily": "trade_date,ticker,session",
    "baskets": "trade_date,basket_id,session",
    "rotation": "trade_date,session,group_kind,group_id",
    "market": "trade_date",
}


def clean(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: clean(v) for key, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def json_value(value):
    return json.dumps(clean(value), ensure_ascii=False, allow_nan=False, default=str)


class MarketService:
    def __init__(self, *, repository, clock):
        self.repo, self.clock = repository, clock

    def run(self, day, *, tickers):
        baskets = self.repo.query("SELECT * FROM graph.baskets ORDER BY level,basket_id").fetchall()
        needed = set(tickers) | {t for b in baskets for t in b["benchmark"].split("/")}
        needed.update("SPY QQQ IWM XLK XLF XLV XLE XLI XLU XLY XLP XLB XLRE XLC SMH IGV KRE MTUM VLUE RSP".split())
        bars = self.repo.query(
            "SELECT * FROM ingest.bars_daily WHERE trade_date BETWEEN %s AND %s AND ticker=ANY(%s) "
            "ORDER BY trade_date,ticker",
            (day - timedelta(days=800), day, sorted(needed)),
        ).fetchall()
        profiles = self.repo.query("SELECT ticker,sic FROM ingest.issuer_profiles").fetchall()
        rules, tickers = load_sic()
        sectors = {r["ticker"]: sector_etf(r["sic"], rules, ticker=r["ticker"], tickers=tickers) for r in profiles}
        result = calculate(bars, baskets, self.repo.vix(), day=day, tickers=tickers, sic_etfs=sectors)
        for table in FIELDS:
            for row in [result[table]] if table == "market" else result[table]:
                self.put(table, row)
        return {
            "status": "ok",
            "processed_count": len(result["daily"]) + len(result["baskets"]) + len(result["rotation"]) + 1,
            "coverage": len({r["ticker"] for r in result["daily"]}),
            "expected": len(set(tickers)),
            "observed_at": self.clock.now_utc(),
            **result,
        }

    def put(self, table, row):
        fields, row = FIELDS[table].split(), clean(row)
        values = [Jsonb(row[k]) if k == "style_spread_z" else row.get(k) for k in fields]
        update = ",".join(f"{k}=EXCLUDED.{k}" for k in fields if k not in KEYS[table].split(","))
        self.repo.query(
            "INSERT INTO marketstate."
            + table
            + " ("
            + ",".join(fields)
            + ") VALUES ("
            + ",".join(["%s"] * len(fields))
            + ") ON CONFLICT ("
            + KEYS[table]
            + ") DO UPDATE SET "
            + update,
            values,
        )
