"""Explicit PIT snapshot validation and read-only adapters to accepted upstream tables."""

from copy import deepcopy
from datetime import date

from inves_cog.ingest.market import exchange
from inves_cog.overlay.rules import timestamp
from inves_cog.shadow.normalization import consensus_revision, contract_observations, segment_inputs
from inves_cog.shadow.risk_inputs import attach_risk_inputs
from inves_cog.trading.scoring.rules import EXCLUDED, load_rule_a

KINDS = {"synthetic", "recorded_fixture", "historical_snapshot", "live_readonly"}


def _visible_timestamps(value, cutoff):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"observed_at", "captured_at", "created_at", "generated_at", "at"} and item is not None:
                instant = timestamp(item)
                if instant > cutoff:
                    raise ValueError("snapshot contains an input observation after cutoff")
            else:
                _visible_timestamps(item, cutoff)
    elif isinstance(value, list):
        for item in value:
            _visible_timestamps(item, cutoff)


def validate_snapshot(bundle, *, cutoff, target):
    if bundle.get("kind") not in KINDS or date.fromisoformat(str(bundle["target"])) != target:
        raise ValueError("M9 snapshot needs an explicit kind and matching target")
    source = timestamp(bundle.get("source_events_asof"))
    if source is None or source > cutoff:
        raise ValueError("snapshot source time missing or after cutoff")
    _visible_timestamps(bundle, cutoff)
    m8 = bundle.get("m8") or {}
    if m8.get("complete") is True:
        stamp = timestamp(m8.get("source_events_asof"))
        if stamp is None or stamp > cutoff:
            raise ValueError("M8 snapshot is not visible at cutoff")
    return deepcopy(bundle)


