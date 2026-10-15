"""Snapshot provenance, offline COPY parsing and same-financial-year windows."""

import csv
import gzip
import hashlib
import json
import re
from datetime import date, datetime, time, timedelta
from io import StringIO
from pathlib import Path
from zoneinfo import ZoneInfo

BJ = ZoneInfo("Asia/Shanghai")
FIELDS = (
    "eps_cq eps_nq eps_cy eps_ny rev_cy rev_ny up_7d down_7d up_3"
    "0d down_30d coverage eps_high_cy eps_low_cy pt_mean pt_media"
    "n fy_cy fy_ny"
).split()


def day(value):
    return value if isinstance(value, date) and not isinstance(value, datetime) else date.fromisoformat(str(value)[:10])


def number(value):
    if value in (None, "", "\\N", "."):
        return None
    result = float(value)
    if not __import__("math").isfinite(result):
        raise ValueError("Nonfinite consensus value")
    return result


class ConsensusStore:
    def __init__(self, rows=()):
        self.rows = {}
        self.history = {}
        for row in rows:
            self.put(row)

    def put(self, row):
        row = dict(row)
        row["as_of"] = day(row["as_of"])
        self.rows[(row["as_of"], row["ticker"], row["source"])] = row


def read_copy_blocks(text):
    result = {}
    columns = None
    table = None
    rows = []
    for line in text.splitlines():
        if table is None:
            match = re.fullmatch(r"COPY ([a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*) \(([^)]+)\) FROM stdin;", line)
            if match:
                table = match[1]
                columns = [c.strip() for c in match[2].split(",")]
                if not all(re.fullmatch(r"[a-z_][a-z0-9_]*", c) for c in columns):
                    raise ValueError("Invalid COPY columns")
                rows = []
            continue
        if line == "\\.":
            result.setdefault(table, []).extend(rows)
            table = None
            continue
        values = line.split("\t")
        if len(values) != len(columns):
            raise ValueError("COPY field count mismatch")

        def decode(value):
            if value == "\\N":
                return None
            replacements = {"t": "\t", "n": "\n", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "\\": "\\"}
            return re.sub(r"\\([tnrbfv\\])", lambda m: replacements[m[1]], value)

        rows.append(dict(zip(columns, map(decode, values), strict=False)))
    if table is not None:
        raise ValueError("Unterminated COPY block")
    return result


def load_exports(folder):
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    tables = {}
    for spec in manifest["tables"]:
        name = spec["file"]
        if Path(name).name != name:
            raise ValueError("Unsafe export path")
        blob = (folder / name).read_bytes()
        if hashlib.sha256(blob).hexdigest() != spec["sha256"]:
            raise ValueError("Export hash mismatch: " + name)
        text = gzip.decompress(blob).decode("utf-8")
        rows = list(csv.DictReader(StringIO(text)))
        if len(rows) != spec["rows"]:
            raise ValueError("Export row count mismatch: " + name)
        tables[spec["table"].split(".")[-1]] = rows
    return tables


def import_muse_exports(folder, *, store, annual_end_asof=None):
    tables = load_exports(folder)
    grouped = {}

    def target(row):
        key = (day(row["snapshot_date"]), row["ticker"])
        return grouped.setdefault(
            key,
            {
                "as_of": key[0],
                "ticker": key[1],
                "source": "muse_import",
                "captured_at": None,
                **{name: None for name in FIELDS},
                "raw": {"missing_fields": "来源无此字段", "tables": {}, "earnings_history": []},
            },
        )

    periods = {"0q": "eps_cq", "+1q": "eps_nq", "0y": "eps_cy", "+1y": "eps_ny"}
    for row in tables.get("estimates_trend", []):
        output = target(row)
        output["raw"]["tables"].setdefault("estimates_trend", []).append(row)
        if row["period"] in periods:
            output[periods[row["period"]]] = number(row.get("cur"))
    for row in tables.get("estimates_revisions", []):
        output = target(row)
        output["raw"]["tables"].setdefault("estimates_revisions", []).append(row)
        if row.get("period") == "0y":
            for dest, src in (("up_7d", "up7"), ("down_7d", "down7"), ("up_30d", "up30"), ("down_30d", "down30")):
                output[dest] = number(row.get(src))
    for row in tables.get("price_targets", []):
        output = target(row)
        output["pt_mean"] = number(row.get("mean"))
        output["pt_median"] = number(row.get("median"))
        output["raw"]["tables"].setdefault("price_targets", []).append(row)
    for row in tables.get("earnings_history", []):
        store.history[(row["ticker"], row["quarter_date"], row.get("first_seen"))] = row
    for row in grouped.values():
        if annual_end_asof is not None:
            from inves_cog.ingest.fundamentals.providers import fiscal_years

            annual_end = annual_end_asof(row["ticker"], row["as_of"])
            row["fy_cy"], row["fy_ny"] = fiscal_years(annual_end)
            row["raw"]["fiscal_year_source"] = {
                "as_of": str(row["as_of"]),
                "annual_period_end": str(annual_end) if annual_end else None,
                "reason": None if annual_end else "PIT annual filing unavailable",
            }
        row["raw"]["earnings_history"] = [r for r in store.history.values() if r["ticker"] == row["ticker"]]
        store.put(row)
    return {"snapshots": len(grouped), "earnings_history": len(store.history), "idempotent_key": "as_of,ticker,source"}


