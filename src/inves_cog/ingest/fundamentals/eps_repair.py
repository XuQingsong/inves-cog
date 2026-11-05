"""Narrow, idempotent missing-EPS repairs; preserve all other historical facts."""

import math
from copy import deepcopy


def evidence_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from evidence_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from evidence_nodes(child)


def repair_missing_eps(original, candidate):
    if original.values.get("eps_ttm") is not None or candidate.values.get("eps_ttm") is None:
        return None
    if (original.ticker, original.extractor, original.filed) != (
        candidate.ticker,
        candidate.extractor,
        candidate.filed,
    ):
        raise ValueError("EPS repair must use the same issuer and PIT filing")
    if original.extractor != "fixed" or original.period_end != candidate.period_end:
        raise ValueError("EPS repair period mismatch")
    proof = candidate.field_sources.get("eps_ttm", {})
    nodes = list(evidence_nodes(proof))
    if any(str(n.get("filed") or "")[:10] > str(original.filed) for n in nodes):
        raise ValueError("EPS repair PIT evidence is not yet public")
    if not any(n.get("eps_fallback") == "class_a_missing_company_period" for n in nodes):
        raise ValueError("EPS repair needs dimensional fallback provenance")
    eps = candidate.values["eps_ttm"]
    if not isinstance(eps, (float, int)) or not math.isfinite(eps):
        raise ValueError("EPS repair value invalid")
    result = deepcopy(original)
    for key in ("eps_ttm", "eps_growth"):
        result.values[key] = candidate.values.get(key)
        result.field_sources[key] = deepcopy(candidate.field_sources.get(key, {}))
    result.field_sources["eps_repair_a030"] = {
        "method": "missing_company_eps_only",
        "filed": str(original.filed),
        "period_end": str(original.period_end),
        "source": deepcopy(proof),
        "unchanged_fields": "all values except eps_ttm and eps_growth",
    }
    codes = set(original.health_codes) - {"ok"}
    if all(result.values.get(k) is not None for k in ("rev_ttm", "eps_ttm", "shares")):
        codes.discard("core_field_missing")
    result.health_codes = sorted(codes) or ["ok"]
    return result


def persist_eps_patches(connection, changes):
    """Only the existing ingest business role may apply accepted, missing Visa EPS patches."""
    from datetime import date

    from psycopg.types.json import Jsonb

    from inves_cog.ingest.fundamentals.repository import state_from_row, text

    role = connection.execute(
        "SELECT pg_has_role(current_user,'role_ingest','USAGE') AS ingest,"
        "pg_has_role(current_user,'inves_cog_admin','MEMBER') AS admin"
    ).fetchone()
    if role["admin"] or not role["ingest"]:
        raise ValueError("EPS backfill requires the existing non-admin role_ingest business login")
    counts = {"updated": 0, "already_present": 0, "missing_state": 0}
    with connection.transaction():
        for change in changes:
            if change["ticker"] != "V":
                raise ValueError("A-030 backfill is limited to confirmed Visa EPS gaps")
            day = date.fromisoformat(change["filed"])
            row = connection.execute(
                "SELECT * FROM fundamentals.fin_state WHERE ticker='V' AND extractor='fixed' AND filed=%s FOR UPDATE",
                (day,),
            ).fetchone()
            if row is None:
                counts["missing_state"] += 1
                continue
            original = state_from_row(row)
            candidate = deepcopy(original)
            candidate.period_end = date.fromisoformat(change["period_end"])
            candidate.values.update(eps_ttm=change["eps_ttm"], eps_growth=change["eps_growth"])
            candidate.field_sources.update(change["field_sources_patch"])
            patched = repair_missing_eps(original, candidate)
            if patched is None:
                counts["already_present"] += 1
                continue
            proof = {k: patched.field_sources[k] for k in ("eps_ttm", "eps_growth", "eps_repair_a030")}
            connection.execute(
                "UPDATE fundamentals.fin_state SET eps_ttm=%s,eps_growth=%s,health_codes=%s,"
                "field_sources=field_sources || %s WHERE ticker='V' AND extractor='fixed' AND filed=%s "
                "AND eps_ttm IS NULL",
                (
                    patched.values["eps_ttm"],
                    patched.values["eps_growth"],
                    patched.health_codes,
                    Jsonb(proof, dumps=text),
                    day,
                ),
            )
            counts["updated"] += 1
    return counts
