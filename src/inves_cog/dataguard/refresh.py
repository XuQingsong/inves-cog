"""Daily bounded refresh for sources whose published history can fill late gaps."""

from datetime import timedelta

from psycopg.types.json import Jsonb

from inves_cog.dataguard.calendar import NY
from inves_cog.dataguard.store import Store
from inves_cog.flows import backfill
from inves_cog.flows.store import polite_http
from inves_cog.ingest.repository import Repository

DEFAULT_RAW = "/home/claudeuser/inves-cog-data/flows_raw"
REFRESH_ENTRIES = {"fred", "ofr", "cftc", "cboe_idx", "cboe_pc", "vxtlt"}


def configured(item):
    days = (item.backfill or {}).get("refresh_days")
    if not days or (item.backfill or {}).get("entry") not in REFRESH_ENTRIES:
        return None
    return int(days)


def window(item, now, days_count):
    today = now.astimezone(NY).date()
    return [
        today - timedelta(days=offset)
        for offset in range(days_count - 1, -1, -1)
        if not item.active_since or today - timedelta(days=offset) >= item.active_since
    ]


def run(reader, writer, items, values, now):
    http = polite_http()
    ran = []
    for item in items:
        days_count = configured(item)
        if not days_count or getattr(item, "disabled", None):
            continue
        state = writer.execute(
            "SELECT last_attempt_at FROM ops.data_guard_refresh WHERE dataset=%s", (item.dataset,)
        ).fetchone()
        if (
            state
            and state["last_attempt_at"]
            and state["last_attempt_at"].astimezone(NY).date() == now.astimezone(NY).date()
        ):
            continue
        _set_state(writer, item.dataset, now, {})
        days = window(item, now, days_count)
        if not days:
            _set_state(writer, item.dataset, now, {"status": "not_due"})
            continue
        reopened = _reopen(writer, item, days, now)
        try:
            reports = _fetch(reader, writer, item, days, values, now, http)
            result = _refresh_result(reports, reopened)
        except Exception as exc:
            result = {
                "status": "error",
                "error_type": type(exc).__name__,
                "failed_sources": _expected_sources(item),
                "reopened": reopened,
            }
        _set_state(writer, item.dataset, now, result)
        ran.append({"dataset": item.dataset, **result})
    return ran


def _report_list(reports):
    if reports is None:
        return []
    return reports if isinstance(reports, list) else [reports]


def _refresh_result(reports, reopened):
    report_list = _report_list(reports)
    failed = [r for r in report_list if r.get("error_type")]
    result = {"status": "ok", "reopened": reopened, "reports": reports}
    if failed:
        written = sum(int(r.get("rows") or 0) for r in report_list)
        error_types = sorted({r["error_type"] for r in failed})
        result.update(
            status="partial" if written else "error",
            error_type=failed[0]["error_type"],
            failed_sources=[r.get("source", "unknown") for r in failed],
        )
        if len(error_types) > 1:
            result["error_types"] = error_types
    return result


def _expected_sources(item):
    entry = item.backfill["entry"]
    if entry == "fred":
        return [f"FRED:{sid.removeprefix('fred_').upper()}" for sid in item.filter.get("series_id", ())]
    if entry == "ofr":
        return ["OFR:FSI"]
    if entry == "cftc":
        return ["CFTC:TFF"]
    if entry == "cboe_idx":
        return [f"CboeIdx:{sid.removeprefix('cboe_idx_').upper()}" for sid in item.filter.get("series_id", ())]
    if entry == "vxtlt":
        return ["Cboe:VXTLT"]
    if entry == "cboe_pc":
        return ["CboePC:daily"]
    return [entry]


def _set_state(writer, dataset, now, result):
    writer.execute(
        "INSERT INTO ops.data_guard_refresh(dataset,last_attempt_at,last_result) VALUES(%s,%s,%s) "
        "ON CONFLICT(dataset) DO UPDATE SET last_attempt_at=EXCLUDED.last_attempt_at,last_result=EXCLUDED.last_result",
        (dataset, now, Jsonb(result)),
    )


