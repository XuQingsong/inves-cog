"""Read the morning page's own inputs and write that page. Nothing is deployed."""

import json
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from inves_cog.ingest.market import trading_day
from inves_cog.perception.anomaly.service import run_recorded
from inves_cog.perception.attribution.chain import (
    _closed_trade_date,
    _daily_pages,
    job_slot,
    prepare_move_pages,
    run_scheduled,
)
from inves_cog.perception.attribution.store import Store

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


def _record_clock(clock):
    """Job rows use a clock that keeps moving. Tests inject one; production uses the wall clock."""
    if clock is not None:
        return clock
    from inves_cog.clock import SystemClock

    return SystemClock()


def main(argv=None, *, connection=None, perception=None, clock=None, client=None, record_clock=None):
    """Run only at the morning page's minute. Tests inject both connections, the clock, and the client."""
    args = list(sys.argv[1:] if argv is None else argv)
    moment = _moment(args, clock)
    borrowed, writer, owned = _connections(connection, perception)
    try:
        if "--page-only" in args:
            if not _is_morning(moment):
                return 0
            return _write_page(borrowed, moment, client)
        if "--chain-only" in args:
            if not in_stage_window("attribution_candidates", moment):
                return 0
            return _run_chain(borrowed, writer, moment, client, _record_clock(record_clock))
        if not _is_morning(moment):
            return 0
        return _execute(borrowed, writer, moment, client, _record_clock(record_clock))
    finally:
        for item in owned:
            item.close()


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


_WRITE_TABLES = (
    "perception.linkage_events",
    "perception.ticker_status",
    "perception.candidates",
    "perception.tracks",
    "perception.claims",
    "perception.reports",
    "perception.market_day",
    "perception.m9_input_snapshots",
)


def _connections(connection, perception):
    """Inputs and jobs stay on the default connection. M8 writes use the perception connection."""
    if connection is not None:
        return connection, connection if perception is None else perception, []
    url = os.environ.get("INVES_COG_DATABASE_URL")
    if not url:
        raise SystemExit("写出这一页需要 INVES_COG_DATABASE_URL，仓库里不保存连接串")
    import psycopg
    from psycopg.rows import dict_row

    borrowed = psycopg.connect(url, row_factory=dict_row, autocommit=True)
    writer_url = os.environ.get("INVES_COG_PERCEPTION_DATABASE_URL")
    if not writer_url:
        return borrowed, None, [borrowed]
    writer = psycopg.connect(writer_url, row_factory=dict_row, autocommit=True)
    return borrowed, writer, [borrowed, writer]


def _require_writer(connection):
    for table in _WRITE_TABLES:
        row = connection.execute(
            "SELECT has_table_privilege(current_user, %s, 'INSERT') AS allowed",
            (table,),
        ).fetchone()
        allowed = row["allowed"] if isinstance(row, dict) else row[0]
        if not allowed:
            raise RuntimeError(f"没有写入权限：{table}")


def _fail_job(connection, _moment, task_name, day, reason, clock=None):
    def refuse():
        raise RuntimeError(reason)

    try:
        run_recorded(
            connection,
            clock=_record_clock(clock),
            task_name=task_name,
            trade_date=day,
            params_version=PARAMS,
            operation=refuse,
        )
    except Exception:
        return 1
    return 1