def visible(row, as_of):
    if day(row["as_of"]) > as_of:
        return False
    captured = row.get("captured_at")
    if captured:
        instant = datetime.fromisoformat(captured.replace("Z", "+00:00")) if isinstance(captured, str) else captured
        if instant.tzinfo is None:
            raise ValueError("captured_at must include timezone")
        if instant >= datetime.combine(as_of + timedelta(days=1), time.min, BJ):
            return False
    return True


def derive_consensus(snapshots, *, ticker, as_of):
    as_of = day(as_of)
    candidates = {}
    for row in snapshots:
        if row["ticker"] != ticker or not visible(row, as_of):
            continue
        key = day(row["as_of"])
        old = candidates.get(key)
        if (
            old is None
            or row["source"] in {"yfinance", "yahoo_page"}
            and old["source"] not in {"yfinance", "yahoo_page"}
        ):
            candidates[key] = row
    today = candidates.get(as_of)
    result = {
        "as_of": as_of,
        "ticker": ticker,
        **{name: today.get(name) if today else None for name in FIELDS},
        "window_status": {},
        "surprise_last4": [],
    }
    for field in ("eps_cy", "eps_ny", "rev_cy"):
        fiscal = "fy_ny" if field == "eps_ny" else "fy_cy"
        for days in (7, 30, 90):
            name = f"{field}_chg_{days}d_pct"
            alias = f"chg_{days}d_pct" if field == "eps_cy" else name
            value = None
            target = as_of - timedelta(days=days)
            prior_dates = [d for d in candidates if d <= target]
            if today is None:
                status = "当日快照缺失"
            elif not candidates or target < min(candidates):
                status = f"不足 {days} 天"
            elif not prior_dates or (target - max(prior_dates)).days > 3:
                status = f"无 {days} 天前快照"
            else:
                prior = candidates[max(prior_dates)]
                base = prior.get(field)
                current = today.get(field)
                if current is None or base is None or today.get(fiscal) is None or prior.get(fiscal) is None:
                    status = "来源无此字段"
                elif str(today[fiscal]) != str(prior[fiscal]):
                    status = "财年切换"
                elif base <= 0:
                    status = "基数 ≤ 0"
                else:
                    value = (current / base - 1) * 100
                    status = "ok"
            result[name] = result[alias] = value
            result["window_status"][name] = result["window_status"][alias] = status
            if field == "eps_cy":
                result["window_status"][f"chg_{days}d"] = status
    coverage = result["coverage"]
    for days in (7, 30):
        up, down = result.get(f"up_{days}d"), result.get(f"down_{days}d")
        result[f"breadth_{days}d"] = (
            (up - down) / coverage if coverage and up is not None and down is not None else None
        )
        if result[f"breadth_{days}d"] is None:
            result["window_status"][f"breadth_{days}d"] = "coverage 为 0/空或来源无此字段"
    mean, high, low = result["eps_cy"], result["eps_high_cy"], result["eps_low_cy"]
    result["dispersion"] = (
        (high - low) / abs(mean)
        if mean is not None and abs(mean) >= 0.01 and high is not None and low is not None
        else None
    )
    if result["dispersion"] is None:
        result["window_status"]["dispersion"] = "均值绝对值 < 0.01 或来源无此字段"
    history = today.get("raw", {}).get("earnings_history", []) if today else []
    history = [
        r
        for r in history
        if (r.get("first_seen") and day(r["first_seen"]) <= as_of)
        or (r.get("captured_at") and visible({"as_of": as_of, "captured_at": r["captured_at"]}, as_of))
    ]
    for row in sorted(history, key=lambda r: day(r["quarter_date"]), reverse=True)[:4]:
        actual, estimate = number(row.get("eps_actual")), number(row.get("eps_est"))
        result["surprise_last4"].append(
            {
                "quarter_date": day(row["quarter_date"]),
                "eps_actual": actual,
                "eps_est": estimate,
                "surprise_pct": number(row.get("surprise_pct"))
                if row.get("surprise_pct") not in (None, "", "\\N")
                else (actual / estimate - 1) * 100
                if actual is not None and estimate
                else None,
            }
        )
    return result
