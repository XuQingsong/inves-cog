"""B-069 spec section 2: rule-based news events. No model calls."""

import re
from datetime import timedelta
from pathlib import Path

import yaml

from inves_cog.perception.core_companies import core_companies

ROOT = Path(__file__).resolve().parents[4]
NY_TZ = timedelta(hours=-4)  # EDT approx; et_date only
KINDS = [
    ("preview", r"Preview|What to Expect|Ahead of Earnings|Earnings Prediction|Expectations"),
    (
        "earnings_result",
        r"Q[1-4].*(EPS|Sales|Revenue).*(Beat|Miss|Inline|Estimate)|Reports .*(Quarter|Q[1-4]).*Results",
    ),
    ("guidance", r"\bSees\b|Guidance|Outlook|Raises |Lowers |Cuts .*(Forecast|Guidance|Outlook)"),
    ("capex", r"capex|capital expenditure"),
    ("supply_shock", r"explosion|fire|shortage|outage|halt|recall|disruption"),
    ("mna", r"acqui|merger|takeover|buyout|deal to buy"),
    ("regulatory", r"SEC|DOJ|FTC|antitrust|export control|ban|tariff|probe|investigation"),
    ("rating", r"Upgrade|Downgrade|Maintains|Reiterates|Price Target"),
]
KIND_RE = [(name, re.compile(pat, re.I if name != "preview" else 0)) for name, pat in KINDS]
TYPE_W = {
    "earnings_result": 30,
    "guidance": 30,
    "capex": 25,
    "supply_shock": 20,
    "mna": 20,
    "regulatory": 15,
    "rating": 5,
    "other": 5,
    "preview": 0,
}

_EPS = re.compile(r"EPS \$([\d.]+) (Beats|Misses|Miss|Beat|Inline) \$([\d.]+) Estimate", re.I)
_SALES = re.compile(r"Sales \$([\d.]+)B? (Beat|Miss|Misses|Beats|Inline) \$([\d.]+)B? Estimate", re.I)
_G_EPS = re.compile(r"Sees Q[1-4][^.]*EPS \$([\d.]+)[^.]*vs \$([\d.]+)B? Est", re.I)
_G_REV = re.compile(r"Sees (?:Q[1-4] )?(?:Adj )?Sales \$([\d.]+)B?-\$([\d.]+)B? vs \$([\d.]+)B? Est", re.I)


from functools import lru_cache


@lru_cache(maxsize=1)
def _names_map():
    """ticker -> set of headline terms (names + aliases), incl. monitored entities."""
    out = {}
    for fname, key in (("news_entities.yaml", "companies"), ("monitored_entities.yaml", "entities")):
        path = ROOT / "config" / fname
        if not path.exists():
            continue
        doc = yaml.safe_load(path.read_text())
        companies = doc.get(key) or {}
        if isinstance(companies, dict):
            for ticker, company in companies.items():
                terms = {company.get("name"), company.get("名称")}
                terms.update(company.get("aliases") or [])
                terms.update(company.get("别名") or [])
                out[ticker] = {t.casefold() for t in terms if isinstance(t, str) and t}
        else:
            for entity in companies:
                codes = entity.get("tickers") or entity.get("代码") or []
                if isinstance(codes, str):
                    codes = [codes]
                terms = {entity.get("name"), entity.get("名称")}
                terms.update(entity.get("aliases") or [])
                terms.update(entity.get("别名") or [])
                for code in codes:
                    if code:
                        out.setdefault(code, set()).update(t.casefold() for t in terms if isinstance(t, str) and t)
    return out


def classify(headline):
    for name, pattern in KIND_RE:
        if pattern.search(headline):
            return name
    return "other"


def subjects(item, scope, names):
    """1-2 tickers: those in scope. >=3 tickers: only when the company's name
    or alias appears in the headline."""
    tickers = [t for t in (item.get("tickers") or []) if isinstance(t, str)]
    if len(tickers) <= 2:
        return [t for t in tickers if t in scope]
    headline = (item.get("headline") or "").casefold()
    return [t for t in tickers if t in scope and any(term in headline for term in names.get(t, set()))]


