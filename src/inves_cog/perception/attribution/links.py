"""Per-step links for an expected scope. Rules still own the other two layers."""

import re
from copy import deepcopy

from inves_cog.perception.attribution.grounding import _anchors

_KINDS = {"来源陈述", "已有关系", "声明的假设"}
_TYPES = {"产业结构", "需求弹性", "暴露关系", "其他"}
_OBSERVED = {"观察到", "有支持", "已确立"}
_RULE_LAYERS = ("已支持的市场关联", "已量化或验证的经营暴露")
_QUOTE = "引文匹配只证明出处，不证明支持推断"
_UNNAMED = "材料未点名"
_SHARED = "共用假设"
_ALIASES = {
    "CRWV": "CoreWeave",
    "DELL": "Dell",
    "NTAP": "NetApp",
    "STX": "Seagate",
    "WDC": "Western Digital",
    "META": "Meta",
    "NVDA": "Nvidia",
    "AMD": "AMD",
    "AVGO": "Broadcom",
    "MSFT": "Microsoft",
    "ORCL": "Oracle",
    "SMCI": "Super Micro",
    "MRVL": "Marvell",
    "VRT": "Vertiv",
    "ETN": "Eaton",
    "TSM": "TSMC",
    "ANET": "Arista",
    "GEV": "GE Vernova",
}


def inspect_links(candidate, items, neighbors):
    """Check a v3 link list. Missing links do not keep the affected tickers."""
    if not isinstance(candidate, dict) or candidate.get("link_checked"):
        return candidate
    if "links" not in candidate or not isinstance(candidate.get("links"), list):
        return _missing_links(candidate)
    row = dict(candidate)
    rejected = [key for key in _RULE_LAYERS if key in row]
    for key in rejected:
        row.pop(key, None)
    problems = []
    links = row.get("links")
    if not isinstance(links, list):
        problems.append("逐环不是数组")
        links = []
    rivals = row.get("竞争解释")
    if not isinstance(rivals, list):
        problems.append("竞争解释未显式给出")
        rivals = None
    if "反证条件" not in row:
        problems.append("反证条件未显式给出")
    valid = []
    for link in links:
        checked = _link(link, row, items, neighbors or [])
        if checked is None:
            problems.append("逐环不合格")
            continue
        valid.append(checked)
    quotes = _quotes(valid)
    groups, missing_prediction = _hypothesis_groups(row, valid)
    hypothesis_kept, shared = _hypothesis_kept(groups)
    gaps = []
    affected = []
    for item in list(row.get("affected") or []):
        if not isinstance(item, dict) or not item.get("ticker"):
            gaps.append({"ticker": None, "reason": "受影响标的缺少代码"})
            continue
        ticker = item["ticker"]
        if _named(ticker, quotes) or ticker in hypothesis_kept:
            affected.append(item)
            continue
        gaps.append({"ticker": ticker, "reason": _gap_reason(ticker, valid, missing_prediction, groups)})
    expected = [dict(item) for item in affected]
    row["affected"] = expected
    row["links"] = valid
    row["research_gaps"] = gaps
    row["link_problems"] = problems
    row["hypothesis_count"] = len(groups)
    row["hypothesis_width"] = len(groups)
    row["共用假设"] = shared
    row["model_scope_rejected"] = rejected
    row["scope_layers"] = {
        "预期影响范围": expected,
        "已支持的市场关联": [],
        "已量化或验证的经营暴露": [],
    }
    row["quote_note"] = _QUOTE
    row["link_checked"] = True
    if rivals is not None:
        row["竞争解释"] = list(rivals)
    return row


def _missing_links(candidate):
    """No array of links is not a path. Keep the candidate and clear its scope."""
    row = dict(candidate)
    rejected = [key for key in _RULE_LAYERS if key in row]
    for key in rejected:
        row.pop(key, None)
    gaps = []
    for item in list(row.get("affected") or []):
        ticker = item.get("ticker") if isinstance(item, dict) else None
        gaps.append({"ticker": ticker, "reason": "未给逐环依据"})
    row["affected"] = []
    row["research_gaps"] = gaps
    row["link_problems"] = ["未给逐环依据"]
    row["hypothesis_count"] = 0
    row["hypothesis_width"] = 0
    row["共用假设"] = False
    row["model_scope_rejected"] = rejected
    row["scope_layers"] = {
        "预期影响范围": [],
        "已支持的市场关联": [],
        "已量化或验证的经营暴露": [],
    }
    row["quote_note"] = _QUOTE
    row["link_checked"] = True
    row["links_missing"] = True
    return row


def link_view(candidates):
    """Split what the report may show. Quote match is provenance only."""
    statements, relations, hypotheses, gaps = [], [], [], []
    expected = []
    widths = []
    for index, row in enumerate(candidates or []):
        if not isinstance(row, dict):
            continue
        widths.append({"candidate_index": index, "hypothesis_width": row.get("hypothesis_width")})
        for link in row.get("links") or []:
            if link.get("kind") == "来源陈述":
                statements.append(link)
            elif link.get("kind") == "已有关系":
                relations.append(link)
            elif link.get("kind") == "声明的假设":
                hypotheses.append(link)
        gaps.extend(row.get("research_gaps") or [])
        expected.extend((row.get("scope_layers") or {}).get("预期影响范围") or row.get("affected") or [])
    return {
        "来源陈述": statements,
        "已有关系": relations,
        "声明的假设": hypotheses,
        "缺证项": gaps,
        "范围": {
            "预期影响范围": expected,
            "已支持的市场关联": [],
            "已量化或验证的经营暴露": [],
        },
        "引文说明": _QUOTE,
        "评分展示名": "时间与关联特征分",
        "分数不是可信度": True,
        "hypothesis_width": widths,
    }


