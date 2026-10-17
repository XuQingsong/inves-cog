"""Five trading-day reports from headlines that were already visible.

The OpenAI case panel is not the live pool, and the export headlines are not
the full news set. A missing recording stays 待分析. This does not close AC-M8-06.
"""

import argparse
import json
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from inves_cog.ingest.market import regular_bounds
from inves_cog.llm.client import LLMUnavailable
from inves_cog.perception.anomaly.cases import case_anomalies
from inves_cog.perception.anomaly.replay import _identify
from inves_cog.perception.attribution.chain import replay_days
from inves_cog.perception.attribution.replay import then_visible

TRADING_DAYS = ("2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16")
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_BARS = "openai_bars.jsonl.gz"


class _NoModel:
    def call(self, task, payload):
        raise LLMUnavailable(f"{task}: 没有录音")


def beijing_deadline(trade_date):
    """The first Beijing 12:30 after that US session."""
    day = date.fromisoformat(trade_date) + timedelta(days=1)
    return datetime.combine(day, time(12, 30), tzinfo=_SHANGHAI)


def headline_items(fixture_dir):
    payload = json.loads((fixture_dir / "m8/export_headlines.json").read_text())
    items = []
    for row in payload["items"]:
        items.append(
            {
                "info_id": row["info_id"],
                "published_at": datetime.fromisoformat(row["published_at"]),
                "first_seen_at": datetime.fromisoformat(row["first_seen_at"]),
                "source_level": row["source_level"],
                "headline": row["headline"],
                "source_root": row["source"],
            }
        )
    return items


def case_anomalies_for_days(fixture_dir, days=TRADING_DAYS):
    """Pool close objects from the frozen OpenAI panel. Other files are not added again."""
    grouped = []
    for trade_date in days:
        detected = case_anomalies(fixture_dir / "m7", _BARS, trade_date)
        chosen = [row for row in detected if row.get("session") == "close" and row.get("universe") == "pool"]
        identified = _identify(date.fromisoformat(trade_date), chosen)
        bounds = regular_bounds(date.fromisoformat(trade_date))
        started = None if bounds is None else bounds[1]
        grouped.append((trade_date, [_anomaly(row, started) for row in identified]))
    return grouped


def five_day_document(anomalies_by_day, items, *, client=None):
    """One report per trading day. Items without a first-seen time stay invisible."""
    client = _NoModel() if client is None else client
    days = []
    for trade_date, anomalies in anomalies_by_day:
        as_of = beijing_deadline(trade_date)
        played = replay_days(anomalies, items, [as_of], client=client)[0]
        by_id = {row["anomaly_id"]: row for row in played["anomalies"]}
        days.append(
            {
                "trade_date": trade_date,
                "as_of": as_of.isoformat(),
                "replay": played["replay"],
                "then_visible": [item["info_id"] for item in then_visible(items, as_of)],
                "anomalies": [_view(by_id[row["anomaly_id"]], row) for row in anomalies],
                "closes_ac_m8_06": False,
            }
        )
    return {
        "fixture": "frozen-openai-panel-and-export-headlines",
        "closes_ac_m8_06": False,
        "closes_case": False,
        "operating_conclusion": "冻结标题的当时可见回放，不是正式五日运行",
        "input_limit": (
            "异常只来自 OpenAI 案例夹具的收盘池内对象，新闻只来自导出标题短摘录。"
            "标题没有实体、代码或批准向量，所以不会进入异常报告。不是全池，也不是当时的全量新闻。"
        ),
        "days": days,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    args = parser.parse_args(argv)
    fixture = Path(args.fixture)
    document = five_day_document(case_anomalies_for_days(fixture), headline_items(fixture))
    json.dump(document, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def _anomaly(row, started):
    return {
        "anomaly_id": row["anomaly_id"],
        "trade_date": str(row["trade_date"])[:10],
        "session": row["session"],
        "universe": row["universe"],
        "baskets": list(row.get("baskets") or []),
        "members": [
            {"ticker": member["ticker"]}
            for member in row.get("members") or []
            if isinstance(member, dict) and member.get("ticker")
        ],
        "direction": row.get("direction"),
        "started_at": started,
    }


def _view(result, source):
    report = result.get("report") or {}
    return {
        "anomaly_id": result.get("anomaly_id"),
        "baskets": list(source.get("baskets") or []),
        "direction": source.get("direction"),
        "status": result.get("status"),
        "lifecycle": result.get("lifecycle"),
        "degraded": result.get("degraded"),
        "operating_impact_proven": result.get("operating_impact_proven"),
        "sources": [item["info_id"] for item in report.get("sources") or []],
        "market_confidence": report.get("market_confidence"),
        "fundamental_standing": report.get("fundamental_standing"),
        "valuation": report.get("valuation"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
