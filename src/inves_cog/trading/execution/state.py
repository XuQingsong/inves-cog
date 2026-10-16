"""Explicit persisted position state and frozen, versioned execution parameters."""

from pathlib import Path

from inves_cog.params import load_params
from inves_cog.trading.scoring.rules import load_rule_a

ROOT = Path(__file__).resolve().parents[4]
PARAMS = load_params(ROOT / "config/params/p-2026.10").values["m4"]
RULE_A = load_rule_a()
TIERS = {
    "defense": RULE_A["tiers"]["defensive"],
    "normal": RULE_A["tiers"]["normal"],
    "attack": RULE_A["tiers"]["aggressive"],
}


def new_position(*, shares, price, tier, index, state_version, **extras):
    return {
        "shares": shares,
        "avg_cost": price,
        "tier_now": tier,
        "tier_entry": tier,
        "entry_index": index,
        "entry_state": state_version,
        "stage": 0,
        "clear_streak": 0,
        "filled_fraction": 0.0,
        "first_fraction": 0.0,
        "certainty": "medium",
        "last_sell_index": -100,
        "last_swing_index": -100,
        "peak_price": price,
        "swing_shares": 0,
        "swing_count": 0,
        "swing_only": False,
        **extras,
    }


def clamp(value, limits):
    multiplier, lower, upper = limits
    return max(lower, min(upper, multiplier * value))


def below(value, bound):
    return value is not None and value < bound


def above(value, bound):
    return value is not None and value > bound
