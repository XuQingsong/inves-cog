"""Read-only TSM PIT score history; never overwrite missing financial facts."""

import csv
import json
import signal
from datetime import date
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from inves_cog.backtest.loader import BacktestLoader
from inves_cog.ingest.fundamentals.state import StateStore
from inves_cog.trading.scoring import FOREIGN, score_history


def main():
    signal.alarm(120)
    out = Path("handoff/A031/evidence")
    with psycopg.connect(
        host="127.0.0.1",
        dbname="inves_cog_bt",
        row_factory=dict_row,
        connect_timeout=5,
        options="-c default_transaction_read_only=on -c statement_timeout=30000",
    ) as db:
        loader = BacktestLoader(db)
        states = loader.states_for("TSM", end=date(2026, 10, 30))
        store = StateStore(states)
        scores = score_history(
            "TSM",
            loader.bars("TSM", end=date(2026, 10, 30)),
            state_asof=store.state_asof,
            start=date(2018, 1, 2),
            end=date(2026, 10, 30),
        )
    rows = []
    for row in scores:
        state = store.state_asof("TSM", row["signal_date"], "fixed")
        rows.append(
            dict(
                date=row["signal_date"],
                tier=row["tier"],
                tradable=row["tradable"],
                foreign_issuer="TSM" in FOREIGN,
                **row["books"],
                filed=state.filed if state else None,
                period_end=state.period_end if state else None,
                eps_ttm=state.values.get("eps_ttm") if state else None,
                health_codes=";".join(row["health_codes"]),
                null_reason=row.get("null_reason"),
            )
        )
    with (out / "tsm-tier-history.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for file in (out / "r3/baseline.json",):
        value = json.loads(file.read_text())
        for row in value["daily"]:
            if row["ticker"] in FOREIGN and "foreign_issuer" not in row["blockers"]:
                row["blockers"].append("foreign_issuer")
        for ticker, summary in value["gate_summary"].items():
            if ticker in FOREIGN:
                summary["gate_days"]["foreign_issuer"] = sum(
                    r["ticker"] == ticker and "snapshot_missing" not in r["blockers"] for r in value["daily"]
                )
        file.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    (out / "tsm-tier-summary.json").write_text(
        json.dumps(
            dict(
                days=len(rows),
                tier_days=sum(r["tier"] is not None for r in rows),
                tradable_days=sum(r["tradable"] for r in rows),
                foreign_rule_block=True,
                note="EPS/network repair alone cannot remove the frozen foreign-issuer eligibility gate",
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
