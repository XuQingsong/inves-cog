"""Merge path hits into one object per overlapping set of names."""

from inves_cog.perception.anomaly.amplify import candidates, features
from inves_cog.perception.anomaly.detect import (
    _basket_hits,
    _index_hits,
    _macro_hits,
    _multi_hits,
    _rotation_hits,
    _stock_hits,
    limits,
)
from inves_cog.perception.anomaly.quality import adjust_daily, same_sign_share, stale_tickers, thin_names


def detect_snapshot(snapshot):
    version, rule = limits()
    blocked = stale_tickers(snapshot.get("bars"))
    prepared = dict(snapshot)
    prepared["daily"] = adjust_daily(snapshot.get("daily") or [], snapshot.get("bars"), rule["split_abs"])
    hits = []
    hits.extend(_basket_hits(prepared, rule, blocked))
    hits.extend(_stock_hits(prepared, rule, blocked))
    hits.extend(_index_hits(prepared, rule))
    hits.extend(_macro_hits(prepared, rule))
    hits.extend(_rotation_hits(prepared, rule))
    hits.extend(_multi_hits(prepared, rule, blocked))
    merged = [_finish(group, prepared, rule, version) for group in _groups(hits)]
    return merged


def _groups(hits):
    parent = list(range(len(hits)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for left in range(len(hits)):
        for right in range(left + 1, len(hits)):
            if _overlap(hits[left], hits[right]):
                parent[find(left)] = find(right)
    groups = {}
    for index, hit in enumerate(hits):
        groups.setdefault(find(index), []).append(hit)
    return groups.values()


def _overlap(left, right):
    market = {"C", "C_abs"}
    if market & set(left["entry_paths"]) and market & set(right["entry_paths"]):
        return True
    if left["tickers"] & right["tickers"]:
        return True
    if set(left["basket_ids"]) & set(right["basket_ids"]):
        return True
    return _basket_contains(left, right) or _basket_contains(right, left)


def _basket_contains(basket_hit, stock_hit):
    if not basket_hit["basket_ids"] or not stock_hit["tickers"]:
        return False
    covered = set()
    for identifier in basket_hit["basket_ids"]:
        covered.update((basket_hit.get("member_returns") or {}).get(identifier, {}))
    return bool(stock_hit["tickers"] & covered)


def _finish(group, snapshot, rule, version):
    paths, baskets, basket_ids, tickers = [], [], [], set()
    score, severity = 0, "watch"
    for hit in group:
        for path in hit["entry_paths"]:
            if path not in paths:
                paths.append(path)
        baskets.extend(name for name in hit["baskets"] if name not in baskets)
        basket_ids.extend(name for name in hit["basket_ids"] if name not in basket_ids)
        tickers |= hit["tickers"]
        if hit["score"] is not None and abs(hit["score"]) >= abs(score):
            score = hit["score"]
        if hit["severity"] == "alert":
            severity = "alert"
    if all(hit["severity"] == "watch" for hit in group):
        severity = "watch"
    daily = {row["ticker"]: row for row in snapshot.get("daily") or []}
    members = []
    for ticker in sorted(tickers):
        row = daily.get(ticker)
        members.append(
            {
                "ticker": ticker,
                "ret": None if row is None else row.get("ret"),
                "resid": None if row is None else row.get("resid"),
                "resid_z": None if row is None else row.get("resid_z"),
                "vol_mult": None if row is None else row.get("volume_mult"),
            }
        )
    anomaly = {
        "trade_date": snapshot["trade_date"],
        "session": snapshot["session"],
        "entry_paths": paths,
        "severity": severity,
        "layer": _layer(paths, basket_ids, snapshot, rule),
        "baskets": baskets,
        "basket_ids": basket_ids,
        "tickers": tickers,
        "members": members,
        "direction": "down" if score < 0 else "up",
        "max_abs_z": abs(score),
        "data_quality": _quality(tickers, snapshot, rule),
        "universe": "pool",
        "status": "已发现·原因未明",
        "params_version": version,
    }
    anomaly["amplification"] = features(anomaly, snapshot, rule)
    anomaly["type_candidates_prelim"] = candidates(anomaly, snapshot, rule)
    anomaly["coverage"] = {"members": len(members)}
    return anomaly


def _layer(paths, basket_ids, snapshot, rule):
    if "C" in paths or "C_abs" in paths:
        return "L1"
    levels = snapshot.get("levels") or {}
    l2_hit = any(
        levels.get(identifier) == "L2" and _share(identifier, snapshot) >= rule["path_a_same_sign"]
        for identifier in basket_ids
    )
    if l2_hit:
        return "L2"
    if any(levels.get(identifier) == "L3" for identifier in basket_ids) or basket_ids:
        return "L3"
    return "L4"


def _share(identifier, snapshot):
    members = snapshot.get("member_returns", {}).get(identifier, {})
    ret = next((row.get("ret_ew") for row in snapshot.get("baskets") or [] if row["basket_id"] == identifier), None)
    return same_sign_share(members, ret) or 0


def _quality(tickers, snapshot, rule):
    thin = thin_names(snapshot["session"], snapshot.get("bars"), rule["thin_post_share"])
    codes = []
    if tickers & thin:
        codes.append("thin_post")
    bars = snapshot.get("bars") or {}
    if any(bars.get(ticker, {}).get("source_changed") for ticker in tickers):
        codes.append("待核验")
    return codes
