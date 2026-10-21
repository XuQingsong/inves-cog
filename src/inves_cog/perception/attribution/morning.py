"""Read the morning page's own inputs and write that page. Nothing is deployed."""

import json
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from inves_cog.ingest.market import trading_day
from inves_cog.perception.anomaly.service import run_recorded
from inves_cog.perception.attribution.chain import _closed_trade_date, job_slot, run_scheduled

PORTFOLIO = "paper-fixed"
PARAMS = "p-2026.10"
_ASK_AGAIN = "可能的原因：这次没问到，下次运行再试"
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_NEW_YORK = ZoneInfo("America/New_York")

_ANOMALIES = """
SELECT anomaly_id, trade_date, session, direction, members, universe
FROM perception.anomalies
WHERE trade_date = %s
  AND generated_at IS NOT NULL
  AND generated_at <= %s
ORDER BY session, anomaly_id
"""

_NEWS = """
SELECT info_id, kind, published_at, first_seen_at, headline, flags, extraction_source, tickers, entities
FROM ingest.info_items
WHERE first_seen_at <= %s
  AND published_at >= %s
  AND published_at <= %s
  AND kind IN ('news', 'sec_8k')
"""

_RANGES = """
SELECT DISTINCT ON (ticker)
    trade_date, ticker, status, bear, neutral, bull, payload, observed_at
FROM valuation_v1.ranges
WHERE trade_date <= %s AND observed_at <= %s
ORDER BY ticker, trade_date DESC, observed_at DESC
"""

_BARS = """
SELECT ticker, close
FROM ingest.bars_daily
WHERE trade_date = %s AND ticker = ANY(%s)
"""

_LEDGER = """
SELECT state, trade_date, observed_at
FROM trading.ledger
WHERE portfolio_id=%s AND trade_date<=%s
AND extractor='fixed' AND rule_set='A' AND (%s::timestamptz IS NULL OR observed_at<=%s)
ORDER BY trade_date DESC, observed_at DESC LIMIT 1
"""

_PLAN = """
SELECT payload, signal_date, trade_date, generated_at
FROM trading.plan
WHERE portfolio_id=%s AND signal_date<=%s
AND extractor='fixed' AND rule_set='A' AND published
AND (%s::timestamptz IS NULL OR generated_at<=%s)
ORDER BY signal_date DESC, generated_at DESC LIMIT 1
"""


class _Frozen:
    def __init__(self, moment):
        self._moment = moment

    def now_utc(self):
        return self._moment


def main(argv=None, *, connection=None, clock=None, client=None):
    """Run only at the morning page's minute. Tests inject the connection, clock, and client."""
    moment = _moment(argv, clock)
    if not _is_morning(moment):
        return 0
    borrowed, owned = _borrow(connection)
    try:
        return _execute(borrowed, moment, client)
    finally:
        if owned:
            borrowed.close()


def _moment(argv, clock):
    args = list(sys.argv[1:] if argv is None else argv)
    if "--at" in args:
        index = args.index("--at")
        if index + 1 >= len(args):
            raise SystemExit("补跑需要 --at 后面的时间")
        return datetime.fromisoformat(args[index + 1])
    if clock is None:
        from inves_cog.clock import SystemClock

        clock = SystemClock()
    return clock.now_utc()


def _is_morning(moment):
    slot = job_slot(moment)
    if slot is None or slot["task_name"] != "attribution_candidates":
        return False
    return trading_day(moment.astimezone(_NEW_YORK).date())


def _borrow(connection):
    if connection is not None:
        return connection, False
    url = os.environ.get("INVES_COG_DATABASE_URL")
    if not url:
        raise SystemExit("写出这一页需要 INVES_COG_DATABASE_URL，仓库里不保存连接串")
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(url, row_factory=dict_row, autocommit=True), True


def _execute(connection, moment, client):
    if client is None:
        from inves_cog.llm.client import Client

        client = Client.from_environment()
    day = _closed_trade_date(moment)

    def operation():
        loaded = _load(connection, moment, day)
        result = run_scheduled(
            moment,
            anomalies=loaded["anomalies"],
            items=loaded["items"],
            client=client,
            valuation=loaded["valuation"],
            plan=loaded["plan"],
            holdings=loaded["holdings"],
        )
        pages = (result or {}).get("daily_pages") or []
        flags = _failed(loaded["anomalies"], (result or {}).get("rows") or [], day)
        text = _soften(pages[0]["text"] if pages else "", flags)
        _emit(day, text)
        reasons = _reasons(loaded["anomalies"], (result or {}).get("rows") or [], day)
        if reasons:
            raise RuntimeError("；".join(reasons))
        return len((result or {}).get("rows") or [])

    try:
        run_recorded(
            connection,
            clock=_Frozen(moment),
            task_name="attribution_candidates",
            trade_date=day,
            params_version=PARAMS,
            operation=operation,
        )
    except Exception:
        return 1
    return 0


