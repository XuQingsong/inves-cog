"""Distinct-period type confirmation and event-driven, auditable range publication."""

from copy import deepcopy

from inves_cog.valuation_v1.calculations import calculate, mark_price, settings


class TypeHistory:
    def __init__(self):
        self.current = None
        self.observations = {}
        self.audit = []

    def observe(self, period, candidate):
        self.observations[str(period)] = candidate
        recent = [v for _, v in sorted(self.observations.items())][-settings()["lifecycle"]["confirmation_periods"] :]
        if self.current is None or (
            len(recent) == settings()["lifecycle"]["confirmation_periods"] and all(v == candidate for v in recent)
        ):
            self.current = candidate
        return self.current

    @property
    def disagreement(self):
        return len(set([v for _, v in sorted(self.observations.items())][-2:])) > 1

    def override(self, kind, *, who, reason, when=None):
        if not who or not reason:
            raise ValueError("人工指定必须记录操作者和理由")
        self.audit.append({"old": self.current, "new": kind, "who": who, "reason": reason, "when": when})
        self.current = kind
        return kind


def classify(data):
    c = settings()["classification"]
    ticker = data.get("ticker")
    sic = data.get("sic")
    if (
        ticker not in c["financial_exceptions"]
        and sic is not None
        and any(a <= int(sic) <= b for a, b in c["financial_sic_ranges"])
    ):
        return "金融"
    ni, fcf, op = [data.get(k) for k in ("ni_ttm", "fcf_ttm", "op_margin_ttm")]
    loss = (ni is not None and ni <= 0) or (
        fcf is not None and fcf <= 0 and op is not None and op < c["low_operating_margin_pct"]
    )
    growth = data.get("rev_growth")
    if loss:
        if growth is None:
            return "未确定"
        return "未盈利成长" if growth >= c["minimum_growth_pct"] else "困境"
    annual_eps = data.get("annual_eps", [])
    collapses = sum(
        previous > 0 and (current / previous - 1) * 100 < c["eps_collapse_pct"]
        for previous, current in zip(annual_eps, annual_eps[1:], strict=False)
        if previous is not None and current is not None
    )
    margins = [m for m in data.get("annual_gross_margins", []) if m is not None]
    cyclical = data.get("subindustry") in settings()["cyclical"]["pe"] or (
        collapses >= c["eps_collapse_count"] and margins and max(margins) - min(margins) >= c["gross_margin_range_pp"]
    )
    if cyclical:
        return "周期"
    cagr, next_growth = data.get("rev_cagr_3y"), data.get("consensus_next_year_eps_growth")
    if (
        cagr is not None
        and cagr >= c["minimum_growth_pct"]
        and any(v is not None and v >= c["minimum_growth_pct"] for v in (growth, next_growth))
    ):
        return "成长"
    return "稳定"


CONSENSUS = {"eps_ntm", "consensus_next_year_eps_growth", "rev_ntm_consensus"}
MULTIPLES = {
    "pe_p25",
    "pe_p50",
    "pe_p75",
    "pe_p90",
    "pe_basis",
    "eligible_count",
    "trim_each",
    "coverage_years",
    "own_p50",
    "pe_reason",
    "insufficient_pe_history",
}


def decompose(old_kind, old_inputs, new_kind, new_inputs):
    out = dict.fromkeys(("类型/方法", "一致预期", "财报", "倍数"), 0.0)
    old = calculate(old_kind, old_inputs)["neutral"]
    new = calculate(new_kind, new_inputs)["neutral"]
    if old is None or new is None:
        return None
    if old_kind != new_kind or old_inputs.get("method_version") != new_inputs.get("method_version"):
        out["类型/方法"] = new - old
        return out
    current = deepcopy(old_inputs)
    previous = old
    groups = [
        ("一致预期", CONSENSUS),
        ("财报", (set(old_inputs) | set(new_inputs)) - CONSENSUS - MULTIPLES - {"price"}),
        ("倍数", MULTIPLES),
    ]
    for label, keys in groups:
        for key in keys:
            current.pop(key, None)
            if key in new_inputs:
                current[key] = new_inputs[key]
        value = calculate(new_kind, current)["neutral"]
        if value is None:
            return None
        out[label] = value - previous
        previous = value
    out["倍数"] += (new - old) - sum(out.values())
    return out


