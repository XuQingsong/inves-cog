"""Price-only FR19 arithmetic and explicit retained-replay scope binding.

No client, database, lifecycle, or default emotional/operating conclusion.
"""

import math
from datetime import date, datetime

from inves_cog.ingest.market import regular_bounds, trading_day
from inves_cog.perception.attribution.tracks import capital_state


class InputGap(ValueError):
    """An explicit missing/unsupported input. Do not fill it from another scope."""


def _finite(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def produce_capital_track(*, scope, origin, as_of, rows, sessions):
    """first=e0, cumulative=sum(e0..ek), k=completed NYSE sessions since origin.

    `rows` are bound daily M7 residuals for the exact full scope, not member means
    or sums of standardized z scores. A future row is ignored, never consumed.
    `sessions` must enumerate all NYSE days from origin through the supplied end;
    caller source binding is retained by the runner separately.
    """
    kind, identifier = scope.get("kind"), scope.get("identifier")
    members = scope.get("members")
    if scope.get("session") != "close":
        raise InputGap("unsupported_session")
    if kind not in {"single_stock", "registered_basket"} or not identifier:
        raise InputGap("unsupported_or_ambiguous_scope")
    if not isinstance(members, list) or not members or any(not isinstance(t, str) or not t for t in members):
        raise InputGap("missing_fixed_members")
    if len(set(members)) != len(members) or kind == "single_stock" and members != [identifier]:
        raise InputGap("scope_members_mismatch")
    if kind == "registered_basket" and (
        scope.get("registered_members") is None or set(scope["registered_members"]) != set(members)
    ):
        raise InputGap("not_the_full_registered_basket")
    if not isinstance(origin, date) or isinstance(origin, datetime) or not trading_day(origin):
        raise InputGap("invalid_origin_session")
    if not isinstance(as_of, datetime) or as_of.tzinfo is None:
        raise InputGap("missing_aware_as_of")
    if (
        not isinstance(sessions, list)
        or not sessions
        or any(not isinstance(d, date) or isinstance(d, datetime) for d in sessions)
        or sessions[0] != origin
        or len(set(sessions)) != len(sessions)
        or sessions != sorted(sessions)
    ):
        raise InputGap("invalid_session_calendar")
    expected = [d for d in sessions if regular_bounds(d) is not None and regular_bounds(d)[1] <= as_of]
    if any(not trading_day(d) for d in sessions):
        raise InputGap("nontrading_session_in_calendar")
    # Reject a missing exchange day rather than silently compressing k.
    from inves_cog.ingest.market import next_trading_day

    if any(next_trading_day(a) != b for a, b in zip(sessions, sessions[1:], strict=False)):
        raise InputGap("session_calendar_gap")
    if not expected:
        raise InputGap("origin_not_completed")
    if next_trading_day(expected[-1]) <= as_of.date():
        next_close = regular_bounds(next_trading_day(expected[-1]))[1]
        if next_close <= as_of:
            raise InputGap("calendar_does_not_reach_completed_as_of")
    indexed = {}
    for row in rows:
        day = row.get("trade_date")
        if day not in expected:
            continue
        if day in indexed:
            raise InputGap("duplicate_residual_day")
        indexed[day] = row
    observed = []
    required_measurement = "m7_stock_residual" if kind == "single_stock" else "m7_registered_basket_residual"
    for day in expected:
        row = indexed.get(day)
        if row is None:
            raise InputGap("missing_residual_session")
        if row.get("measurement") != required_measurement:
            raise InputGap("wrong_residual_measurement")
        if (
            not isinstance(row.get("members"), list)
            or len(row["members"]) != len(members)
            or set(row["members"]) != set(members)
            or row.get("missing_members")
        ):
            raise InputGap("incomplete_or_changed_scope")
        if not _finite(row.get("resid")):
            raise InputGap("missing_or_nonfinite_residual")
        observed.append(row)
    first = observed[0]["resid"]
    if first == 0:
        raise InputGap("zero_initial_residual")
    result, running = [], []
    for k, row in enumerate(observed):
        running.append(row["resid"])
        cumulative = sum(running)
        if not _finite(cumulative):
            raise InputGap("nonfinite_cumulative")
        result.append(
            {
                "trade_date": row["trade_date"].isoformat(),
                "scope_kind": kind,
                "scope_id": identifier,
                "members": list(members),
                "measurement": required_measurement,
                "resid": row["resid"],
                "first": first,
                "cumulative": cumulative,
                "k": k,
                "sessions_elapsed": k,
                "retrace": 1 - cumulative / first,
                "capital": capital_state(k, cumulative, first),
                "emotion": None,
                "fundamental": None,
            }
        )
    return {
        "scope": scope,
        "origin": origin.isoformat(),
        "as_of": as_of.isoformat(),
        "rows": result,
        "only_price_capital_track": True,
        "emotion": None,
        "fundamental": None,
        "second_hit": None,
        "lifecycle": None,
        "operating_impact_proven": None,
        "k_definition": "Number of completed NYSE sessions strictly after origin; origin k=0",
        "cumulative_definition": (
            "Arithmetic sum of this fixed-scope daily M7 residuals from origin inclusive; "
            "not compounded raw prices or z scores"
        ),
    }


def _stamp(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return value if isinstance(value, datetime) and value.tzinfo is not None else None


def bound_capital_rows(anomaly, as_of):
    """Recompute a scoped retained replay; a hash/flag is provenance, not source authentication."""
    from inves_cog.ingest.market import NY, next_trading_day

    envelope = anomaly.get("capital_track")
    if not isinstance(envelope, dict) or envelope.get("version") != 1:
        raise InputGap("invalid_capital_track_version")
    now = _stamp(as_of)
    started = _stamp(anomaly.get("started_at"))
    if now is None or _stamp(envelope.get("as_of")) != now:
        raise InputGap("capital_track_as_of_mismatch")
    if started is None or _stamp(envelope.get("started_at")) != started:
        raise InputGap("capital_track_origin_mismatch")
    if (
        envelope.get("anomaly_id") != anomaly.get("anomaly_id")
        or envelope.get("origin") != str(anomaly.get("trade_date"))[:10]
    ):
        raise InputGap("capital_track_event_mismatch")
    if envelope.get("mode") != "retained_price_replay":
        raise InputGap("capital_track_mode_not_supported")
    sources = envelope.get("source_hashes")
    if (
        not isinstance(sources, dict)
        or not sources
        or any(
            not isinstance(k, str)
            or not k
            or not isinstance(v, str)
            or len(v) != 64
            or any(c not in "0123456789abcdef" for c in v)
            for k, v in sources.items()
        )
    ):
        raise InputGap("capital_track_source_binding_missing")
    scope = envelope.get("scope")
    if not isinstance(scope, dict):
        raise InputGap("capital_track_scope_missing")
    members = [row.get("ticker") if isinstance(row, dict) else row for row in anomaly.get("members") or []]
    if not members or len(set(members)) != len(members) or set(scope.get("members") or []) != set(members):
        raise InputGap("capital_track_scope_mismatch")
    if scope.get("session") != anomaly.get("session"):
        raise InputGap("capital_track_session_mismatch")
    if scope.get("kind") == "registered_basket":
        registered = next(
            (
                b
                for b in anomaly.get("basket_members") or []
                if isinstance(b, dict) and b.get("basket_id") == scope.get("identifier")
            ),
            None,
        )
        if registered is None:
            raise InputGap("capital_track_basket_binding_missing")
        registered_members = [m.get("ticker") if isinstance(m, dict) else m for m in registered.get("members") or []]
        if set(registered_members) != set(members) or set(scope.get("registered_members") or []) != set(members):
            raise InputGap("capital_track_basket_incomplete")
        if anomaly.get("basket_ids") != [scope["identifier"]] and anomaly.get("baskets") != [registered.get("name")]:
            raise InputGap("capital_track_basket_identity_mismatch")
    try:
        origin = date.fromisoformat(envelope["origin"])
        incoming = envelope["rows"]
        rows = [
            {
                **row,
                "trade_date": date.fromisoformat(row["trade_date"]),
                "missing_members": [],
                "measurement": row.get("measurement"),
            }
            for row in incoming
        ]
    except (ValueError, TypeError, KeyError):
        raise InputGap("capital_track_rows_invalid") from None
    if started.astimezone(NY).date() != origin:
        raise InputGap("capital_track_started_date_mismatch")
    days, day = [], origin
    while trading_day(day) and regular_bounds(day)[1] <= now:
        days.append(day)
        day = next_trading_day(day)
    if any(row["trade_date"] not in days for row in rows):
        raise InputGap("capital_track_uncompleted_or_wrong_origin_row")
    if any(
        row.get("emotion") is not None or row.get("fundamental") is not None or row.get("missing_members")
        for row in incoming
    ):
        raise InputGap("capital_track_not_price_only")
    result = produce_capital_track(scope=scope, origin=origin, as_of=now, rows=rows, sessions=days)
    if len(incoming) != len(result["rows"]):
        raise InputGap("capital_track_row_count_mismatch")
    tracks = []
    for supplied, computed in zip(incoming, result["rows"], strict=True):
        if any(
            supplied.get(key) != computed[key]
            for key in ("trade_date", "first", "cumulative", "k", "sessions_elapsed", "capital")
        ):
            raise InputGap("capital_track_arithmetic_mismatch")
        metrics = {key: computed[key] for key in ("resid", "first", "cumulative", "k", "retrace", "measurement")}
        metrics.update(
            version=1,
            scope=scope,
            origin=envelope["origin"],
            started_at=envelope["started_at"],
            as_of=envelope["as_of"],
            source_hashes=dict(sources),
            mode=envelope["mode"],
            source_authentication="caller_supplied_retained_snapshot_not_verified_by_hash_shape",
        )
        tracks.append(
            {
                "trade_date": computed["trade_date"],
                "emotion": None,
                "capital": computed["capital"],
                "fundamental": None,
                "price_only": True,
                "metrics": {"price_capital": metrics},
            }
        )
    return tracks
