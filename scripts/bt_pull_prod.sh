#!/bin/bash
# Pull backtest-needed tables from prod → local inves_cog_bt. Gentle on prod:
# single pg_dump, idle-class I/O, run only outside US market hours.
set -e
OUT=${1:-~/inves-cog-bt}
mkdir -p "$OUT"
DUMP="$OUT/prod_bt.dump"
# only the tables prepare_inputs/run_backtest/evaluate read (grepped from code):
TABLES="ingest.bars_daily ingest.macro_observations fundamentals.fin_state ingest.sec_filings fundamentals.consensus_snapshot"
TARGS=$(for t in $TABLES; do echo "-t $t"; done | tr '\n' ' ')
echo "dumping $(echo $TABLES | wc -w) tables → $DUMP"
ssh -o ConnectTimeout=30 claude-ubuntu "nice -n 19 ionice -c3 docker exec inves-cog-database pg_dump -Fc $TARGS -U inves_cog_admin -d inves_cog" > "$DUMP"
echo "restoring → inves_cog_bt"
pg_restore -h localhost -p 5432 -d inves_cog_bt --no-owner --no-privileges --clean --if-exists "$DUMP" || pg_restore -h localhost -p 5432 -d inves_cog_bt --no-owner --no-privileges "$DUMP"
echo "done — dump at $DUMP"
