"""P2-M1: backfill flows.barometer_daily over a range."""

import argparse
import os
from datetime import date

import psycopg
from psycopg.rows import dict_row

from inves_cog.perception.barometer.run import persist, run_range

p = argparse.ArgumentParser()
p.add_argument("--start", type=date.fromisoformat, default=date(2018, 1, 2))
p.add_argument("--end", type=date.fromisoformat, required=True)
p.add_argument("--dry", action="store_true")
a = p.parse_args()
conn = psycopg.connect(os.environ["INVES_COG_DATABASE_URL"], row_factory=dict_row, autocommit=True)
recs = run_range(conn, a.start, a.end)
if not a.dry:
    persist(conn, recs)
print(
    {
        "days": len(recs),
        "first": str(recs[0]["date"].date()),
        "last": str(recs[-1]["date"].date()),
        "sample": {k: recs[-1][k] for k in ("fear", "greed", "nature")},
    }
)
