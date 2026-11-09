"""资金动向卡：内部人交易、FINRA 场外成交、空头持仓。

纯函数：输入 connection、ticker、as_of（页面日期对应的可见时点），输出 dict。
页面只格式化，不重算；阈值全部来自 config 参数。PIT：Form 4 按 filed_at ≤ as_of；
空头按 publish_date ≤ as_of（空则推断发布日）；场外成交按 FINRA 次日发布。"""

from datetime import date, datetime, timezone
from pathlib import Path

from inves_cog.ingest.market import next_trading_day

_DEFAULTS = {
    "insider_days": 90,
    "insider_top_people": 5,
    "insider_bullish_buy_usd": 1_000_000,
    "insider_bearish_unplanned_sell_usd": 10_000_000,
    "offexchange_days": 20,
    "offexchange_spike_multiple": 2.0,
    "short_periods": 8,
    "short_change_threshold_pct": 10.0,
    "publish_lag_sessions": 9,
}

_EXCLUDED_CODES = {"A", "G", "F", "M"}


def _params(params):
    if params is None:
        from inves_cog.params import load_params

        params = (load_params(Path("config/params/p-2026.10")).get("m1") or {}).get("smartmoney") or {}
    merged = dict(_DEFAULTS)
    merged.update(params)
    return merged


def _day(as_of):
    if isinstance(as_of, datetime):
        return as_of.date() if as_of.tzinfo is None else as_of.astimezone(timezone.utc).date()
    if isinstance(as_of, date):
        return as_of
    return date.fromisoformat(str(as_of)[:10])


def _inferred_publish(settlement, sessions):
    day = settlement
    for _ in range(sessions):
        day = next_trading_day(day)
    return day


def _bucket(buckets, key):
    return buckets[key]


def _insiders(connection, ticker, day, p):
    rows = connection.execute(
        """
        SELECT insider_name, officer_title, is_director, aff10b5_one, transaction_code, shares, price, amount
        FROM ingest.form4_events
        WHERE ticker = %s AND filed_at <= %s AND filed_at >= %s - %s * INTERVAL '1 day'
        ORDER BY filed_at DESC
        """,
        (ticker, day, day, p["insider_days"]),
    ).fetchall()
    if not rows:
        return {"missing": "近 90 天无 Form 4 申报", "label": "中性", "people": [], "totals": {}, "excluded_count": 0}

    people = {}
    # key -> {"people": set, "usd": float}
    totals = {k: {"people": set(), "usd": 0.0} for k in ("unplanned", "planned", "unknown_plan", "buys")}
    excluded = 0
    for name, title, director, plan, code, shares, price, amount in rows:
        name = name or "未知"
        if code in _EXCLUDED_CODES or code not in {"P", "S"}:
            excluded += 1
            continue
        usd = float(amount) if amount is not None else (float(shares) * float(price) if shares and price else 0.0)
        entry = people.setdefault(name, {"title": None, "director": False, "buy": 0.0, "sell": 0.0})
        entry["title"] = entry["title"] or title
        entry["director"] = entry["director"] or bool(director)
        if code == "P":
            entry["buy"] += usd
            key = "buys"
        else:
            entry["sell"] += usd
            key = "unknown_plan" if plan is None else ("planned" if plan else "unplanned")
        totals[key]["people"].add(name)
        totals[key]["usd"] += usd

    ranked = sorted(people.items(), key=lambda kv: kv[1]["buy"] + kv[1]["sell"], reverse=True)[
        : p["insider_top_people"]
    ]
    buys_usd = totals["buys"]["usd"]
    unplanned_usd = totals["unplanned"]["usd"]
    if buys_usd >= p["insider_bullish_buy_usd"]:
        label = "偏多"
    elif unplanned_usd >= p["insider_bearish_unplanned_sell_usd"] and buys_usd == 0:
        label = "偏空"
    else:
        label = "中性"
    return {
        "missing": None,
        "label": label,
        "people": [
            {
                "name": name,
                "title": info["title"] or ("董事" if info["director"] else "暂缺"),
                "buy": info["buy"],
                "sell": info["sell"],
            }
            for name, info in ranked
        ],
        "totals": {k: {"people": len(v["people"]), "usd": v["usd"]} for k, v in totals.items()},
        "excluded_count": excluded,
        "as_of_note": f"近 {p['insider_days']} 天 · 按申报日",
    }