class ValuationBook:
    def __init__(self):
        self.published = {}
        self.types = {}
        self.pending = {}
        self.audit = []

    def update(
        self, ticker, day, candidate, inputs, *, period, price, financial_version=None, month_refresh=False, manual=None
    ):
        c = settings()["lifecycle"]
        old = self.published.get(ticker)
        financial_version = str(financial_version or period)
        new_report = old is None or financial_version != old["financial_version"]
        h = self.types.setdefault(ticker, TypeHistory())
        kind = h.observe(period, candidate) if new_report else h.current
        if manual:
            kind = h.override(manual["type"], who=manual["who"], reason=manual["reason"], when=manual.get("when"))
        old_ntm = old["inputs"].get("eps_ntm") if old else None
        new_ntm = inputs.get("eps_ntm")
        bounds = (
            sorted([old_ntm * (1 - c["consensus_trigger_pct"] / 100), old_ntm * (1 + c["consensus_trigger_pct"] / 100)])
            if old_ntm is not None
            else None
        )
        consensus_event = (old_ntm is None) != (new_ntm is None) or (
            new_ntm is not None and bounds is not None and not bounds[0] <= new_ntm <= bounds[1]
        )
        trigger = new_report or consensus_event or month_refresh or manual is not None
        if trigger:
            if old and not new_report and not month_refresh and manual is None:
                # A consensus-only event updates E/g inputs, not daily PE history.
                inputs = {**old["inputs"], **{key: inputs.get(key) for key in CONSENSUS}}
            elif old and month_refresh and not new_report and not consensus_event and manual is None:
                inputs = {**old["inputs"], **{key: inputs.get(key) for key in MULTIPLES}}
            fresh = calculate(kind, {**inputs, "type_disagreement": h.disagreement})
            fresh.update(
                ticker=ticker,
                date=day,
                period=str(period),
                financial_version=financial_version,
                type_state={"current": h.current, "observations": dict(h.observations), "audit": deepcopy(h.audit)},
                change_decomposition=decompose(old["type"], old["inputs"], kind, fresh["inputs"]) if old else None,
            )
            before = old.get("neutral") if old else None
            after = fresh["neutral"]
            large = (
                before not in (None, 0)
                and after is not None
                and abs(after / before - 1) * 100 > c["review_trigger_pct"]
            )
            if old and not new_report and large:
                self.pending[ticker] = deepcopy(fresh)
                shown = mark_price(old, price)
                shown.update(
                    date=day,
                    pending_review=True,
                    proposed=mark_price(fresh, price),
                    review_reason="无新财报，中性值变化超过25%",
                )
                return shown
            self.published[ticker] = deepcopy(fresh)
            self.pending.pop(ticker, None)
        shown = mark_price(self.published[ticker], price)
        shown["date"] = day
        if ticker in self.pending:
            shown.update(
                pending_review=True,
                proposed=mark_price(self.pending[ticker], price),
                review_reason="待人工复核，沿用已发布值",
            )
        return shown

    def approve(self, ticker, *, who, reason, when):
        if not who or not reason:
            raise ValueError("复核必须记录操作者和理由")
        proposed = self.pending.pop(ticker)
        self.audit.append(
            {
                "ticker": ticker,
                "who": who,
                "reason": reason,
                "when": when,
                "old_version": self.published[ticker]["version"],
                "new_version": proposed["version"],
            }
        )
        proposed["review_audit"] = deepcopy(self.audit[-1])
        proposed["pending_review"] = False
        self.published[ticker] = proposed
        return deepcopy(proposed)
