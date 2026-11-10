"""Verdict computation for review labels. All PIT: only data visible at
the horizon close may be used. Thresholds read from config."""

import math
from pathlib import Path

PROMPT = (Path(__file__).resolve().parents[4] / "config/prompts/review_message.txt").read_text()
Z_CONFIRM, Z_DENY, EPS_DELTA = 0.5, -0.5, 1.0


def _bars(conn, tickers, start, end):
    # Bounded window: 90 trading days back is enough for the 60-day sigma.
    rows = conn.execute(
        "SELECT ticker, trade_date, close FROM ingest.bars_daily "
        "WHERE ticker=ANY(%s) AND trade_date>=%s AND trade_date<=%s",
        (list(tickers), start, end),
    ).fetchall()
    return rows


def _returns(rows, ticker, end):
    closes = [
        r["close"]
        for r in sorted((x for x in rows if x["ticker"] == ticker), key=lambda r: r["trade_date"])
        if r["trade_date"] <= end
    ]
    rets = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes)) if closes[i - 1]]
    return closes, rets


def market_verdict(conn, case, horizon, due, visible, hits):
    """second_hits outcome wins; else price-based continuation/reversal."""
    confirmed = [h["info_id"] for h in hits if h["outcome"] == "确认"]
    denied = [h["info_id"] for h in hits if h["outcome"] == "否定"]
    if confirmed:
        return "确认", "二次命中", {"info_ids": confirmed}
    if denied:
        return "否定", "二次命中", {"info_ids": denied}
    members = case.get("member_tickers") or []
    if not members:
        return "未定", "按价格延续/反转", {"reason": "无成员股"}
    direction = 1 if case.get("direction") in ("up", 1) else -1
    n_sessions = {"T+1": 1, "T+5": 5, "T+20": 20}[horizon]
    anchor = case["trade_date"]
    from datetime import timedelta as _td

    rows = _bars(conn, set(members) | {"SPY"}, anchor - _td(days=130), due)
    zs = []
    for t in members:
        closes, rets = _returns(rows, t, due)
        spy_closes, _ = _returns(rows, "SPY", due)
        if len(closes) < n_sessions + 2 or len(spy_closes) < n_sessions + 2:
            continue
        r_t = closes[-1] / closes[-1 - n_sessions] - 1
        r_spy = spy_closes[-1] / spy_closes[-1 - n_sessions] - 1
        sigma_window = rets[-(60 + n_sessions) : -n_sessions] or rets[:60]
        if len(sigma_window) < 10:
            continue
        mu = sum(sigma_window) / len(sigma_window)
        sigma = math.sqrt(sum((x - mu) ** 2 for x in sigma_window) / max(len(sigma_window) - 1, 1))
        if sigma <= 0:
            continue
        zs.append((r_t - r_spy) / (sigma * math.sqrt(n_sessions)))
    if not zs:
        return "未定", "按价格延续/反转", {"reason": "价格数据不足"}
    z = sum(zs) / len(zs)
    dz = direction * z
    verdict = "确认" if dz >= Z_CONFIRM else ("否定" if dz <= Z_DENY else "未定")
    label = {"确认": "市场确认（延续）", "否定": "市场否定（反转）", "未定": "未定"}[verdict]
    return label, "按价格延续/反转", {"z": round(z, 3), "members": len(zs), "direction": direction}


def _candidate_info(conn, case, visible, due):
    """Post-session to horizon-close infos, excluding cause_info_ids, <=30.
    Order: most member hits first, then 8-K priority, then publish time."""
    cause_ids = case.get("cause_info_ids") or []
    members = list(case.get("member_tickers") or [])
    start = case.get("session_start") or case["trade_date"]
    rows = list(
        conn.execute(
            "SELECT info_id, kind, published_at, source, headline, left(body, 400) AS body, tickers "
            "FROM ingest.info_items WHERE published_at > %s AND published_at <= %s "
            "AND info_id != ALL(%s) AND tickers && %s",
            (start, visible, cause_ids, members),
        ).fetchall()
    )
    member_set = set(members)

    def key(row):
        hits = len(member_set & set(row.get("tickers") or []))
        is_8k = 1 if (row.get("kind") or "") == "8-K" else 0
        return (-hits, -is_8k, row["published_at"])

    return sorted(rows, key=key)[:30]


TASK = "review_message"


