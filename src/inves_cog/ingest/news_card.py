"""Close-read news card. One call replaces the single-item entity tag."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
QUESTION = (
    "这条新闻说了什么？会影响美股哪些行业？名单里哪些公司受影响："
    "每家写利好、利空或不确定，一句理由，以及和新闻的关系"
    "（新闻点了名 / 是它的产品 / 它的供应商或客户 / 它的竞争对手 / 同行业）。"
    "对每家的重要程度是高、中还是低？名单外明显受影响的公司也写上，单独列出。"
    "没有受影响的公司就让两个名单都空着。"
)


def tracked_list():
    """59 pool names plus monitored entities. Meta AI keeps the Muse alias."""
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


def read_card(reply, catalog=None):
    """Keep every company the model named. Split only into on-list and off-list."""
    if not isinstance(reply, dict):
        raise ValueError("新闻卡回答不是对象")
    inside = reply.get("名单内", [])
    outside = reply.get("名单外", [])
    if not isinstance(inside, list) or not isinstance(outside, list):
        raise ValueError("新闻卡名单不是数组")
    index = _index(tracked_list() if catalog is None else catalog)
    kept_in, kept_out = [], []
    for raw in [*inside, *outside]:
        if not isinstance(raw, dict):
            raise ValueError("新闻卡公司不是对象")
        company = dict(raw)
        (kept_in if _on_list(company, index) else kept_out).append(company)
    return {
        "说了什么": reply.get("说了什么", ""),
        "行业": reply.get("行业", []),
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
