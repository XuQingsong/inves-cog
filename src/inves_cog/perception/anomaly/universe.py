"""Pool membership for anomaly universe labels. Marketstate coverage is not membership."""

from pathlib import Path

import yaml

from inves_cog.marketstate.rotation import SECTORS, STYLES


def rotation_names():
    names = set(SECTORS)
    names.update(ticker for pair in STYLES.values() for ticker in pair)
    names.update(("SPY", "QQQ", "IWM"))
    return names


def pool_names(baskets, root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[4]
    document = yaml.safe_load((root / "config/universe.yaml").read_text())
    names = {row["ticker"] for row in document["stocks"]}
    names.update(document["etfs"])
    for basket in baskets:
        for member in basket["members"]:
            names.add(member["ticker"] if isinstance(member, dict) else member)
    return names