def message_verdict(conn, case, horizon, due, visible, client):
    """LLM verdict with the verbatim prompt file; call failure is 未判定,
    invalid output downgrades to 仍未知."""
    infos = _candidate_info(conn, case, visible, due)
    cause = case.get("cause_text") or "（无候选原因）"
    payload = {
        "指令": PROMPT,
        "异动": {
            "日期": str(case["trade_date"]),
            "时段": case.get("session"),
            "方向": case.get("direction_label"),
            "股票": case.get("member_tickers"),
        },
        "候选原因": cause,
        "后续信息": [
            {
                "编号": i["info_id"],
                "发布时间": str(i["published_at"]),
                "来源": i["source"],
                "标题": i["headline"],
                "摘要": i["body"],
            }
            for i in infos
        ],
    }
    try:
        raw = client.call(TASK, payload)
    except Exception as exc:
        return (
            "未判定（模型调用失败）",
            "模型",
            {
                "error": f"{type(exc).__name__}: {exc}",
                "raw": None,
            },
        )
    allowed_ids = {i["info_id"] for i in infos}
    verdict = (raw or {}).get("verdict")
    ids = [x for x in (raw or {}).get("info_ids", []) if x in allowed_ids]
    if verdict not in ("证实", "证伪", "仍未知"):
        verdict = "仍未知"
    if verdict in ("证实", "证伪") and not ids:
        verdict = "仍未知"
    other_ids = [x for x in (raw or {}).get("other_info_ids", []) if x in allowed_ids]
    other_cause = (raw or {}).get("other_cause") or ""
    return (
        verdict,
        "模型",
        {
            "raw": raw,
            "info_ids": ids,
            "other_cause": other_cause,
            "other_info_ids": other_ids,
            "prompt_file": "config/prompts/review_message.txt",
        },
    )


def _member_business(conn, ticker, anchor, due, direction):
    pre = conn.execute(
        "SELECT eps_avg FROM valuation_v1.consensus_snapshots WHERE ticker=%s AND kind='estimate' "
        "AND horizon='FY1' AND fetched_at::date<=%s ORDER BY fetched_at DESC LIMIT 1",
        (ticker, anchor),
    ).fetchone()
    post = conn.execute(
        "SELECT eps_avg, fetched_at FROM valuation_v1.consensus_snapshots WHERE ticker=%s AND kind='estimate' "
        "AND horizon='FY1' AND fetched_at::date<=%s ORDER BY fetched_at DESC LIMIT 1",
        (ticker, due),
    ).fetchone()
    if not pre or not post or pre["eps_avg"] in (None, 0):
        return "数据不足", {"ticker": ticker}
    delta = (float(post["eps_avg"]) - float(pre["eps_avg"])) / abs(float(pre["eps_avg"])) * 100
    if abs(delta) < EPS_DELTA:
        verdict = "未见变化"
    elif (delta > 0) == (direction > 0):
        verdict = "经营面印证"
    else:
        verdict = "经营面相反"
    ev = {
        "ticker": ticker,
        "pre_eps": float(pre["eps_avg"]),
        "post_eps": float(post["eps_avg"]),
        "delta_pct": round(delta, 2),
    }
    card = conn.execute(
        "SELECT report_date, card->>'eps_actual' AS actual, card->>'eps_expected' AS expected "
        "FROM perception.earnings_cards WHERE ticker=%s AND report_date>%s AND report_date<=%s "
        "ORDER BY report_date LIMIT 1",
        (ticker, anchor, due),
    ).fetchone()
    if card:
        ev["earnings_in_window"] = {
            "report_date": str(card["report_date"]),
            "actual": card.get("actual"),
            "expected": card.get("expected"),
        }
    return verdict, ev


def business_verdict(conn, case, due, visible):
    """T+20 only: AV FY1 eps_avg per member; basket decides by majority."""
    members = case.get("member_tickers") or []
    if not members:
        return "数据不足", "Alpha Vantage", {"reason": "无成员股"}
    anchor = case["trade_date"]
    direction = 1 if case.get("direction") in ("up", 1) else -1
    results, evs = {}, {}
    for t in members:
        results[t], evs[t] = _member_business(conn, t, anchor, due, direction)
    scored = [r for r in results.values() if r != "数据不足"]
    if not scored:
        return "数据不足", "Alpha Vantage", {"members": evs}
    from collections import Counter

    verdict = Counter(scored).most_common(1)[0][0]
    return verdict, "Alpha Vantage", {"majority": verdict, "members": evs}
