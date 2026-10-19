"""Close-read news card. One call replaces the single-item entity tag."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
_TRACKED = None
QUESTION = (
    "回答就用这些栏：说了什么、行业、名单内、名单外。"
    "说了什么写这条新闻说了什么。"
    "行业用文字；要写影响和理由时，写在行业名后面。"
    "名单内和名单外的公司用代码、名称、方向、理由、关系、重要程度。"
    "方向写利好、利空或不确定。"
    "关系写新闻点了名、是它的产品、它的供应商或客户、它的竞争对手或同行业。"
    "重要程度写高、中或低。"
    "没有受影响的公司就让名单内和名单外都空着。"
)


def _load_tracked():
    universe = yaml.safe_load((ROOT / "config/universe.yaml").read_text())
    companies = yaml.safe_load((ROOT / "config/news_entities.yaml").read_text())["companies"]
    monitored = yaml.safe_load((ROOT / "config/monitored_entities.yaml").read_text())["entities"]
    rows = []
    for stock in universe["stocks"]:
        ticker = stock["ticker"]
        company = companies[ticker]
        rows.append({"名称": company["name"], "别名": list(company.get("aliases") or []), "代码": ticker})
    for entity in monitored:
        tickers = [ticker for ticker in entity.get("tickers") or [] if ticker]
        code = tickers[0] if len(tickers) == 1 else tickers
        rows.append({"名称": entity["name"], "别名": list(entity.get("aliases") or []), "代码": code})
    return rows


def tracked_list():
    """59 pool names plus monitored entities. Meta AI keeps the Muse alias."""
    global _TRACKED
    if _TRACKED is None:
        _TRACKED = _load_tracked()
    return [dict(row, 别名=list(row["别名"])) for row in _TRACKED]


def news_card_payload(item):
    from inves_cog.ingest.info import extraction_body

    prose = extraction_body(item.get("body"))
    return {
        "标题": item.get("headline") or "",
        "正文": prose[:2000] if prose else "只有标题",
        "跟踪名单": tracked_list(),
        "问法": QUESTION,
    }


def _index(catalog):
    tickers, names = set(), set()
    for row in catalog:
        if not isinstance(row, dict):
            continue
        code = row.get("代码")
        if isinstance(code, str) and code:
            tickers.add(code)
        elif isinstance(code, list):
            tickers.update(item for item in code if isinstance(item, str) and item)
        for term in (row.get("名称"), row.get("name"), *(row.get("别名") or []), *(row.get("aliases") or [])):
            if isinstance(term, str) and term:
                names.add(term.casefold())
    return {"tickers": tickers, "names": names}


def _on_list(company, index):
    code = company.get("代码")
    if isinstance(code, str) and code in index["tickers"]:
        return True
    aliases = company.get("别名") or []
    if isinstance(aliases, str):
        aliases = [aliases]
    for term in (company.get("名称"), company.get("name"), *aliases):
        if isinstance(term, str) and term.casefold() in index["names"]:
            return True
    return False


_TEXT = (
    ("说了什么", ("summary", "新闻摘要"), ""),
    ("行业", ("industries", "受影响美股行业", "affected_industries"), []),
)
_LISTS = (
    ("名单内", ("companies_affected", "跟踪名单内受影响公司", "tracked_companies")),
    ("名单外", ("companies_outside_list", "名单外明显受影响公司", "outside_companies")),
)
_COMPANY = (
    ("代码", ("code",)),
    ("名称", ("name",)),
    ("方向", ("direction", "影响", "impact")),
    ("理由", ("reason",)),
    ("关系", ("relation", "与新闻关系")),
    ("重要程度", ("importance",)),
)


def _blank(value):
    return value is None or value == "" or value == []


def _prefer(source, chinese, fallbacks, default):
    """A filled Chinese field wins, then the English field, then the other name."""
    if chinese in source and not _blank(source.get(chinese)):
        return source.get(chinese)
    for key in fallbacks:
        if key in source and not _blank(source.get(key)):
            return source.get(key)
    if chinese in source:
        return source.get(chinese)
    for key in fallbacks:
        if key in source:
            return source.get(key)
    return default


def _company(raw):
    company = dict(raw)
    for chinese, fallbacks in _COMPANY:
        if not _blank(company.get(chinese)):
            continue
        for key in fallbacks:
            if not _blank(raw.get(key)):
                company[chinese] = raw.get(key)
                break
    return company


def _industry_name(item):
    for key in ("行业名", "行业"):
        name = item.get(key)
        if isinstance(name, str) and name:
            return name
    return ""


def _industry_line(item):
    """A text industry stays. An object keeps its name, then the effect and reason."""
    if not isinstance(item, dict):
        return None
    parts = [_industry_name(item), item.get("影响"), item.get("理由")]
    words = [part for part in parts if isinstance(part, str) and part]
    return " ".join(words) or None


def _industries(value):
    """One sentence is one industry line. A list keeps its items."""
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list):
        return value
    lines = []
    for item in value:
        if isinstance(item, str):
            lines.append(item)
            continue
        line = _industry_line(item)
        if line:
            lines.append(line)
    return lines


def read_card(reply, catalog=None):
    """Keep every company the model named. Split only into on-list and off-list."""
    if not isinstance(reply, dict):
        raise ValueError("新闻卡回答不是对象")
    chosen = {chinese: _prefer(reply, chinese, fallbacks, default) for chinese, fallbacks, default in _TEXT}
    for chinese, fallbacks in _LISTS:
        chosen[chinese] = _prefer(reply, chinese, fallbacks, [])
    if not isinstance(chosen["名单内"], list) or not isinstance(chosen["名单外"], list):
        raise ValueError("新闻卡名单不是数组")
    chosen["行业"] = _industries(chosen["行业"])
    if not isinstance(chosen["行业"], list):
        raise ValueError("新闻卡行业不是数组")
    index = _index(tracked_list() if catalog is None else catalog)
    kept_in, kept_out = [], []
    for raw in [*chosen["名单内"], *chosen["名单外"]]:
        if not isinstance(raw, dict):
            raise ValueError("新闻卡公司不是对象")
        company = _company(raw)
        (kept_in if _on_list(company, index) else kept_out).append(company)
    return {
        "说了什么": chosen["说了什么"] if isinstance(chosen["说了什么"], str) else "",
        "行业": chosen["行业"],
        "名单内": kept_in,
        "名单外": kept_out,
    }


def _name_matches(result, entities):
    by_id = {entity["entity_id"]: entity for entity in entities}
    rows = []
    for identifier in result.get("entities") or []:
        entity = by_id.get(identifier)
        if entity is None:
            continue
        tickers = [ticker for ticker in entity.get("tickers") or [] if ticker]
        rows.append(
            {
                "代码": tickers[0] if len(tickers) == 1 else tickers,
                "名称": entity.get("name", ""),
                "标明": "名字匹配",
            }
        )
    return rows


def attach_news_card(result, llm, entities):
    """Store the card on the item. A bad reply records the reason and keeps name matches."""
    try:
        card = read_card(llm.call("news_card", news_card_payload(result)))
    except Exception as exc:
        from inves_cog.ingest.info import record_extraction_error

        record_extraction_error(result, "news_card", exc)
        card = {"说了什么": "", "行业": [], "名单内": [], "名单外": [], "原因": str(exc)}
    else:
        for company in [*card["名单内"], *card["名单外"]]:
            company.setdefault("标明", "模型判断")
    card["名字匹配"] = _name_matches(result, entities)
    result.setdefault("extraction_source", {})["news_card"] = card
    return card