class ReadInputs:
    """Use only a supplied role_shadow connection; no URL, writes or model clients."""

    def __init__(self, connection, m8_provider=None):
        self.connection, self.m8_provider = connection, m8_provider

    def load(self, *, clock, target, tickers, cutoff=None):
        target = date.fromisoformat(str(target))
        if target != clock.today_trade_date():
            raise ValueError("Historical days require an original PIT snapshot, not mutable latest DB rows")
        signal_day = exchange(target.year).previous_session(str(target)).date()
        cutoff = cutoff or clock.now_utc()
        if cutoff > clock.now_utc():
            raise ValueError("M9 input cutoff cannot be in the future")
        db = self.connection
        scores = db.execute(
            "SELECT * FROM trading.daily_scores WHERE signal_date=%s AND ticker=ANY(%s) "
            "AND extractor='fixed' AND rule_set='A' AND params_version='p-2026.10'",
            (signal_day, tickers),
        ).fetchall()
        states = db.execute(
            "SELECT * FROM fundamentals.fin_state WHERE filed<=%s AND ticker=ANY(%s) AND extractor='fixed' "
            "ORDER BY ticker,filed DESC",
            (signal_day, tickers),
        ).fetchall()
        valuations = db.execute(
            "SELECT DISTINCT ON(ticker) * FROM valuation_v1.shadow_rules WHERE trade_date<=%s "
            "AND observed_at<=%s AND ticker=ANY(%s) ORDER BY ticker,trade_date DESC,observed_at DESC",
            (signal_day, cutoff, tickers),
        ).fetchall()
        segments = db.execute(
            "SELECT * FROM fundamentals.segments WHERE ticker=ANY(%s) AND filed<=%s ORDER BY ticker,filed",
            (tickers, signal_day),
        ).fetchall()
        consensus = db.execute(
            "SELECT * FROM fundamentals.consensus_snapshot WHERE ticker=ANY(%s) AND as_of<=%s "
            "AND captured_at IS NOT NULL AND captured_at<=%s ORDER BY ticker,as_of,captured_at",
            (tickers, signal_day, cutoff),
        ).fetchall()
        ledger = db.execute(
            "SELECT state,equity,observed_at FROM trading.ledger WHERE portfolio_id='paper-fixed' "
            "AND extractor='fixed' AND rule_set='A' AND trade_date<=%s AND observed_at<=%s "
            "ORDER BY trade_date DESC,observed_at DESC LIMIT 1",
            (target, cutoff),
        ).fetchone()
        plan = db.execute(
            "SELECT payload,generated_at FROM trading.plan WHERE trade_date=%s AND portfolio_id='paper-fixed' "
            "AND extractor='fixed' AND rule_set='A' AND params_version='p-2026.10' AND generated_at<=%s "
            "ORDER BY generated_at DESC LIMIT 1",
            (target, cutoff),
        ).fetchone()
        m8 = (
            self.m8_provider(signal_day, cutoff)
            if self.m8_provider
            else {"complete": False, "null_reason": "K01：M8当日完成标记/快照接口未接通", "events": []}
        )
        grouped = {}
        for row in states:
            grouped.setdefault(row["ticker"], []).append(row)
        valuation_map = {row["ticker"]: row for row in valuations}
        normalized, factor_inputs = {}, {}
        segment_map, consensus_map = {}, {}
        for item in segments:
            segment_map.setdefault(item["ticker"], []).append(item)
        for item in consensus:
            consensus_map.setdefault(item["ticker"], []).append(item)
        tier_names = {"defense": "defensive", "normal": "normal", "attack": "aggressive"}
        rule = load_rule_a()
        for row in scores:
            ticker = row["ticker"]
            snapshot = {
                **row,
                "books": {key: row.get(key) for key in ("quality", "growth", "valuation", "timing")},
                "excluded_red_line": bool(EXCLUDED.intersection(row.get("red_lines") or [])),
            }
            normalized[ticker] = snapshot
            history = grouped.get(ticker) or []
            financial = history[0] if history else {}
            previous = next((item for item in history if item.get("period_end") != financial.get("period_end")), {})
            raw = {**(financial.get("values_extra") or {}), **financial, **(row.get("derived") or {})}
            previous_rev = previous.get("rev_ttm")
            previous_profit = previous.get("ni_ttm")
            raw.update(
                gm_change_pp=financial.get("gross_margin_change_pp"),
                prev_eps_ttm=previous.get("eps_ttm"),
                prev_net_margin_pct=(
                    previous_profit / previous_rev * 100 if previous_rev and previous_profit is not None else None
                ),
                ni_ttm_positive=(financial["ni_ttm"] > 0 if financial.get("ni_ttm") is not None else None),
                valuation_shadow=valuation_map.get(ticker),
                segments=segment_inputs(segment_map.get(ticker) or [], asof=signal_day),
                eps_revision_30d_pct=consensus_revision(
                    consensus_map.get(ticker) or [], ticker=ticker, asof=signal_day, cutoff=cutoff
                ),
            )
            tech = row.get("tech") or {}
            tier = row.get("tier")
            raw.update(
                vol60=tech.get("vol60"),
                vol20=tech.get("vol20"),
                cap=rule["tiers"][tier_names[tier]]["cap"] if tier in tier_names else None,
            )
            factor_inputs[ticker] = raw
        observations = contract_observations(
            scores=normalized,
            factor_inputs=factor_inputs,
            plan=plan["payload"] if plan else None,
            ledger=ledger,
            events=m8.get("events") or [],
            consensus=consensus_map,
            signal_day=signal_day,
            cutoff=cutoff,
        )
        attach_risk_inputs(
            db,
            factor_inputs=factor_inputs,
            observations=observations,
            history=grouped,
            plan=plan["payload"] if plan else None,
            ledger=ledger,
            m8=m8,
            day=signal_day,
            cutoff=cutoff,
        )
        bundle = {
            "kind": "live_readonly",
            "target": target.isoformat(),
            "source_events_asof": cutoff.isoformat(),
            "scores": normalized,
            "factor_inputs": factor_inputs,
            "observations": observations,
            "m8": m8,
            "plan": plan["payload"] if plan else None,
            "source_ids": {
                "signal_date": signal_day.isoformat(),
                "plan_generated_at": str(plan["generated_at"]) if plan else None,
                "m8_trade_date": signal_day.isoformat(),
                "m8": deepcopy(m8.get("source_ids") or {}),
            },
        }
        return validate_snapshot(bundle, cutoff=cutoff, target=target)
