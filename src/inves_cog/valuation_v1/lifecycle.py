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
    if data.get("subindustry") in settings()["cyclical"]["pe"]:
        return "周期"
    if data.get("annual_eps_basis_unknown"):
        return "未确定"
    annual_eps = data.get("annual_eps", [])
    collapses = sum(
        previous > 0 and (current / previous - 1) * 100 < c["eps_collapse_pct"]
        for previous, current in zip(annual_eps, annual_eps[1:], strict=False)
        if previous is not None and current is not None
    )
    margins = [m for m in data.get("annual_gross_margins", []) if m is not None]
    cyclical = (
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


def unit_signature(inputs, *, actual_only=False):
    return {
        k: tuple(v.get(field) for field in ("status", "from_unit", "to_unit", "factor"))
        for k, v in inputs.get("listed_unit_audit", {}).items()
        if not actual_only or k != "eps_ntm"
    }


class ValuationBook:
    def __init__(self):
        self.published = {}
        self.types = {}
        self.pending = {}
        self.audit = []

    def update(self, ticker, day, candidate, inputs, *, period, price, financial_version=None, month_refresh=False):
        c = settings()["lifecycle"]
        old = self.published.get(ticker)
        financial_version = str(financial_version or period)
        new_report = old is None or financial_version != old["financial_version"]
        method_refresh = bool(old and old.get("method_version") != settings()["method_version"])
        unit_event = bool(old and unit_signature(old["inputs"]) != unit_signature(inputs))
        actual_unit_event = bool(
            old and unit_signature(old["inputs"], actual_only=True) != unit_signature(inputs, actual_only=True)
        )
        input_contract_event = bool(
            old
            and (
                old["inputs"].get("historical_pe_unit_audit", {}).get("contract")
                != inputs.get("historical_pe_unit_audit", {}).get("contract")
                or old["inputs"].get("valuation_input_errors", []) != inputs.get("valuation_input_errors", [])
            )
        )
        h = self.types.setdefault(ticker, TypeHistory())
        kind = h.observe(period, candidate) if new_report or method_refresh else h.current
        old_ntm = old["inputs"].get("eps_ntm") if old else None
        new_ntm = inputs.get("eps_ntm")
        withdrawn = bool(
            unit_event
            and old_ntm is not None
            and inputs.get("listed_unit_audit", {}).get("eps_ntm", {}).get("status") == "unknown"
        )
        bounds = (
            sorted([old_ntm * (1 - c["consensus_trigger_pct"] / 100), old_ntm * (1 + c["consensus_trigger_pct"] / 100)])
            if old_ntm is not None
            else None
        )
        consensus_event = (old_ntm is None) != (new_ntm is None) or (
            new_ntm is not None and bounds is not None and not bounds[0] <= new_ntm <= bounds[1]
        )
        trigger = new_report or method_refresh or consensus_event or unit_event or input_contract_event or month_refresh
        audit = {
            "new_report": new_report,
            "consensus_event": consensus_event,
            "month_refresh": month_refresh,
            "method_refresh": method_refresh,
            "unit_contract_event": unit_event,
            "actual_unit_contract_event": actual_unit_event,
            "input_contract_event": input_contract_event,
            "invalid_forecast_withdrawn": withdrawn,
            "previous_eps_ntm": old_ntm,
            "candidate_eps_ntm": new_ntm,
            "consensus_bounds": bounds,
            "recomputed": trigger,
            "publication": "updated" if trigger else "held",
        }
        if trigger:
            if (
                old
                and not new_report
                and not month_refresh
                and not method_refresh
                and not actual_unit_event
                and not input_contract_event
            ):
                # A consensus-only event updates E/g inputs, not daily PE history.
                unit_keys = {"listed_unit_audit", "listed_unit_blockers", "consensus_reason"} if unit_event else set()
                inputs = {**old["inputs"], **{key: inputs.get(key) for key in CONSENSUS | unit_keys}}
            elif (
                old
                and month_refresh
                and not new_report
                and not consensus_event
                and not method_refresh
                and not unit_event
                and not input_contract_event
            ):
                inputs = {**old["inputs"], **{key: inputs.get(key) for key in MULTIPLES}}
        # 用户 2026-11-11 决定：估值不接受人工批准，人只能通过带版本号的方法变更影响估值。
        # 待确认状态每天照常重算，让确认窗口吃到真实的每日序列。
        if trigger or ticker in self.pending:
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
            san = settings().get("sanity") or {}
            lo_r, hi_r = float(san.get("ratio_low", 0.2)), float(san.get("ratio_high", 5))
            # 合理性闸门优先：触发闸门的新值直接发布为“估值暂不可用”，不进确认期。
            flagged = after is not None and price not in (None, 0) and (after / price < lo_r or after / price > hi_r)
            if method_refresh:
                fresh["publish_basis"] = f"方法 {settings()['method_version']} 重算"
            elif new_report:
                fresh["publish_basis"] = "新财报触发"
            if old and not new_report and not method_refresh and large and not withdrawn and not flagged:
                confirm_days = int(c.get("pending_confirm_days", 3))
                confirm_band = float(c.get("pending_confirm_band_pct", 10)) / 100
                expire_days = int(c.get("pending_expire_days", 5))
                p = self.pending.setdefault(ticker, {"since": str(day), "values": []})
                p["row"] = deepcopy(fresh)
                vals = p["values"]
                vals[:] = [v for v in vals if v[0] != str(day)] + [[str(day), after]]
                vals.sort(key=lambda v: v[0])
                if len(vals) >= confirm_days:
                    recent = [v[1] for v in vals[-confirm_days:]]
                    lo_v = min(recent)
                    if lo_v > 0 and max(recent) / lo_v - 1 <= confirm_band:
                        pct = abs(after / before - 1) * 100
                        fresh["publish_basis"] = f"较前值变化 {pct:.1f}%，已连续 {confirm_days} 日确认"
                        self.published[ticker] = deepcopy(fresh)
                        self.pending.pop(ticker, None)
                        shown = mark_price(self.published[ticker], price)
                        shown.update(date=day, trigger_audit={**audit, "publication": "confirmed"})
                        return shown
                if len(vals) >= expire_days:
                    fresh["unstable"] = True
                    self.published[ticker] = deepcopy(fresh)
                    self.pending.pop(ticker, None)
                    shown = mark_price(self.published[ticker], price)
                    shown.update(date=day, unstable=True, trigger_audit={**audit, "publication": "unstable"})
                    return shown
                shown = mark_price(old, price)
                shown.update(
                    date=day,
                    pending_review=True,
                    confirm_day=len(vals),
                    confirm_total=confirm_days,
                    proposed={"row": mark_price(p["row"], price), "values": p["values"], "since": p["since"]},
                    review_reason=f"估值变化待确认（第 {len(vals)}/{confirm_days} 日）",
                    trigger_audit={**audit, "publication": "pending_review"},
                )
                return shown
            self.published[ticker] = deepcopy(fresh)
            self.pending.pop(ticker, None)
        shown = mark_price(self.published[ticker], price)
        shown["date"] = day
        shown["trigger_audit"] = audit
        if ticker in self.pending:
            entry = self.pending[ticker]
            row = entry["row"] if isinstance(entry, dict) and "row" in entry else entry
            shown.update(
                pending_review=True,
                proposed={"row": mark_price(row, price), "values": entry.get("values", []), "since": entry.get("since")}
                if isinstance(entry, dict)
                else {"row": mark_price(row, price)},
                review_reason=shown.get("review_reason") or "估值变化待确认",
            )
        return shown
