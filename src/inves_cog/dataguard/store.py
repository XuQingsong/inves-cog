"""Idempotent gap transitions and transactional notification outbox."""

from datetime import timedelta
from hashlib import sha256
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from inves_cog.dataguard.mail import compose


class Store:
    def __init__(self, connection):
        self.db = connection

    def reconcile(self, dataset, day, findings, now):
        """The caller owns the transaction: state, audit and mail enqueue commit together."""
        old = {
            r["kind"]: r
            for r in self.db.execute(
                "SELECT * FROM ops.data_gaps WHERE dataset=%s AND data_date=%s FOR UPDATE", (dataset, day)
            ).fetchall()
        }
        present = {f.kind for f in findings}
        notices, keys = [], []
        for f in findings:
            prev = old.get(f.kind)
            reopened = prev and prev["status"] == "resolved"
            generation = (prev["generation"] + 1 if reopened else prev["generation"]) if prev else 1
            status = "open" if not prev or reopened else prev["status"]
            detail = {**(prev["detail"] if prev and not reopened else {}), **f.detail}
            self.db.execute(
                "INSERT INTO ops.data_gaps(dataset,data_date,kind,detail,first_detected_at,last_checked_at,generation) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(dataset,data_date,kind) DO UPDATE SET "
                "detail=EXCLUDED.detail,last_checked_at=EXCLUDED.last_checked_at,status=%s,generation=%s,"
                "resolved_at=CASE WHEN %s THEN NULL ELSE ops.data_gaps.resolved_at END,"
                "attempts=CASE WHEN %s THEN 0 ELSE ops.data_gaps.attempts END,"
                "last_attempt_at=CASE WHEN %s THEN NULL ELSE ops.data_gaps.last_attempt_at END",
                (
                    dataset,
                    day,
                    f.kind,
                    Jsonb(detail),
                    now,
                    now,
                    generation,
                    status,
                    generation,
                    bool(reopened),
                    bool(reopened),
                    bool(reopened),
                ),
            )
            if prev is None or reopened:
                row = dict(
                    dataset=dataset,
                    data_date=day,
                    kind=f.kind,
                    detail=detail,
                    status=status,
                    generation=generation,
                    attempts=0,
                )
                self.event(row, now)
                notices.append(row)
                keys.append(f"{dataset}:{day}:{f.kind}:{generation}:open")
        for kind, prev in old.items():
            if kind not in present and prev["status"] != "resolved":
                prev.update(status="resolved", resolved_at=now, last_checked_at=now)
                self.transition(prev, now)
        return notices, keys

    def event(self, row, now):
        self.db.execute(
            "INSERT INTO ops.data_gap_events(dataset,data_date,kind,generation,at,status,detail) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                row["dataset"],
                row["data_date"],
                row["kind"],
                row["generation"],
                now,
                row["status"],
                Jsonb(row["detail"]),
            ),
        )

    def transition(self, row, now):
        if row.get("reason"):
            row["detail"] = {**row["detail"], "recovery_reason": row["reason"]}
        self.db.execute(
            "UPDATE ops.data_gaps SET status=%s,attempts=%s,last_attempt_at=%s,resolved_at=%s,"
            "last_checked_at=%s,detail=%s WHERE dataset=%s AND data_date=%s AND kind=%s",
            (
                row["status"],
                row["attempts"],
                row.get("last_attempt_at"),
                row.get("resolved_at"),
                now,
                Jsonb(row["detail"]),
                row["dataset"],
                row["data_date"],
                row["kind"],
            ),
        )
        self.event(row, now)

    def enqueue(self, keys, rows, now, *, event_key=None, daily=False, resources="资源状态尚未核实"):
        if not rows and not daily:
            return
        key = event_key or sha256("\n".join(sorted(keys)).encode()).hexdigest()
        subject, body = compose(rows, daily=daily, resources=resources)
        stamp = now.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
        body = f"检测记录时间（北京时间）：{stamp}\n" + body
        self.db.execute(
            "INSERT INTO ops.data_notices(event_key,subject,body,created_at,next_attempt_at) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (key, subject, body, now, now),
        )

    def send_pending(self, mailer, now, *, alert_interval=timedelta(hours=3)):
        """Two mail types only: the 08:30 daily plus merged gap alerts.

        Backfill status changes never mail — only newly opened/reopened gaps
        do, and all due alert rows merge into ONE mail at most every
        ``alert_interval`` (arrivals inside the window roll into the next one).
        """
        if not mailer.configured:
            return "邮件未配置"
        # Service singleton lock excludes a second sender; one merged batch per cycle bounds SMTP time.
        rows = self.db.execute(
            "SELECT * FROM ops.data_notices WHERE sent_at IS NULL AND next_attempt_at<=%s "
            "ORDER BY next_attempt_at,created_at",
            (now,),
        ).fetchall()
        if not rows:
            waiting = self.db.execute(
                "SELECT result FROM ops.data_notices WHERE sent_at IS NULL AND attempts>0 "
                "ORDER BY next_attempt_at LIMIT 1"
            ).fetchone()
            return "邮件发送失败，等待重试" if waiting else "邮件已配置"
        last = self.db.execute(
            "SELECT max(sent_at) AS t FROM ops.data_notices WHERE event_key NOT LIKE 'daily:%'"
        ).fetchone()["t"]
        daily = next((r for r in rows if str(r["event_key"]).startswith("daily:")), None)
        alerts = [r for r in rows if not str(r["event_key"]).startswith("daily:")]
        alert_due = alerts and (last is None or now - last >= alert_interval)
        sent, outcome = 0, "邮件已配置"
        for group in ([daily] if daily else [], alerts if alert_due else []):
            if not group:
                continue
            outcome = self._send_group(mailer, group, now)
            sent += outcome == "sent"
        if alerts and not alert_due:
            return "告警暂存，等待发送间隔" if outcome == "邮件已配置" else outcome
        return "邮件发送正常" if sent else outcome

    def _send_group(self, mailer, group, now):
        if len(group) == 1:
            event_key, subject, body = group[0]["event_key"], group[0]["subject"], group[0]["body"]
        else:
            event_key = sha256("\n".join(sorted(r["event_key"] for r in group)).encode()).hexdigest()
            subject = f"数据提醒：{len(group)} 批"
            body = "\n\n".join(r["body"] for r in group)
        outcome = mailer.send(event_key, subject, body)
        for row in group:
            attempts = row["attempts"] + 1
            self.db.execute(
                "UPDATE ops.data_notices SET result=%s,attempts=%s,sent_at=%s,next_attempt_at=%s WHERE event_key=%s",
                (
                    outcome,
                    attempts,
                    now if outcome == "sent" else None,
                    now + timedelta(minutes=min(120, 5 * attempts)),
                    row["event_key"],
                ),
            )
        return outcome
