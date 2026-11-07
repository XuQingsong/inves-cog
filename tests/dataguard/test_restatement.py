from datetime import date, datetime, timezone

import pytest

from inves_cog.dataguard.restatement import InputView, restate, verified

pytestmark = pytest.mark.phase1_blocking
DAY = date(2026, 11, 5)
NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)


class Result:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class DB:
    def __init__(self):
        self.calls = []

    def execute(self, sql, args=()):
        self.calls.append((sql, args))
        return Result()


def test_restatement_reads_are_bounded_and_late_daily_values_use_observation_day():
    db = DB()
    view = InputView(db, DAY, NOW)
    view.execute(
        'SELECT obs_date AS d, value, published_at AS p FROM flows.observations '
        'WHERE series_id=%s ORDER BY published_at', ('cboe_pc_equity',)
    )
    sql, args = db.calls[-1]
    assert 'obs_date>=' in sql and 'obs_date<=' in sql
    assert 'ingested_at<=' in sql and 'published_at<=' in sql
    assert 'obs_date::timestamp' in sql and args[0] == 'cboe_pc_equity'
    assert DAY in args and NOW in args
    view.execute('SELECT market, release_at AS p FROM flows.cftc_positions ORDER BY release_at')
    sql, args = db.calls[-1]
    assert 'report_date<=' in sql and 'release_at<=' in sql
    assert 'report_date::timestamp' not in sql  # weekly publication semantics are preserved
    with pytest.raises(ValueError):
        view.execute('DELETE FROM flows.barometer_daily')


def test_append_only_restatement_preserves_original_and_uses_actual_revision_time():
    db = DB()
    record = dict(date=DAY, fear=42.0, greed=20.0, missing=[], inputs={'VIX': 28.18})
    got = restate(db, DAY, NOW, compute=lambda view, start, end: [record], code_rev='test')
    assert got['revised_at'] == NOW.isoformat() and got['record']['asof'] == NOW.isoformat()
    assert got['record']['date'] == str(DAY)
    assert got['input_hash'] and got['record']['inputs']['VIX'] == 28.18
    assert all('UPDATE flows.' not in sql and 'INSERT INTO flows.' not in sql for sql, _ in db.calls)
    insert = next((sql, args) for sql, args in db.calls if 'INSERT INTO ops.barometer_revisions' in sql)
    assert 'DO NOTHING' in insert[0] and NOW in insert[1]
    assert verified(got)
    assert not verified({**got, 'record': {**got['record'], 'missing': ['债市信用']}})
    assert not verified({**got, 'record': {**got['record'], 'fear': None}})
    with pytest.raises(ValueError):
        restate(db, DAY, datetime(2026, 11, 4, tzinfo=timezone.utc), compute=lambda *a: [record])


def test_page_discloses_original_and_revision_without_replacing_original():
    from inves_cog.web.data_status import revision_notice

    html = revision_notice([dict(data_date=DAY, revised_at=NOW, record={'fear': 42, 'greed': 20, 'missing': []})])
    assert '事后修订' in html and '原读数' in html and '2026-11-05' in html
    assert '42' in html and '20' in html and '2026-11-07' in html
