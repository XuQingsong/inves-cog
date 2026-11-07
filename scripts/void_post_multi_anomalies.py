"""Void post-session anomalies whose entry paths are all multi_*.

They inherited the close-session daily-residual z (fixed in detect.py for new
rows); stored rows are kept but marked 已作废·统计口径错误 so readers skip them.

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
    "SELECT anomaly_id, status FROM perception.anomalies "
    "WHERE session='post' AND entry_paths <@ '{multi_3d,multi_5d}'::text[] "
    "ORDER BY trade_date, anomaly_id"
)
NEW_STATUS = "已作废·统计口径错误"


def main():
    import psycopg
    from psycopg.rows import dict_row

    from inves_cog.ingest.settings import read_environment

    values = read_environment(ROOT / ".env", environ={})
    conn = psycopg.connect(values["INVES_COG_DATABASE_URL"], row_factory=dict_row)
    rows = conn.execute(SELECT).fetchall()
    targets = [r for r in rows if r["status"] != NEW_STATUS]
    print(f"matched {len(rows)} post multi_* rows, {len(targets)} need voiding")
    if "--apply" not in sys.argv:
        for r in rows:
            print(" ", r["anomaly_id"], r["status"])
        print("dry-run only; pass --apply to update")
        return
    evidence = ROOT / "ops" / f"swe2-void-post-multi-{datetime.now(timezone.utc).date().isoformat()}.json"
    evidence.parent.mkdir(exist_ok=True)
    evidence.write_text(json.dumps({"rows": targets, "new_status": NEW_STATUS}, ensure_ascii=False, indent=2))
    print("evidence:", evidence)
    with conn.transaction():
        result = conn.execute(
            "UPDATE perception.anomalies SET status=%s WHERE anomaly_id=ANY(%s)",
            (NEW_STATUS, [r["anomaly_id"] for r in targets]),
        )
        updated = result.rowcount
        if updated != len(targets):
            raise SystemExit(f"rollback: updated {updated} != expected {len(targets)}")
    print(f"voided {updated} rows")


if __name__ == "__main__":
    main()