def parse_facts(headline):
    """Benzinga fixed formats; unparseable fields are simply absent."""
    facts = {}
    found = set()
    m = _EPS.search(headline)
    if m:
        facts["eps_actual"], facts["eps_est"] = float(m.group(1)), float(m.group(3))
        found.add(
            "beat"
            if m.group(2).lower() in ("beats", "beat")
            else "inline"
            if m.group(2).lower() == "inline"
            else "miss"
        )
        if facts["eps_est"]:
            facts["surprise_pct"] = round(100 * (facts["eps_actual"] - facts["eps_est"]) / abs(facts["eps_est"]), 1)
    m = _SALES.search(headline)
    if m:
        facts["rev_actual"], facts["rev_est"] = float(m.group(1)), float(m.group(3))
        found.add(
            "beat"
            if m.group(2).lower() in ("beats", "beat")
            else "inline"
            if m.group(2).lower() == "inline"
            else "miss"
        )
        if facts["rev_est"] and "surprise_pct" not in facts:
            facts["surprise_pct"] = round(100 * (facts["rev_actual"] - facts["rev_est"]) / abs(facts["rev_est"]), 1)
    m = _G_EPS.search(headline)
    if m:
        facts["guide_eps"], facts["guide_eps_est"] = float(m.group(1)), float(m.group(2))
        if facts["guide_eps_est"]:
            facts["guide_gap_pct"] = round(
                100 * (facts["guide_eps"] - facts["guide_eps_est"]) / abs(facts["guide_eps_est"]), 1
            )
    m = _G_REV.search(headline)
    if m:
        lo, hi, est = float(m.group(1)), float(m.group(2)), float(m.group(3))
        facts["guide_rev"], facts["guide_rev_est"] = round((lo + hi) / 2, 3), est
        if est:
            gap = round(100 * (facts["guide_rev"] - est) / est, 1)
            if "guide_gap_pct" not in facts or abs(gap) > abs(facts["guide_gap_pct"]):
                facts["guide_gap_pct"] = gap
    if found:
        facts["direction"] = "mixed" if len(found) > 1 else next(iter(found))
    elif facts:
        facts["direction"] = "inline"
    return facts


def importance(subject, kind, facts, scope_core):
    parts = {
        "position": 40 if subject in scope_core else 20,
        "type": TYPE_W[kind],
    }
    dev = 0
    if kind in ("earnings_result", "guidance"):
        gap = max(abs(facts.get("surprise_pct") or 0), abs(facts.get("guide_gap_pct") or 0))
        dev = min(30, int(1.5 * gap))
    parts["deviation"] = dev
    return min(100, sum(parts.values())), parts


def build_events(items, scope, et_now):
    """items: dicts with info_id/headline/tickers/first_seen_at. Returns events dict."""
    names = _names_map()
    core = core_companies()
    events = {}
    for item in sorted(items, key=lambda i: i.get("first_seen_at") or ""):
        if item.get("kind") not in (None, "news"):
            continue
        headline = item.get("headline") or ""
        kind = classify(headline)
        facts = parse_facts(headline)
        for subject in subjects(item, scope, names):
            seen = item["first_seen_at"]
            day = (seen + NY_TZ).date()
            hour = (seen + NY_TZ).hour
            session = (
                "post" if hour >= 16 else "pre" if hour < 9 or (hour == 9 and (seen + NY_TZ).minute < 30) else "regular"
            )
            eid = f"{subject}:{kind}:{day}"
            if eid in events:
                ev = events[eid]
                ev["info_ids"].append(item["info_id"])
                ev["last_seen_at"] = seen
            else:
                score, parts = importance(subject, kind, facts, set(core))
                events[eid] = {
                    "event_id": eid,
                    "subject": subject,
                    "kind": kind,
                    "et_date": str(day),
                    "session": session,
                    "first_seen_at": seen,
                    "last_seen_at": seen,
                    "info_ids": [item["info_id"]],
                    "headline": headline,
                    "facts": facts,
                    "segment": core.get(subject),
                    "importance": score,
                    "importance_parts": parts,
                }
    return sorted(events.values(), key=lambda e: (-e["importance"], str(e["first_seen_at"])))
