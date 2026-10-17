"""Persist attribution rows on a caller-supplied connection.

Wide anomalies stay retrieval and report only. This module does not open a
database URL and does not write ingest.
"""

from psycopg.types.json import Jsonb


def _json(value):
    if value is None:
        return None
    return Jsonb(value)


def _complete(entry):
    return isinstance(entry, dict) and {"at", "old", "new", "trigger", "evidence_ids"} <= set(entry)


def _guard(bundle):
    wide = bundle.get("universe") == "wide"
    blocked = ("candidates", "linkage", "second_hits", "tracks", "ticker_status")
    if wide and any(bundle.get(key) for key in blocked):
        raise ValueError("广域异常只记录回捞和报告")
    for candidate in bundle.get("candidates") or []:
        if candidate.get("scored") and not candidate.get("info_ids"):
            raise ValueError("已评分候选必须引用信息")
    for row in bundle.get("ticker_status") or []:
        if row.get("n_code") not in {"N1", "N2", "N6"}:
            raise ValueError("标的代码只接受 N1、N2、N6")


class Store:
    def __init__(self, connection):
        self.connection = connection

    def prior(self, event_id):
        found = self.connection.execute(
            "SELECT e.lifecycle, e.history, e.deadline_outcome, e.closing_reason, e.unknowns, r.report "
            "FROM perception.linkage_events AS e "
            "LEFT JOIN perception.reports AS r ON r.anomaly_id = e.anomaly_id "
            "WHERE e.event_id = %s",
            (event_id,),
        ).fetchone()
        if found is None:
            return None
        report = found[5] if isinstance(found[5], dict) else {}
        outcome = found[2]
        reason = found[3]
        formed = outcome is not None or reason is not None
        standing = report.get("fundamental_standing") if formed else None
        if standing not in {"待验证", "局部支持", "支持", "冲突", "失效"}:
            standing = None
        proven = report.get("operating_impact_proven") if formed and "operating_impact_proven" in report else None
        return {
            "lifecycle": found[0],
            "history": list(found[1] or []),
            "deadline_outcome": outcome,
            "closing_reason": reason,
            "unknowns": list(found[4] or []),
            "fundamental": standing,
            "operating_impact_proven": proven,
        }

    def save(self, bundle):
        _guard(bundle)
        linkage = bundle.get("linkage")
        if linkage is not None:
            self._require_linkage(linkage)
        anomaly_id = bundle["anomaly_id"]
        for row in bundle.get("retrievals") or []:
            self._retrieval(anomaly_id, row)
        for row in bundle.get("claims") or []:
            self._claim(row)
        for index, row in enumerate(bundle.get("candidates") or []):
            self._candidate(anomaly_id, row, index)
        linkage = bundle.get("linkage")
        if linkage is not None:
            self._linkage(anomaly_id, linkage)
        event_id = linkage["event_id"] if linkage else None
        for row in bundle.get("tracks") or []:
            self._track(event_id, row)
        for row in bundle.get("second_hits") or []:
            self._second_hit(event_id, row)
        if bundle.get("impact") is not None:
            self._impact(anomaly_id, bundle["impact"])
        if bundle.get("market_day") is not None:
            self._market_day(bundle["market_day"])
        for row in bundle.get("ticker_status") or []:
            self._ticker(anomaly_id, row)
        if bundle.get("report") is not None:
            self._report(anomaly_id, bundle)

    def _retrieval(self, anomaly_id, row):
        self.connection.execute(
            "INSERT INTO perception.retrievals "
            "(anomaly_id, info_id, role, relevance, published_at, source_level, retrieval_mode) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (anomaly_id, info_id) DO UPDATE SET "
            "role = EXCLUDED.role, relevance = EXCLUDED.relevance, "
            "published_at = EXCLUDED.published_at, source_level = EXCLUDED.source_level, "
            "retrieval_mode = EXCLUDED.retrieval_mode",
            (
                anomaly_id,
                row["info_id"],
                row["role"],
                row.get("relevance"),
                row.get("published_at"),
                row.get("source_level"),
                row["retrieval_mode"],
            ),
        )

    def _claim(self, row):
        self.connection.execute(
            "INSERT INTO perception.claims "
            "(claim_id, info_id, subject, variable, mechanism, direction, quantity, horizon, certainty, source_level) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (claim_id) DO UPDATE SET "
            "info_id = EXCLUDED.info_id, subject = EXCLUDED.subject, variable = EXCLUDED.variable, "
            "mechanism = EXCLUDED.mechanism, direction = EXCLUDED.direction, quantity = EXCLUDED.quantity, "
            "horizon = EXCLUDED.horizon, certainty = EXCLUDED.certainty, source_level = EXCLUDED.source_level",
            (
                row["claim_id"],
                row["info_id"],
                row.get("subject"),
                row.get("variable"),
                row.get("mechanism"),
                row.get("direction"),
                row.get("quantity"),
                row.get("horizon"),
                row.get("certainty"),
                row.get("source_level"),
            ),
        )

    def _candidate(self, anomaly_id, row, index):
        self.connection.execute(
            "INSERT INTO perception.candidates "
            "(anomaly_id, candidate_id, mechanism, chain, affected, control_baskets, info_ids, "
            "evidence, score, confidence, magnitude, fundamental, scored) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (anomaly_id, candidate_id) DO UPDATE SET "
            "mechanism = EXCLUDED.mechanism, chain = EXCLUDED.chain, affected = EXCLUDED.affected, "
            "control_baskets = EXCLUDED.control_baskets, info_ids = EXCLUDED.info_ids, "
            "evidence = EXCLUDED.evidence, score = EXCLUDED.score, confidence = EXCLUDED.confidence, "
            "magnitude = EXCLUDED.magnitude, fundamental = EXCLUDED.fundamental, scored = EXCLUDED.scored",
            (
                anomaly_id,
                row.get("candidate_id") or f"c{index}",
                row["mechanism"],
                _json(row.get("chain") or []),
                _json(row.get("affected") or []),
                row.get("control_baskets") or [],
                row.get("info_ids") or [],
                _json(row.get("evidence")),
                row.get("score"),
                row.get("confidence"),
                _json(row.get("magnitude")),
                row.get("fundamental"),
                bool(row.get("scored")),
            ),
        )

    def _require_linkage(self, row):
        history = list(row.get("history") or [])
        for entry in history:
            if not _complete(entry):
                raise ValueError("审计链缺少时间、触发条件或证据")
        found = self.connection.execute(
            "SELECT lifecycle, history FROM perception.linkage_events WHERE event_id = %s",
            (row["event_id"],),
        ).fetchone()
        if found is None or found[0] == row["lifecycle"]:
            return
        combined = list(found[1] or []) + history
        covered = any(_complete(entry) and entry.get("new") == row["lifecycle"] for entry in combined)
        if not covered:
            raise ValueError("状态变更缺少完整审计")

    def _linkage(self, anomaly_id, row):
        self.connection.execute(
            "INSERT INTO perception.linkage_events "
            "(event_id, anomaly_id, lifecycle, history, deadline_outcome, closing_reason, unknowns, mechanism) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (event_id) DO UPDATE SET "
            "anomaly_id = EXCLUDED.anomaly_id, "
            "lifecycle = EXCLUDED.lifecycle, "
            "deadline_outcome = EXCLUDED.deadline_outcome, "
            "closing_reason = EXCLUDED.closing_reason, "
            "unknowns = EXCLUDED.unknowns, "
            "mechanism = EXCLUDED.mechanism, "
            "history = ("
            "SELECT COALESCE(jsonb_agg(entry ORDER BY seq), '[]'::jsonb) FROM ("
            "SELECT entry, seq FROM jsonb_array_elements(perception.linkage_events.history) "
            "WITH ORDINALITY AS prior(entry, seq) "
            "UNION ALL "
            "SELECT entry, seq + 1000000 FROM jsonb_array_elements(COALESCE(EXCLUDED.history, '[]'::jsonb)) "
            "WITH ORDINALITY AS incoming(entry, seq) "
            "WHERE NOT EXISTS ("
            "SELECT 1 FROM jsonb_array_elements(perception.linkage_events.history) AS kept(entry) "
            "WHERE kept.entry = incoming.entry"
            ")) AS combined)",
            (
                row["event_id"],
                anomaly_id,
                row["lifecycle"],
                _json(row.get("history") or []),
                row.get("deadline_outcome"),
                row.get("closing_reason"),
                _json(row.get("unknowns") or []),
                row.get("mechanism"),
            ),
        )

    def _track(self, event_id, row):
        self.connection.execute(
            "INSERT INTO perception.tracks (event_id, trade_date, emotion, capital, fundamental, metrics) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (event_id, trade_date) DO UPDATE SET "
            "emotion = EXCLUDED.emotion, capital = EXCLUDED.capital, "
            "fundamental = EXCLUDED.fundamental, metrics = EXCLUDED.metrics",
            (
                row.get("event_id") or event_id,
                row["trade_date"],
                row.get("emotion"),
                row.get("capital"),
                row.get("fundamental"),
                _json(row.get("metrics") or {}),
            ),
        )

    def _second_hit(self, event_id, row):
        self.connection.execute(
            "INSERT INTO perception.second_hits "
            "(event_id, info_id, session, expected_z, control_z, outcome, source_root, published_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (event_id, info_id) DO UPDATE SET "
            "session = EXCLUDED.session, expected_z = EXCLUDED.expected_z, control_z = EXCLUDED.control_z, "
            "outcome = EXCLUDED.outcome, source_root = EXCLUDED.source_root, published_at = EXCLUDED.published_at",
            (
                row.get("event_id") or event_id,
                row["info_id"],
                row.get("session"),
                row.get("expected_z"),
                row.get("control_z"),
                row["outcome"],
                row["source_root"],
                row["published_at"],
            ),
        )

    def _impact(self, anomaly_id, row):
        self.connection.execute(
            "INSERT INTO perception.impact_decomposition "
            "(anomaly_id, total_residual, event_part, amplification, unexplained) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (anomaly_id) DO UPDATE SET "
            "total_residual = EXCLUDED.total_residual, event_part = EXCLUDED.event_part, "
            "amplification = EXCLUDED.amplification, unexplained = EXCLUDED.unexplained",
            (anomaly_id, row["total_residual"], row["event"], row["amplification"], row["unexplained"]),
        )

    def _market_day(self, row):
        self.connection.execute(
            "INSERT INTO perception.market_day (trade_date, systemic_event_tag, info_ids) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (trade_date) DO UPDATE SET "
            "systemic_event_tag = EXCLUDED.systemic_event_tag, info_ids = EXCLUDED.info_ids",
            (row["trade_date"], row["systemic_event_tag"], row.get("info_ids") or []),
        )

    def _ticker(self, anomaly_id, row):
        self.connection.execute(
            "INSERT INTO perception.ticker_status (anomaly_id, ticker, exposure, mechanism, n_code, note) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (anomaly_id, ticker) DO UPDATE SET "
            "exposure = EXCLUDED.exposure, mechanism = EXCLUDED.mechanism, "
            "n_code = EXCLUDED.n_code, note = EXCLUDED.note",
            (anomaly_id, row["ticker"], row.get("exposure"), row.get("mechanism"), row["n_code"], row.get("note")),
        )

    def _report(self, anomaly_id, bundle):
        report = dict(bundle["report"])
        if bundle.get("universe") == "wide":
            report["status"] = "已记录"
        self.connection.execute(
            "INSERT INTO perception.reports (anomaly_id, report) VALUES (%s, %s) "
            "ON CONFLICT (anomaly_id) DO UPDATE SET report = EXCLUDED.report",
            (anomaly_id, _json(report)),
        )
