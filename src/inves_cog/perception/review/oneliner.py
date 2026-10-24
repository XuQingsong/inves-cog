"""One grounded sentence per day. A miss, or a model failure, keeps the template."""

from psycopg.types.json import Jsonb


def template_sentence(anomaly_count):
    return f"今日异常 {anomaly_count} 个，详见下方"


def ground(client, page):
    """Call once. The payload is that day's ids and counts, not another date's page."""
    sentence, _note = ground_outcome(client, page)
    return sentence


def ground_outcome(client, page):
    """Return the stored sentence and whether the job adopted the model text."""
    ids = _ids(page)
    counts = page.get("counts") if isinstance(page.get("counts"), dict) else {}
    facts = {"date": str(page.get("date")), "anomaly_ids": ids, "counts": counts}
    fallback = template_sentence(counts.get("anomaly_count") or 0)
    try:
        result = client.call("summary_oneliner", {"facts": facts})
    except Exception as exc:
        if _MISSING_DATABASE in str(exc):
            raise
        return fallback, "模板（" + _reason(exc) + "）"
    text = result.get("text") if isinstance(result, dict) else None
    text = str(text or "")
    if any(item and item in text for item in ids):
        return text, "模型原文采用"
    if not ids and "无异常" in text:
        return text, "模型原文采用"
    return fallback, "模板（原文未引用当日编号）"


def _reason(exc):
    text = " ".join(str(exc).split())
    return text or type(exc).__name__


_MISSING_DATABASE = "缺少 INVES_COG_DATABASE_URL"


def store_oneliner(connection, day, clock, sentence):
    connection.execute(
        """
        INSERT INTO perception.reports_weekly (report_id, period_end, generated_at, payload)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (report_id) DO UPDATE
        SET generated_at = EXCLUDED.generated_at, payload = EXCLUDED.payload
        """,
        (
            "oneliner:" + day.isoformat(),
            day,
            clock.now_utc(),
            Jsonb({"sentence": sentence, "date": day.isoformat()}),
        ),
    )
    return sentence


def _ids(page):
    found = []
    for key in ("anomalies", "unhandled"):
        for row in page.get(key) or []:
            if isinstance(row, dict) and isinstance(row.get("anomaly_id"), str) and row["anomaly_id"] not in found:
                found.append(row["anomaly_id"])
    return found
