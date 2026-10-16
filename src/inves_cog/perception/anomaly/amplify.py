"""Boolean amplification features. Missing inputs stay null."""


def _values(rows, key):
    return [row[key] for row in rows if row.get(key) is not None]


def features(anomaly, snapshot, rule):
    rows = [row for row in snapshot.get("daily") or [] if row["ticker"] in anomaly["tickers"]]
    shorts = snapshot.get("shorts") or {}
    known = [shorts[ticker] for ticker in anomaly["tickers"] if shorts.get(ticker)]
    missing = [ticker for ticker in anomaly["tickers"] if ticker in shorts and shorts[ticker] is None]
    squeeze, reason, inferred = _squeeze(rows, known, missing, rule)
    return {
        "stampede": _stampede(anomaly, snapshot, rows, rule),
        "short_squeeze": squeeze,
        "short_squeeze_reason": reason,
        "publish_date_inferred": inferred,
        "leverage_passive": _leverage(snapshot),
        "leverage_passive_reason": None if _leverage(snapshot) is not None else "指数调整未接通",
        "sentiment": None,
        "implied_vol": None,
        "implied_vol_reason": "未接通",
    }


def _stampede(anomaly, snapshot, rows, rule):
    if not anomaly["basket_ids"] or not rows:
        return False
    share = _basket_share(anomaly, snapshot)
    ranks = _values(rows, "ret_6m_rank")
    jumps = _values(rows, "corr_jump")
    gaps = _values(rows, "gap_open")
    volumes = _values(rows, "volume_mult")
    if not ranks or not jumps or not gaps or not volumes or share is None:
        return False
    return (
        min(ranks) <= rule["stampede_rank"]
        and max(jumps) >= rule["stampede_corr"]
        and min(gaps) <= rule["stampede_gap"]
        and max(volumes) >= rule["stampede_volume"]
        and share >= rule["stampede_same"]
    )


def _basket_share(anomaly, snapshot):
    shares = []
    for identifier in anomaly["basket_ids"]:
        members = snapshot.get("member_returns", {}).get(identifier, {})
        ret = next((row.get("ret_ew") for row in snapshot.get("baskets") or [] if row["basket_id"] == identifier), None)
        if ret in (None, 0) or not members:
            continue
        usable = [value for value in members.values() if value not in (None, 0)]
        if usable:
            shares.append(sum((value > 0) == (ret > 0) for value in usable) / len(usable))
    return max(shares) if shares else None


def _squeeze(rows, known, missing, rule):
    if missing and not known:
        return None, "数据暂缺", False
    if not known or not rows:
        return False, None, False
    gaps = _values(rows, "gap_open")
    volumes = _values(rows, "volume_mult")
    rets = _values(rows, "ret")
    inferred = any(item.get("publish_date_inferred") for item in known if item)
    triggered = (
        any(
            item
            and (
                (item.get("si_pct") or 0) >= rule["squeeze_si"]
                or (item.get("days_to_cover") or 0) >= rule["squeeze_days"]
            )
            for item in known
        )
        and gaps
        and max(gaps) >= rule["squeeze_gap"]
        and volumes
        and max(volumes) >= rule["squeeze_volume"]
        and rets
        and max(rets) > 0
    )
    return triggered, None, inferred


def _leverage(snapshot):
    calendar = snapshot.get("calendar") or {}
    if calendar.get("index_rebalance") or calendar.get("option_expiry"):
        return True
    if calendar.get("index_rebalance_connected") is False:
        return None
    return False


def candidates(anomaly, snapshot, rule):
    found = []
    if (
        "rotation_style" in anomaly["entry_paths"]
        or "rotation_sector" in anomaly["entry_paths"]
        or "rotation_theme" in anomaly["entry_paths"]
    ):
        found.append("主题轮动")
    if anomaly.get("amplification", {}).get("stampede"):
        found.append("踩踏")
    if anomaly.get("amplification", {}).get("short_squeeze"):
        found.append("轧空")
    if anomaly.get("layer") == "L1" and _macro(snapshot, rule):
        found.append("宏观/流动性")
    return found or ["待定"]


def _macro(snapshot, rule):
    hot = 0
    for key in ("VIX", "DGS2", "DTWEXBGS", "DCOILWTICO"):
        row = (snapshot.get("macro") or {}).get(key) or {}
        if row.get("z") is not None and abs(row["z"]) >= rule["macro_z"]:
            hot += 1
    return hot >= 2
