"""Persist weekly unnamed proposals; no automatic basket membership changes."""

from datetime import timedelta

import pandas as pd
from psycopg.types.json import Jsonb

from inves_cog.marketstate.clustering import suggestions


def weekly_suggestions(repository, *, day, clock):
    rows = repository.connection.execute(
        "SELECT trade_date,ticker,resid FROM marketstate.daily WHERE session='close' "
        "AND trade_date BETWEEN %s AND %s ORDER BY trade_date,ticker",
        (day - timedelta(days=100), day),
    ).fetchall()
    frame = pd.DataFrame(rows)
    returns = (
        frame.pivot(index="trade_date", columns="ticker", values="resid").sort_index().tail(60)
        if rows
        else pd.DataFrame()
    )
    proposed = suggestions(returns, existing=repository.baskets())
    reason = "insufficient_history" if len(returns) < 60 else None
    monday = day - timedelta(days=day.weekday())
    repository.connection.execute(
        "INSERT INTO graph.cluster_suggestions (week_start,as_of,proposals,null_reason,created_at) "
        "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (week_start) DO UPDATE SET as_of=EXCLUDED.as_of,"
        "proposals=EXCLUDED.proposals,null_reason=EXCLUDED.null_reason,created_at=EXCLUDED.created_at",
        (monday, day, Jsonb(proposed), reason, clock.now_utc()),
    )
    return {"processed_count": len(proposed), "sample_days": len(returns), "null_reason": reason, "proposals": proposed}
