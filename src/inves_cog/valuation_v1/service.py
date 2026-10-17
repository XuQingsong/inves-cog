"""Daily standalone valuation; read M2 fixed, M1 prices, and M4 snapshots only."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from inves_cog.ingest.fundamentals.state import StateStore
from inves_cog.ingest.market import exchange
from inves_cog.valuation_v1.calculations import LABEL, calculate, pe_percentiles, settings
from inves_cog.valuation_v1.inputs import consensus_inputs, financial_inputs, selected_consensus
from inves_cog.valuation_v1.lifecycle import TypeHistory, classify
from inves_cog.valuation_v1.shadows import panel, shadow, summarize

NY = ZoneInfo("America/New_York")


def memberships(baskets, as_of):
    membership = {}
    peers = {}
    for basket in baskets:
        members = [
            m
            for m in basket["members"]
            if str(m.get("effective_from") or "0001-01-01") <= str(as_of)
            and (m.get("effective_to") is None or str(as_of) < str(m["effective_to"]))
        ]
        for member in members:
            ticker = member["ticker"]
            level = basket["level"].lower()
            if member.get("primary", True):
                membership.setdefault(ticker, {})[level] = basket["name"]
            if level == "l2":
                peers[ticker] = [m["ticker"] for m in members if m["ticker"] != ticker]
    return membership, peers


def first_session(day):
    cal = exchange(day.year)
    return cal.date_to_session(day.replace(day=1), direction="next").date() == day


def describe_actual(shadows, holdings):
    # A missing M4 feed is unknown, not an assertion that no actual buys exist.
    actual_buys = {}
    for order in holdings["candidates"]:
        if order.get("side") == "buy":
            actual_buys[order["ticker"]] = actual_buys.get(order["ticker"], 0) + 1
    for record in shadows:
        available = not holdings.get("reason")
        count = actual_buys.get(record["ticker"], 0) if available else None
        record.update(actual_comparison_available=available, actual_buy_count=count)
        if not available:
            record["difference"] = "无法比较规则A实际计划：" + holdings["reason"]
        elif count:
            effects = ["规则A当日" + str(count) + "笔买入"]
            if record["vt1"]:
                effects.append("若V-T1生效会禁止这些买入")
            if record["vt2"]:
                effects.append("若V-T2生效会将单票买入上限减半")
            if record["v2_coef"] is not None:
                effects.append("V2影子目标系数" + str(record["v2_coef"]))
            if record["v3_trim_flag"]:
                effects.append("V3达到单版本一次减持三分之一条件")
            effects.append("仅记录假设差异，实际订单不变")
            record["difference"] = "；".join(effects)
        else:
            record["difference"] = "规则A当日无买入计划；记录影子分与系数，实际订单不变"


def candidate_sources(state, rows, as_of, cutoff):
    selected = selected_consensus(rows, as_of, cutoff=cutoff)
    captured = selected.get("captured_at") if selected else None
    return {
        "decision_cutoff": str(cutoff),
        "financial": {
            "filed": str(state.filed) if state else None,
            "period_end": str(state.period_end) if state else None,
            "accession": state.accession if state else None,
            "form": state.form if state else None,
            "captured_at": None,
            "capture_status": "not_provided_by_M2_contract",
            "raw_values": deepcopy(state.values) if state else None,
            "field_sources_reference": {
                "table": "fundamentals.fin_state",
                "extractor": "fixed",
                "ticker": state.ticker if state else None,
                "filed": str(state.filed) if state else None,
            },
            "field_sources_sha256": hashlib.sha256(
                json.dumps(state.field_sources, default=str, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            if state
            else None,
        },
        "consensus": {
            "snapshot_as_of": str(selected["as_of"]) if selected else None,
            "captured_at": str(captured) if captured is not None else None,
            "capture_status": "no_snapshot"
            if selected is None
            else "recorded"
            if captured is not None
            else "unknown_import_time",
            "source": selected.get("source") if selected else None,
            "raw_candidate": {k: deepcopy(v) for k, v in selected.items() if k != "raw"} if selected else None,
        },
    }


def build(*, clock, repository, universe, as_of, persist=True, book=None, source=None):
    tickers = [e["ticker"] for e in universe]
    source = source or repository.inputs(as_of, tickers)
    book = book or repository.restore(as_of)
    seen, bear_past = repository.shadow_history(as_of)
    cutoff = min(clock.now_utc(), datetime.combine(as_of, time(22, 30), NY).astimezone(timezone.utc))
    membership, peers = memberships(source["baskets"], as_of)
    pe = {}
    for ticker in tickers:
        store = StateStore(source["states"].get(ticker, []))
        rows = []
        for bar in source["bars"].get(ticker, []):
            # Current price is not an input to a historical multiple. Each PE uses
            # the financial state that was visible on that historical trade date.
            if bar["trade_date"] >= as_of:
                continue
            state = store.state_asof(ticker, bar["trade_date"], "fixed")
            rows.append(
                {
                    "date": bar["trade_date"],
                    "close": bar["close"],
                    "eps_ttm": state.values.get("eps_ttm") if state else None,
                }
            )
        pe[ticker] = pe_percentiles(rows, as_of)
    ranges = []
    shadows = []
    for entity in universe:
        ticker = entity["ticker"]
        entity = {**entity, "sic": source.get("sic", {}).get(ticker, entity.get("sic"))}
        state = source["store"].state_asof(ticker, as_of, "fixed")
        bars = [r for r in source["bars"].get(ticker, []) if r["trade_date"] == as_of]
        price = bars[-1]["close"] if bars else None
        try:
            if ticker not in book.types:
                h = TypeHistory()
                for prior in source["states"].get(ticker, []):
                    if prior.period_end is None or (state is not None and prior.filed >= state.filed):
                        continue
                    prior_inputs = financial_inputs(prior, source["states"][ticker], entity)
                    prior_inputs.update(consensus_inputs(source["consensus"].get(ticker, []), prior.filed))
                    h.observe(prior.period_end, classify(prior_inputs))
                book.types[ticker] = h
            inputs = financial_inputs(state, source["states"].get(ticker, []), entity, as_of=cutoff)
            inputs.update(consensus_inputs(source["consensus"].get(ticker, []), as_of, cutoff=cutoff))
            p = dict(pe[ticker])
            if p["insufficient_pe_history"]:
                fallback = pe_percentiles(
                    [], as_of, peer_p50=[pe[t]["own_p50"] for t in peers.get(ticker, []) if t in pe]
                )
                p.pop("pe_reason", None)
                p.update(
                    {
                        key: value
                        for key, value in fallback.items()
                        if key.startswith("pe_p") or key in {"pe_basis", "pe_reason"}
                    }
                )
            inputs.update(p)
            evidence = candidate_sources(state, source["consensus"].get(ticker, []), as_of, cutoff)
            kind = classify(inputs)
            row = book.update(
                ticker,
                as_of,
                kind,
                inputs,
                period=state.period_end if state else "missing",
                financial_version=state.filed if state else "missing",
                price=price,
                month_refresh=first_session(as_of),
            )
            # Daily read candidates and provenance are audit payloads, not formula
            # inputs or a claim that an historical replay was captured at that time.
            row.update(candidate_inputs=deepcopy(inputs), source_evidence=evidence)
            if row["status"] != "ok":
                extra = [inputs.get("input_reason"), inputs.get("annual_eps_reason")]
                if row["type"] in {"稳定", "周期", "未盈利成长"} and inputs.get("diluted_shares") is None:
                    extra.append(inputs.get("diluted_shares_reason"))
                if row["type"] == "周期":
                    extra.append(inputs.get("normal_margin_reason"))
                if row["type"] in {"稳定", "成长", "未盈利成长"}:
                    extra.append(inputs.get("consensus_reason"))
                if row["type"] == "金融":
                    missing = [key for key in ("rote_5y_avg", "tbv_per_share") if inputs.get(key) is None]
                    extra.append("M2未提供金融估值字段：" + ", ".join(missing) if missing else None)
                row["reason"] = "; ".join(filter(None, [row["reason"], *extra]))
            row.update(membership.get(ticker, {}))
        except Exception as exc:
            row = calculate("未确定", {})
            row.update(
                ticker=ticker,
                date=as_of,
                price=price,
                status="failed",
                reason=type(exc).__name__ + ": " + str(exc),
                p=None,
                p_label=None,
                implied_growth=None,
                delta_g=None,
                financial_version="failed",
                period=None,
            )
        ranges.append(row)
        shadows.append(shadow(row, bear_30d=bear_past.get(ticker), seen_versions=seen.get(ticker, set())))
    holdings = repository.holdings(as_of, cutoff=cutoff)
    by_ticker = {r["ticker"]: r for r in ranges}
    describe_actual(shadows, holdings)
    panel_rows = {}
    if "cash" in holdings:
        # Ledger equity can be from an older mark. Use the same current closes
        # in both the numerator and cash-plus-position equity denominator.
        marks = [by_ticker.get(h["ticker"], {}).get("price") for h in holdings["holdings"]]
        complete = holdings["cash"] is not None and all(p is not None for p in marks)
        equity = (
            holdings["cash"] + sum(h["shares"] * p for h, p in zip(holdings["holdings"], marks, strict=True))
            if complete
            else None
        )
        holdings["equity"] = equity
        holdings["holdings"] = [{**h, "equity": equity} for h in holdings["holdings"]]
    for holding in holdings["holdings"]:
        ticker = holding["ticker"]
        valuation = by_ticker.get(ticker)
        if valuation is None:
            valuation = calculate("未确定", {})
            valuation.update(ticker=ticker, price=None, p=None, delta_g=None)
        equity = holding.get("equity")
        price = valuation.get("price")
        weight = (
            holding["shares"] * price / equity * 100
            if price is not None and equity is not None and equity > 0
            else None
        )
        panel_rows[ticker] = panel({**valuation, "weight_pct": weight}, bear_30d=bear_past.get(ticker))
    candidates = {}
    for candidate in holdings["candidates"]:
        if candidate.get("side") == "buy":
            candidates.setdefault(candidate["ticker"], []).append(candidate.get("notional_est"))
    for ticker, amounts in candidates.items():
        valuation = by_ticker.get(ticker)
        if valuation is None:
            continue
        equity = holdings.get("equity")
        amount = sum(amounts) if all(v is not None for v in amounts) else None
        increment = amount / equity * 100 if amount is not None and equity is not None and equity > 0 else None
        old = panel_rows.get(ticker)
        actual = old["weight_pct"] if old else increment
        target = (
            (old["weight_pct"] + increment)
            if old and old["weight_pct"] is not None and increment is not None
            else increment
            if not old
            else None
        )
        # M4 notional_est is an incremental buy. The comparison uses the total
        # target (existing exposure plus all planned buys), never a last-order overwrite.
        row = {**valuation, "weight_pct": actual, "target_weight_pct": target}
        panel_rows[ticker] = panel(row, bear_30d=bear_past.get(ticker))
    summary = summarize(list(panel_rows.values()))
    summary["date"] = as_of
    if holdings.get("reason"):
        summary.update(valuation_at_risk_pct=None, shadow_weight_pct=None, reason=holdings["reason"])
    result = {
        "label": LABEL,
        "params_version": settings()["params_version"],
        "trade_date": as_of,
        "ranges": ranges,
        "shadows": shadows,
        "panel": list(panel_rows.values()),
        "summary": summary,
        "holdings_reason": holdings.get("reason"),
        "processed_count": len(ranges),
        "status": "degraded" if any(r["status"] != "ok" for r in ranges) or holdings.get("reason") else "ok",
        "note": str(sum(r["status"] != "ok" for r in ranges)) + "只明确不估或失败；交易不受影响",
    }
    if persist:
        repository.save(as_of, result, clock.now_utc())
    return result
