"""M9 end-to-end operations over explicit snapshots and scoped output repositories."""

import json
from copy import deepcopy

from inves_cog.overlay.delivery import FileDelivery
from inves_cog.overlay.rules import generate_overlay
from inves_cog.shadow.factors import evaluate_factors
from inves_cog.shadow.hysteresis import step_hysteresis
from inves_cog.shadow.registry import Registry
from inves_cog.shadow.signals import generate_signals


class MemoryOutputs:
    """Offline implementation of the same output protocol as the database adapter."""

    def __init__(self, folder):
        self.delivery = FileDelivery(folder)
        self.overlays, self.signals, self.factors, self.states = [], {}, {}, {}
        self.overlay_dates = {}
        self.registry = Registry()

    def last_overlay(self, target):
        current = self.delivery.read(str(target))
        available = [(day, row) for day, row in self.overlay_dates.items() if day <= str(target)]
        return current if current is not None else deepcopy(max(available, default=("", None))[1])

    def next_version(self):
        return len(self.overlays) + 1

    def publish_overlay(self, target, payload):
        self.delivery.publish(str(target), payload)
        self.overlays.append(deepcopy(payload))
        self.overlay_dates[str(target)] = deepcopy(payload)

    def retain_overlay(self, target, payload):
        self.delivery.publish(str(target), payload)

    def register(self, definitions, at):
        return {
            row["factor_id"]: self.registry.register(row["factor_id"], row, at=at)["version"] for row in definitions
        }

    def seen_signals(self):
        return set(self.signals)

    def save_signals(self, rows):
        for row in rows:
            self.signals.setdefault(row["signal_key"], deepcopy(row))

    def save_factors(self, rows):
        for row in rows:
            key = tuple(row[name] for name in ("date", "ticker", "factor_id", "version"))
            self.factors.setdefault(key, deepcopy(row))

    def prior_state(self, ticker, holding_id, version, target):
        matching = [
            (key[0], row)
            for key, row in self.states.items()
            if key[1:] == (ticker, holding_id, version) and key[0] < str(target)
        ]
        return deepcopy(max(matching, default=("", {}))[1].get("state", {}))

    def save_state(self, row):
        key = tuple(row[name] for name in ("date", "ticker", "holding_id", "version"))
        self.states.setdefault(key, deepcopy(row))


def run_overlay(*, clock, target, source, outputs):
    previous = outputs.last_overlay(target)
    diagnostics = {
        "source_ids": deepcopy(source.get("source_ids") or {}),
        "missing": deepcopy(source.get("missing") or {}),
        "source_events_asof": source.get("source_events_asof"),
    }
    if source.get("complete") is not True:
        if previous is not None:
            outputs.retain_overlay(target, previous)
        note = source.get("null_reason") or "M8当日快照输入不完整，保留旧版本及生成时间"
        if diagnostics["missing"]:
            note += "；缺失=" + json.dumps(diagnostics["missing"], ensure_ascii=False, sort_keys=True)
        return {
            **diagnostics,
            "status": "degraded",
            "processed_count": 0,
            "overlay": previous,
            "note": note,
        }
    payload = generate_overlay(
        source.get("events") or [],
        clock=clock,
        version=outputs.next_version(),
        source_asof=source.get("source_events_asof"),
        market=source.get("market"),
    )
    outputs.publish_overlay(target, payload)
    return {
        **diagnostics,
        "status": "ok",
        "processed_count": len(payload["tickers"]),
        "overlay": payload,
        "note": "M8来源=" + json.dumps(diagnostics["source_ids"], ensure_ascii=False, sort_keys=True),
    }


def run_shadows(*, clock, target, bundle, tickers, outputs):
    if not bundle.get("plan"):
        return {
            "status": "degraded",
            "processed_count": 0,
            "factors": [],
            "signals": [],
            "note": "对应M4基础计划尚未生成，不提前计算计划影子",
            "business_orders_written": 0,
        }
    versions = outputs.register(Registry().initial_definitions(), clock.now_utc())
    factors, observations = [], deepcopy(bundle.get("observations") or {})
    source_ids = deepcopy(bundle.get("source_ids") or {})
    for ticker in tickers:
        snapshot = (bundle.get("scores") or {}).get(ticker)
        if snapshot is None:
            snapshot = {"ticker": ticker, "tier": None, "books": {}, "entry_pass": None}
        rows = evaluate_factors(snapshot, (bundle.get("factor_inputs") or {}).get(ticker, {}), day=target)
        for row in rows:
            row.update(
                version=versions[row["factor_id"]], params_version="p-2026.10", generated_at=clock.now_utc().isoformat()
            )
            row["gap_detail"].update(source_ids=source_ids, source_kind=bundle["kind"])
        factors.extend(rows)
        observations.setdefault(ticker, {})
        observation = observations[ticker]
        if observation.get("holding_id") and observation.get("holding") is True:
            version = versions["F-02"]
            prior = outputs.prior_state(ticker, observation["holding_id"], version, target)
            value = deepcopy(observation.get("hysteresis") or {})
            if not prior:
                value.update(event="entry", b2_active=observation.get("b2_at_entry") is True)
            state, result = step_hysteresis(prior, value)
            if not prior and type(observation.get("b2_at_entry")) is not bool:
                state["entry_null_reason"] = "规则A原持仓入场日B2适用快照缺失，未追认适用"
            outputs.save_state(
                {
                    "date": str(target),
                    "ticker": ticker,
                    "holding_id": observation["holding_id"],
                    "version": version,
                    "state": state,
                    "shadow_action": result["action"],
                    "params_version": "p-2026.10",
                }
            )
    seen = outputs.seen_signals()
    signals = generate_signals((bundle.get("m8") or {}).get("events") or [], observations, day=target, seen=seen)
    for row in signals:
        row["condition_detail"].update(
            source_ids=source_ids,
            source_kind=bundle["kind"],
            cutoff=bundle.get("decision_cutoff", clock.now_utc().isoformat()),
            actual_generated_at=clock.now_utc().isoformat(),
        )
    outputs.save_factors(factors)
    outputs.save_signals(signals)
    nulls = sum(row["value"] is None for row in factors)
    return {
        "status": "degraded" if nulls else "ok",
        "processed_count": len(factors),
        "factors": factors,
        "signals": signals,
        "n9": [row for row in factors if row["gap_detail"].get("n_code") == "N9"],
        "null_factors": nulls,
        "source_kind": bundle["kind"],
        "business_orders_written": 0,
    }
