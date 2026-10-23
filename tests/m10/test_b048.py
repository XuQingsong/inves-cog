"""B-048 daily page JSON. Numbers are copied from upstream columns; writes are rejected."""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from inves_cog.clock import FrozenClock
from inves_cog.web.api import create_app
from inves_cog.web.db import open_reader
from inves_cog.web.pages import (
    COMPLETENESS_MISSING,
    MISSING,
    MODEL_CALLS,
    PAPER_LABEL,
    STALE,
    UNCONNECTED,
    VALUATION_LABEL,
)

pytestmark = pytest.mark.phase1_blocking

ROOT = Path(__file__).resolve().parents[2]
DAY = date(2031, 4, 17)
DAY2 = date(2031, 4, 18)
SIGNAL = date(2031, 4, 16)
SEEN = datetime(2031, 4, 17, 2, 0, tzinfo=timezone.utc)
# 2031-04-18 01:00 America/New_York is 05:00 UTC. Rows stamped LATE stay after that cutoff.
DEADLINE = datetime(2031, 4, 18, 5, 0, tzinfo=timezone.utc)
LATE = datetime(2031, 4, 18, 6, 0, tzinfo=timezone.utc)
BEFORE = FrozenClock(datetime(2031, 4, 17, 4, 0, tzinfo=timezone.utc))
AFTER = FrozenClock(DEADLINE)
PUBLISHED = SEEN + timedelta(hours=1)

# Every numeric field the pages emit is one of these upstream columns or a SQL count of them.
COMPARED_FIELDS = (
    "perception.anomalies.max_abs_z",
    "perception.anomalies count",
    "perception.linkage_events.lifecycle grouped count",
    "ingest.info_items source_level count",
    "trading.orders action count",
    "perception.ticker_status count",
    "factor_shadow.daily divergence count",
    "marketstate.market.spy_5d_pct",
    "marketstate.market.vix",
    "marketstate.daily.ret",
    "marketstate.daily.resid_z",
    "marketstate.rotation.rank",
    "perception.candidates.score",
    "perception.candidates.evidence",
    "perception.retrievals.relevance",
    "perception.second_hits.expected_z",
    "perception.second_hits.control_z",
    "perception.impact_decomposition.total_residual",
    "perception.impact_decomposition.event_part",
    "perception.impact_decomposition.amplification",
    "perception.impact_decomposition.unexplained",
    "perception.reports.report.magnitude_channels",
    "perception.tracks.metrics",
    "graph.relations.strength",
    "graph.relations.exposure_usd",
    "ingest.source_health.latency_sec",
    "ingest.source_health.items_last_run",
    "trading.plan.payload",
    "trading.ledger.cash",
    "trading.ledger.equity",
    "trading.ledger.peak_equity",
    "trading.ledger.state.positions",
    "trading.plan.payload.portfolio.tier_usage",
    "trading.daily_scores.quality",
    "trading.daily_scores.growth",
    "trading.daily_scores.valuation",
    "trading.daily_scores.timing",
    "valuation_v1.ranges.bear",
    "valuation_v1.ranges.neutral",
    "valuation_v1.ranges.bull",
    "factor_shadow.daily.value",
    "trading.orders.qty",
    "trading.orders.fill_price",
    "trading.orders.cost",
    "overlay.versions.payload.exposure",
    "overlay.versions.payload.cooling_status",
    "overlay.versions.payload.m8_gaps",
    "overlay.versions.payload.m8_completeness",
)

FORBIDDEN_FIELDS = {
    "orders",
    "order",
    "order_id",
    "cancels",
    "positions",
    "position",
    "qty",
    "quantity",
    "shares",
    "fill_price",
    "cash",
    "equity",
    "peak_equity",
    "bear",
    "neutral",
    "bull",
    "holdings",
    "cost",
    "side",
    "notional",
    "notional_est",
    "position_panel",
    "valuation_range",
    "valuation_ranges",
    "tier_usage",
    "tier_budget",
    "portfolio",
}

PAPER_PATHS = (
    "/api/pages/paper/plan",
    "/api/pages/paper/portfolio",
    "/api/pages/paper/universe",
    "/api/pages/paper/stock/NVDA",
    "/api/pages/paper/health",
    "/api/pages/paper/ledger",
)
MARKET_PATHS = (
    ("/api/pages/home", "/"),
    ("/api/pages/market", "/market"),
    ("/api/pages/linkage/b048-e2", "/linkage"),
    ("/api/pages/stock/MU", "/stock"),
    ("/api/pages/graph", "/graph"),
    ("/api/pages/settings/data", "/settings/data"),
)


def _ticker(event_id, exposure, cooling, gaps):
    return {
        "linkage_events": [{"event_id": event_id, "exposure": exposure}],
        "cooling_off": cooling == "on",
        "cooling_status": cooling,
        "m8_gaps": gaps,
        "first_lot_multiplier": 1.0,
        "divergence_tag": None,
        "stop_review_eligible": False,
        "reason": "",
    }


EVIDENCE = {
    "source": 1,
    "specificity": 0.8,
    "magnitude": 0.6,
    "alignment": 0.7,
    "opposition": 0.4,
    "independence": 0.5,
}
PLAN = {
    "orders": [],
    "cancels": [],
    "skips": [
        {
            "ticker": "NVDA",
            "n_code": "N6",
            "rule_ids": ["M-59"],
            "reason_zh": "继续持有",
            "params_version": "p-2026.10",
            "next_check_date": "2031-04-24",
        },
        {
            "ticker": "AMD",
            "n_code": "N1",
            "rule_ids": ["M-8"],
            "reason_zh": "原因未明不动",
            "params_version": "p-2026.10",
            "next_check_date": "2031-04-22",
        },
    ],
    "portfolio": {"gates": {"panic": False}, "tier_usage": {"attack": {"market_value": 500, "weight_pct": 33}}},
    "input_completeness": {
        "bars": {
            "status": "ok",
            "asof": "2031-04-17T02:00:00+00:00",
            "covered": 59,
            "missing_reason": None,
            "fallback": None,
            "decision_impact": "无",
        }
    },
}
OVERLAY = {
    "version": 1,
    "generated_at": SEEN.isoformat(),
    "source_events_asof": SEEN.isoformat(),
    "params_version": "p-2026.10",
    "tickers": {
        "AMD": _ticker("b048-e2", "概念关联", "off", []),
        "MU": _ticker(
            "b048-e3",
            "直接",
            "on",
            [{"event_id": "b048-e3", "field": "deadline_outcome", "reason": "缺口仍在"}],
        ),
        "AVGO": _ticker("b048-e4", "纯共振", "off", []),
        "AMAT": _ticker("b048-e6", "概念关联", "off", []),
    },
    "m8_completeness": {
        "complete": True,
        "source_events_asof": SEEN.isoformat(),
        "unknown_ticker_count": 0,
        "unknown_tickers": [],
    },
    "market": {"risk_level": None, "l1_state": "风险偏好", "systemic_events": []},
}
REPORT = {
    "magnitude_channels": [{"channel": "价格", "value": 1.25}],
    "market_fingerprint": {"baskets": ["SMH"]},
    "tracking": [{"item": "供给"}],
    "constraint_conclusion": "待验证",
    "weakest_link": {"step": "需求"},
    "scope": {"exposure": "概念关联"},
    "fundamental_standing": "未变",
    "market_confidence": "中",
}


