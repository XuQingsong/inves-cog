"""Turn one day's price snapshot into merged anomalies."""

import math
from pathlib import Path

import numpy as np

from inves_cog.params import load_params
from inves_cog.perception.anomaly.quality import same_sign_share, trailing_z


def limits():
    directory = Path(__file__).resolve().parents[4] / "config/params/p-2026.10"
    loaded = load_params(directory)
    return loaded.params_version, loaded.values["m7"]


def _sign(value):
    if value is None or not np.isfinite(value) or value == 0:
        return None
    return "up" if value > 0 else "down"


def _member(ticker, row):
    return {
        "ticker": ticker,
        "ret": None if row is None else row.get("ret"),
        "resid": None if row is None else row.get("resid"),
        "resid_z": None if row is None else row.get("resid_z"),
        "vol_mult": None if row is None else row.get("volume_mult"),
    }


def _draft(snapshot, path, severity, score, tickers, baskets, basket_ids):
    return {
        "trade_date": snapshot["trade_date"],
        "session": snapshot["session"],
        "entry_paths": [path],
        "severity": severity,
        "baskets": list(baskets),
        "basket_ids": list(basket_ids),
        "tickers": set(tickers),
        "member_returns": tickers if isinstance(tickers, dict) else {},
        "score": score,
        "universe": "pool",
    }


def _basket_hits(snapshot, rule, blocked):
    hits = []
    for basket in snapshot.get("baskets") or []:
        identifier = basket["basket_id"]
        members = snapshot.get("member_returns", {}).get(identifier, {})
        if members and set(members) <= blocked:
            continue
        history = list(snapshot.get("basket_history", {}).get(identifier) or [])
        score = trailing_z(history, rule["sigma_min"]) if history else None
        share = same_sign_share(members, basket.get("ret_ew"))
        name = snapshot.get("names", {}).get(identifier, identifier)
        level = snapshot.get("levels", {}).get(identifier)
        common = (snapshot, score, members, [name], [identifier])
        if score is not None and abs(score) >= rule["path_a_z"] and (share or 0) >= rule["path_a_same_sign"]:
            hits.append(_draft(*common[:1], "A", "alert", score, members, *common[3:]))
        elif (
            score is not None
            and abs(score) >= rule["watch_z"]
            and (share or 0) >= rule["watch_same_sign"]
            and basket.get("ret_ew") is not None
            and abs(basket["ret_ew"]) >= rule["watch_abs_ret"]
        ):
            hits.append(_draft(snapshot, "A_watch", "watch", score, members, [name], [identifier]))
        elif _linked(basket, members, share, rule):
            hits.append(_draft(snapshot, "A_linked", "watch", score, members, [name], [identifier]))
        resid_z = basket.get("resid_z")
        if resid_z is not None and abs(resid_z) >= rule["path_b_basket_z"]:
            hits.append(_draft(snapshot, "B_basket", "alert", resid_z, members, [name], [identifier]))
        if level is not None:
            for hit in hits:
                hit.setdefault("level", level)
    return hits


def _linked(basket, members, share, rule):
    ret = basket.get("ret_ew")
    priced = [value for value in members.values() if value is not None]
    return (
        ret is not None
        and abs(ret) >= rule["linked_abs_ret"]
        and (share or 0) >= rule["linked_same_sign"]
        and priced
        and all(abs(value) >= rule["linked_member_abs_ret"] for value in priced)
    )


def _stock_hits(snapshot, rule, blocked):
    hits = []
    for row in snapshot.get("daily") or []:
        if row["ticker"] in blocked or row.get("resid_z") is None and row.get("ret") is None:
            continue
        if not _path_b(row, rule):
            continue
        hits.append(_draft(snapshot, "B", "alert", row.get("resid_z"), [row["ticker"]], [], []))
    return hits


def _path_b(row, rule):
    ret, resid = row.get("ret"), row.get("resid")
    if ret is None or resid is None or abs(ret) < rule["path_b_abs_ret"] or np.sign(ret) != np.sign(resid) or ret == 0:
        return False
    resid_z = row.get("resid_z")
    return resid_z is not None and abs(resid_z) >= rule["path_b_z"]


