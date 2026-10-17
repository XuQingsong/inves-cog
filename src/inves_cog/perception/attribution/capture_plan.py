"""Fixed inputs and recording paths for the four historical cases.

Printing the plan and writing the input files does not call a model.
``--capture`` is the demand-side command that calls the approved client.
"""

import argparse
import hashlib
import json
import sys
from datetime import date, datetime
from pathlib import Path

from inves_cog.llm.client import canonical_payload
from inves_cog.perception.anomaly.cases import case_anomalies
from inves_cog.perception.anomaly.replay import _identify
from inves_cog.perception.attribution.claims import claim_payload
from inves_cog.perception.attribution.historical import headline_lead, recording_path, retrieval_items
from inves_cog.perception.attribution.propose import candidate_payload

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


def case_payloads(fixture_dir, read_on=READ_ON):
    """The exact claim and candidate objects. Claims stay empty in the candidate object."""
    rows = []
    for bundle in case_bundles(fixture_dir, read_on):
        items = retrieval_items(bundle["leads"], bundle["anomaly"]["trade_date"], bundle["read_on"])
        claim = claim_payload(items) if items else None
        if claim is not None and not claim["items"]:
            claim = None
        rows.append(
            {
                **bundle,
                "items": items,
                "candidate_payload": candidate_payload(bundle["anomaly"], items, []),
                "claim_payload": claim,
            }
        )
    return rows


def case_plans(fixture_dir, root, read_on=READ_ON):
    plans = []
    for row in case_payloads(fixture_dir, read_on):
        path = recording_path("anomaly_candidates", row["candidate_payload"], root)
        claim = None if row["claim_payload"] is None else recording_path("claim_extraction", row["claim_payload"], root)
        plans.append(
            {
                "case_kind": row["case_kind"],
                "anomaly_id": row["anomaly"]["anomaly_id"],
                "trade_date": str(row["anomaly"]["trade_date"])[:10],
                "sources": row["sources"],
                "recording": str(path),
                "claim_recording": None if claim is None else str(claim),
                "candidate_sha256": path.stem,
                "claim_sha256": None if claim is None else claim.stem,
                "evidence_mode": "后补录历史案例",
                "collected_then": False,
                "closes_case": False,
                "closes_ac_m8_06": False,
            }
        )
    return plans


def write_inputs(fixture_dir, dest, read_on=READ_ON):
    """Write the canonical payloads. These are inputs, not recordings."""
    dest = Path(dest)
    index = []
    for row in case_payloads(fixture_dir, read_on):
        folder = dest / row["case_kind"] / row["anomaly"]["anomaly_id"]
        folder.mkdir(parents=True, exist_ok=True)
        candidate_text = canonical_payload(row["candidate_payload"])
        (folder / "anomaly_candidates.json").write_text(candidate_text, encoding="utf-8")
        claim_name = None
        if row["claim_payload"] is not None:
            claim_name = "claim_extraction.json"
            (folder / claim_name).write_text(canonical_payload(row["claim_payload"]), encoding="utf-8")
        index.append(
            {
                "case_kind": row["case_kind"],
                "anomaly_id": row["anomaly"]["anomaly_id"],
                "candidate_sha256": _sha(row["candidate_payload"]),
                "claim_sha256": None if row["claim_payload"] is None else _sha(row["claim_payload"]),
                "candidate_input": str((folder / "anomaly_candidates.json").relative_to(dest)),
                "claim_input": None if claim_name is None else str((folder / claim_name).relative_to(dest)),
                "evidence_mode": "后补录历史案例",
                "collected_then": False,
                "closes_case": False,
                "closes_ac_m8_06": False,
            }
        )
    (dest / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return index


def capture_cases(fixture_dir, root, client, read_on=READ_ON):
    """Call ``client`` and store recordings. A failed anomaly does not stop the next one."""
    root = Path(root)
    saved = []
    seen = {}
    for row in case_payloads(fixture_dir, read_on):
        claim_file, claim_error = None, None
        payload = row["claim_payload"]
        if payload is not None:
            digest = _sha(payload)
            if digest not in seen:
                seen[digest] = _invoke(root, "claim_extraction", payload, client)
            claim_file, claim_error = seen[digest]
        candidate_file, candidate_error = _invoke(root, "anomaly_candidates", row["candidate_payload"], client)
        saved.append(
            {
                "case_kind": row["case_kind"],
                "anomaly_id": row["anomaly"]["anomaly_id"],
                "recording": None if candidate_file is None else str(candidate_file),
                "claim_recording": None if claim_file is None else str(claim_file),
                "candidate_error": candidate_error,
                "claim_error": claim_error,
                "evidence_mode": "后补录历史案例",
                "collected_then": False,
                "closes_case": False,
                "closes_ac_m8_06": False,
            }
        )
    return saved


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--inputs")
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args(argv)
    if args.capture:
        from inves_cog.llm.client import Client

        rows = capture_cases(args.fixture, args.root, Client.from_environment())
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
        return 0
    if args.inputs:
        write_inputs(args.fixture, args.inputs)
    json.dump(case_plans(args.fixture, args.root), sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 0


def _sha(payload):
    return hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()


def _invoke(root, task, payload, client):
    try:
        result = client.call(task, payload)
    except Exception as exc:
        return None, type(exc).__name__
    if not isinstance(result, dict):
        return None, "结果不是对象"
    return _store(root, task, payload, result), None


def _store(root, task, payload, result):
    digest = _sha(payload)
    path = Path(root) / task / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"task": task, "payload_sha256": digest, "result": result}
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return path


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
