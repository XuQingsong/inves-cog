"""Conservative adapters for accepted M2 period identities and timestamped consensus."""

from collections import defaultdict
from datetime import date

from inves_cog.ingest.fundamentals.consensus import derive_consensus
from inves_cog.overlay.rules import timestamp
from inves_cog.trading.scoring.curves import finite


def as_date(value):
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _quarter(value):
    day = as_date(value)
    return day.year * 4 + (day.month - 1) // 3


def segment_inputs(rows, *, asof):
    visible = [
        row
        for row in rows
        if row.get("filed") and as_date(row["filed"]) <= asof and row.get("period_len") == "Q" and row.get("period_end")
    ]
    if not visible or len({row.get("axis") for row in visible}) != 1:
        return None
    groups = defaultdict(dict)
    for row in sorted(visible, key=lambda r: as_date(r["filed"])):
        key = (row.get("segment_raw"), row.get("recast_group"))
        groups[key][_quarter(row["period_end"])] = row
    latest = max(_quarter(row["period_end"]) for row in visible)
    result = []
    for (name, recast), periods in groups.items():
        current = periods.get(latest)
        if not name or current is None:
            continue
        recent = [periods.get(q) for q in range(latest - 3, latest + 1)]
        if any(row is None or not finite(row.get("revenue")) for row in recent):
            return None
        previous = periods.get(latest - 4) or {}
        margins = current.get("margin_pct"), previous.get("margin_pct")
        margin_delta = margins[0] - margins[1] if all(finite(v) for v in margins) else None
        yoy = current.get("yoy_pct")
        if not finite(yoy) and finite(previous.get("revenue")) and previous["revenue"] > 0:
            yoy = (current["revenue"] / previous["revenue"] - 1) * 100
        result.append(
            {
                "name": name,
                "recast_group": recast,
                "revenue_4q": [row["revenue"] for row in recent],
                "margin_change_pp": margin_delta,
                "revenue_yoy_pct": yoy,
                "source_row_ids": [row.get("row_id") for row in recent],
            }
        )
    return result if len(result) >= 2 else None


def visible_consensus(rows, *, cutoff, asof):
    return [
        row
        for row in rows
        if row.get("as_of")
        and as_date(row["as_of"]) <= asof
        and row.get("captured_at")
        and timestamp(row["captured_at"]) <= cutoff
    ]


def event_eps_change(rows, *, event_at, cutoff, asof):
    current_rows = visible_consensus(rows, cutoff=cutoff, asof=asof)
    baseline_rows = [row for row in current_rows if timestamp(row["captured_at"]) <= event_at]

    def order(row):
        return as_date(row["as_of"]), timestamp(row["captured_at"])

    current, baseline = max(current_rows, key=order, default=None), max(baseline_rows, key=order, default=None)
    if current is None or baseline is None or not current.get("fy_cy") or current["fy_cy"] != baseline.get("fy_cy"):
        return None
    value, base = current.get("eps_cy"), baseline.get("eps_cy")
    return (value / base - 1) * 100 if finite(value) and finite(base) and base > 0 else None


def consensus_revision(rows, *, ticker, asof, cutoff):
    visible = visible_consensus(rows, asof=asof, cutoff=cutoff)
    return derive_consensus(visible, ticker=ticker, as_of=asof).get("chg_30d_pct")


def contract_observations(*, scores, factor_inputs, plan, ledger, events, consensus, signal_day, cutoff):
    """Preserve actual plan/order identities; do not infer a missing opening/holding state."""
    state = (ledger or {}).get("state") or {}
    positions = state.get("positions") or {}
    orders = (plan or {}).get("orders") or []
    original = [row.get("original_order") for row in (plan or {}).get("cancels") or [] if row.get("original_order")]
    result = {}
    for ticker, score in scores.items():
        position = positions.get(ticker)
        holding = position is not None if ledger is not None else None
        actual = [row for row in orders if row.get("ticker") == ticker]
        intended = actual + [row for row in original if row.get("ticker") == ticker]
        buys = [row for row in intended if str(row.get("action")).startswith("buy")]
        tech, financial = score.get("tech") or {}, factor_inputs.get(ticker) or {}
        holding_id = None
        if position and position.get("entry_index") is not None and position.get("entry_state") is not None:
            holding_id = ":".join(
                str(value)
                for value in (
                    (plan or {}).get("portfolio_id", "paper-fixed"),
                    ticker,
                    position["entry_index"],
                    position["entry_state"],
                )
            )
        event_inputs, tags = {}, set()
        for event in events:
            member = next((member for member in event.get("affected") or [] if member.get("ticker") == ticker), None)
            if member is None:
                continue
            if member.get("divergence_tag") is not None:
                tags.add(member["divergence_tag"])
            established = timestamp(event.get("created_at"))
            event_inputs[event["event_id"]] = {
                "eps_change_pct": event_eps_change(
                    consensus.get(ticker) or [], event_at=established, cutoff=cutoff, asof=signal_day
                )
                if established
                else None
            }
        amount = (
            sum(row["notional_est"] for row in buys)
            if buys and all(finite(row.get("notional_est")) for row in buys)
            else None
        )
        factor_inputs[ticker]["plan_buy_amount"] = amount
        result[ticker] = {
            "holding": holding,
            "holding_id": holding_id,
            "close": tech.get("price"),
            "ma50": tech.get("ma50"),
            "source_order_ids": [row["order_id"] for row in intended if row.get("order_id")],
            "rule_a_action": [row.get("action") for row in actual],
            "base_opening_order": bool(buys) if holding is False else (False if holding is True else None),
            "actual_watchlist_wave_buy": any(row.get("action") == "buy_watch" for row in actual),
            "watchlist_wave_eligible": True if any(row.get("action") == "buy_watch" for row in intended) else None,
            "divergence_tag": next(iter(tags)) if len(tags) == 1 else None,
            "event_inputs": event_inputs,
            "eps_revision_30d_pct": financial.get("eps_revision_30d_pct"),
            "hysteresis": {
                "event": "filing" if financial.get("filed") else "daily",
                "filing_id": str(financial["filed"]) if financial.get("filed") else None,
                "growth": (score.get("books") or {}).get("growth"),
                "raw_quality": (score.get("books") or {}).get("quality"),
                "rev_accel_pp": financial.get("rev_accel_pp"),
                "gm_change_pp": financial.get("gm_change_pp"),
            },
        }
    return result
