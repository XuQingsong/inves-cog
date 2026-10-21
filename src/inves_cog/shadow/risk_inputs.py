"""Read-only M4/M6/M1 provenance for S10; missing history never means clear."""

from inves_cog.ingest.market import exchange
from inves_cog.shadow.normalization import as_date
from inves_cog.shadow.settings import settings
from inves_cog.trading.scoring.curves import finite


def s1_from_history(history):
    cfg = settings()["s10"]
    periods = {}
    for row in history:
        if row.get("period_end"):
            periods.setdefault(as_date(row["period_end"]), row)
    rows = [periods[key] for key in sorted(periods, reverse=True)]
    if not rows:
        return None
    accelerations = [row.get("rev_accel_pp") for row in rows[:2]]
    slowing = (
        all(value <= cfg["s1_acceleration_max"] for value in accelerations)
        if len(accelerations) == 2 and all(finite(v) for v in accelerations)
        else None
    )
    latest = as_date(rows[0]["period_end"])
    prior = next(
        (
            row
            for row in rows[1:]
            if as_date(row["period_end"]).year == latest.year - 1 and as_date(row["period_end"]).month == latest.month
        ),
        {},
    )
    current, old = rows[0].get("rev_q_yoy"), prior.get("rev_q_yoy")
    halved = current < old * cfg["s1_prior_year_ratio"] if finite(current) and finite(old) else None
    if slowing is True or halved is True:
        return True
    return False if slowing is False and halved is False else None


def shock_identity(rows, day):
    cal, expected, earliest = exchange(day.year), day, None
    for row in rows:
        current = as_date(row["trade_date"])
        if current != expected:
            return None
        if row.get("shock_flag") is False:
            return str(earliest) if earliest else None
        if row.get("shock_flag") is not True:
            return None
        earliest = current
        expected = cal.previous_session(str(current)).date()
    return None


def attach_risk_inputs(db, *, factor_inputs, observations, history, plan, ledger, m8, day, cutoff):
    orders = [
        row for row in (plan or {}).get("orders") or [] if {"M-51", "M-55"}.intersection(row.get("rule_ids") or [])
    ]
    if not orders:
        return
    markets = db.execute(
        "SELECT trade_date,shock_flag FROM marketstate.market WHERE trade_date<=%s ORDER BY trade_date DESC", (day,)
    ).fetchall()
    current = markets[0] if markets and as_date(markets[0]["trade_date"]) == day else {}
    shock = shock_identity(markets, day)
    structure = {
        row["ticker"]: row
        for row in db.execute(
            "SELECT ticker,resid_5d_z FROM marketstate.daily WHERE trade_date=%s AND session='close'", (day,)
        ).fetchall()
    }
    lower = day
    for _ in range(settings()["s10"]["earnings_sessions"] - 1):
        lower = exchange(lower.year).previous_session(str(lower)).date()
    reactions = {
        row["ticker"]
        for row in db.execute(
            "SELECT ticker FROM ingest.earnings_events WHERE reaction_day BETWEEN %s AND %s AND fetched_at<=%s "
            "AND (superseded_at IS NULL OR superseded_at>%s)",
            (lower, day, cutoff, cutoff),
        ).fetchall()
    }
    prior = db.execute(
        "SELECT value,gap_detail FROM factor_shadow.daily WHERE factor_id='F-08' AND date<%s AND generated_at<=%s",
        (plan["trade_date"], cutoff),
    ).fetchall()
    reviewed = set()
    for row in prior:
        details = row["value"] if isinstance(row["value"], list) else [row["gap_detail"]]
        reviewed.update(
            (item.get("holding_id"), item.get("shock_id")) for item in details if item.get("eligible") is True
        )
    positions = ((ledger or {}).get("state") or {}).get("positions") or {}
    equity = (ledger or {}).get("equity")
    for order in orders:
        ticker = order["ticker"]
        observation, position = observations.get(ticker) or {}, positions.get(ticker) or {}
        price, cost, shares = observation.get("close"), position.get("avg_cost"), position.get("shares")
        loss = (
            max(0.0, (cost - price) * shares / equity * 100)
            if all(finite(v) for v in (cost, price, shares, equity)) and equity > 0
            else None
        )
        identity = observation.get("holding_id")
        item = {
            "rule_id": next(rule for rule in order["rule_ids"] if rule in ("M-51", "M-55")),
            "source_order_id": order.get("order_id"),
            "holding_id": identity,
            "shock_id": shock,
            "shock_flag": current.get("shock_flag"),
            "resid_5d_z": (structure.get(ticker) or {}).get("resid_5d_z"),
            "earnings_reaction_5d": ticker in reactions,
            "s4_triggered": False if ticker not in reactions else None,
            # An actual M51/M55 order proves M4's higher-priority M50 did not win.
            "m50_triggered": False,
            "new_s1": s1_from_history(history.get(ticker) or []),
            "loss_equity_pct": loss,
            "price": price,
            "tier": order.get("tier"),
            "systemic_event_tag": (m8.get("market") or {}).get("systemic_events"),
            "already_reviewed": (identity, shock) in reviewed if identity and shock else None,
        }
        factor_inputs.setdefault(ticker, {}).setdefault("s10_orders", []).append(item)
