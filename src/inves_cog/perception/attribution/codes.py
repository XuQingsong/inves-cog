"""Ticker codes. Only the three named cases write a code."""


def n_code(*, mechanism, narrative_shock, fundamental_unchanged, unexplained):
    if unexplained:
        return "N6"
    if mechanism == "估值倍数":
        return "N2"
    if narrative_shock and fundamental_unchanged:
        return "N1"
    return None


def ticker_codes(anomaly, candidates, *, narrative_shock=False, fundamental_unchanged=False):
    """Pool names only. A wide anomaly and a supply move without the narrative flags stay blank."""
    if anomaly.get("universe") == "wide":
        return []
    if _unexplained(candidates):
        return [_row(name, "N6", None) for name in _member_names(anomaly)]
    multiples = _affected(candidates, "估值倍数")
    others = [row for row in _scored(candidates) if row.get("mechanism") != "估值倍数"]
    rows = []
    seen = set()
    for ticker in multiples:
        rows.append(_row(ticker, "N2", "估值倍数"))
        seen.add(ticker)
    if not (narrative_shock and fundamental_unchanged):
        return rows
    for candidate in others:
        code = n_code(
            mechanism=candidate.get("mechanism"),
            narrative_shock=True,
            fundamental_unchanged=True,
            unexplained=False,
        )
        if code is None:
            continue
        for ticker in _names(candidate):
            if ticker in seen:
                continue
            seen.add(ticker)
            rows.append(_row(ticker, code, candidate.get("mechanism")))
    return rows


def _unexplained(candidates):
    scores = [row["score"] for row in candidates if row.get("scored") and row.get("score") is not None]
    return not scores or all(score < 0.5 for score in scores)


def _scored(candidates):
    return [row for row in candidates if row.get("scored") and row.get("score") is not None and row["score"] >= 0.5]


def _affected(candidates, mechanism):
    names = []
    for row in _scored(candidates):
        if row.get("mechanism") != mechanism:
            continue
        for name in _names(row):
            if name not in names:
                names.append(name)
    return names


def _names(candidate):
    found = []
    for affected in candidate.get("affected") or []:
        name = affected.get("ticker") if isinstance(affected, dict) else affected
        if name and name not in found:
            found.append(name)
    return found


def _member_names(anomaly):
    return _names({"affected": anomaly.get("members") or []})


def _row(ticker, code, mechanism):
    return {"ticker": ticker, "n_code": code, "mechanism": mechanism}
