"""Current-price fundamentals and the four rule A books, without I/O."""

from inves_cog.trading.scoring.curves import CURVES, finite, interp, mean_available, weighted_book

WEIGHTS = {
    "quality": {"gross_margin": 25, "roe": 25, "fcf_margin": 25, "fcf_conversion": 15, "net_debt_fcf": 10},
    "growth": {"rev_growth": 40, "rev_accel_pp": 25, "eps_growth": 25, "gross_margin_change_pp": 10},
    "valuation": {"pe": 35, "peg": 25, "ps": 20, "fcf_yield": 20},
}
TIMING = {
    "trend": (["price_vs_ma200", "ma50_vs_ma200", "ma200_slope20"], 35),
    "momentum": (["mom3", "mom6"], 20),
    "volume": (["vol_ratio", "up_share"], 15),
    "position": (["dev50", "rsi"], 20),
    "risk": (["vol20", "drawdown252"], 10),
}


def ratio(a, b, factor=1):
    return a / b * factor if finite(a) and finite(b) and b != 0 else None


def derivatives(fields, price):
    eps, shares = fields.get("eps_ttm"), fields.get("shares")
    cap = price * shares if finite(price) and finite(shares) else None
    pe = ratio(price, eps) if finite(eps) and eps > 0 else None
    growth = fields.get("rev_growth")
    return {
        "pe": pe,
        "peg": ratio(pe, growth) if finite(growth) and growth > 0 else None,
        "mktcap": cap,
        "ps": ratio(cap, fields.get("rev_ttm")),
        "fcf_yield": ratio(fields.get("fcf_ttm"), cap, 100),
    }


def split_suspect(derived, fields):
    pe, ps, gm = derived.get("pe"), derived.get("ps"), fields.get("gross_margin")
    return bool((pe and pe < 5 and ps and ps < 2) or (ps and ps < 3 and gm and gm > 60))


def build_books(fields, tech):
    derived = derivatives(fields, tech.get("price", fields.get("price")))
    raw = {**fields, **derived}
    missing = sorted(key for weights in WEIGHTS.values() for key in weights if not finite(raw.get(key)))
    books = {
        name: weighted_book([(interp(raw.get(key), CURVES[key]), w) for key, w in weights.items()])
        for name, weights in WEIGHTS.items()
    }
    subitems, timing_missing = {}, {}
    for name, (keys, _) in TIMING.items():
        subitems[name] = mean_available([interp(tech.get(key), CURVES[key]) for key in keys])
        timing_missing[name] = {key: "missing_technical_input" for key in keys if not finite(tech.get(key))}
    books["timing"] = weighted_book([(subitems[name], weight) for name, (_, weight) in TIMING.items()])
    return books, derived, subitems, sorted(set(missing)), timing_missing
