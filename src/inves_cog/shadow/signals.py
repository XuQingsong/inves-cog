"""Auditable X1–X4 observations with durable deduplication keys, never orders."""

from datetime import date
from hashlib import sha256

from inves_cog.shadow.settings import settings


def _row(signal, ticker, event, day, observation, conditions, action, *, holding=None):
    event_id = event.get("event_id")
    scope = holding if signal == "X1" else day
    key = sha256(f"{signal}:{ticker}:{event_id}:{scope}".encode()).hexdigest()
    return {
        "date": str(day),
        "signal": signal,
        "ticker": ticker,
        "event_id": event_id,
        "signal_key": key,
        "condition_detail": {
            "conditions": conditions,
            "inputs": observation,
            "evidence_ids": list(event.get("evidence_ids") or []),
            "source_order_ids": list(observation.get("source_order_ids") or []),
            "holding_id": holding,
        },
        "shadow_action": action,
        "rule_a_action": observation.get("rule_a_action"),
        "params_version": "p-2026.10",
    }


def generate_signals(events, observations, *, day, seen):
    result, emitted = [], set(seen)
    cfg = settings()
    for event in events:
        for member in event.get("affected") or []:
            ticker = member.get("ticker")
            obs = observations.get(ticker) or {}
            eps, price, ma50 = obs.get("eps_change_pct"), obs.get("close"), obs.get("ma50")
            conditions = {
                "holding": obs.get("holding") is True and bool(obs.get("holding_id")),
                "verified_adverse": event.get("lifecycle") == "已验证·有影响"
                and event.get("direction") in ("不利", "down"),
                "direct_exposure": member.get("exposure") == "直接",
                "eps_revision": eps is not None and eps <= cfg["x1"]["eps_revision_pct"],
                "below_ma50": price is not None and ma50 is not None and price < ma50,
            }
            if all(conditions.values()):
                row = _row("X1", ticker, event, day, obs, conditions, "减1/3", holding=obs["holding_id"])
                if row["signal_key"] not in emitted:
                    result.append(row)
                    emitted.add(row["signal_key"])
            x2 = {
                "fundamental_review": event.get("lifecycle") == "基本面核查中",
                "direct_exposure": member.get("exposure") == "直接",
                "base_opening_order": obs.get("base_opening_order") is True,
            }
            if all(x2.values()):
                row = _row("X2", ticker, event, day, obs, x2, "首笔×0.5")
                if row["signal_key"] not in emitted:
                    result.append(row)
                    emitted.add(row["signal_key"])
    for ticker, obs in observations.items():
        tag = obs.get("divergence_tag") == "情绪性折价"
        actual = obs.get("actual_watchlist_wave_buy") is True
        qualified = obs.get("watchlist_wave_eligible") is True
        if actual or (tag and qualified):
            result.append(
                _row(
                    "X3",
                    ticker,
                    {},
                    day,
                    obs,
                    {"actual_rule_a_wave_buy": actual, "emotional_discount": tag, "eligible": qualified},
                    "记录实际观察名单波段买入" if actual else "观察名单波段影子机会",
                )
            )
        mature = date.fromisoformat(str(day)) >= date.fromisoformat(cfg["f03"]["mature_on"])
        row = _row(
            "X4", ticker, {}, day, obs, {"snapshot_mature": mature}, "按F03记录单因子替换" if mature else "快照不足"
        )
        row["condition_detail"].update(
            raw_revision_pct=obs.get("eps_revision_30d_pct"), status="可计算" if mature else "快照不足"
        )
        result.append(row)
    return [row for row in result if row["signal_key"] not in seen]