def _dsn(host):
    return f"postgresql://b048_web@{host}/inves_cog"


def _roles(admin):
    admin.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'b048_web') THEN "
        "CREATE ROLE b048_web LOGIN INHERIT; END IF; END $$"
    )
    admin.execute("GRANT role_web TO b048_web")


def _clear(admin):
    admin.execute("DELETE FROM graph.relations WHERE relation_id LIKE 'b048-%'")
    admin.execute("DELETE FROM graph.entities WHERE entity_id LIKE 'b048-%'")
    admin.execute("DELETE FROM perception.second_hits WHERE event_id LIKE 'b048-%'")
    admin.execute("DELETE FROM perception.tracks WHERE event_id LIKE 'b048-%'")
    admin.execute("DELETE FROM perception.retrievals WHERE anomaly_id LIKE 'b048-%'")
    admin.execute("DELETE FROM perception.candidates WHERE anomaly_id LIKE 'b048-%'")
    admin.execute("DELETE FROM perception.ticker_status WHERE anomaly_id LIKE 'b048-%'")
    admin.execute("DELETE FROM perception.impact_decomposition WHERE anomaly_id LIKE 'b048-%'")
    admin.execute("DELETE FROM perception.reports WHERE anomaly_id LIKE 'b048-%'")
    admin.execute("DELETE FROM perception.linkage_events WHERE event_id LIKE 'b048-%'")
    admin.execute("DELETE FROM perception.anomalies WHERE anomaly_id LIKE 'b048-%'")
    admin.execute("DELETE FROM perception.market_day WHERE trade_date IN (%s, %s)", (DAY, DAY2))
    admin.execute("DELETE FROM trading.orders WHERE portfolio_id = 'b048-paper'")
    admin.execute("DELETE FROM trading.plan WHERE portfolio_id = 'b048-paper'")
    admin.execute("DELETE FROM trading.ledger WHERE portfolio_id = 'b048-paper'")
    admin.execute(
        "DELETE FROM trading.daily_scores WHERE signal_date = %s AND params_version = 'p-2026.10'",
        (DAY,),
    )
    admin.execute("DELETE FROM valuation_v1.position_panel WHERE trade_date = %s", (DAY,))
    admin.execute("DELETE FROM valuation_v1.ranges WHERE trade_date = %s AND params_version = 'p-2026.10'", (DAY,))
    admin.execute("DELETE FROM fundamentals.profile WHERE as_of = %s AND ticker = 'NVDA'", (DAY,))
    admin.execute("DELETE FROM overlay.versions WHERE date = %s", (DAY,))
    admin.execute("DELETE FROM factor_shadow.daily WHERE factor_id = 'b048-f'")
    admin.execute("DELETE FROM perception_shadow.signals WHERE signal_key = 'b048-x1'")
    admin.execute("DELETE FROM ingest.earnings_events WHERE event_id = 'b048-earn'")
    admin.execute("DELETE FROM ingest.info_items WHERE info_id LIKE 'b048-%'")
    admin.execute(
        "DELETE FROM ingest.wide_universe WHERE trade_date = %s AND ticker IN ('BIG', 'MEME', 'TQQQ')", (DAY,)
    )
    admin.execute("DELETE FROM ingest.job_runs WHERE trade_date = %s AND params_version = 'p-2026.10'", (DAY,))
    admin.execute("DELETE FROM ingest.source_health WHERE source LIKE 'b048-%'")
    admin.execute("DELETE FROM marketstate.daily WHERE trade_date = %s", (DAY,))
    admin.execute("DELETE FROM marketstate.rotation WHERE trade_date = %s", (DAY,))
    admin.execute("DELETE FROM marketstate.market WHERE trade_date = %s", (DAY,))


def _anomaly(admin, anomaly_id, ticker, basket, generated, z=1.1):
    admin.execute(
        """
        INSERT INTO perception.anomalies (
            anomaly_id, trade_date, session, entry_paths, layer, severity, baskets, members, direction,
            max_abs_z, data_quality, coverage, amplification, type_candidates_prelim, status, universe,
            params_version, generated_at
        ) VALUES (
            %s, %s, 'close', ARRAY['A'], 'L3', 'alert', %s, %s, 'up',
            %s, '{}', '{}', '{}', ARRAY[]::text[], '已发现·原因未明', 'pool', 'p-2026.10', %s
        )
        """,
        (anomaly_id, DAY, [basket], Jsonb([{"ticker": ticker}]), z, generated),
    )


def _event(admin, event_id, anomaly_id, lifecycle, outcome=None):
    history = [{"at": SEEN.isoformat(), "old": None, "new": lifecycle, "trigger": "证据", "evidence_ids": []}]
    admin.execute(
        """
        INSERT INTO perception.linkage_events (event_id, anomaly_id, lifecycle, history, deadline_outcome, unknowns)
        VALUES (%s, %s, %s, %s, %s, '[]')
        """,
        (event_id, anomaly_id, lifecycle, Jsonb(history), outcome),
    )


