"""Read M8 historical snapshots into explicitly marked, isolated M9 artifacts."""

import json
from datetime import date
from pathlib import Path

from inves_cog.overlay.delivery import validate_payload
from inves_cog.overlay.rules import generate_overlay
from inves_cog.perception.attribution.snapshot import read_replay_snapshot


def replay_m8(connection, *, days, clock, output_directory, live_directory):
    output, live = Path(output_directory).resolve(), Path(live_directory).resolve()
    if output == live or output.is_relative_to(live) or live.is_relative_to(output):
        raise ValueError("M8 replay requires a separate directory outside live delivery")
    dates = [date.fromisoformat(str(day)) for day in days]
    if not dates or len(set(dates)) != len(dates) or any(day > clock.today_trade_date() for day in dates):
        raise ValueError("replay requires unique, explicit dates that are not in the future")
    if output.exists():
        raise ValueError("replay output directory already exists; retain the original evidence")
    generated = clock.now_utc().isoformat()
    artifacts = []
    connection.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
    try:
        for index, day in enumerate(dates, 1):
            source = read_replay_snapshot(connection, day)
            if source.get("replay") is not True:
                raise ValueError("M8 replay reader must explicitly identify historical input")
            payload = None
            if source.get("complete") is True:
                payload = validate_payload(
                    generate_overlay(
                        source.get("events") or [],
                        clock=clock,
                        version=index,
                        source_asof=source.get("source_events_asof"),
                        market=source.get("market"),
                        missing=source.get("missing"),
                    )
                )
            artifacts.append(
                {
                    "kind": "historical_backfill_not_natural",
                    "replay": True,
                    "trade_date": str(day),
                    "actual_generated_at": generated,
                    "status": "ok" if payload is not None else "unavailable",
                    "source_events_asof": source.get("source_events_asof"),
                    "source_ids": source.get("source_ids") or {},
                    "missing": source.get("missing") or {},
                    "empty_reason": "该日回放快照没有事件；未补造事件"
                    if payload is not None and not source.get("events")
                    else None,
                    "overlay": payload,
                }
            )
    finally:
        connection.execute("ROLLBACK")
    # Do not use FileDelivery or its live filenames. Every artifact carries the replay marker.
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for row in artifacts:
        path = output / ("replay_overlay_" + row["trade_date"] + ".json")
        path.write_text(json.dumps(row, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
        path.chmod(0o600)
    result = {
        "kind": "historical_backfill_not_natural",
        "replay": True,
        "actual_generated_at": generated,
        "days": [
            {key: row[key] for key in ("trade_date", "status", "empty_reason")}
            | {"ticker_count": len((row["overlay"] or {}).get("tickers") or {})}
            for row in artifacts
        ],
    }
    manifest = output / "replay-manifest.json"
    manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest.chmod(0o600)
    return result
