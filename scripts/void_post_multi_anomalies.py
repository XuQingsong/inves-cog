"""Void post-session anomalies whose entry paths are all multi_*.

They inherited the close-session daily-residual z (fixed in detect.py for new
rows); stored rows are kept but marked via a `voided` object in data_quality so
readers skip them. status has a CHECK constraint (M7 contract) and is unchanged.

Usage:
    python scripts/void_post_multi_anomalies.py            # dry-run (default)
    python scripts/void_post_multi_anomalies.py --apply    # evidence file + one transaction
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECT = (
    "SELECT anomaly_id, status, data_quality FROM perception.anomalies "
    "WHERE session='post' AND entry_paths <@ '{multi_3d,multi_5d}'::text[] "
    "ORDER BY trade_date, anomaly_id"
)
VOID_REASON = "盘后多日路径沿用收盘日线残差z"
VOID_FIXED_IN = "dbc6465"
UPDATE = (
    "UPDATE perception.anomalies SET data_quality = "
    "coalesce(data_quality,'[]'::jsonb) || '[\"voided\"]'::jsonb "
    "WHERE anomaly_id=ANY(%s) AND NOT (coalesce(data_quality,'[]'::jsonb) ? 'voided')"
)


def main():
    import psycopg
    from psycopg.rows import dict_row

    from inves_cog.ingest.settings import read_environment

    values = read_environment(ROOT / ".env", environ={})
    conn = psycopg.connect(values["INVES_COG_PERCEPTION_DATABASE_URL"], row_factory=dict_row)
    rows = conn.execute(SELECT).fetchall()
    targets = [r for r in rows if "voided" not in (r.get("data_quality") or [])]
    print(f"matched {len(rows)} post multi_* rows, {len(targets)} need voiding")
    if "--apply" not in sys.argv:
        for r in rows:
            print(" ", r["anomaly_id"], r["status"], "voided" if "voided" in (r.get("data_quality") or []) else "")
        print("dry-run only; pass --apply to update")
        return
    evidence = ROOT / "ops" / f"swe2-void-post-multi-{datetime.now(timezone.utc).date().isoformat()}.json"
    evidence.parent.mkdir(exist_ok=True)
    evidence.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "anomaly_id": r["anomaly_id"],
                        "status": r["status"],
                        "data_quality": r["data_quality"],
                    }
                    for r in targets
                ],
                "void": {"reason": VOID_REASON, "fixed_in": VOID_FIXED_IN},
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print("evidence:", evidence)
    with conn.transaction():
        result = conn.execute(
            UPDATE,
            ([r["anomaly_id"] for r in targets],),
        )
        updated = result.rowcount
        if updated != len(targets):
            raise SystemExit(f"rollback: updated {updated} != expected {len(targets)}")
    print(f"voided {updated} rows")


if __name__ == "__main__":
    main()