def _bar(admin, ticker, session, ret, resid_z, basket):
    admin.execute(
        """
        INSERT INTO marketstate.daily (
            trade_date, ticker, session, ret, resid_z, primary_basket, factor_set, health_codes
        ) VALUES (%s, %s, %s, %s, %s, %s, 'p-2026.10', ARRAY['ok'])
        """,
        (DAY, ticker, session, ret, resid_z, basket),
    )


def _info(admin, info_id, kind, level, ticker, seen):
    admin.execute(
        """
        INSERT INTO ingest.info_items (
            info_id, kind, published_at, first_seen_at, source, source_level, headline,
            tickers, entities, extraction_status, flags, payload, extraction_source
        ) VALUES (%s, %s, %s, %s, 'fixture', %s, %s, %s, '{}', 'ok', '{}', '{}', '{}')
        """,
        (info_id, kind, seen, seen, level, info_id, [ticker]),
    )


def _seed_perception(admin):
    _anomaly(admin, "b048-a1", "LITE", "LITE-BKT", SEEN, 1.1)
    _anomaly(admin, "b048-a2", "AMD", "SMH", SEEN, 2.5)
    _anomaly(admin, "b048-a3", "MU", "CHIP", SEEN, 3.0)
    _anomaly(admin, "b048-a4", "AVGO", "CHIP", SEEN, 1.7)
    _anomaly(admin, "b048-a6", "AMAT", "AMAT-BKT", SEEN, 1.2)
    _anomaly(admin, "b048-late", "INTC", "INTC-BKT", LATE, 9.9)
    _event(admin, "b048-e2", "b048-a2", "市场确认")
    _event(admin, "b048-e3", "b048-a3", "市场确认")
    _event(admin, "b048-e4", "b048-a4", "已验证·有影响", "支持")
    _event(admin, "b048-e6", "b048-a6", "假设中")
    _event(admin, "b048-e-late", "b048-late", "市场确认")
    admin.execute(
        "UPDATE perception.linkage_events SET history = %s WHERE event_id = 'b048-e-late'",
        (Jsonb([{"at": LATE.isoformat(), "old": None, "new": "市场确认", "trigger": "次日", "evidence_ids": []}]),),
    )
    admin.execute(
        """
        INSERT INTO perception.candidates (
            anomaly_id, candidate_id, mechanism, chain, affected, control_baskets, info_ids,
            evidence, score, confidence, magnitude, scored
        ) VALUES
            ('b048-a2', 'b048-c-amd', '供给', '[]', %s, '{}', ARRAY['b048-news'], %s, 0.82, '高', NULL, true),
            ('b048-a1', 'b048-c-crwd', '需求', '[]', %s, '{}', '{}', NULL, NULL, NULL, NULL, false)
        """,
        (Jsonb({"ticker": "AMD"}), Jsonb(EVIDENCE), Jsonb({"ticker": "CRWD"})),
    )
    admin.execute(
        """
        INSERT INTO perception.ticker_status (anomaly_id, ticker, exposure, mechanism, n_code)
        VALUES ('b048-a2', 'AMD', '概念关联', '供给', 'N1')
        """
    )
    admin.execute(
        """
        INSERT INTO perception.retrievals (
            anomaly_id, info_id, role, relevance, published_at, source_level, retrieval_mode
        ) VALUES ('b048-a2', 'b048-news', 'primary', 0.9, %s, 1, 'rules')
        """,
        (PUBLISHED,),
    )
    admin.execute(
        """
        INSERT INTO perception.second_hits (
            event_id, info_id, session, expected_z, control_z, outcome, source_root, published_at
        ) VALUES ('b048-e2', 'b048-news', 'close', 1.25, 0.1, '命中', 'sec', %s)
        """,
        (SEEN,),
    )
    admin.execute(
        """
        INSERT INTO perception.impact_decomposition (
            anomaly_id, total_residual, event_part, amplification, unexplained
        ) VALUES ('b048-a2', 3, 2, 0.5, 0.5)
        """
    )
    admin.execute("INSERT INTO perception.reports (anomaly_id, report) VALUES ('b048-a2', %s)", (Jsonb(REPORT),))
    admin.execute(
        """
        INSERT INTO perception.tracks (event_id, trade_date, emotion, capital, fundamental, metrics)
        VALUES ('b048-e2', %s, '初现', '冲击中', '待验证', %s)
        """,
        (DAY, Jsonb({"z": 2.2})),
    )
    admin.execute(
        "INSERT INTO perception.market_day (trade_date, systemic_event_tag, info_ids) VALUES (%s, '无', '{}')",
        (DAY,),
    )
    admin.execute(
        """
        INSERT INTO overlay.versions (date, generated_at, source_events_asof, params_version, payload, published)
        VALUES (%s, %s, %s, 'p-2026.10', %s, true), (%s, %s, %s, 'p-2026.10', %s, true)
        """,
        (DAY, SEEN, SEEN, Jsonb(OVERLAY), DAY, LATE, LATE, Jsonb({"m8_gaps_reason": "次日才生成", "tickers": {}})),
    )


