"""M5-only canonical split units, retaining the upstream value and exact source chain."""

import json
import math
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def cutoff(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("EPS unit cutoff must have a timezone")
        return value
    return datetime.combine(date.fromisoformat(str(value)[:10]), time.max, NY)


def visible_events(events, as_of):
    when = cutoff(as_of)
    return [
        e for e in events if datetime.fromisoformat(e["effective_at"]) <= when and cutoff(e["announced_on"]) <= when
    ]


def terms(source, sign=1):
    # M2 EPS Q4 is annual - Q1 - Q2 - Q3. Expand its exact provenance
    # before deciding the TTM basis: the matching quarter terms cancel.
    if source.get("derivation") == "eps_q4_derived" and len(source.get("inputs", [])) == 4:
        for index, child in enumerate(source["inputs"]):
            yield from terms(child, sign if index == 0 else -sign)
    else:
        yield json.dumps(source, sort_keys=True, ensure_ascii=False), sign


def alias_event(adjustment, events):
    for event in events:
        for alias in event["aliases"]:
            if (
                adjustment.get("ratio") == event["ratio"]
                and adjustment.get("event_date") == alias["end"]
                and adjustment.get("first_reported") == alias["filed"]
                and adjustment.get("accession") == alias["accession"]
            ):
                return event
    return None


def unmapped_observations(states, events, as_of):
    """Unknown observations may affect earlier annual units even if Q4 cancels them."""
    day = str(cutoff(as_of).astimezone(NY).date())
    found = {}

    def walk(value):
        if isinstance(value, dict):
            for adjustment in value.get("split_adjustment", []):
                if adjustment.get("first_reported", "9999") <= day and alias_event(adjustment, events) is None:
                    found[json.dumps(adjustment, sort_keys=True)] = deepcopy(adjustment)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for state in states:
        if str(state.filed) <= day:
            walk(state.field_sources.get("eps_ttm", {}))
    return list(found.values())


def normalize_eps(value, source, events, as_of, *, periods=4):
    active = visible_events(events, as_of)
    audit = {
        "raw_value": value,
        "raw_source": deepcopy(source),
        "as_of": str(as_of),
        "target_event_ids": [e["id"] for e in active],
        "public_reference_capture": "verified_later; original_system_capture_unknown",
        "status": "known",
        "terms": [],
    }

    def unknown(reason):
        return None, {**audit, "status": "unknown", "reason": reason, "remaining_factor": None}

    if value is None:
        return None, {**audit, "status": "missing", "remaining_factor": None}
    components = source.get("components", [])[-periods:]
    if not components:
        return unknown("EPS source basis missing") if active else (value, {**audit, "remaining_factor": 1})
    expression = Counter()
    expanded_count = 0
    for component in components:
        for key, sign in terms(component):
            expression[key] += sign
            expanded_count += 1
    audit["cancelled_terms"] = (expanded_count - sum(abs(v) for v in expression.values())) // 2
    target = math.prod(e["ratio"] for e in active)
    factors = []
    for key, coefficient in expression.items():
        if not coefficient:
            continue
        leaf = json.loads(key)
        filed = leaf.get("filed")
        if active and (not filed or not leaf.get("accn")):
            return unknown("EPS source filing basis missing")
        if filed and filed > str(cutoff(as_of).astimezone(NY).date()):
            return unknown("future source filing")
        # A later filing can already restate an earlier comparative period.
        # These issuer-specific restatement boundaries are verified in SEC notes;
        # period_end alone never determines a source's included events.
        intrinsic = [e for e in active if filed and filed >= e["restated_from_filed"]]
        applied = []
        for adjustment in leaf.get("split_adjustment", []):
            if adjustment.get("first_reported", "9999") > str(cutoff(as_of).astimezone(NY).date()):
                return unknown("future split observation in selected EPS source")
            event = alias_event(adjustment, active)
            if event is None:
                return unknown("unrecognized or not-yet-effective split observation")
            applied.append(event)
        factor = math.prod(e["ratio"] for e in intrinsic + applied) / target
        included = sorted({e["id"] for e in intrinsic + applied})
        audit["terms"].append(
            {
                "coefficient": coefficient,
                "source_filed": filed,
                "source_accession": leaf.get("accn"),
                "source_end": leaf.get("end"),
                "intrinsic_event_ids": [e["id"] for e in intrinsic],
                "applied_event_ids": [e["id"] for e in applied],
                "included_event_ids": included,
                "duplicate_event_count": len(intrinsic + applied) - len(included),
                "remaining_factor": factor,
            }
        )
        factors.append(factor)
    # Without the original component values, unequal unit factors cannot be
    # applied to a sum. Report the exact gap rather than infer it from NI/EPS.
    if not factors or any(not math.isclose(f, factors[0], rel_tol=1e-12) for f in factors):
        return unknown("mixed EPS source units; original term values unavailable")
    factor = factors[0]
    return value * factor, {**audit, "remaining_factor": factor}
