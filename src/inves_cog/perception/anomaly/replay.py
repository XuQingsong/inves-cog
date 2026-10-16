"""Replay close-session anomalies and score them against the frozen event list."""

import argparse
import json
from datetime import date
from pathlib import Path

from inves_cog.perception.anomaly.panel import PricePanel

STYLE_GROUPS = {"iwm_qqq", "mtum_vlue"}
MILD_DATES = {"2023-08-02", "2023-10-03", "2025-06-13"}
OBJECT_COUNT_RULE = "close 且 universe=pool，合并之后的 alert 与 watch。不含 post，不含 wide。Q-M7-9。"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", required=True)
    parser.add_argument("--source", choices=("file", "db"), required=True)
    parser.add_argument("--input")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    report = build_report(args)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n")
    summary = report["summary"]
    print(summary["recall_non_mild"])
    print(summary["recall_out_of_sample_non_mild"])
    print(summary["control_basket_anomalies"])
    print(summary["mean_objects_per_day"])
    return 0


def build_report(args):
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    if args.source == "db":
        panel = _database_panel()
    else:
        if not args.input:
            raise SystemExit("--source file 需要 --input")
        panel = PricePanel(args.input)
    detected = {}
    sessions = [day for day in panel.sessions if start <= day <= end]
    for day in sessions:
        rows = _identify(day, panel.detect(day))
        detected[day] = [row for row in rows if row["session"] == "close" and row["universe"] == "pool"]
    document = json.loads(Path(args.events).read_text())
    events, misses = [], []
    for event in document["events"]:
        scored = _score_event(event, detected.get(date.fromisoformat(event["date"]), []))
        events.append(scored)
        if not event.get("mild") and event["date"] not in MILD_DATES and not scored["hit_any"]:
            misses.append(
                {
                    "date": event["date"],
                    "scopes": scored["missed_scopes"],
                    "reason": "当日合并后的池内异常没有覆盖这些范围",
                }
            )
    counted = [len(detected[day]) for day in sessions]
    non_mild = [row for row in events if not row["mild"]]
    outside = [row for row in non_mild if row["split"] == "out_of_sample"]
    controls = document.get("controls") or []
    control_hits = 0
    for control in controls:
        day = date.fromisoformat(control["date"])
        control_hits += sum(1 for row in detected.get(day, []) if row["baskets"])
    summary = {
        "recall_non_mild": _ratio(non_mild),
        "recall_out_of_sample_non_mild": _ratio(outside),
        "control_basket_anomalies": control_hits,
        "mean_objects_per_day": (sum(counted) / len(counted)) if counted else None,
        "n_days": len(counted),
        "object_count_rule": OBJECT_COUNT_RULE,
        "membership_note": getattr(panel, "membership_note", None),
    }
    return {"events": events, "misses": misses, "summary": summary}


def write_window(panel, days, path):
    payload = {}
    for day in days:
        payload[day.isoformat()] = {
            "close": [_public(row) for row in _identify(day, panel.detect(day))],
            "post": [_public(row) for row in _identify(day, panel.detect(day, "post"))],
        }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")


def _database_panel():
    from inves_cog.perception.anomaly.database import DatabasePanel

    return DatabasePanel.from_env()


def _identify(day, rows):
    for index, row in enumerate(rows, 1):
        row["anomaly_id"] = f"{day.isoformat()}:{row['session']}:{index:03d}"
    return rows


def _score_event(event, anomalies):
    hit, missed = [], []
    for scope in event["scope"]:
        (hit if _scope_hit(scope, anomalies) else missed).append(scope)
    return {
        "date": event["date"],
        "split": event["split"],
        "mild": bool(event.get("mild") or event["date"] in MILD_DATES),
        "scopes": list(event["scope"]),
        "hit_scopes": hit,
        "missed_scopes": missed,
        "hit_any": bool(hit),
        "anomaly_ids": [row["anomaly_id"] for row in anomalies],
    }


def _scope_hit(scope, anomalies):
    if scope == "L1":
        return any(row["layer"] == "L1" for row in anomalies)
    if scope == "style":
        return any(_style(row) for row in anomalies)
    if scope.startswith("sector:"):
        return any(_sector(row, scope.split(":", 1)[1]) for row in anomalies)
    if scope.startswith("basket:"):
        return any(_basket(row, scope.split(":", 1)[1]) for row in anomalies)
    if scope.startswith("stock:"):
        ticker = scope.split(":", 1)[1]
        return any(member["ticker"] == ticker for row in anomalies for member in row["members"])
    return False


def _style(row):
    if not any(path.startswith("rotation") for path in row["entry_paths"]):
        return False
    return bool({member["ticker"] for member in row["members"]} & STYLE_GROUPS)


def _sector(row, etf):
    paths = set(row["entry_paths"])
    if "C" not in paths and not any(path.startswith("rotation") for path in paths):
        return False
    return any(member["ticker"] == etf for member in row["members"])


def _basket(row, name):
    needle = name.replace(" ", "")
    for basket in row["baskets"]:
        hay = str(basket).replace(" ", "")
        if needle and (needle in hay or hay in needle):
            return True
    return False


def _ratio(rows):
    if not rows:
        return None
    return sum(row["hit_any"] for row in rows) / len(rows)


def _public(row):
    copied = dict(row)
    copied["tickers"] = sorted(copied.get("tickers") or [])
    return copied


if __name__ == "__main__":
    raise SystemExit(main())
