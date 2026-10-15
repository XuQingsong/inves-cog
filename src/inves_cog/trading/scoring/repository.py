"""Score persistence; no direct financial-table access is exposed here."""

import json
from datetime import date, datetime

FIELDS = (
    "signal_date ticker extractor rule_set params_version tech derived quality growth valuation timing "
    "timing_subitems rank_score red_lines tier tier_changed_on certainty certainty_points hold_score hold_ok "
    "fund_bad runway_ok m31_adjusted_valuation m32_ok gate_pass entry_pass consec_pass tradable null_reason"
).split()
JSON = {"tech", "derived", "timing_subitems"}


def json_value(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        default=lambda x: x.isoformat() if isinstance(x, (date, datetime)) else str(x),
    )


class Repository:
    def __init__(self, connection):
        self.connection = connection

    def put(self, snapshot):
        row = {**snapshot, **snapshot["books"]}
        row["tech"] = {**row["tech"], "health_codes": snapshot["health_codes"]}
        row["timing_subitems"] = {
            **row["timing_subitems"],
            "_missing": snapshot["timing_missing"],
            "_missing_fields": snapshot["missing_fields"],
        }
        values = [json_value(row[key]) if key in JSON else row.get(key) for key in FIELDS]
        parameters = ",".join("%s::jsonb" if key in JSON else "%s" for key in FIELDS)
        update = ",".join(f"{key}=EXCLUDED.{key}" for key in FIELDS[5:])
        self.connection.execute(
            "INSERT INTO trading.daily_scores (" + ",".join(FIELDS) + ") VALUES (" + parameters + ") "
            "ON CONFLICT (signal_date,ticker,extractor,rule_set,params_version) DO UPDATE SET " + update,
            values,
        )

    def bars(self, ticker, through):
        return self.connection.execute(
            "SELECT * FROM ingest.bars_daily WHERE ticker=%s AND trade_date<=%s ORDER BY trade_date", (ticker, through)
        ).fetchall()

    def previous(self, ticker, before, extractor, params_version):
        return self.connection.execute(
            "SELECT signal_date,tier,tier_changed_on,consec_pass FROM trading.daily_scores "
            "WHERE ticker=%s AND signal_date<%s AND extractor=%s AND rule_set='A' "
            "AND params_version=%s ORDER BY signal_date DESC LIMIT 1",
            (ticker, before, extractor, params_version),
        ).fetchone()
