"""Fixed-only conservative plausibility checks; original financial values survive."""


def violations(values, series):
    result = []
    ni, rev, eps, shares = (values.get(k) for k in ("ni_ttm", "rev_ttm", "eps_ttm", "shares"))
    if ni is not None and rev and abs(ni / rev) > 1:
        result.append({"rule": 1, "field": "ni_ttm/rev_ttm", "ratio": ni / rev})
    if ni is not None and abs(ni) >= 10_000_000 and eps is not None and shares is not None:
        ratio = eps * shares / ni
        if not 0.5 <= ratio <= 2:
            result.append({"rule": 2, "field": "eps_ttm*shares/ni_ttm", "ratio": ratio})
    for field, rows in series.items():
        latest = [(end, rows[end]) for end in sorted(rows)[-4:]]
        if len(latest) != 4:
            continue
        for index, (end, row) in enumerate(latest):
            if row.get("derivation") not in {"q4_derived", "ytd_derived", "eps_q4_derived"}:
                continue
            others = [r["val"] for i, (_, r) in enumerate(latest) if i != index]
            if all(row["val"] * x < 0 for x in others) and abs(row["val"]) > sum(abs(x) for x in others):
                result.append(
                    {
                        "rule": 3,
                        "field": field,
                        "derived_end": str(end),
                        "quarters": [
                            {"end": str(d), "value": r["val"], "derivation": r.get("derivation")} for d, r in latest
                        ],
                    }
                )
    for error in result:
        if error["rule"] in {1, 2}:
            names = ("ni", "rev") if error["rule"] == 1 else ("ni", "eps")
            error["quarters"] = {
                name: [{"end": str(end), "value": series[name][end]["val"]} for end in sorted(series[name])[-4:]]
                for name in names
                if name in series
            }
            if error["rule"] == 2:
                error["shares_date"] = values.get("shares_date")
    return result


def split_events(data, as_of):
    selected = {}
    for nodes in data.values():
        for tag, node in nodes.items():
            if tag not in {"StockholdersEquityNoteStockSplitConversionRatio1", "StockSplitConversionRatio"}:
                continue
            for row in node.get("units", {}).get("pure", []):
                if row.get("filed", "9999") > str(as_of) or row.get("end", "9999") > str(as_of):
                    continue
                if type(row.get("val")) not in (int, float) or row["val"] <= 0 or row["val"] == 1:
                    continue
                key = row["end"], row["val"]
                if key not in selected or row["filed"] < selected[key]["filed"]:
                    selected[key] = row
    return list(selected.values())


def adjust_eps(row, events):
    adjustments = []
    for event in events:
        if str(row["end"]) <= event["end"] and str(row["filed"]) < event["filed"]:
            adjustments.append(
                {
                    "ratio": event["val"],
                    "event_date": event["end"],
                    "first_reported": event["filed"],
                    "accession": event.get("accn"),
                }
            )
            row["val"] /= event["val"]
    if adjustments:
        row["split_adjustment"] = adjustments
    return row