def fill_rule_layers(view, *, market, operating):
    """The model does not write these two layers."""
    scoped = deepcopy(view)
    scoped["范围"]["已支持的市场关联"] = list(market or [])
    scoped["范围"]["已量化或验证的经营暴露"] = list(operating or [])
    return scoped


def _link(link, candidate, items, neighbors):
    if not isinstance(link, dict):
        return None
    kind = link.get("kind")
    origin = link.get("from")
    target = link.get("to")
    if kind not in _KINDS or not isinstance(origin, str) or not origin or not isinstance(target, str) or not target:
        return None
    if kind == "来源陈述":
        return _statement(link, candidate, items, origin, target)
    if kind == "已有关系":
        return _relation(link, neighbors, origin, target)
    return _hypothesis(link, origin, target)


def _statement(link, candidate, items, origin, target):
    anchors = link.get("anchors")
    if not isinstance(anchors, list) or not anchors:
        return None
    cited = set(candidate.get("info_ids") or [])
    audits = _anchors(anchors, items, cited=cited)
    valid = [row for row in audits if row.get("literal_anchor_valid")]
    if not valid:
        return None
    combined = len(valid) > 1
    if combined and link.get("组合") is not True:
        return None
    if combined and not all(_provides(anchors, row["index"]) for row in valid):
        return None
    kept = {
        "from": origin,
        "to": target,
        "kind": "来源陈述",
        "anchors": [anchors[row["index"]] for row in valid],
        "组合": combined,
    }
    return kept


def _provides(anchors, index):
    row = anchors[index] if 0 <= index < len(anchors) else None
    return isinstance(row, dict) and isinstance(row.get("provides"), str) and bool(row["provides"].strip())


def _relation(link, neighbors, origin, target):
    identifier = link.get("relation_id")
    if not isinstance(identifier, str) or not identifier:
        return None
    for row in neighbors:
        if not isinstance(row, dict) or row.get("relation_id") != identifier:
            continue
        if row.get("status") not in _OBSERVED:
            continue
        ends = {row.get("from_entity"), row.get("to_entity")}
        if origin in ends and target in ends:
            return {"from": origin, "to": target, "kind": "已有关系", "relation_id": identifier}
    return None


def _hypothesis(link, origin, target):
    text = link.get("hypothesis")
    kind = link.get("hypothesis_type")
    falsify = link.get("falsify")
    if not isinstance(text, str) or not text.strip() or kind not in _TYPES or not isinstance(falsify, dict):
        return None
    metric = falsify.get("metric")
    direction = falsify.get("direction")
    window = falsify.get("window")
    if not all(isinstance(value, str) and value.strip() for value in (metric, direction, window)):
        return None
    return {
        "from": origin,
        "to": target,
        "kind": "声明的假设",
        "hypothesis": text,
        "hypothesis_type": kind,
        "falsify": {"metric": metric, "direction": direction, "window": window},
    }


def _quotes(links):
    quotes = []
    for link in links:
        if link.get("kind") != "来源陈述":
            continue
        for anchor in link.get("anchors") or []:
            quote = anchor.get("quote") if isinstance(anchor, dict) else None
            if isinstance(quote, str):
                quotes.append(quote)
    return quotes


def _mentioned(quote, ticker):
    code = ticker.upper()
    names = [code]
    alias = _ALIASES.get(code)
    if alias and alias.upper() != code:
        names.append(alias)
    return any(re.search(rf"\b{re.escape(name)}\b", quote, flags=re.IGNORECASE) for name in names)


def _named(ticker, quotes):
    return any(_mentioned(quote, ticker) for quote in quotes)


def _hypothesis_groups(row, links):
    groups = {}
    missing = set()
    for link in links:
        if link.get("kind") != "声明的假设" or not isinstance(link.get("to"), str):
            continue
        ticker = link["to"]
        prediction = _prediction(row.get("证伪预测"), ticker)
        if prediction is None:
            missing.add(ticker)
            continue
        groups.setdefault((link["hypothesis"], prediction), []).append(ticker)
    return groups, missing


def _hypothesis_kept(groups):
    kept = set()
    shared = False
    for tickers in groups.values():
        unique = list(dict.fromkeys(tickers))
        if len(unique) > 1:
            shared = True
            continue
        kept.add(unique[0])
    return kept, shared


def _gap_reason(ticker, links, missing_prediction, groups):
    if not links:
        return "没有到达该标的的逐环路径"
    if ticker in missing_prediction:
        return "假设标的缺少证伪预测"
    for tickers in groups.values():
        unique = list(dict.fromkeys(tickers))
        if ticker in unique and len(unique) > 1:
            return _SHARED
    return _UNNAMED


def _prediction(rows, ticker):
    if not isinstance(rows, list):
        return None
    found = [row for row in rows if isinstance(row, dict) and row.get("ticker") == ticker]
    if len(found) != 1:
        return None
    row = found[0]
    basket = row.get("control_basket")
    direction = row.get("direction")
    window = row.get("window")
    if not isinstance(basket, str) or not basket or direction not in {"up", "down"}:
        return None
    if not isinstance(window, str) or not window.strip():
        return None
    return (basket, direction, window)
