"""Persist attribution rows on a caller-supplied connection.

Wide anomalies stay retrieval and report only. This module does not open a
database URL and does not write ingest.
"""

from psycopg.types.json import Jsonb


def _json(value):
    if value is None:
        return None
    return Jsonb(value)


def _guard(bundle):
    wide = bundle.get("universe") == "wide"
    blocked = ("candidates", "linkage", "second_hits", "tracks")
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

    def save(self, bundle):
        _guard(bundle)
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
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
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
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
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
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
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

    def _linkage(self, anomaly_id, row):
        self.connection.execute(
            "INSERT INTO perception.linkage_events "
            "(event_id, anomaly_id, lifecycle, history, deadline_outcome, closing_reason, unknowns, mechanism) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
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
            "VALUES (%s, %s, %s, %s, %s, %s)",
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
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
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
            "VALUES (%s, %s, %s, %s, %s)",
            (anomaly_id, row["total_residual"], row["event"], row["amplification"], row["unexplained"]),
        )

    def _market_day(self, row):
        self.connection.execute(
            "INSERT INTO perception.market_day (trade_date, systemic_event_tag, info_ids) VALUES (%s, %s, %s)",
            (row["trade_date"], row["systemic_event_tag"], row.get("info_ids") or []),
        )

    def _ticker(self, anomaly_id, row):
        self.connection.execute(
            "INSERT INTO perception.ticker_status (anomaly_id, ticker, exposure, mechanism, n_code, note) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (anomaly_id, row["ticker"], row.get("exposure"), row.get("mechanism"), row["n_code"], row.get("note")),
        )

    def _report(self, anomaly_id, bundle):
        report = dict(bundle["report"])
        if bundle.get("universe") == "wide":
            report["status"] = "已记录"
        self.connection.execute(
            "INSERT INTO perception.reports (anomaly_id, report) VALUES (%s, %s)",
            (anomaly_id, _json(report)),
        )
