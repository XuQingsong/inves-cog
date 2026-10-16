"""Recording paths for the four historical cases. Printing them does not call a model."""

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from inves_cog.perception.anomaly.cases import case_anomalies
from inves_cog.perception.anomaly.replay import _identify
from inves_cog.perception.attribution.historical import candidate_capture, headline_lead, retrieval_items

READ_ON = "2026-10-16"


def case_bundles(fixture_dir, read_on=READ_ON):
    fixture_dir = Path(fixture_dir)
    manual = json.loads((fixture_dir / "m8/manual_leads_2026-10-16.json").read_text())
    export = json.loads((fixture_dir / "m8/export_headlines.json").read_text())
    manual_by_kind = {row["kind"]: row for row in manual["leads"]}
    headlines = [headline_lead(row) for row in export["items"]]
    bundles = []
    for spec in _SPECS:
        anomalies = _identify(
            date.fromisoformat(spec["trade_date"]),
            case_anomalies(fixture_dir / "m7", spec["bars"], spec["trade_date"]),
        )
        chosen = spec["select"](anomalies)
        if not chosen:
            raise ValueError(f"没有对上的异常对象: {spec['case_kind']}")
        leads = spec["leads"](manual_by_kind, headlines)
        for anomaly in chosen:
            copied = {
                key: anomaly[key]
                for key in ("anomaly_id", "trade_date", "session", "baskets", "members", "direction", "universe")
                if key in anomaly
            }
            copied["case_kind"] = spec["case_kind"]
            plain = _plain(copied)
            bundles.append(
                {
                    "case_kind": spec["case_kind"],
                    "anomaly": plain,
                    "leads": leads,
                    "read_on": read_on,
                    "sources": [item["info_id"] for item in retrieval_items(leads, plain["trade_date"], read_on)],
                }
            )
    return bundles


def case_plans(fixture_dir, root, read_on=READ_ON):
    plans = []
    for bundle in case_bundles(fixture_dir, read_on):
        path = candidate_capture(bundle["anomaly"], bundle["leads"], bundle["read_on"], root)
        plans.append(
            {
                "case_kind": bundle["case_kind"],
                "anomaly_id": bundle["anomaly"]["anomaly_id"],
                "trade_date": str(bundle["anomaly"]["trade_date"])[:10],
                "sources": bundle["sources"],
                "recording": str(path),
                "evidence_mode": "后补录历史案例",
                "collected_then": False,
                "closes_case": False,
                "closes_ac_m8_06": False,
            }
        )
    return plans


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--root", required=True)
    args = parser.parse_args(argv)
    json.dump(case_plans(args.fixture, args.root), sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 0


def _plain(value):
    return json.loads(json.dumps(value, default=_json_default))


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    item = getattr(type(value), "item", None)
    if item is not None:
        return value.item()
    raise TypeError(f"不能序列化 {type(value).__name__}")


def _lead(manual_by_kind, kind):
    return [manual_by_kind[kind]]


def _headlines(headlines, kinds):
    return [row for row in headlines if row["kind"] in kinds]


def _r1(rows):
    return [
        row
        for row in rows
        if row["universe"] == "pool"
        and row["direction"] == "down"
        and "加速" in " ".join(row["baskets"])
        and any(member["ticker"] == "NVDA" for member in row["members"])
    ]


def _muse(rows):
    chosen = []
    for row in rows:
        if row["universe"] != "pool":
            continue
        members = {member["ticker"] for member in row["members"]}
        baskets = " ".join(row["baskets"])
        if ("META" in members and row["severity"] == "alert") or "CPU" in baskets:
            chosen.append(row)
    return chosen


def _named(rows, name):
    return [row for row in rows if row["universe"] == "pool" and name in " ".join(row["baskets"])]


_SPECS = (
    {
        "case_kind": "r1_release",
        "bars": "case_20250127_bars.jsonl.gz",
        "trade_date": "2025-01-27",
        "select": _r1,
        "leads": lambda manual, _headlines_ignored: _lead(manual, "r1_release"),
    },
    {
        "case_kind": "muse_rank",
        "bars": "meta_bars.jsonl.gz",
        "trade_date": "2026-09-21",
        "select": _muse,
        "leads": lambda manual, _headlines_ignored: _lead(manual, "muse_rank"),
    },
    {
        "case_kind": "toshiba",
        "bars": "toshiba_bars.jsonl.gz",
        "trade_date": "2026-10-02",
        "select": lambda rows: _named(rows, "HDD"),
        "leads": lambda _manual, headlines: _headlines(headlines, {"toshiba_supply", "tdk_second_hit"}),
    },
    {
        "case_kind": "openai_arr",
        "bars": "openai_bars.jsonl.gz",
        "trade_date": "2026-10-14",
        "select": lambda rows: _named(rows, "OpenAI"),
        "leads": lambda manual, headlines: [
            *_headlines(headlines, {"coreweave_debt", "barclays_downgrade", "cpi_hot"}),
            *_lead(manual, "openai_arr"),
        ],
    },
)


if __name__ == "__main__":
    raise SystemExit(main())