def _seed_market(admin):
    bars = [
        ("NVDA", "close", 0.01, 0.1, "SMH"),
        ("NVDA", "post", 0.08, 2.2, "SMH"),
        ("AMD", "post", 0.04, 1.0, "SMH"),
        ("LITE", "post", 0.12, 2.4, "LITE-BKT"),
        ("MU", "post", 0.09, 1.6, "CHIP"),
        ("AVGO", "post", 0.04, 0.8, "CHIP"),
        ("BIG", "post", 0.09, 3.3, "BIG-BKT"),
        ("ORCL", "post", 0.11, 2.0, "ORCL-BKT"),
        ("JPM", "post", -0.08, -1.5, "JPM-BKT"),
        ("INTC", "post", 0.15, 4.0, "INTC-BKT"),
        ("SPY", "post", 0.01, 0.2, "SPY"),
        ("MEME", "post", 0.5, 8, "MEME"),
        ("TQQQ", "post", 0.3, 6, "TQQQ"),
    ]
    for ticker, session, ret, resid_z, basket in bars:
        _bar(admin, ticker, session, ret, resid_z, basket)
    admin.execute(
        """
        INSERT INTO marketstate.rotation (
            trade_date, session, group_kind, group_id, ret, z, rank, health_codes
        ) VALUES
            (%s, 'post', 'l3', 'SMH', 0.05, 1.1, 3, ARRAY['ok']),
            (%s, 'post', 'l3', 'CHIP', 0.04, 0.9, 1, ARRAY['ok'])
        """,
        (DAY, DAY),
    )
    admin.execute(
        """
        INSERT INTO marketstate.market (trade_date, spy_5d_pct, vix, shock_flag, l1_state, style_spread_z)
        VALUES (%s, 1.2, 15.5, false, '风险偏好', '{}')
        """,
        (DAY,),
    )
    admin.execute(
        """
        INSERT INTO ingest.wide_universe (trade_date, ticker, mktcap, included, exclude_reason, notes)
        VALUES
            (%s, 'BIG', 25000000000, true, NULL, '{}'),
            (%s, 'MEME', 1000000000, true, NULL, '{}'),
            (%s, 'TQQQ', 50000000000, false, 'non_common', '{}')
        """,
        (DAY, DAY, DAY),
    )
    _info(admin, "b048-news", "news", 1, "NVDA", SEEN)
    _info(admin, "b048-8k", "sec_8k", 1, "ORCL", SEEN)
    _info(admin, "b048-form4", "form4", 1, "JPM", SEEN)
    _info(admin, "b048-low", "news", 2, "NVDA", SEEN)
    _info(admin, "b048-late-info", "news", 1, "INTC", LATE)
    admin.execute(
        """
        INSERT INTO ingest.earnings_events (event_id, ticker, reaction_day, fallback, flags, fetched_at)
        VALUES ('b048-earn', 'BIG', %s, false, '{}', %s)
        """,
        (DAY, SEEN),
    )
    for name, status, summary in (
        ("anomaly_daily", "failed", "skipped_upstream: bars_full 没有记录"),
        ("bars_prefill", "ok", None),
        ("market_structure", "failed", "连接中断"),
        ("bars_full", "ok", None),
    ):
        admin.execute(
            """
            INSERT INTO ingest.job_runs (
                task_name, trade_date, started_at, ended_at, status, processed_count, error_summary, params_version
            ) VALUES (%s, %s, %s, %s, %s, 0, %s, 'p-2026.10')
            """,
            (name, DAY, SEEN, SEEN, status, summary),
        )
    admin.execute(
        """
        INSERT INTO ingest.source_health (source, last_attempt_at, status, latency_sec, items_last_run)
        VALUES
            ('b048-alpaca', %s, 'ok', 0.4, 10),
            ('b048-tavily', %s, '未接通', 9.9, 4),
            ('b048-late-source', %s, 'ok', 99, 1)
        """,
        (SEEN, SEEN, LATE),
    )


def _seed_paper(admin):
    admin.execute(
        """
        INSERT INTO trading.plan (
            portfolio_id, trade_date, signal_date, extractor, rule_set, params_version, published, generated_at, payload
        ) VALUES
            ('b048-paper', %s, %s, 'fixed', 'A', 'p-2026.10', true, %s, %s),
            ('b048-paper', %s, %s, 'fixed', 'A', 'p-2026.10', true, %s, %s)
        """,
        (
            DAY,
            SIGNAL,
            SEEN,
            Jsonb(PLAN),
            DAY2,
            DAY,
            datetime(2031, 4, 18, 2, tzinfo=timezone.utc),
            Jsonb({"skips": []}),
        ),
    )
    admin.execute(
        """
        INSERT INTO trading.ledger (
            portfolio_id, trade_date, phase, extractor, rule_set, params_version,
            cash, equity, peak_equity, state, observed_at
        ) VALUES (
            'b048-paper', %s, 'close', 'fixed', 'A', 'p-2026.10', 1000, 1500, 1600, %s, %s
        )
        """,
        (DAY, Jsonb({"positions": {"NVDA": {"shares": 10}, "COST": {"shares": 4}}}), SEEN),
    )
    admin.execute(
        """
        INSERT INTO trading.orders (
            portfolio_id, order_id, signal_date, trade_date, ticker, side, kind, qty, fill_price, cost,
            rule_ids, reason_zh, tier, rule_set, params_version, status, intent
        ) VALUES
            ('b048-paper', 'b048-fill', %s, %s, 'NVDA', 'buy', 'open', 10, 100.5, 1, ARRAY['M-1'], '买入',
             'attack', 'A', 'p-2026.10', 'filled', '{}'),
            ('b048-paper', 'b048-pend', %s, %s, 'AMAT', 'buy', 'open', 5, NULL, NULL, ARRAY['M-1'], '挂单',
             'attack', 'A', 'p-2026.10', 'pending', '{}')
        """,
        (SIGNAL, DAY, SIGNAL, DAY),
    )
    admin.execute(
        """
        INSERT INTO trading.daily_scores (
            signal_date, ticker, extractor, rule_set, params_version, tech, derived,
            quality, growth, valuation, timing, timing_subitems, red_lines, tier, certainty, certainty_points,
            hold_score, hold_ok, fund_bad, runway_ok, m32_ok, gate_pass, entry_pass, consec_pass, tradable
        ) VALUES (
            %s, 'NVDA', 'fixed', 'A', 'p-2026.10', '{}', '{}',
            80, 70, 60, 50, '{}', '{}', 'attack', 'high', 3,
            75, true, false, true, true, true, true, 2, true
        )
        """,
        (DAY,),
    )
    label = Jsonb({"label": VALUATION_LABEL})
    admin.execute(
        """
        INSERT INTO valuation_v1.ranges (
            trade_date, ticker, params_version, method_version, version, type, status,
            bear, neutral, bull, pending_review, payload, observed_at
        ) VALUES (%s, 'NVDA', 'p-2026.10', 'v1', 'v1', 'range', 'ok', 10, 20, 30, false, %s, %s)
        """,
        (DAY, label, SEEN),
    )
    admin.execute(
        """
        INSERT INTO valuation_v1.position_panel (trade_date, ticker, params_version, payload, observed_at)
        VALUES (%s, 'NVDA', 'p-2026.10', %s, %s)
        """,
        (DAY, Jsonb({"label": VALUATION_LABEL, "note": "对照"}), SEEN),
    )
    admin.execute(
        """
        INSERT INTO fundamentals.health (ticker, latest_period_end, latest_filed, health_codes, can_score, can_trade)
        VALUES ('NVDA', %s, %s, ARRAY['ok'], true, true)
        ON CONFLICT (ticker) DO UPDATE
        SET health_codes = EXCLUDED.health_codes, can_score = true, can_trade = true, reason = NULL
        """,
        (DAY, DAY),
    )
    admin.execute(
        "INSERT INTO fundamentals.profile (as_of, ticker, profile) VALUES (%s, 'NVDA', %s)",
        (DAY, Jsonb({"name": "NVIDIA"})),
    )
    admin.execute(
        """
        INSERT INTO factor_shadow.registry (
            factor_id, version, definition, inputs, pit_note, target, rationale, source,
            expected_direction, status, created_at
        ) VALUES ('b048-f', 'v1', 'def', '{}', 'pit', 'entry', 'why', 'shadow', 'up', '观察', %s)
        ON CONFLICT DO NOTHING
        """,
        (SEEN,),
    )
    admin.execute(
        """
        INSERT INTO factor_shadow.daily (
            date, ticker, factor_id, version, value, would_pass, rule_a_entry_pass, gap_detail,
            params_version, generated_at
        ) VALUES
            (%s, 'NVDA', 'b048-f', 'v1', %s, true, false, '{}', 'p-2026.10', %s),
            (%s, 'AMD', 'b048-f', 'v1', %s, false, false, '{}', 'p-2026.10', %s)
        """,
        (DAY, Jsonb({"value": 1.5}), SEEN, DAY, Jsonb({"value": 2.5}), SEEN),
    )
    admin.execute(
        """
        INSERT INTO perception_shadow.signals (
            signal_key, date, signal, ticker, event_id, condition_detail, shadow_action, rule_a_action, params_version
        ) VALUES ('b048-x1', %s, 'X1', 'NVDA', 'b048-e2', '{}', '减仓', %s, 'p-2026.10')
        """,
        (DAY, Jsonb({"action": "hold"})),
    )