def _offexchange(connection, ticker, day, p):
    volume = connection.execute(
        "SELECT date, total_volume FROM flows.short_volume"
        " WHERE ticker = %s AND date <= %s ORDER BY date DESC LIMIT %s",
        (ticker, day, p["offexchange_days"] + 10),
    ).fetchall()
    if not volume:
        return {"missing": "该股不在 FINRA 返回中", "label": "暂缺", "series": []}
    closes = {
        r[0]: float(r[1])
        for r in connection.execute(
            """
            SELECT trade_date, close FROM ingest.bars_daily
            WHERE ticker = %s AND trade_date <= %s ORDER BY trade_date DESC LIMIT %s
            """,
            (ticker, day, p["offexchange_days"] + 10),
        )
    }
    visible = [
        {
            "date": vdate,
            "amount": None if closes.get(vdate) is None else float(total) * closes[vdate],
        }
        for vdate, total in volume
        if next_trading_day(vdate) <= day
    ]
    visible.sort(key=lambda r: r["date"])
    series = visible[-p["offexchange_days"] :]
    amounts = [r["amount"] for r in series if r["amount"] is not None]
    latest = series[-1]["amount"] if series else None
    mean = sum(amounts) / len(amounts) if amounts else None
    ratio = None if latest is None or not mean else latest / mean
    return {
        "missing": None,
        "label": "暂缺"
        if ratio is None
        else ("正常" if ratio < p["offexchange_spike_multiple"] else f"放量 {ratio:.1f} 倍"),
        "series": series,
        "latest_amount": latest,
        "mean_amount": mean,
        "ratio": ratio,
        "as_of_note": "近 20 个交易日 · FINRA 次日发布",
    }


def _short(connection, ticker, day, p):
    rows = connection.execute(
        """
        SELECT settlement_date, publish_date, short_interest, days_to_cover
        FROM ingest.short_interest WHERE ticker = %s ORDER BY settlement_date DESC
        """,
        (ticker,),
    ).fetchall()
    lag = p["publish_lag_sessions"]
    visible = []
    for settlement, publish, short, dtc in rows:
        pub = publish or _inferred_publish(settlement, lag)
        if pub <= day:
            visible.append(
                {
                    "settlement": settlement,
                    "publish": pub,
                    "publish_inferred": publish is None,
                    "short_interest": short,
                    "days_to_cover": dtc,
                }
            )
    if not visible:
        return {"missing": "无 FINRA 持仓记录", "label": "暂缺", "series": []}
    latest = visible[0]
    prev = visible[1] if len(visible) > 1 else None
    change = None
    if prev and prev["short_interest"]:
        change = (float(latest["short_interest"]) / float(prev["short_interest"]) - 1) * 100
    shares = connection.execute(
        """
        SELECT shares FROM fundamentals.fin_state
        WHERE ticker = %s AND extractor = 'fixed' AND filed <= %s
        ORDER BY filed DESC LIMIT 1
        """,
        (ticker, day),
    ).fetchone()
    si_pct = None
    if shares and shares[0] and latest["short_interest"] is not None:
        si_pct = float(latest["short_interest"]) / float(shares[0]) * 100
    threshold = p["short_change_threshold_pct"]
    label = (
        "暂缺"
        if change is None
        else ("空头增加" if change >= threshold else "空头回补" if change <= -threshold else "平稳")
    )
    return {
        "missing": None,
        "label": label,
        "latest": {**latest, "si_pct": si_pct},
        "change_pct": change,
        "series": [r["short_interest"] for r in reversed(visible[: p["short_periods"]])],
        "as_of_note": "半月一期 · 按发布日",
    }


def money_flow(connection, ticker, as_of, params=None):
    p = _params(params)
    day = _day(as_of)
    insiders = _insiders(connection, ticker, day, p)
    offexchange = _offexchange(connection, ticker, day, p)
    short = _short(connection, ticker, day, p)
    labels = [insiders.get("label"), offexchange.get("label"), short.get("label")]
    directional = [item for item in labels if item not in {"中性", "正常", "平稳", "暂缺", None}]
    return {
        "ticker": ticker,
        "as_of": day.isoformat(),
        "labels": labels,
        "summary": "三层都没有明显方向" if not directional else "、".join(directional),
        "insiders": insiders,
        "offexchange": offexchange,
        "short": short,
    }
