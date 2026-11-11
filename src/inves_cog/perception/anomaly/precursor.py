"""T-1 flow signals per anomaly member. An anomaly-level annotation only; it never
enters candidate scoring, because every candidate of the same anomaly would share it.

Only rows with date < trade_date are read, so the T session itself can never leak in.
FINRA off-exchange short volume and OCC option volume publish T+1, which is why the
annotation describes the day before the anomaly, not the anomaly day. A point day whose
underlying volume is too small to be meaningful is marked 成交过少，不判 instead of
producing a noisy extreme z-score."""

import statistics

_SHORT = """
SELECT date, short_volume, total_volume
FROM flows.short_volume
WHERE ticker = %s AND date < %s
ORDER BY date DESC
LIMIT %s
"""

_OCC = """
SELECT date, cp, SUM(quantity) AS quantity
FROM flows.option_volume_occ
WHERE underlying = %s AND date < %s
GROUP BY date, cp
ORDER BY date DESC
"""

_BASELINE_MIN = 10


def compute_precursor(
    connection,
    members,
    trade_date,
    direction,
    *,
    baseline_days=20,
    z_threshold=2.0,
    min_baseline=_BASELINE_MIN,
    short_min_volume=1_000_000,
    occ_min_contracts=1_000,
):
    """Flag members whose T-1 short ratio or put/call ratio z-scored |z| >= z_threshold
    against that member's own prior `baseline_days` trading days."""
    tickers = []
    for member in members or []:
        name = member.get("ticker") if isinstance(member, dict) else member
        if isinstance(name, str) and name and name not in tickers:
            tickers.append(name)
    details = []
    for ticker in tickers:
        detail = _member(
            connection,
            ticker,
            trade_date,
            direction,
            baseline_days,
            z_threshold,
            min_baseline,
            short_min_volume,
            occ_min_contracts,
        )
        details.append(detail)
    flagged = [row for row in details if row["flagged"]]
    return {
        "members_flagged": len(flagged),
        "aligned": sum(1 for row in flagged if row["aligned"]),
        "details": details,
        "baseline_days": baseline_days,
        "z_threshold": z_threshold,
    }


def _member(
    connection,
    ticker,
    trade_date,
    direction,
    baseline_days,
    z_threshold,
    min_baseline,
    short_min_volume,
    occ_min_contracts,
):
    short = _short_series(connection, ticker, trade_date, baseline_days)
    occ = _occ_series(connection, ticker, trade_date, baseline_days)
    short_z = _z(short, min_baseline)
    pc_z = _z(occ, min_baseline)
    notes = []
    skipped = set()
    if short["point"] is None:
        notes.append("做空数据不足")
    elif short["point_volume"] is not None and short["point_volume"] < short_min_volume:
        short_z = None
        skipped.add("short")
        notes.append("成交过少，不判")
    if occ["point"] is None:
        notes.append("期权数据不足")
    elif occ["point_volume"] is not None and occ["point_volume"] < occ_min_contracts:
        pc_z = None
        skipped.add("occ")
        notes.append("成交过少，不判")
    for name, z_value, series in (("short", short_z, short), ("occ", pc_z, occ)):
        if (
            name not in skipped
            and z_value is None
            and series["point"] is not None
            and len(series["baseline"]) < min_baseline
        ):
            notes.append("基线样本不足")
            break
    flagged = any(value is not None and abs(value) >= z_threshold for value in (short_z, pc_z))
    if direction == "down":
        aligned = flagged and any(value is not None and value >= z_threshold for value in (short_z, pc_z))
    elif direction == "up":
        aligned = flagged and pc_z is not None and pc_z <= -z_threshold
    else:
        aligned = False
    return {
        "ticker": ticker,
        "as_of": _stamp(short["point_date"] or occ["point_date"]),
        "short_ratio": _round(short["point"]),
        "short_z": _round(short_z),
        "pc_ratio": _round(occ["point"]),
        "pc_z": _round(pc_z),
        "occ_missing": occ["point"] is None,
        "flagged": flagged,
        "aligned": bool(aligned),
        "notes": notes,
    }


def _short_series(connection, ticker, trade_date, baseline_days):
    rows = connection.execute(_SHORT, (ticker, trade_date, baseline_days + 1)).fetchall()
    values = []
    for row in reversed(rows):
        mapped = row if isinstance(row, dict) else dict(row)
        total = mapped.get("total_volume")
        short = mapped.get("short_volume")
        if total and short is not None:
            values.append((mapped.get("date"), float(short) / float(total), float(total)))
    return _split(values)


def _occ_series(connection, ticker, trade_date, baseline_days):
    rows = connection.execute(_OCC, (ticker, trade_date)).fetchall()
    grouped = {}
    for row in rows:
        mapped = row if isinstance(row, dict) else dict(row)
        day = mapped.get("date")
        bucket = grouped.setdefault(day, {})
        bucket[mapped.get("cp")] = bucket.get(mapped.get("cp"), 0.0) + float(mapped.get("quantity") or 0)
    ordered = sorted(grouped, reverse=True)[: baseline_days + 1]
    values = []
    for day in reversed(ordered):
        bucket = grouped[day]
        calls = bucket.get("C") or 0
        if calls > 0:
            volume = calls + (bucket.get("P") or 0)
            values.append((day, (bucket.get("P") or 0) / calls, volume))
    return _split(values)


def _split(values):
    if not values:
        return {"point": None, "point_date": None, "point_volume": None, "baseline": []}
    (point_date, point, point_volume), *rest = reversed(values)
    return {
        "point": point,
        "point_date": point_date,
        "point_volume": point_volume,
        "baseline": [value for _, value, _volume in rest],
    }


def _z(series, min_baseline):
    baseline = series["baseline"]
    if series["point"] is None or len(baseline) < max(2, min_baseline):
        return None
    spread = statistics.stdev(baseline)
    if spread == 0:
        return None
    return (series["point"] - statistics.mean(baseline)) / spread


def _stamp(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _round(value):
    return round(value, 4) if isinstance(value, float) else value


def precursor_line(precursor, member_count=None):
    """One display sentence, or None when no annotation exists at all."""
    if not isinstance(precursor, dict) or precursor.get("unavailable"):
        return None
    details = precursor.get("details") or []
    flagged = precursor.get("members_flagged")
    if flagged is None:
        return None
    total = member_count or len(details)
    if not details or not total:
        return None
    line = f"异动前一日：{flagged}/{total} 只成员场外做空或看跌期权异常（同向 {precursor.get('aligned') or 0}）"
    if all(row.get("occ_missing") for row in details):
        line += "，期权数据不足"
    return line
