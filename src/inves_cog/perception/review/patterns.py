"""Pattern candidates. Fewer than 10 stay hidden; 30 holdout passes become 有效."""

from psycopg.types.json import Jsonb

FIELDS = ("trigger_type", "mechanism", "capital_behavior", "outcome")


def pattern_status(count, retained_holds):
    if count < 10:
        return None
    if count >= 30 and retained_holds:
        return "有效"
    return "观察"


def record_example(connection, clock, **fields):
    now = clock.now_utc()
    case_id = fields["case_id"]
    connection.execute(
        """
        INSERT INTO perception.cases (case_id, anomaly_id, trade_date, status, reason, updated_at)
        VALUES (%s, %s, %s, '未完成', NULL, %s)
        ON CONFLICT (case_id) DO NOTHING
        """,
        (case_id, case_id, fields["trade_date"], now),
    )
    pattern = {
        "trigger_type": fields["trigger_type"],
        "mechanism": fields["mechanism"],
        "capital_behavior": fields["capital_behavior"],
        "outcome": fields["outcome"],
        "retained": bool(fields.get("retained")),
        "holds": bool(fields.get("holds")),
        "counterexample": bool(fields.get("counterexample")),
    }
    connection.execute(
        """
        INSERT INTO perception.case_labels (
            case_id, horizon, as_of, drafted, confirmed_at, labels, reason, visible_until, written_at
        ) VALUES (%s, 'T+20', %s, true, NULL, %s, NULL, %s, %s)
        ON CONFLICT (case_id, horizon) DO UPDATE SET labels = EXCLUDED.labels
        """,
        (case_id, fields["trade_date"], Jsonb({"pattern": pattern}), now, now),
    )
    return case_id


def rebuild_patterns(connection, clock):
    rows = connection.execute("SELECT case_id, labels FROM perception.case_labels WHERE labels ? 'pattern'").fetchall()
    groups = {}
    for row in rows:
        pattern = row["labels"]["pattern"]
        key = tuple(pattern[name] for name in FIELDS)
        groups.setdefault(key, []).append((row["case_id"], pattern))
    now = clock.now_utc()
    connection.execute("DELETE FROM perception.patterns")
    kept = []
    for key, items in sorted(groups.items()):
        retained = [item for item in items if item[1]["retained"]]
        holds = bool(retained) and all(item[1]["holds"] for item in retained)
        status = pattern_status(len(items), holds)
        if status is None:
            continue
        examples = [item[0] for item in items]
        counters = [item[0] for item in items if item[1]["counterexample"]]
        pattern_id = "|".join(key)
        connection.execute(
            """
            INSERT INTO perception.patterns (
                pattern_id, trigger_type, mechanism, capital_behavior, outcome,
                example_count, retained_holds, status, examples, counterexamples, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (pattern_id, *key, len(items), holds, status, Jsonb(examples), Jsonb(counters), now),
        )
        kept.append(
            {
                "pattern_id": pattern_id,
                "status": status,
                "example_count": len(items),
                "counterexamples": counters,
            }
        )
    return kept
