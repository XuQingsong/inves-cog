"""个股期权成交（OCC 按账户类型口径，T+1 发布）。

纯函数：输入 connection、ticker、as_of（页面日期），只用 date < as_of 的已发布数据。
输出最新一日的看涨/看跌量、put/call 比、相对前 20 个交易日的倍数与 z 值、
按 account_type 的客户/做市/自营占比。页面只格式化；阈值全部来自 m1 smartmoney。
"""

import math
from datetime import date, datetime, timezone
from pathlib import Path

_OCC = """
SELECT date, cp, account_type, SUM(quantity) AS quantity
FROM flows.option_volume_occ
WHERE underlying = %s AND date < %s
GROUP BY date, cp, account_type
ORDER BY date DESC
"""

_DEFAULTS = {
    "options_baseline_days": 20,
    "options_min_contracts": 1000,
    "options_min_history": 10,
    "options_spike_multiple": 3.0,
    "options_pc_z": 2.0,
}


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


def _round(value, digits=2):
    return None if value is None else round(value, digits)


def options_activity(connection, ticker, as_of, params=None):
    """Latest published OCC day plus a 20-day baseline; labels 放量 only when both
    volume and put/call z point the same way. OCC 不区分买卖方向、开仓/平仓不明."""
    p = _params(params)
    day = _day(as_of)
    rows = connection.execute(_OCC, (ticker, day)).fetchall()
    grouped = {}
    for row in rows:
        r = row if isinstance(row, dict) else dict(row)
        bucket = grouped.setdefault(r["date"], {"C": 0.0, "P": 0.0, "accounts": {}})
        qty = float(r["quantity"] or 0)
        bucket[r["cp"]] = bucket.get(r["cp"], 0.0) + qty
        accounts = bucket["accounts"]
        accounts[r["account_type"]] = accounts.get(r["account_type"], 0.0) + qty
    if not grouped:
        return {"ticker": ticker, "as_of": day.isoformat(), "missing": "无 OCC 期权成交记录", "label": "暂缺"}

    ordered = sorted(grouped, reverse=True)
    latest, baseline = ordered[0], ordered[1 : p["options_baseline_days"] + 1]
    point = grouped[latest]
    calls, puts = point.get("C", 0.0), point.get("P", 0.0)
    total = calls + puts
    pc = puts / calls if calls > 0 else None
    base_calls = [grouped[d].get("C", 0.0) for d in baseline]
    base_puts = [grouped[d].get("P", 0.0) for d in baseline]
    base_pc = [grouped[d]["P"] / grouped[d]["C"] for d in baseline if grouped[d].get("C", 0) > 0]

    call_multiple = calls / (sum(base_calls) / len(base_calls)) if base_calls and sum(base_calls) > 0 else None
    put_multiple = puts / (sum(base_puts) / len(base_puts)) if base_puts and sum(base_puts) > 0 else None
    pc_z = None
    if pc is not None and len(base_pc) >= 2:
        mean = sum(base_pc) / len(base_pc)
        variance = sum((v - mean) ** 2 for v in base_pc) / len(base_pc)
        if variance > 0:
            pc_z = (pc - mean) / math.sqrt(variance)

    accounts = point["accounts"]
    total_accounts = sum(accounts.values())
    shares = {name: (accounts.get(name, 0.0) / total_accounts if total_accounts else None) for name in "CMF"}

    if total < p["options_min_contracts"]:
        label = "成交过少，不判"
    elif len(baseline) < p["options_min_history"]:
        label = "历史不足"
    elif (
        call_multiple is not None
        and call_multiple >= p["options_spike_multiple"]
        and pc_z is not None
        and pc_z <= -p["options_pc_z"]
    ):
        label = "看涨放量"
    elif (
        put_multiple is not None
        and put_multiple >= p["options_spike_multiple"]
        and pc_z is not None
        and pc_z >= p["options_pc_z"]
    ):
        label = "看跌放量"
    else:
        label = "正常"

    series = [
        {"date": d.isoformat(), "pc": _round(grouped[d]["P"] / grouped[d]["C"], 3) if grouped[d].get("C") else None}
        for d in sorted([latest] + baseline)
    ]
    return {
        "ticker": ticker,
        "as_of": day.isoformat(),
        "data_date": latest.isoformat(),
        "call_volume": int(calls),
        "put_volume": int(puts),
        "total_volume": int(total),
        "pc_ratio": _round(pc, 3),
        "call_multiple": _round(call_multiple),
        "put_multiple": _round(put_multiple),
        "pc_z": _round(pc_z),
        "customer_share": _round(shares["C"], 3),
        "mm_share": _round(shares["M"], 3),
        "firm_share": _round(shares["F"], 3),
        "baseline_days": len(baseline),
        "label": label,
        "series": series,
    }
