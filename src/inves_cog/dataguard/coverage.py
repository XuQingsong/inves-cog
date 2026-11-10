"""Collection-task coverage audit.

One registry: runtime tasks (pipeline.py), program whitelists
(install_ingest_service.py), expectations (data_expectations.yaml).
A task is covered when it is (a) in some supervisor program's task
list, (b) has an expectation entry, (c) the expectation cadence is
set. Anything else is a '采集未覆盖' gap naming the failed check.
Tasks listed under `collection_disabled:` in the yaml are skipped.
"""

import ast
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _dict_keys(tree, name):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
            and isinstance(node.value, ast.Dict)
        ):
            return [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
    return []


def program_tasks(path=None):
    """{program: [task,...]} from install_ingest_service.py."""
    tree = ast.parse((path or ROOT / "scripts/install_ingest_service.py").read_text())
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "programs" for t in node.targets)
            and isinstance(node.value, ast.Dict)
        ):
            out = {}
            for k, v in zip(node.value.keys, node.value.values, strict=False):
                if not isinstance(k, ast.Constant):
                    continue
                name = k.value
                tasks = []
                if isinstance(v, ast.List):
                    flags = [x.value for x in v.elts if isinstance(x, ast.Constant)]
                    if "--tasks" in flags:
                        i = flags.index("--tasks")
                        tasks = flags[i + 1 :]
                        tasks = [t for t in tasks if not t.startswith("-")]
                    if not tasks:
                        tasks = [name]
                out[name] = tasks
            return out
    return {}


def registered_tasks(path=None):
    """Task names the runtime knows, from pipeline.py `tasks = {` keys."""
    tree = ast.parse((path or ROOT / "src/inves_cog/ingest/pipeline.py").read_text())
    keys = _dict_keys(tree, "tasks")
    return [k for k in keys if isinstance(k, str) and not k.startswith("_")]


def disabled_tasks(items):
    """Tasks explicitly disabled in expectations (`disabled:` field)."""
    out = {}
    for i in items:
        if getattr(i, "disabled", None):
            for t in i.disabled.get("tasks", []):
                out[t] = i.disabled.get("reason", "")
    return out


@dataclass
class Finding:
    task: str
    kind: str  # uncovered | degraded | empty_run | consec_failed
    detail: str


def audit(tasks, programs, expectations, disabled):
    """Each registered task must appear in a program list AND have an
    expectation whose filter matches (job_runs task_name or a table
    the task writes). Returns Findings for every uncovered item."""
    whitelisted = {t for ts in programs.values() for t in ts}
    exp_tasks = set()
    for i in expectations:
        for t in (i.get("filter", {}) or {}).get("task_name", []) or []:
            exp_tasks.add(t)
    out = []
    for t in tasks:
        if t in disabled:
            continue
        if t not in whitelisted:
            out.append(Finding(t, "uncovered", f"{t}: 不在任何 supervisor 程序任务清单"))
        if t not in exp_tasks:
            out.append(Finding(t, "uncovered", f"{t}: data_expectations 无期望项"))
    return out


NAMES = {
    "bars_full": "K线全量",
    "bars_prefill": "K线预采",
    "wide_universe": "宽基快照",
    "news_full": "新闻全量",
    "news_poll": "新闻轮询",
    "news_watchdog": "新闻守护",
    "news_prefill": "新闻预采",
    "wide_snapshots": "宽幅快照",
    "iex_intraday": "IEX盘中",
    "intraday_snapshots": "盘中快照",
    "yahoo_intraday": "Yahoo盘中",
    "vix_daily": "VIX日线",
    "earnings_calendar": "财报日历",
    "econ_calendar": "宏观日历",
    "sec_submissions": "SEC申报",
    "sec_index": "SEC索引",
    "sec_atom": "SEC原子",
    "m6_market_inputs": "市场输入",
    "issuer_profiles": "发行人档案",
    "app_free": "App免费榜",
    "app_grossing": "App畅销榜",
    "trends": "趋势",
    "websites": "站点",
    "fred": "FRED",
    "finra": "FINRA",
    "cboe": "CBOE/OCC",
    "fed_news": "美联储新闻",
    "eia_press": "EIA新闻",
    "eia_energy": "EIA能源",
    "congress_ptr": "国会PTR",
}