def _seed_graph(admin):
    admin.execute(
        """
        INSERT INTO graph.entities (entity_id, kind, name) VALUES
            ('b048-nvda', 'company', 'NVIDIA'),
            ('b048-tsmc', 'company', 'TSMC'),
            ('b048-late-co', 'company', 'Later')
        """
    )
    admin.execute(
        """
        INSERT INTO graph.relations (
            relation_id, from_entity, to_entity, connection_type, mechanism, strength, exposure_usd,
            evidence, first_discovered_at, status, drafted_by, reviewed_at
        ) VALUES
            ('b048-rel-1', 'b048-nvda', 'b048-tsmc', '业务关系', '供给', 0.5, 1200000, %s, %s,
             '观察到', 'b048', %s),
            ('b048-rel-late', 'b048-nvda', 'b048-late-co', '业务关系', '供给', 9, 9, '{}', %s,
             '观察到', 'b048', %s)
        """,
        (Jsonb({"quote": "supplies wafers", "status_basis": "SEC原文引文核对"}), SEEN, SEEN, LATE, LATE),
    )


def _open():
    import psycopg
    from psycopg.rows import dict_row

    from tests.m8.test_attribution import _disposable_database

    host = _disposable_database()
    admin = psycopg.connect(
        host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row, autocommit=True
    )
    _roles(admin)
    _clear(admin)
    _seed_perception(admin)
    _seed_market(admin)
    _seed_paper(admin)
    _seed_graph(admin)
    return admin, _dsn(host)


@pytest.fixture(scope="module")
def pages():
    admin, dsn = _open()
    yield {"admin": admin, "dsn": dsn}
    admin.close()


def _get(pages, path, clock=AFTER, day=DAY):
    with TestClient(create_app(dsn=pages["dsn"], clock=clock)) as client:
        response = client.get(path, params={"date": day.isoformat()})
    assert response.status_code == 200, response.text
    return response.json()


def _same(actual, expected):
    assert actual == json.loads(json.dumps(expected))