def _execute(connection, writer, moment, client, record_clock):
    day = _closed_trade_date(moment)
    if writer is None:
        return _fail_job(
            connection,
            moment,
            "attribution_candidates",
            day,
            "缺少 INVES_COG_PERCEPTION_DATABASE_URL",
            clock=record_clock,
        )
    if writer is not connection:
        try:
            _require_writer(writer)
        except Exception as exc:
            return _fail_job(connection, moment, "attribution_candidates", day, str(exc), clock=record_clock)
    if client is None:
        from inves_cog.llm.client import Client

        client = Client.from_environment()

    def operation():
        loaded = _load(connection, moment, day)
        prepared = prepare_move_pages(
            loaded["anomalies"],
            loaded["items"],
            as_of=moment,
            client=client,
            valuation=loaded["valuation"],
            plan=loaded["plan"],
        )
        synthetic = []
        for anomaly in loaded["anomalies"]:
            ready = prepared.get(anomaly.get("anomaly_id"))
            if isinstance(ready, dict):
                synthetic.append({"anomaly_id": anomaly.get("anomaly_id"), "move_card": ready.get("move_card")})
            elif isinstance(ready, Exception):
                synthetic.append({"anomaly_id": anomaly.get("anomaly_id"), "degraded": str(ready)})
        material = [item for item in loaded["items"] if item.get("published_at") is not None]
        early = _daily_pages(
            loaded["anomalies"],
            material,
            synthetic,
            loaded["valuation"],
            loaded["plan"],
            moment,
            holdings=loaded["holdings"],
        )
        _emit(day, _soften(early[0]["text"] if early else "", _failed(loaded["anomalies"], synthetic, day)))
        result = run_scheduled(
            moment,
            anomalies=loaded["anomalies"],
            items=loaded["items"],
            client=client,
            store=Store(writer),
            valuation=loaded["valuation"],
            plan=loaded["plan"],
            holdings=loaded["holdings"],
            prepared_pages=prepared,
        )
        rows = (result or {}).get("rows") or []
        reasons = _reasons(loaded["anomalies"], rows, day)
        saved = [row for row in rows if row.get("saved")]
        if rows and not saved:
            detail = "；".join(row.get("degraded") or row.get("status") or "未保存" for row in rows) or "未保存"
            if "；".join(reasons) != detail:
                reasons.append(detail)
        if reasons:
            raise RuntimeError("；".join(reasons))
        return len(saved)

    try:
        run_recorded(
            connection,
            clock=record_clock,
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


_RETRY_LIMIT = {
    "attribution_candidates": 0,
    "attribution_tracks": 2,
    "attribution_labels": 2,
    "anomaly_daily": 2,
}
_UPSTREAM = {
    "attribution_candidates": ("anomaly_daily",),
    "attribution_tracks": ("attribution_candidates",),
    "attribution_labels": ("attribution_tracks",),
    "anomaly_daily": ("bars_full", "market_structure"),
}
_FINISHED = {"ok", "degraded"}
_PENDING_LINE = "异常检测未完成"
_JOB_ROWS = """
SELECT task_name, status, ended_at, error_summary
FROM ingest.job_runs
WHERE trade_date = %s AND task_name = %s
ORDER BY started_at
"""


def stage_bounds(task_name, trade_date):
    """ET start and deadline for the closed US session. Beijing follows the existing offset."""
    day = date.fromisoformat(str(trade_date)[:10])
    nxt = day + timedelta(days=1)
    if task_name in {"morning_page", "attribution_candidates"}:
        start = _et(day, 21, 15)
        end = start if task_name == "morning_page" else _et(day, 21, 45)
    elif task_name == "attribution_tracks":
        start, end = _et(day, 21, 30), _et(nxt, 0, 0)
    elif task_name == "attribution_labels":
        start, end = _et(nxt, 0, 30), _et(nxt, 7, 30)
    elif task_name == "anomaly_daily":
        start, end = _et(day, 20, 55), _et(day, 21, 10)
    else:
        raise ValueError(task_name)
    return start, end


def stage_cutoff(task_name, moment):
    """Visibility stays on the window open. A late start does not move it."""
    return stage_bounds(task_name, _closed_trade_date(moment))[0]


def in_stage_window(task_name, moment):
    day = _closed_trade_date(moment)
    if not trading_day(date.fromisoformat(day)):
        return False
    start, end = stage_bounds(task_name, day)
    local = moment.astimezone(_NEW_YORK)
    return start <= local < end + timedelta(minutes=1)


def at_stage_deadline(task_name, moment):
    if not in_stage_window(task_name, moment):
        return False
    end = stage_bounds(task_name, _closed_trade_date(moment))[1]
    local = moment.astimezone(_NEW_YORK)
    return end <= local < end + timedelta(minutes=1)


def dispatch_decision(task_name, rows):
    """ok/degraded or a skip is final. Failed rows, excluding skips, count toward the retry cap."""
    found = list(rows or [])
    if any(row.get("status") in _FINISHED for row in found):
        return "done"
    if any(row.get("status") == "running" for row in found):
        return "running"
    if any(str(row.get("error_summary") or "").startswith("skipped_upstream:") for row in found):
        return "skipped"
    failures = [row for row in found if row.get("status") == "failed"]
    if len(failures) > _RETRY_LIMIT[task_name]:
        return "exhausted"
    return "run"


def upstream_ready(rows, now, name=None):
    for row in rows or []:
        if name is not None and row.get("task_name") not in (None, name):
            continue
        ended = _aware(row.get("ended_at"))
        if row.get("status") in _FINISHED and ended is not None and ended <= now:
            return True
    return False


def upstream_phrase(name, rows):
    if not rows:
        return f"{name} 没有记录"
    row = list(rows)[-1]
    summary = str(row.get("error_summary") or "")
    if summary.startswith("skipped_upstream:"):
        return f"{name} 被跳过"
    return f"{name} 状态 {row.get('status')}"


def skip_summary(missing):
    return "skipped_upstream: " + "；".join(missing)


def job_rows(connection, day, task_name):
    return [_job_view(row) for row in connection.execute(_JOB_ROWS, (str(day)[:10], task_name)).fetchall()]


def record_skip(connection, task_name, day, summary, clock):
    def refuse():
        raise RuntimeError(summary)

    try:
        run_recorded(
            connection,
            clock=_record_clock(clock),
            task_name=task_name,
            trade_date=day,
            params_version=PARAMS,
            operation=refuse,
        )
    except Exception:
        return 1
    return 1


def _et(day, hour, minute):
    return datetime.combine(day, time(hour, minute), tzinfo=_NEW_YORK)


def _aware(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value
    return None


def _job_view(row):
    if isinstance(row, dict):
        return row
    return {
        "task_name": row[0],
        "status": row[1],
        "ended_at": row[2],
        "error_summary": row[3] if len(row) > 3 else None,
    }


def _write_page(connection, moment, client):
    cutoff = stage_cutoff("morning_page", moment)
    day = _closed_trade_date(cutoff)
    pending = not upstream_ready(job_rows(connection, day, "anomaly_daily"), moment, "anomaly_daily")
    text = _compose(connection, cutoff, client or _client(None), anomalies_pending=pending)
    _emit(day, text)
    return 0


def _compose(connection, moment, client, *, anomalies_pending):
    day = _closed_trade_date(moment)
    loaded = _load(connection, moment, day)
    prepared = prepare_move_pages(
        loaded["anomalies"],
        loaded["items"],
        as_of=moment,
        client=client,
        valuation=loaded["valuation"],
        plan=loaded["plan"],
    )
    synthetic = _synthetic(loaded["anomalies"], prepared)
    material = [item for item in loaded["items"] if item.get("published_at") is not None]
    early = _daily_pages(
        loaded["anomalies"],
        material,
        synthetic,
        loaded["valuation"],
        loaded["plan"],
        moment,
        holdings=loaded["holdings"],
    )
    text = _soften(early[0]["text"] if early else "", _failed(loaded["anomalies"], synthetic, day))
    if anomalies_pending:
        text = f"{text}\n{_PENDING_LINE}"
    return text


def _synthetic(anomalies, prepared):
    rows = []
    for anomaly in anomalies:
        ready = prepared.get(anomaly.get("anomaly_id"))
        if isinstance(ready, dict):
            rows.append({"anomaly_id": anomaly.get("anomaly_id"), "move_card": ready.get("move_card")})
        elif isinstance(ready, Exception):
            rows.append({"anomaly_id": anomaly.get("anomaly_id"), "degraded": str(ready)})
    return rows


def _run_chain(connection, writer, now, client, record_clock):
    cutoff = stage_cutoff("attribution_candidates", now)
    day = _closed_trade_date(cutoff)
    if writer is None:
        return _fail_job(
            connection,
            now,
            "attribution_candidates",
            day,
            "缺少 INVES_COG_PERCEPTION_DATABASE_URL",
            clock=record_clock,
        )
    if writer is not connection:
        try:
            _require_writer(writer)
        except Exception as exc:
            return _fail_job(connection, now, "attribution_candidates", day, str(exc), clock=record_clock)
    client = client or _client(None)

    def operation():
        loaded = _load(connection, cutoff, day)
        result = run_scheduled(
            cutoff,
            anomalies=loaded["anomalies"],
            items=loaded["items"],
            client=client,
            store=Store(writer),
            valuation=loaded["valuation"],
            plan=loaded["plan"],
            holdings=loaded["holdings"],
        )
        rows = (result or {}).get("rows") or []
        saved = [row for row in rows if row.get("saved")]
        if rows and not saved:
            detail = "；".join(row.get("degraded") or row.get("status") or "未保存" for row in rows) or "未保存"
            raise RuntimeError(detail)
        return len(saved)

    try:
        run_recorded(
            connection,
            clock=record_clock,
            task_name="attribution_candidates",
            trade_date=day,
            params_version=PARAMS,
            operation=operation,
        )
    except Exception:
        return 1
    return 0


def _client(client):
    if client is not None:
        return client
    from inves_cog.llm.client import Client

    return Client.from_environment()


if __name__ == "__main__":
    raise SystemExit(main())
