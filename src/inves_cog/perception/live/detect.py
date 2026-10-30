"""B-070: 5-minute live anomaly detection (stocks, baskets, market).

All sigmas are daily-scale (data_quality 'daily_sigma'); no time scaling.
Thresholds come from detect.limits() — no new params.
"""

import numpy as np


def stock_hits(quotes, l3_of, sigmas, rule, session):
    """quotes[ticker] = {ret, as_of}; resid = ret - median(>=2 basket mates)."""
    hits = []
    for ticker, q in quotes.items():
        ret = q.get("ret")
        if ret is None:
            continue
        primary = l3_of.get(ticker)
        mates = []
        if primary is not None:
            for m in primary.get("members") or []:
                name = m["ticker"] if isinstance(m, dict) else m
                if name != ticker and name in quotes and quotes[name].get("ret") is not None:
                    mates.append(quotes[name]["ret"])
        resid = ret - float(np.median(mates)) if len(mates) >= 2 else ret
        sigma = sigmas.get(ticker)
        z = None if sigma in (None, 0) else resid / sigma
        if (
            abs(ret) >= rule["path_b_abs_ret"]
            and np.sign(ret) == np.sign(resid)
            and ret != 0
            and z is not None
            and abs(z) >= rule["path_b_z"]
        ):
            hits.append(
                {
                    "scope": "stock",
                    "subject": ticker,
                    "ret": ret,
                    "z": z,
                    "direction": "up" if ret > 0 else "down",
                    "as_of": q.get("as_of"),
                }
            )
    return hits


def basket_hits(quotes, baskets, basket_sigmas, rule):
    hits = []
    for basket in baskets:
        members = [(m["ticker"] if isinstance(m, dict) else m) for m in basket.get("members") or []]
        rets = {t: quotes[t]["ret"] for t in members if t in quotes and quotes[t].get("ret") is not None}
        if len(rets) < 2:
            continue
        ret_ew = float(np.mean(list(rets.values())))
        sigma = basket_sigmas.get(basket["basket_id"])
        z = None if sigma in (None, 0) else ret_ew / sigma
        share = sum(1 for v in rets.values() if np.sign(v) == np.sign(ret_ew)) / len(rets) if ret_ew != 0 else 0
        if z is not None and abs(z) >= rule["path_a_z"] and share >= rule["path_a_same_sign"]:
            hits.append(
                {
                    "scope": "basket",
                    "subject": basket["basket_id"],
                    "ret": ret_ew,
                    "z": z,
                    "direction": "up" if ret_ew > 0 else "down",
                    "members": rets,
                }
            )
    return hits


def market_hits(quotes, rule):
    hits = []
    for idx, key in (("SPY", "spy_abs"), ("QQQ", "qqq_abs")):
        q = quotes.get(idx)
        if q and q.get("ret") is not None and abs(q["ret"]) >= rule[key]:
            hits.append(
                {
                    "scope": "market",
                    "subject": idx,
                    "ret": q["ret"],
                    "z": None,
                    "direction": "up" if q["ret"] > 0 else "down",
                    "as_of": q.get("as_of"),
                }
            )
    return hits


def apply_round(connection, hits, now, day, session):
    """Upsert hits into perception.live_anomalies; stale actives -> faded."""
    import json

    keep = set()
    for hit in hits:
        direction = hit["direction"]
        keep.add((hit["scope"], hit["subject"], direction))
        connection.execute(
            """INSERT INTO perception.live_anomalies
               (trade_date, session, scope, subject, direction, first_seen_at, last_seen_at,
                first_ret, last_ret, peak_ret, last_z, peak_z, quote_time, members, data_quality,
                status, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',now())
               ON CONFLICT (trade_date, session, scope, subject, direction) DO UPDATE SET
                last_seen_at=EXCLUDED.last_seen_at,
                last_ret=EXCLUDED.last_ret,
                last_z=EXCLUDED.last_z,
                quote_time=EXCLUDED.quote_time,
                members=EXCLUDED.members,
                peak_ret=CASE WHEN abs(EXCLUDED.last_ret) > abs(perception.live_anomalies.peak_ret)
                              THEN EXCLUDED.last_ret ELSE perception.live_anomalies.peak_ret END,
                peak_z=CASE WHEN EXCLUDED.last_z IS NOT NULL
                                 AND (perception.live_anomalies.peak_z IS NULL
                                      OR abs(EXCLUDED.last_z) > abs(perception.live_anomalies.peak_z))
                            THEN EXCLUDED.last_z ELSE perception.live_anomalies.peak_z END,
                status='active', updated_at=now()""",
            (
                day,
                session,
                hit["scope"],
                hit["subject"],
                direction,
                now,
                now,
                hit["ret"],
                hit["ret"],
                hit["ret"],
                hit.get("z"),
                hit.get("z"),
                hit.get("as_of"),
                json.dumps(hit.get("members") or {}),
                ["daily_sigma"],
            ),
        )
    if keep:
        connection.execute(
            """UPDATE perception.live_anomalies SET status='faded', updated_at=now()
               WHERE trade_date=%s AND session=%s AND status='active'
               AND (scope, subject, direction) NOT IN
                   (SELECT * FROM (VALUES (NULL,NULL,NULL)"""
            + "".join(",(%s,%s,%s)" for _ in keep)
            + ") v)",  # row-comparison tuple
            (day, session, *(t for k in keep for t in k)),
        )
    else:
        connection.execute(
            "UPDATE perception.live_anomalies SET status='faded', updated_at=now()"
            " WHERE trade_date=%s AND session=%s AND status='active'",
            (day, session),
        )
    return len(hits)