def _index_hits(snapshot, rule):
    hits = []
    rows = {(row["group_kind"], row["group_id"]): row for row in snapshot.get("rotation") or []}
    for key, row in rows.items():
        kind, name = key
        if kind in {"index", "sector"} and row.get("z") is not None and abs(row["z"]) >= rule["path_c_z"]:
            hits.append(_draft(snapshot, "C", "alert", row["z"], [name], [], []))
    spy, qqq = rows.get(("index", "SPY")), rows.get(("index", "QQQ"))
    vix = (snapshot.get("macro") or {}).get("VIX") or {}
    jump = None
    if vix.get("level") not in (None, 0) and vix.get("prev") not in (None, 0):
        jump = vix["level"] / vix["prev"] - 1
    absolute = (
        (spy and spy.get("ret") is not None and abs(spy["ret"]) >= rule["spy_abs"])
        or (qqq and qqq.get("ret") is not None and abs(qqq["ret"]) >= rule["qqq_abs"])
        or (jump is not None and jump >= rule["vix_jump"])
    )
    if absolute:
        score = spy["z"] if spy and spy.get("z") is not None else 0
        hosts = [hit for hit in hits if "C" in hit["entry_paths"]]
        if hosts:
            for hit in hosts:
                if "C_abs" not in hit["entry_paths"]:
                    hit["entry_paths"].append("C_abs")
        else:
            hits.append(_draft(snapshot, "C_abs", "watch", score, ["SPY"], [], []))
    return hits


def _macro_hits(snapshot, rule):
    hits = []
    for key in ("VIX", "DGS2", "DTWEXBGS", "DCOILWTICO"):
        row = (snapshot.get("macro") or {}).get(key) or {}
        score = row.get("z")
        if score is not None and abs(score) >= rule["path_c_z"]:
            hits.append(_draft(snapshot, "C", "alert", score, [key], [], []))
    return hits


def _rotation_hits(snapshot, rule):
    hits = []
    rows = list(snapshot.get("rotation") or [])
    by_key = {(row["group_kind"], row["group_id"]): row for row in rows}
    spy = by_key.get(("index", "SPY"))
    spy_z = abs(spy["z"]) if spy and spy.get("z") is not None else None
    for name in ("iwm_qqq", "mtum_vlue"):
        row = by_key.get(("style", name))
        if row and row.get("z") is not None and abs(row["z"]) >= rule["style_z"]:
            hits.append(_draft(snapshot, "rotation_style", "alert", row["z"], [name], [], []))
    sectors = [row for row in rows if row["group_kind"] == "sector" and row.get("z") is not None]
    if sectors and spy_z is not None and spy_z < rule["spy_calm_z"]:
        spread = max(row["z"] for row in sectors) - min(row["z"] for row in sectors)
        if spread >= rule["sector_spread_z"]:
            strong = max(sectors, key=lambda row: row["z"])
            weak = min(sectors, key=lambda row: row["z"])
            hits.append(
                _draft(snapshot, "rotation_sector", "watch", spread, [strong["group_id"], weak["group_id"]], [], [])
            )
    themes = [row for row in rows if row["group_kind"] == "l3" and row.get("z") is not None]
    high = [row for row in themes if row["z"] >= rule["theme_z"]]
    low = [row for row in themes if row["z"] <= -rule["theme_z"]]
    if high and low and spy_z is not None and spy_z < rule["spy_calm_z"]:
        pair = high + low
        names = [snapshot.get("names", {}).get(row["group_id"], row["group_id"]) for row in pair]
        hits.append(
            _draft(
                snapshot,
                "rotation_theme",
                "alert",
                max(abs(row["z"]) for row in pair),
                [],
                names,
                [row["group_id"] for row in pair],
            )
        )
    return hits


def _multi_hits(snapshot, rule, blocked):
    hits = []
    daily = {row["ticker"]: row for row in snapshot.get("daily") or []}
    for ticker, history in (snapshot.get("daily_history") or {}).items():
        if ticker in blocked:
            continue
        for window, label in ((3, "multi_3d"), (5, "multi_5d")):
            score = _cumulative(history, window, rule)
            if score is None:
                continue
            hits.append(_draft(snapshot, label, "alert", score, [ticker], [], []))
            if ticker in daily:
                hits[-1]["tickers"] = {ticker}
    return hits


def _cumulative(history, window, rule):
    if len(history) < window:
        return None
    chosen = history[-window:]
    residuals = [row.get("resid") for row in chosen]
    sigma = chosen[-1].get("sigma")
    if any(value is None for value in residuals) or not sigma:
        return None
    total = sum(residuals)
    if total == 0:
        return None
    score = total / (sigma * math.sqrt(window))
    share = sum(np.sign(value) == np.sign(total) for value in residuals) / window
    if abs(score) >= rule["multi_z"] and share >= rule["multi_same_sign"]:
        return score
    return None


def detect_snapshot(snapshot):
    from inves_cog.perception.anomaly.assemble import detect_snapshot as run

    return run(snapshot)
