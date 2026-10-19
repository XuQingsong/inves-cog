"""News records and price records for phase 1.

Close reading keeps at most three tracked companies whose names are written in
the text. It does not guess a company the text does not name, and it does not
change a valuation or place an order.
"""

import re
from pathlib import Path

import yaml

_LEVELS = {"只入库", "已经细读"}
_NAMED = "正文写了"
_UNNAMED = "已看到新闻，正文没有这家公司"
_NONE = "已入库新闻对不上"
_LIMIT = 3


def _aware(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("时间缺少时区")


def _root():
    return Path(__file__).resolve().parents[4]


def load_catalog(root=None):
    """Company names for the tracked stocks. Product aliases are not companies."""
    root = Path(root) if root is not None else _root()
    universe = yaml.safe_load((root / "config/universe.yaml").read_text())
    names = yaml.safe_load((root / "config/news_entities.yaml").read_text())["companies"]
    tickers = [row["ticker"] for row in universe["stocks"]]
    return [(ticker, names[ticker]["name"]) for ticker in tickers if ticker in names]


def _at(text, term, *, folded=False):
    haystack = text.casefold() if folded else text
    needle = term.casefold() if folded else term
    match = re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", haystack)
    return None if match is None else match.start()


def companies_in_text(text, catalog):
    found = []
    for ticker, name in catalog:
        token = "$" + ticker if len(ticker) < 3 else ticker
        spots = [spot for spot in (_at(text, name, folded=True), _at(text, token)) if spot is not None]
        if spots:
            found.append((min(spots), ticker))
    found.sort()
    chosen = []
    for _spot, ticker in found:
        if ticker in chosen:
            continue
        chosen.append(ticker)
        if len(chosen) == _LIMIT:
            break
    return [{"代码": ticker, "标明": _NAMED} for ticker in chosen]


class NewsRecords:
    def __init__(self, root=None):
        self.catalog = load_catalog(root)
        self._rows = {}

    def ingest(self, news_id, text, *, ingested_at, published_at, level):
        if news_id in self._rows:
            return self._rows[news_id]
        _aware(ingested_at)
        _aware(published_at)
        if level not in _LEVELS:
            raise ValueError("处理级别不合格")
        row = {
            "编号": news_id,
            "入库时间": ingested_at,
            "发布时间": published_at,
            "处理级别": level,
            "公司": companies_in_text(text, self.catalog) if level == "已经细读" else [],
            "判断": "",
        }
        self._rows[news_id] = row
        return row

    def price(self, ticker, moved_at):
        _aware(moved_at)
        known = [row for row in self._rows.values() if row["入库时间"] < moved_at and row["发布时间"] <= moved_at]
        known.sort(key=lambda row: (row["入库时间"], row["编号"]))
        named = any(item["代码"] == ticker for row in known for item in row["公司"])
        if not known:
            mark = _NONE
        elif named:
            mark = _NAMED
        else:
            mark = _UNNAMED
        return {"代码": ticker, "当时已经知道": [row["编号"] for row in known], "标记": mark}
