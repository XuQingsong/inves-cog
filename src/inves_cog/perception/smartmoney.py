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

        directory = Path(__file__).resolve().parents[3] / "config/params/p-2026.10"
        params = (load_params(directory).values.get("m1") or {}).get("smartmoney") or {}
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
        return {"missing": "近 90 天无内部人申报", "label": "中性", "people": [], "totals": {}, "excluded_count": 0}

    people = {}
    # key -> {"people": set, "usd": float}
    totals = {k: {"people": set(), "usd": 0.0} for k in ("unplanned", "planned", "unknown_plan", "buys")}
    excluded = 0
    for row in rows:
        name = row["insider_name"] or "未知"
        code = row["transaction_code"]
        if code in _EXCLUDED_CODES or code not in {"P", "S"}:
            excluded += 1
            continue
        amount = row["amount"]
        shares, price = row["shares"], row["price"]
        usd = float(amount) if amount is not None else (float(shares) * float(price) if shares and price else 0.0)
        entry = people.setdefault(name, {"title": None, "director": False, "buy": 0.0, "sell": 0.0})
        entry["title"] = entry["title"] or row["officer_title"]
        entry["director"] = entry["director"] or bool(row["is_director"])
        if code == "P":
            entry["buy"] += usd
            key = "buys"
        else:
            entry["sell"] += usd
            key = "unknown_plan" if row["aff10b5_one"] is None else ("planned" if row["aff10b5_one"] else "unplanned")
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
        r["trade_date"]: float(r["close"])
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
            "date": r["date"],
            "amount": None if closes.get(r["date"]) is None else float(r["total_volume"]) * closes[r["date"]],
        }
        for r in volume
        if next_trading_day(r["date"]) <= day
    ]
    visible.sort(key=lambda r: r["date"])
    series = visible[-p["offexchange_days"] :]
    amounts = [r["amount"] for r in series if r["amount"] is not None]
    latest = series[-1]["amount"] if series else None
    sufficient = len(amounts) >= p["offexchange_days"]
    mean = sum(amounts) / len(amounts) if (amounts and sufficient) else None
    ratio = None if latest is None or not mean else latest / mean
    return {
        "missing": None,
        "label": "暂缺"
        if latest is None
        else ("正常" if ratio is None or ratio < p["offexchange_spike_multiple"] else f"放量 {ratio:.1f} 倍"),
        "series": series,
        "latest_amount": latest,
        "mean_amount": mean,
        "ratio": ratio,
        "insufficient": not sufficient,
        "as_of_note": (
            f"近 {len(series)} 个交易日（数据自 {series[0]['date']} 起）· FINRA 次日发布"
            if series
            else "FINRA 次日发布"
        ),
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
    for r in rows:
        pub = r["publish_date"] or _inferred_publish(r["settlement_date"], lag)
        if pub <= day:
            visible.append(
                {
                    "settlement": r["settlement_date"],
                    "publish": pub,
                    "publish_inferred": r["publish_date"] is None,
                    "short_interest": r["short_interest"],
                    "days_to_cover": r["days_to_cover"],
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
    if shares and shares["shares"] and latest["short_interest"] is not None:
        si_pct = float(latest["short_interest"]) / float(shares["shares"]) * 100
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


def _usd_short(usd):
    usd = float(usd or 0)
    if abs(usd) >= 1e9:
        return f"${usd / 1e8:.1f} 亿"
    if abs(usd) >= 1e8:
        return f"${usd / 1e8:.2f} 亿"
    if abs(usd) >= 1e4:
        return f"${usd / 1e4:.0f} 万"
    return f"${usd:.0f}"


def money_flow(connection, ticker, as_of, params=None):
    p = _params(params)
    day = _day(as_of)
    insiders = _insiders(connection, ticker, day, p)
    offexchange = _offexchange(connection, ticker, day, p)
    short = _short(connection, ticker, day, p)
    labels = [insiders.get("label"), offexchange.get("label"), short.get("label")]
    parts, neutral, absent = [], [], []
    if insiders.get("missing") or insiders.get("label") == "暂缺":
        absent.append("内部人")
    elif insiders["label"] != "中性":
        t = insiders["totals"]
        detail = (
            f"买入 {_usd_short(t['buys']['usd'])}"
            if insiders["label"] == "偏多"
            else f"计划外卖出 {_usd_short(t['unplanned']['usd'])}"
        )
        parts.append(f"内部人{insiders['label']}：{detail}")
    else:
        neutral.append("内部人")
    if offexchange.get("missing") or offexchange.get("label") == "暂缺":
        absent.append("场外成交")
    elif offexchange["label"].startswith("放量"):
        parts.append(f"场外成交{offexchange['label']}")
    else:
        neutral.append("场外成交")
    if short.get("missing") or short.get("label") == "暂缺":
        absent.append("空头")
    elif short["label"] in {"空头增加", "空头回补"}:
        chg = short.get("change_pct")
        suffix = f"（较上期 {chg:+.1f}%）" if chg is not None else ""
        parts.append(f"空头{short['label'].replace('空头', '')}{suffix}")
    else:
        neutral.append("空头")
    if not parts:
        summary = (
            "三层都没有明显方向" if not absent else f"{'、'.join(neutral) or '三层'}无明显方向，{'、'.join(absent)}暂缺"
        )
    else:
        summary = "；".join(parts)
        if neutral:
            summary += f"；{'、'.join(neutral)}无明显变化"
        if absent:
            summary += f"，{'、'.join(absent)}暂缺"
    return {
        "ticker": ticker,
        "as_of": day.isoformat(),
        "labels": labels,
        "summary": summary,
        "insiders": insiders,
        "offexchange": offexchange,
        "short": short,
    }