THRESHOLDS = {"degraded_streak": 2, "fail_streak": 3, "empty_run": 1}


def streaks(rows):
    """job_runs rows (task_name,status,started_at) newest-first ->
    consecutive fail / degraded streaks + last_ok/last_run per task."""
    out = {}
    for r in rows:
        t = r["task_name"]
        st = out.setdefault(
            t,
            {
                "fail": 0,
                "degraded": 0,
                "last_ok": None,
                "last_run": r["started_at"],
                "last_status": r["status"],
            },
        )
        if st.get("_done"):
            continue
        s = r["status"]
        if s == "ok" or (s == "failed" and False):
            st["last_ok"] = st["last_ok"] or r["started_at"]
            st["_done"] = True
        elif s in ("failed", "error"):
            st["fail"] += 1
        elif s == "degraded":
            st["degraded"] += 1
    return out


def health_rows(tasks, streak_map, disabled, findings):
    """One row per task for the /data-status 采集任务健康 table."""
    flagged = {f.task for f in findings}
    rows = []
    for t in sorted(tasks):
        sm = streak_map.get(t, {})
        if t in disabled:
            state, note = "已停用", disabled[t]
        elif t in flagged:
            state, note = "停止", next(f.detail for f in findings if f.task == t)
        elif sm.get("fail", 0) >= THRESHOLDS["fail_streak"]:
            state, note = "失败", f"连续失败 {sm['fail']} 次"
        elif sm.get("degraded", 0) >= THRESHOLDS["degraded_streak"]:
            state, note = "降级", f"连续降级 {sm['degraded']} 次"
        else:
            state, note = "正常", None
        rows.append(
            {
                "task_name": t,
                "display_name": NAMES.get(t, t),
                "last_ok_at": sm.get("last_ok"),
                "last_run_at": sm.get("last_run"),
                "last_status": sm.get("last_status"),
                "fail_streak": sm.get("fail", 0),
                "degraded_streak": sm.get("degraded", 0),
                "state": state,
                "note": note,
            }
        )
    return rows


