"""Describe actual M4 inputs without changing their decision semantics."""

from inves_cog.trading.execution.contracts import members_asof


def describe_inputs(plan, inputs, universe, *, signal_day, cutoff, insiders, ledger, ledger_checked, overlay=None):
    members = members_asof(
        [
            {**r, "first_trade_date": inputs.get("first_trade_dates", {}).get(r["ticker"])}
            for r in universe
            if not r.get("foreign", False)
        ],
        signal_day,
    )
    expected = len(members)

    def source(status, available, missing, fallback, impact, *, visible_at=None):
        return {
            "status": status,
            "visible_at": visible_at,
            "data_date": str(signal_day),
            "read_cutoff": cutoff,
            "visible_time_reason": None if visible_at is not None else "来源未提供可独立证明的入库时间",
            "coverage": {"expected": expected, "available": available},
            "missing": missing,
            "fallback": fallback,
            "impact": impact,
        }

    missing_scores = plan.get("missing_scores", [])
    missing_bars = plan.get("missing_tickers", [])
    listing_gaps = [r["ticker"] for r in universe if r["ticker"] in members and not r.get("listed_on")]
    layer = plan.get("overlay") or {"status": "missing", "version": None}
    overlay_status = layer.get("status", "unknown")
    sources = {
        # These tables have no capture timestamp: a signal date is not an observation timestamp.
        "scores": source(
            "degraded" if missing_scores else "unknown",
            expected - len(missing_scores),
            {"tickers": missing_scores, "fields": ["observation_time"]},
            "缺分数标的不买",
            "保留规则A评分门槛",
        ),
        "bars": source(
            "degraded" if missing_bars else "unknown",
            expected - len(missing_bars),
            {"tickers": missing_bars},
            "不填造缺失价格",
            "覆盖不足95%不发布",
        ),
        "vix": source(
            "ok" if inputs["vix"].get(signal_day) is not None else "missing",
            int(inputs["vix"].get(signal_day) is not None),
            {"fields": [] if inputs["vix"].get(signal_day) is not None else ["value"]},
            "按非恐慌",
            "缺失时不启用恐慌判断",
        ),
        "membership": source(
            "unknown" if listing_gaps else "ok",
            expected - len(listing_gaps),
            {"tickers": listing_gaps, "fields": ["listed_on"] if listing_gaps else []},
            "沿用现有首个行情日判定",
            "不凭推测调整成员",
        ),
        "insiders": source(
            "unknown",
            len(set(insiders) & set(members)),
            {"fields": ["collection_coverage", "absence_confirmation"]},
            "只消费实际已记录事件",
            "无行不能证明已检查无事件",
        ),
        "overlay": source(
            overlay_status,
            int(overlay_status == "ok"),
            {"fields": [] if overlay_status == "ok" else ["current_overlay"]},
            "照常按规则A出计划",
            "冷静期未生效" if overlay_status != "ok" else "仅按覆盖层收紧",
        ),
        "ledger": source(
            "ok" if ledger else "missing" if ledger_checked else "unknown",
            int(bool(ledger)),
            {"fields": [] if ledger else ["prior_ledger"]},
            "沿用现有初始账户逻辑",
            "按实际恢复状态生成计划",
            visible_at=ledger.get("observed_at") if ledger else None,
        ),
    }
    sources["vix"]["coverage"] = {"expected": 1, "available": int(inputs["vix"].get(signal_day) is not None)}
    sources["overlay"]["coverage"] = {"expected": 1, "available": int(overlay_status == "ok")}
    sources["overlay"]["version"] = layer.get("version")
    if overlay_status == "ok" and overlay:
        sources["overlay"]["visible_at"] = overlay.get("generated_at")
        sources["overlay"]["visible_time_reason"] = None
        sources["overlay"]["m8_completeness"] = overlay.get("m8_completeness")
    sources["ledger"]["coverage"] = {"expected": 1, "available": int(bool(ledger))}
    states = {s["status"] for s in sources.values()}
    summary = "unpublished" if not plan.get("published", True) else "complete" if states == {"ok"} else "degraded"
    rows = []
    for name, item in sources.items():
        gaps = [
            {"ticker": t, "field": name, "reason": "实际消费的输入缺失"} for t in item["missing"].get("tickers", [])
        ]
        gaps.extend(
            {"ticker": None, "field": f, "reason": "缺失或无法独立证明"} for f in item["missing"].get("fields", [])
        )
        if item["visible_at"] is None:
            gaps.append({"ticker": None, "field": "as_of", "reason": item["visible_time_reason"]})
        row = {
            "source": name,
            "status": item["status"],
            "required": name in {"scores", "bars"},
            "as_of": item["visible_at"],
            "expected_count": item["coverage"]["expected"],
            "available_count": item["coverage"]["available"],
            "missing": gaps,
            "fallback": item["fallback"],
            "decision_effect": item["impact"],
            "data_date": str(signal_day),
        }
        if name == "overlay":
            row["version"] = item.get("version")
            row["m8_completeness"] = item.get("m8_completeness")
        rows.append(row)
    return {"status": summary, "cutoff": cutoff, "sources": rows}
