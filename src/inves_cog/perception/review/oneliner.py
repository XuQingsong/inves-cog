"""One grounded sentence per day. A miss, or a model failure, keeps the template."""

from psycopg.types.json import Jsonb


def template_sentence(anomaly_count):
    return f"今日异常 {anomaly_count} 个，详见下方"


def ground(client, page):
    """Call once. The payload is that day's ids and counts, not another date's page."""
    ids = _ids(page)
    counts = page.get("counts") if isinstance(page.get("counts"), dict) else {}
    facts = {"date": str(page.get("date")), "anomaly_ids": ids, "counts": counts}
    fallback = template_sentence(counts.get("anomaly_count") or 0)
    try:
        result = client.call("summary_oneliner", {"facts": facts})
    except Exception:
        return fallback
    text = result.get("text") if isinstance(result, dict) else None
    text = str(text or "")
    if any(item and item in text for item in ids):
        return text
    if not ids and "无异常" in text:
        return text
    return fallback


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