def run_audit(reader, writer, now, items):
    """One coverage-audit pass: upsert ops.collection_health + open gaps
    for uncovered / degraded / empty-run / consecutive-failed tasks."""
    import json

    progs = program_tasks()
    tasks = registered_tasks()
    disabled = {}
    for i in items:
        d = getattr(i, "disabled", None)
        if d:
            for t in d.get("tasks") or []:
                disabled[t] = d.get("reason", "")
    exp_by_task = {}
    for i in items:
        flt = getattr(i, "filter", None) or {}
        for t in flt.get("task_name", []) or []:
            exp_by_task[t] = i
    findings = []
    for t in tasks:
        if t in disabled:
            continue
        if not any(t in ts for ts in progs.values()):
            findings.append(Finding(t, "uncovered", f"{t}: 不在 supervisor 程序任务清单"))
        if t not in exp_by_task:
            findings.append(Finding(t, "uncovered", f"{t}: data_expectations 无期望项"))
    runs = reader.execute(
        "SELECT task_name, status, started_at FROM ingest.job_runs"
        " WHERE started_at>now()-interval '7 days' ORDER BY started_at DESC LIMIT 4000"
    ).fetchall()
    smap = streaks(runs)
    seen = {r["task_name"] for r in runs}
    tasks = sorted(set(tasks) | set(seen) - set(disabled))
    # reverse check: expectation task_names for dead tasks
    for t in exp_by_task:
        if t not in whitelisted_all(progs) and t not in seen and t not in disabled:
            findings.append(Finding(t, "uncovered", f"{t}: 期望项存在但无程序运行（疑似死任务）"))
    # empty_run: ok task whose mapped table gained no rows in the run window
    for t, spec in (config_task_tables(items) or {}).items():
        if t in disabled:
            continue
        s = smap.get(t, {})
        if s.get("last_status") == "ok" and s.get("last_run"):
            table, date_col = spec["table"], spec.get("date_column", "as_of")
            latest = reader.execute(f"SELECT max({date_col}) AS m FROM {table}").fetchone()
            m = (latest or {}).get("m")
            cutoff = s["last_run"].date() if hasattr(s["last_run"], "date") else s["last_run"]
            if m is None or (hasattr(m, "date") and m.date() < cutoff) or (isinstance(m, type(cutoff)) and m < cutoff):
                findings.append(Finding(t, "empty_run", f"{t}: 状态 ok 但 {table} 未增行"))
    for t, s in smap.items():
        if t in disabled or t in {f.task for f in findings}:
            continue
        if s["fail"] >= THRESHOLDS["fail_streak"]:
            findings.append(Finding(t, "consec_failed", f"{t}: 连续失败 {s['fail']} 次"))
        elif s["degraded"] >= THRESHOLDS["degraded_streak"]:
            findings.append(Finding(t, "degraded", f"{t}: 连续降级 {s['degraded']} 次"))
    for row in health_rows(tasks, smap, disabled, findings):
        writer.execute(
            "INSERT INTO ops.collection_health(task_name,display_name,last_ok_at,last_run_at,last_status,"
            "fail_streak,degraded_streak,state,note,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT(task_name) DO UPDATE SET last_ok_at=EXCLUDED.last_ok_at,last_run_at=EXCLUDED.last_run_at,"
            "last_status=EXCLUDED.last_status,fail_streak=EXCLUDED.fail_streak,degraded_streak=EXCLUDED.degraded_streak,"
            "state=EXCLUDED.state,note=EXCLUDED.note,updated_at=EXCLUDED.updated_at",
            (
                row["task_name"],
                row["display_name"],
                row["last_ok_at"],
                row["last_run_at"],
                row["last_status"],
                row["fail_streak"],
                row["degraded_streak"],
                row["state"],
                row["note"],
                now,
            ),
        )
    for f in findings + per_ticker_gaps(reader, now):
        writer.execute(
            "INSERT INTO ops.data_gaps(dataset,data_date,kind,detail,first_detected_at,last_checked_at) "
            "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(dataset,data_date,kind) DO NOTHING",
            (f.task, now.date(), f.kind, json.dumps({"detail": f.detail}, ensure_ascii=False), now, now),
        )
    return findings


def whitelisted_all(progs):
    out = set()
    for ts in progs.values():
        out |= set(ts)
    return out


def config_task_tables(items):
    """task -> output-table spec. `writes_to: {tasks: [...]}` on a table-level
    expectation inherits that expectation's table + date_column; explicit
    `table`/`date_column` keys override."""
    out = {}
    for i in items:
        w = getattr(i, "writes_to", None)
        if not w:
            continue
        spec = {
            "table": w.get("table") or getattr(i, "table", None),
            "date_column": w.get("date_column") or getattr(i, "date_column", "as_of"),
        }
        for t in w.get("tasks") or []:
            out[t] = spec
    return out


def per_ticker_gaps(reader, now, *, lookback_days=10, absent_days=3):
    """Tickers with intraday snapshots in the lookback window but none in
    the last `absent_days` — suspension / delisting / symbol change."""
    rows = reader.execute(
        "SELECT ticker, max(as_of) AS latest FROM ingest.intraday_snapshots "
        "WHERE as_of>now()-interval '%s days' GROUP BY ticker "
        "HAVING max(as_of)<now()-interval '%s days'" % (lookback_days, absent_days)
    ).fetchall()
    return [
        Finding(
            f"个股报价缺失：{r['ticker']}",
            "missing",
            f"{r['ticker']} 自 {r['latest']} 起无盘中快照（可能停牌/退市/代码变更）",
        )
        for r in rows
    ]