def _load(connection, moment, day):
    anomalies = [_anomaly(row) for row in _all(connection, _ANOMALIES, (day, moment))]
    items = [_item(row) for row in _all(connection, _NEWS, (moment, _news_start(day), moment))]
    valuation = _valuation(connection, moment, day)
    holdings, plan = _book(connection, moment, day)
    return {"anomalies": anomalies, "items": items, "valuation": valuation, "holdings": holdings, "plan": plan}


def _all(connection, statement, params):
    return connection.execute(statement, params).fetchall()


def _one(connection, statement, params):
    return connection.execute(statement, params).fetchone()


def _news_start(day):
    opened = date.fromisoformat(day) - timedelta(days=7)
    return datetime.combine(opened, time.min, tzinfo=_NEW_YORK)


def _anomaly(row):
    prepared = dict(row)
    prepared["members"] = _array(prepared.get("members"))
    prepared["trade_date"] = str(prepared.get("trade_date") or "")[:10]
    return prepared


def _item(row):
    prepared = dict(row)
    prepared["extraction_source"] = _object(prepared.get("extraction_source"))
    prepared["tickers"] = _array(prepared.get("tickers"))
    prepared["entities"] = _array(prepared.get("entities"))
    prepared["flags"] = _array(prepared.get("flags"))
    return prepared


def _valuation(connection, moment, day):
    ranges = _all(connection, _RANGES, (day, moment))
    if not ranges:
        return None
    tickers = [row["ticker"] for row in ranges if row.get("ticker")]
    closes = {}
    if tickers:
        for bar in _all(connection, _BARS, (day, tickers)):
            closes[bar["ticker"]] = bar["close"]
    rows = []
    for row in ranges:
        prepared = dict(row)
        prepared["trade_date"] = str(prepared.get("trade_date") or "")[:10]
        prepared["payload"] = _object(prepared.get("payload"))
        if prepared.get("ticker") in closes:
            prepared["price"] = closes[prepared["ticker"]]
        rows.append(prepared)
    return rows


def _book(connection, moment, day):
    bound = (PORTFOLIO, day, moment, moment)
    ledger = _one(connection, _LEDGER, bound)
    plan_row = _one(connection, _PLAN, bound)
    positions = _positions(ledger["state"]) if ledger else None
    orders = _orders(plan_row["payload"]) if plan_row else None
    if orders is not None:
        row = {"trade_date": day, "payload": {"orders": orders}}
        if positions:
            row["positions"] = positions
        return None, [row]
    return (list(positions) if positions else None), None


def _positions(state):
    body = _object(state)
    source = body.get("positions") if isinstance(body.get("positions"), dict) else {}
    kept = {}
    for ticker, value in source.items():
        shares = value.get("shares") if isinstance(value, dict) else value
        if isinstance(shares, bool) or not isinstance(shares, (int, float)) or shares <= 0:
            continue
        kept[ticker] = shares
    return kept


def _orders(payload):
    body = _object(payload)
    found = body.get("orders")
    if not isinstance(found, list):
        return []
    return [order for order in found if isinstance(order, dict)]


def _object(value):
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, dict) else {}


def _array(value):
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, list) else []


def _failed(anomalies, rows, day):
    by_id = {row.get("anomaly_id"): row for row in rows}
    flags = []
    for anomaly in _shown(anomalies, day):
        found = by_id.get(anomaly.get("anomaly_id")) or {}
        flags.append(not isinstance(found.get("move_card"), dict) and bool(found.get("degraded")))
    return flags


def _reasons(anomalies, rows, day):
    by_id = {row.get("anomaly_id"): row for row in rows}
    reasons = []
    for anomaly, failed in zip(_shown(anomalies, day), _failed(anomalies, rows, day), strict=True):
        if failed:
            reasons.append(str((by_id.get(anomaly.get("anomaly_id")) or {}).get("degraded") or "这次没问到"))
    return reasons


def _shown(anomalies, day):
    shown = []
    for anomaly in anomalies:
        if anomaly.get("universe") == "wide" or str(anomaly.get("trade_date") or "")[:10] != day:
            continue
        shown.append(anomaly)
    return shown


def _soften(text, flags):
    lines = []
    index = -1
    in_moves = False
    for line in text.split("\n"):
        if line.startswith("一、"):
            in_moves = True
        elif line.startswith("二、"):
            in_moves = False
        if in_moves and line[:1].isdigit() and ". " in line[:4]:
            index += 1
        if in_moves and 0 <= index < len(flags) and flags[index] and line.startswith("可能的原因："):
            lines.append(_ASK_AGAIN)
            continue
        lines.append(line)
    return "\n".join(lines)


def _emit(day, text):
    folder = os.environ.get("INVES_COG_PAGE_DIR")
    if not folder:
        print(text)
        return
    path = Path(folder)
    path.mkdir(parents=True, exist_ok=True)
    (path / f"daily_page_{day}.txt").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
