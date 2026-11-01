"""Current-price fundamentals and the four rule A books, without I/O."""

from inves_cog.trading.scoring.curves import CURVES, finite, interp, mean_available, weighted_book

# Muse aacea04 code/paper_trade_2026.py L127–144, L176–179: fixed three-book weights.
# code/screen_asof_2026_01_01.py L154–182 supplies EPS growth and FCF/NI via M2;
# negative NI does not invalidate conversion, and EPS growth requires two positive TTM EPS.
WEIGHTS = {
    "quality": {"gross_margin": 25, "roe": 25, "fcf_margin": 25, "fcf_conversion": 15, "net_debt_fcf": 10},
    "growth": {"rev_growth": 40, "rev_accel_pp": 25, "eps_growth": 25, "gross_margin_change_pp": 10},
    "valuation": {"pe": 35, "peg": 25, "ps": 20, "fcf_yield": 20},
}
# Muse aacea04 code/paper_trade_2026.py L149–173: equal-weight inner groups, then 35/20/15/20/10.
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
    # Muse aacea04 code/paper_trade_2026.py L79–80, L109–123: rebuild valuation from today's
    # price and PIT financial levels; never reuse the initial state's price-derived values.
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
    # Muse aacea04 code/paper_trade_2026.py L124–125: the two valuation plausibility predicates.
    pe, ps, gm = derived.get("pe"), derived.get("ps"), fields.get("gross_margin")
    return bool((pe and pe < 5 and ps and ps < 2) or (ps and ps < 3 and gm and gm > 60))


def build_books(fields, tech):
    derived = derivatives(fields, tech["raw_price"] if "raw_price" in tech else tech.get("price", fields.get("price")))
    # Muse aacea04 code/screen_asof_2026_01_01.py L154–182: consume M2's FCF/NI and EPS
    # growth unchanged; extraction belongs to M2, while current-price fields take precedence.
    raw = {**fields, **derived}
    missing = sorted(key for weights in WEIGHTS.values() for key in weights if not finite(raw.get(key)))
    # Muse aacea04 code/paper_trade_2026.py L127–144, L176–179: curve scores feed fixed weights.
    books = {
        name: weighted_book([(interp(raw.get(key), CURVES[key]), w) for key, w in weights.items()])
        for name, weights in WEIGHTS.items()
    }
    subitems, timing_missing = {}, {}
    # Muse aacea04 code/paper_trade_2026.py L149–173: average each inner group before the
    # five outer weights; do not give three-input trend more weight just for its input count.
    for name, (keys, _) in TIMING.items():
        subitems[name] = mean_available([interp(tech.get(key), CURVES[key]) for key in keys])
        timing_missing[name] = {key: "missing_technical_input" for key in keys if not finite(tech.get(key))}
    books["timing"] = weighted_book([(subitems[name], weight) for name, (_, weight) in TIMING.items()])
    return books, derived, subitems, sorted(set(missing)), timing_missing
