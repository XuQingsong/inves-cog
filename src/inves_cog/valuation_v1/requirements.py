"""All currently blocking formula inputs, separate from intentional non-valuation."""

import math

from inves_cog.valuation_v1.calculations import settings


def missing_inputs(kind, data):
    required = []

    def need(key, positive=False):
        required.append((key, positive))

    if kind == "稳定":
        need("eps_ttm")
        if data.get("fcf_per_share") is None:
            need("valuation_fcf_ttm" if "valuation_fcf_ttm" in data else "fcf_ttm")
            need("diluted_shares", True)
        for k in ["pe_p25", "pe_p50", "pe_p75"]:
            need(k, True)
    elif kind == "成长":
        need("eps_ntm" if data.get("eps_ntm") is not None else "eps_ttm", True)
        need(
            "consensus_next_year_eps_growth" if data.get("consensus_next_year_eps_growth") is not None else "eps_growth"
        )
        need("rev_cagr_3y")
    elif kind == "周期":
        need("normal_net_margin")
        need("normal_revenue", True)
        need("diluted_shares", True)
    elif kind == "未盈利成长":
        need("rev_growth")
        need("rev_ntm_consensus" if data.get("rev_ntm_consensus") is not None else "rev_ttm", True)
        for k in ["gross_margin", "net_debt", "fcf_ttm", "cash"]:
            need(k)
        need("diluted_shares", True)
    elif kind == "金融":
        need("rote_5y_avg")
        need("tbv_per_share", True)
    elif kind != "困境":
        return [
            {"field": "classification_type", "reason": data.get("annual_eps_reason") or "valuation type not determined"}
        ]
    missing = list(data.get("listed_unit_blockers", []))
    for key, positive in required:
        value = data.get(key)
        try:
            valid = value is not None and math.isfinite(float(value)) and (not positive or float(value) > 0)
        except (TypeError, ValueError, OverflowError):
            valid = False
        if not valid:
            reason = (
                data.get("diluted_shares_reason")
                if key == "diluted_shares"
                else data.get("normal_margin_reason")
                if key == "normal_net_margin"
                else data.get("valuation_fcf_reason")
                if key == "valuation_fcf_ttm"
                else None
            )
            proof = data.get("input_sources", {}).get(key, {})
            missing.append(
                {
                    "field": key,
                    "reason": reason or proof.get("reason") or "required value missing or invalid",
                    "source": proof,
                }
            )
    if kind == "周期" and data.get("subindustry") not in settings()["cyclical"]["pe"]:
        missing.append(
            {
                "field": "cyclical_subindustry_PE_parameters",
                "reason": "no approved PE parameters for this cyclical subindustry; no substitution",
            }
        )
    return missing