def _reopen(writer, item, days, now):
    with writer.transaction():
        rows = writer.execute(
            "SELECT * FROM ops.data_gaps WHERE dataset=%s AND data_date=ANY(%s) "
            "AND status='unrecoverable' AND kind IN ('missing','partial') FOR UPDATE",
            (item.dataset, days),
        ).fetchall()
        store = Store(writer)
        for row in rows:
            row.update(
                status="open",
                attempts=0,
                last_attempt_at=None,
                resolved_at=None,
                reason="每日回看补采重新尝试",
            )
            store.transition(row, now)
    return len(rows)


def _existing_obs(reader, item, days):
    key_column = item.filter.get("series_id")
    if not key_column:
        return set()
    if item.table == "ingest.macro_observations":
        rows = reader.execute(
            "SELECT series_id,observation_date AS d FROM ingest.macro_observations WHERE observation_date=ANY(%s)",
            (days,),
        ).fetchall()
    elif item.table == "flows.observations":
        rows = reader.execute(
            "SELECT series_id,obs_date AS d FROM flows.observations WHERE obs_date=ANY(%s)", (days,)
        ).fetchall()
    else:
        return set()
    return {(r["series_id"], r["d"]) for r in rows}


def _existing_cftc(reader, days):
    rows = reader.execute(
        "SELECT report_date AS d,market,trader_class FROM flows.cftc_positions WHERE report_date=ANY(%s)", (days,)
    ).fetchall()
    return {(r["d"], r["market"], r["trader_class"]) for r in rows}


def _fetch(reader, writer, item, days, values, now, http):
    entry = item.backfill["entry"]
    start, end = min(days), max(days)
    target = set(days)
    if entry == "fred" and item.table == "ingest.macro_observations":
        return _fred_macro(writer, item, days, values, target)
    existing = _existing_cftc(reader, days) if entry == "cftc" else _existing_obs(reader, item, days)
    if entry == "fred":
        sids = [s[5:].upper() if s.lower().startswith("fred_") else s.upper() for s in item.filter["series_id"]]
        return backfill.backfill_fred(
            http,
            writer,
            DEFAULT_RAW,
            now,
            sids=sids,
            dates=target,
            existing=existing,
            conflict="nothing",
            api_key=values.get("FRED_API_KEY"),
        )
    if entry == "ofr":
        return backfill.backfill_ofr(
            http,
            writer,
            DEFAULT_RAW,
            now,
            series_filter=item.filter["series_id"],
            dates=target,
            existing=existing,
            conflict="nothing",
        )
    if entry == "cftc":
        return [
            backfill.backfill_cftc(http, writer, DEFAULT_RAW, start, end, now, existing=existing, conflict="nothing")
        ]
    if entry == "cboe_idx":
        return backfill.backfill_cboe_index(
            http, writer, DEFAULT_RAW, now, dates=target, existing=existing, conflict="nothing"
        )
    if entry == "vxtlt":
        return backfill.backfill_vxtlt(
            http, writer, DEFAULT_RAW, start, end, now, existing=existing, conflict="nothing"
        )
    if entry == "cboe_pc":
        return backfill.backfill_cboe_pc(
            http,
            writer,
            DEFAULT_RAW,
            start,
            end,
            now,
            pace=0.2,
            dates=target,
            existing=existing,
            conflict="nothing",
        )
    raise ValueError(f"unsupported refresh entry {entry}")


def _fred_macro(writer, item, days, values, target):
    from inves_cog.clock import SystemClock
    from inves_cog.ingest import providers

    fred = providers.FRED(key=values.get("FRED_API_KEY"), clock=SystemClock())
    repo = Repository(writer)
    existing = _existing_obs(writer, item, days)
    reports = []
    for sid in item.filter["series_id"]:
        written = 0
        try:
            for row in fred.collect(sid):
                day = row["observation_date"]
                if day in target and row.get("value") is not None and (sid, day) not in existing:
                    repo.write("macro_observations", row)
                    existing.add((sid, day))
                    written += 1
            reports.append({"source": f"FRED:{sid}", "rows": written})
        except Exception as exc:
            reports.append({"source": f"FRED:{sid}", "rows": written, **backfill._error_fields(exc)})
    return reports
