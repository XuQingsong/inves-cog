"""Execution-only streaks and PIT financial identity around accepted M3 scores."""


def enrich(scores, lookup, ticker, extractor):
    counts = {"consec_below200": 0, "consec_tim35": 0, "consec_tim30": 0}
    result = {}
    for row in scores:
        state = lookup(ticker, row["signal_date"], extractor)
        tech, timing = row["tech"], row["books"]["timing"]
        tests = {
            "consec_below200": tech.get("price_vs_ma200") is not None and tech["price_vs_ma200"] < 0,
            "consec_tim35": timing is not None and timing < 35,
            "consec_tim30": timing is not None and timing < 30,
        }
        counts = {key: counts[key] + 1 if test else 0 for key, test in tests.items()}
        fields = state.values if state else {}
        result[row["signal_date"]] = {
            **row,
            **counts,
            "state_version": str(state.filed) if state else "",
            "rev_growth": fields.get("rev_growth"),
            "rev_accel_pp": fields.get("rev_accel_pp"),
        }
    return result
