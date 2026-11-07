"""Alert throttling: merged gap alerts at most every 3h; status changes never mail."""

import contextlib
from datetime import date, datetime, timedelta, timezone

import pytest

from inves_cog.dataguard.core import Finding
from inves_cog.dataguard.store import Store

pytestmark = pytest.mark.phase1_blocking
NOW = datetime(2026, 11, 7, 10, tzinfo=timezone.utc)
DAY = date(2026, 11, 6)


class _Res:
    def __init__(self, rows=()):
        self._rows = list(rows)

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class DB:
    def __init__(self):
        self.notices = {}
        self.gaps = {}
        self.events = []

    def transaction(self):
        return contextlib.nullcontext()

    def execute(self, sql, args=()):
        if "FROM ops.data_gaps WHERE dataset" in sql and "FOR UPDATE" in sql:
            return _Res(r for r in self.gaps.values() if r["dataset"] == args[0] and r["data_date"] == args[1])
        if sql.startswith("INSERT INTO ops.data_gaps"):
            key = (args[0], args[1], args[2])
            if key in self.gaps:
                row = self.gaps[key]
                row.update(detail=args[3], last_checked_at=args[5], status=args[7], generation=args[8])
                if args[9]:
                    row.update(resolved_at=None, attempts=0, last_attempt_at=None)
            else:
                self.gaps[key] = dict(
                    dataset=args[0],
                    data_date=args[1],
                    kind=args[2],
                    detail=args[3],
                    first_detected_at=args[4],
                    last_checked_at=args[5],
                    generation=args[6],
                    status=args[7],
                    resolved_at=None,
                    attempts=0,
                    last_attempt_at=None,
                )
            return _Res()
        if sql.startswith("UPDATE ops.data_gaps"):
            row = self.gaps[(args[6], args[7], args[8])]
            row.update(status=args[0], attempts=args[1], last_attempt_at=args[2], resolved_at=args[3])
            return _Res()
        if sql.startswith("INSERT INTO ops.data_gap_events"):
            self.events.append(args)
            return _Res()
        if sql.startswith("INSERT INTO ops.data_notices"):
            self.notices.setdefault(
                args[0],
                dict(
                    event_key=args[0],
                    subject=args[1],
                    body=args[2],
                    created_at=args[3],
                    next_attempt_at=args[4],
                    attempts=0,
                    sent_at=None,
                    result=None,
                ),
            )
            return _Res()
        if "sent_at IS NULL AND next_attempt_at" in sql:
            return _Res(
                sorted(
                    (r for r in self.notices.values() if r["sent_at"] is None and r["next_attempt_at"] <= args[0]),
                    key=lambda r: (r["next_attempt_at"], r["created_at"]),
                )
            )
        if "attempts>0" in sql:
            return _Res(r for r in self.notices.values() if r["sent_at"] is None and r["attempts"] > 0)
        if "max(sent_at)" in sql:
            sent = [
                r["sent_at"] for r in self.notices.values() if r["sent_at"] and not r["event_key"].startswith("daily:")
            ]
            return _Res([{"t": max(sent) if sent else None}])
        if sql.startswith("UPDATE ops.data_notices"):
            row = self.notices[args[4]]
            row.update(result=args[0], attempts=args[1], sent_at=args[2], next_attempt_at=args[3])
            return _Res()
        raise AssertionError("unexpected SQL: " + sql)


class Mailer:
    configured = True

    def __init__(self):
        self.sent = []

    def send(self, event_key, subject, body):
        self.sent.append((event_key, subject, body))
        return "sent"


def _finding(kind="missing"):
    return Finding("测试集", DAY, kind, {"impact": "测试影响"})


def _open(db, dataset="测试集"):
    rows, keys = Store(db).reconcile(dataset, DAY, [_finding()], NOW)
    Store(db).enqueue(keys, rows, NOW)


def test_status_changes_produce_no_alert_mails():
    """New gap mails once; resolve/reopen/backfill transitions never enqueue."""
    db, mailer = DB(), Mailer()
    _open(db)
    assert len(db.notices) == 1
    for _ in range(5):
        rows, keys = Store(db).reconcile("测试集", DAY, [], NOW)
        Store(db).enqueue(keys, rows, NOW)
    assert len(db.notices) == 1  # resolved transitions create no notice rows
    assert Store(db).send_pending(mailer, NOW) == "邮件发送正常"
    assert len(mailer.sent) == 1


def test_two_batches_within_interval_merge_into_one_mail():
    db, mailer = DB(), Mailer()
    store = Store(db)
    _open(db)
    _open(db, "测试集B")
    assert store.send_pending(mailer, NOW) == "邮件发送正常"
    assert len(mailer.sent) == 1
    _, subject, body = mailer.sent[0]
    assert "2 批" in subject and "测试集" in body and "测试集B" in body
    assert all(r["sent_at"] == NOW for r in db.notices.values())

    _open(db, "测试集C")  # a new gap inside the 3h window -> held
    held = store.send_pending(mailer, NOW + timedelta(hours=1))
    assert "暂存" in held and len(mailer.sent) == 1
    later = NOW + timedelta(hours=3, minutes=1)
    assert store.send_pending(mailer, later) == "邮件发送正常"
    assert len(mailer.sent) == 2 and "测试集C" in mailer.sent[1][2]


def test_daily_sends_regardless_of_alert_interval():
    db, mailer = DB(), Mailer()
    store = Store(db)
    _open(db)
    assert store.send_pending(mailer, NOW) == "邮件发送正常"
    assert len(mailer.sent) == 1
    row = dict(
        dataset="日报",
        data_date=DAY,
        kind="missing",
        status="resolved",
        detail={"impact": "汇总"},
        attempts=0,
        generation=1,
    )
    store.enqueue([], [row], NOW + timedelta(hours=1), event_key="daily:2026-11-07", daily=True)
    assert store.send_pending(mailer, NOW + timedelta(hours=1)) == "邮件发送正常"
    assert len(mailer.sent) == 2 and mailer.sent[1][1].startswith("数据日报")
