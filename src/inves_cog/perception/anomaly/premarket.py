"""Premarket flags for holdings and linked names. Never creates a daily anomaly."""

from pathlib import Path

from inves_cog.params import load_params


def _limit():
    directory = Path(__file__).resolve().parents[4] / "config/params/p-2026.10"
    return load_params(directory).values["m7"]["premarket_z"]


def review_premarket(scope):
    limit = _limit()
    rows = []
    linked = set(scope.get("linked") or [])
    for ticker in list(scope.get("holdings") or []) + [
        name for name in linked if name not in set(scope.get("holdings") or [])
    ]:
        quote = (scope.get("quotes") or {}).get(ticker)
        if not quote or not quote.get("prev_close") or not quote.get("sigma"):
            continue
        ret = quote["premarket_last"] / quote["prev_close"] - 1
        score = ret / quote["sigma"]
        rows.append(
            {
                "ticker": ticker,
                "prev_close": quote["prev_close"],
                "premarket_last": quote["premarket_last"],
                "premarket_ret": ret,
                "premarket_z": score,
                "reason": "holding" if ticker in set(scope.get("holdings") or []) else "linked_event",
                "flag": abs(score) >= limit,
            }
        )
    return rows