def _numbers(value, path=""):
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        yield path, value
        return
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _numbers(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _numbers(item, f"{path}[{index}]")


def _column(admin, sql, params):
    return admin.execute(sql, params).fetchone()


def test_page_json_contracts(pages):
    home = _get(pages, "/api/pages/home")
    market = _get(pages, "/api/pages/market")
    linkage = _get(pages, "/api/pages/linkage/b048-e2")
    stock = _get(pages, "/api/pages/stock/MU")
    graph = _get(pages, "/api/pages/graph")
    settings = _get(pages, "/api/pages/settings/data")
    plan = _get(pages, "/api/pages/paper/plan")
    portfolio = _get(pages, "/api/pages/paper/portfolio")
    universe = _get(pages, "/api/pages/paper/universe")
    paper_stock = _get(pages, "/api/pages/paper/stock/NVDA")
    health = _get(pages, "/api/pages/paper/health")
    ledger = _get(pages, "/api/pages/paper/ledger")
    missing = _get(pages, "/api/pages/linkage/missing")
    assert isinstance(home["summary_oneliner"], str) and isinstance(home["counts"]["anomaly_count"], int)
    assert isinstance(home["unhandled"], list) and home["counts"]["status_counts"]
    for layer in ("L1", "L2", "L3", "L4"):
        assert isinstance(market["layers"][layer]["state"], str)
        assert market["layers"][layer]["coverage"] == MISSING
    assert isinstance(market["anomalies"], list) and isinstance(market["linkage_events"], list)
    assert isinstance(market["systemic_event_tag"], str)
    assert set(market["move_board"]) == {"联动", "单股事件"}
    assert isinstance(linkage["evidence_timeline"], list) and isinstance(linkage["candidates"], list)
    assert isinstance(linkage["magnitude_channels"], list) and isinstance(linkage["second_hits"], list)
    assert isinstance(linkage["chain"], dict) and isinstance(linkage["fingerprint"], dict)
    assert isinstance(linkage["dimensions"], dict) and isinstance(linkage["tracking"], list)
    assert isinstance(linkage["constraints"], str) and isinstance(linkage["impact"], dict)
    assert isinstance(linkage["exposure"], str) and isinstance(linkage["cooling_status"], str)
    assert isinstance(linkage["m8_gaps"], list) and isinstance(linkage["m8_completeness"], dict)
    assert isinstance(stock["linkage_events"], list) and "what_changed" in stock and "fundamental_profile" in stock
    assert graph["relations"] and isinstance(graph["relations"][0]["status_basis"], str)
    assert isinstance(settings["sources"], list)
    assert isinstance(plan["plan"], dict) and isinstance(plan["input_completeness"], dict)
    assert isinstance(plan["n9_records"], list) and isinstance(plan["shadow_summary"], list)
    assert isinstance(portfolio["holdings"], dict) and isinstance(portfolio["valuation_position_panel"], list)
    assert isinstance(portfolio["timeline"], list) and len(universe["rows"]) == 59
    assert isinstance(paper_stock["timeline"], list) and isinstance(paper_stock["books_history"], list)
    assert isinstance(health["health"], list) and isinstance(ledger["fills"], list)
    assert missing["event_id"] is None
    dumped = json.dumps(market) + json.dumps(home) + json.dumps(graph)
    assert "b048-late" not in dumped and "b048-rel-late" not in dumped and "次日才生成" not in json.dumps(linkage)


def test_pages_no_recompute(pages):
    admin = pages["admin"]
    market = _get(pages, "/api/pages/market")
    linkage = _get(pages, "/api/pages/linkage/b048-e2")
    graph = _get(pages, "/api/pages/graph")
    settings = _get(pages, "/api/pages/settings/data")
    plan = _get(pages, "/api/pages/paper/plan")
    portfolio = _get(pages, "/api/pages/paper/portfolio")
    universe = _get(pages, "/api/pages/paper/universe")
    paper_stock = _get(pages, "/api/pages/paper/stock/NVDA")
    ledger = _get(pages, "/api/pages/paper/ledger")
    stored_market = _column(admin, "SELECT spy_5d_pct, vix FROM marketstate.market WHERE trade_date = %s", (DAY,))
    assert market["market"]["spy_5d_pct"] == stored_market["spy_5d_pct"]
    assert market["market"]["vix"] == stored_market["vix"]
    for anomaly in market["anomalies"]:
        stored = _column(
            admin, "SELECT max_abs_z FROM perception.anomalies WHERE anomaly_id = %s", (anomaly["anomaly_id"],)
        )
        assert anomaly["max_abs_z"] == stored["max_abs_z"]
    for column in market["move_board"].values():
        for row in column:
            stored = _column(
                admin,
                """
                SELECT ret, resid_z FROM marketstate.daily
                WHERE trade_date = %s AND ticker = %s AND session = 'post'
                """,
                (DAY, row["ticker"]),
            )
            assert row["ret"] == stored["ret"] and row["resid_z"] == stored["resid_z"]
            for peer in row["peers"]:
                peer_row = _column(
                    admin,
                    "SELECT ret FROM marketstate.daily WHERE trade_date = %s AND ticker = %s AND session = 'post'",
                    (DAY, peer["ticker"]),
                )
                assert peer["ret"] == peer_row["ret"]
            if isinstance(row["rank"], int):
                rank = _column(
                    admin,
                    """
                    SELECT rank FROM marketstate.rotation
                    WHERE trade_date = %s AND group_id = %s AND session = 'post'
                    """,
                    (DAY, row["primary_basket"]),
                )
                assert row["rank"] == rank["rank"]
    candidate = linkage["candidates"][0]
    stored_candidate = _column(
        admin,
        "SELECT score, evidence FROM perception.candidates WHERE candidate_id = 'b048-c-amd'",
        (),
    )
    assert candidate["score"] == stored_candidate["score"]
    _same(candidate["evidence"], stored_candidate["evidence"])
    assert (
        linkage["evidence_timeline"][0]["relevance"]
        == _column(admin, "SELECT relevance FROM perception.retrievals WHERE anomaly_id = 'b048-a2'", ())["relevance"]
    )
    hit = _column(admin, "SELECT expected_z, control_z FROM perception.second_hits WHERE event_id = 'b048-e2'", ())
    assert linkage["second_hits"][0]["expected_z"] == hit["expected_z"]
    assert linkage["second_hits"][0]["control_z"] == hit["control_z"]
    impact = _column(
        admin,
        """
        SELECT total_residual, event_part, amplification, unexplained
        FROM perception.impact_decomposition WHERE anomaly_id = 'b048-a2'
        """,
        (),
    )
    assert linkage["impact"] == dict(impact)
    _same(linkage["magnitude_channels"], REPORT["magnitude_channels"])
    _same(linkage["dimensions"]["metrics"], {"z": 2.2})
    relation = graph["relations"][0]
    stored_relation = _column(
        admin, "SELECT strength, exposure_usd FROM graph.relations WHERE relation_id = 'b048-rel-1'", ()
    )
    assert relation["strength"] == stored_relation["strength"]
    assert relation["exposure_usd"] == stored_relation["exposure_usd"]
    source = next(row for row in settings["sources"] if row["source"] == "b048-alpaca")
    stored_source = _column(
        admin, "SELECT latency_sec, items_last_run FROM ingest.source_health WHERE source = 'b048-alpaca'", ()
    )
    assert source["latency_sec"] == stored_source["latency_sec"]
    assert source["items_last_run"] == stored_source["items_last_run"]
    _same(plan["plan"], PLAN)
    _same(plan["n9_records"][0]["value"], {"value": 1.5})
    ledger_row = _column(
        admin,
        "SELECT cash, equity, peak_equity, state FROM trading.ledger WHERE portfolio_id = 'b048-paper'",
        (),
    )
    assert portfolio["cash"] == ledger_row["cash"]
    assert portfolio["equity"] == ledger_row["equity"]
    assert portfolio["peak_equity"] == ledger_row["peak_equity"]
    _same(portfolio["holdings"], ledger_row["state"]["positions"])
    _same(portfolio["tier_budget"], PLAN["portfolio"]["tier_usage"])
    nvda = next(row for row in universe["rows"] if row["ticker"] == "NVDA")
    score = _column(
        admin,
        """
        SELECT quality, growth, valuation, timing FROM trading.daily_scores
        WHERE signal_date = %s AND ticker = 'NVDA'
        """,
        (DAY,),
    )
    assert nvda["books"] == dict(score)
    assert paper_stock["books_history"][0]["quality"] == score["quality"]
    valuation = _column(
        admin, "SELECT bear, neutral, bull FROM valuation_v1.ranges WHERE trade_date = %s AND ticker = 'NVDA'", (DAY,)
    )
    assert nvda["valuation_reference"]["bear"] == valuation["bear"]
    assert nvda["valuation_reference"]["neutral"] == valuation["neutral"]
    assert nvda["valuation_reference"]["bull"] == valuation["bull"]
    assert paper_stock["valuation_card"]["bear"] == valuation["bear"]
    _same(nvda["factor_shadow"][0]["value"], {"value": 1.5})
    fill = ledger["fills"][0]
    stored_fill = _column(admin, "SELECT qty, fill_price, cost FROM trading.orders WHERE order_id = 'b048-fill'", ())
    assert fill["qty"] == stored_fill["qty"]
    assert fill["fill_price"] == stored_fill["fill_price"]
    assert fill["cost"] == stored_fill["cost"]
    assert COMPARED_FIELDS


def test_system_log_counts_match(pages):
    admin = pages["admin"]
    early = _get(pages, "/api/pages/home", BEFORE)
    late = _get(pages, "/api/pages/home", AFTER)
    anomaly_count = _column(
        admin,
        """
        SELECT count(*) AS n FROM perception.anomalies
        WHERE trade_date = %s AND (generated_at IS NULL OR generated_at < %s)
        """,
        (DAY, LATE),
    )["n"]
    statuses = admin.execute(
        """
        SELECT COALESCE(event.lifecycle, anomaly.status) AS status, count(*) AS n
        FROM perception.anomalies AS anomaly
        LEFT JOIN perception.linkage_events AS event ON event.anomaly_id = anomaly.anomaly_id
            AND event.event_id <> 'b048-e-late'
        WHERE anomaly.trade_date = %s AND (anomaly.generated_at IS NULL OR anomaly.generated_at < %s)
        GROUP BY 1
        """,
        (DAY, LATE),
    ).fetchall()
    info_count = _column(
        admin,
        """
        SELECT count(*) AS n FROM ingest.info_items
        WHERE source_level = 1 AND first_seen_at >= %s AND first_seen_at < %s
        """,
        (datetime(2031, 4, 16, 16, tzinfo=timezone.utc), LATE),
    )["n"]
    action_count = _column(
        admin,
        """
        SELECT count(*) AS n FROM trading.orders
        WHERE trade_date = %s AND status IN ('pending', 'filled', 'canceled')
        """,
        (DAY,),
    )["n"]
    no_action = _column(
        admin,
        """
        SELECT count(*) AS n FROM perception.ticker_status AS status
        JOIN perception.anomalies AS anomaly ON anomaly.anomaly_id = status.anomaly_id
        WHERE anomaly.trade_date = %s AND (anomaly.generated_at IS NULL OR anomaly.generated_at < %s)
        """,
        (DAY, LATE),
    )["n"]
    divergence = _column(
        admin,
        """
        SELECT count(*) AS n FROM factor_shadow.daily
        WHERE date = %s AND generated_at < %s AND would_pass IS DISTINCT FROM rule_a_entry_pass
        """,
        (DAY, LATE),
    )["n"]
    counts = late["counts"]
    assert counts["anomaly_count"] == anomaly_count == 5
    assert counts["status_counts"] == {row["status"]: row["n"] for row in statuses}
    assert counts["high_priority_info_count"] == info_count == 3
    assert counts["trade_action_count"] == action_count == 2
    assert counts["no_action_count"] == no_action == 1
    assert counts["shadow_divergence_count"] == divergence == 1
    assert early["summary_oneliner"] == "今日异常 5 个，详见下方"
    assert early["unhandled"] == [{"anomaly_id": "b048-a1", "disposition": "①", "highlighted": False}]
    assert late["unhandled"] == [{"anomaly_id": "b048-a1", "disposition": "①", "highlighted": True}]


def test_disposition_states(pages):
    market = _get(pages, "/api/pages/market")
    found = {row["anomaly_id"]: row["disposition"] for row in market["anomalies"]}
    assert found == {
        "b048-a1": "①",
        "b048-a2": "②",
        "b048-a3": "③",
        "b048-a4": "④",
        "b048-a6": "③",
    }
    mu_orders = (
        pages["admin"]
        .execute("SELECT order_id FROM trading.orders WHERE ticker = 'MU' AND trade_date = %s", (DAY,))
        .fetchall()
    )
    assert mu_orders == []
    linkage = _get(pages, "/api/pages/linkage/b048-e3")
    assert linkage["cooling_status"] == "on" and linkage["exposure"] == "直接"
    assert "⑤" not in json.dumps(market, ensure_ascii=False)
    assert "⑤" not in json.dumps(_get(pages, "/api/pages/home"), ensure_ascii=False)


def test_timeline_records_no_action(pages):
    timeline = _get(pages, "/api/pages/paper/portfolio")["timeline"]
    tickers = {row["ticker"] for row in timeline}
    assert {"NVDA", "COST", "AMD", "CRWD"} <= tickers
    nvda = next(
        row for row in timeline if row["ticker"] == "NVDA" and row.get("kind") == "不动" and row["n_code"] == "N6"
    )
    amd = next(row for row in timeline if row["ticker"] == "AMD" and row.get("next_check_date") == "2031-04-22")
    assert nvda["next_check_date"] == "2031-04-24" and nvda["reason_zh"] == "继续持有"
    assert amd["kind"] == "不动" and amd["n_code"] == "N1"
    for ticker in ("COST", "CRWD"):
        row = next(item for item in timeline if item["ticker"] == ticker)
        assert row == {"ticker": ticker, "text": MISSING}
        assert "n_code" not in row


def test_valuation_position_panel(pages):
    portfolio = _get(pages, "/api/pages/paper/portfolio")
    assert portfolio["valuation_label"] == VALUATION_LABEL
    assert portfolio["valuation_position_panel"] == [{"label": VALUATION_LABEL, "note": "对照"}]
    text = json.dumps(portfolio, ensure_ascii=False)
    assert VALUATION_LABEL in text


def test_paper_labels(pages):
    for path in PAPER_PATHS:
        body = _get(pages, path)
        assert body["label"] == PAPER_LABEL
    for path in ("/api/pages/paper/portfolio", "/api/pages/paper/universe", "/api/pages/paper/stock/NVDA"):
        assert _get(pages, path)["valuation_label"] == VALUATION_LABEL


def test_market_pages_no_trading_fields(pages):
    for path, _name in MARKET_PATHS:
        body = _get(pages, path)
        found = _keys(body)
        assert not (found & FORBIDDEN_FIELDS), sorted(found & FORBIDDEN_FIELDS)


def _keys(value):
    found = set()
    if isinstance(value, dict):
        found.update(value)
        for item in value.values():
            found.update(_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_keys(item))
    return found


def test_unconnected_shown(pages):
    settings = _get(pages, "/api/pages/settings/data")
    offline = next(row for row in settings["sources"] if row["source"] == "b048-tavily")
    assert offline == {"source": "b048-tavily", "status": UNCONNECTED, "display": UNCONNECTED}
    assert list(_numbers(offline)) == []
    assert all(row["source"] != "b048-late-source" for row in settings["sources"])
    home = _get(pages, "/api/pages/home")
    assert home["sections"]["anomalies"]["state"] == STALE
    assert home["sections"]["anomalies"]["job_status"] == "failed"
    assert home["sections"]["anomalies"]["error_summary"] == "skipped_upstream: bars_full 没有记录"
    assert home["sections"]["info"]["state"] == "ok"
    market = _get(pages, "/api/pages/market")
    assert market["sections"]["layers"]["state"] == STALE
    assert market["sections"]["layers"]["job_status"] == "failed"
    assert market["sections"]["layers"]["error_summary"] == "连接中断"
    assert market["sections"]["moves"]["state"] == "ok"
    assert market["move_board"]["联动"]


def test_paper_input_completeness_passthrough(pages):
    plan = _get(pages, "/api/pages/paper/plan")
    assert plan["input_completeness"] == PLAN["input_completeness"]
    assert plan["plan"]["input_completeness"] == PLAN["input_completeness"]
    absent = _get(pages, "/api/pages/paper/plan", day=DAY2)
    assert absent["input_completeness"] == COMPLETENESS_MISSING
    assert "input_completeness" not in absent["plan"]
    linkage = _get(pages, "/api/pages/linkage/b048-e3")
    stock = _get(pages, "/api/pages/stock/MU")
    stored = OVERLAY["tickers"]["MU"]
    assert linkage["exposure"] == stored["linkage_events"][0]["exposure"]
    assert linkage["cooling_status"] == stored["cooling_status"]
    assert linkage["m8_gaps"] == stored["m8_gaps"]
    assert linkage["m8_completeness"] == OVERLAY["m8_completeness"]
    assert stock["linkage_events"][0]["exposure"] == "直接"
    assert stock["linkage_events"][0]["cooling_status"] == "on"
    assert stock["linkage_events"][0]["m8_gaps"] == stored["m8_gaps"]
    assert stock["m8_completeness"] == OVERLAY["m8_completeness"]
    board = _get(pages, "/api/pages/market")["move_board"]
    assert [row["ticker"] for row in board["联动"]] == ["LITE", "MU", "NVDA"]
    assert [row["ticker"] for row in board["单股事件"]] == ["BIG", "INTC", "JPM", "ORCL"]
    by_ticker = {row["ticker"]: row for row in board["联动"] + board["单股事件"]}
    assert by_ticker["NVDA"]["peers"] == [{"ticker": "AMD", "ret": by_ticker["NVDA"]["peers"][0]["ret"]}]
    assert by_ticker["NVDA"]["rank"] == 3 and by_ticker["NVDA"]["has_anomaly"] is False
    assert by_ticker["MU"]["rank"] == 1 and by_ticker["MU"]["has_anomaly"] is True
    assert by_ticker["LITE"]["has_anomaly"] is True and by_ticker["LITE"]["peers"] == []
    assert by_ticker["INTC"]["has_anomaly"] is False
    assert by_ticker["BIG"]["tags"] == ["财报"]
    assert by_ticker["ORCL"]["tags"] == ["8-K"]
    assert by_ticker["JPM"]["tags"] == ["Form 4"]
    assert "MEME" not in by_ticker and "TQQQ" not in by_ticker and "SPY" not in by_ticker
    assert MODEL_CALLS == 0


def test_read_only_transaction_rejects_writes(pages):
    import psycopg

    connection = open_reader(pages["dsn"])
    try:
        mode = connection.execute("SHOW default_transaction_read_only").fetchone()
        assert mode["default_transaction_read_only"] == "on"
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            connection.execute(
                """
                INSERT INTO ingest.source_health (source, last_attempt_at, status, items_last_run)
                VALUES ('b048-write', %s, 'ok', 0)
                """,
                (SEEN,),
            )
    finally:
        connection.rollback()
        connection.close()
    _get(pages, "/api/pages/home")
    pending = (ROOT / "tests/harness/pending.txt").read_text()
    for name in (
        "test_page_json_contracts",
        "test_pages_no_recompute",
        "test_system_log_counts_match",
        "test_disposition_states",
        "test_timeline_records_no_action",
        "test_valuation_position_panel",
        "test_paper_labels",
        "test_market_pages_no_trading_fields",
        "test_unconnected_shown",
        "test_paper_input_completeness_passthrough",
        "test_case_cadence",
        "test_oneliner_grounded",
        "test_precursor_snapshot_daily",
        "test_miss_sample_frame",
        "test_reports_contents",
    ):
        assert name not in pending
    source = (
        (ROOT / "src/inves_cog/web").read_text()
        if False
        else "\n".join(path.read_text() for path in (ROOT / "src/inves_cog/web").glob("*.py"))
    )
    assert "m9_input_snapshots" not in source
    assert "GRANT" not in source
