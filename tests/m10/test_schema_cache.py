"""_table_exists/_column_exists schema-probe caching."""

import inves_cog.web.brief as brief


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Connection:
    def __init__(self, exists=True):
        self.calls = []
        self.exists = exists

    def execute(self, sql, params=None):
        self.calls.append(" ".join(str(sql).split()))
        if "to_regclass" in self.calls[-1]:
            return _Cursor([{"t": "x" if self.exists else None}])
        return _Cursor([{"x": 1} if self.exists else None])


def setup_function():
    brief._SCHEMA_CACHE.clear()


def test_table_exists_probes_once():
    conn = _Connection()
    assert brief._table_exists(conn, "ingest.bars_daily") is True
    assert brief._table_exists(conn, "ingest.bars_daily") is True
    assert len(conn.calls) == 1


def test_missing_table_also_cached():
    conn = _Connection(exists=False)
    assert brief._table_exists(conn, "ingest.nope") is False
    assert brief._table_exists(conn, "ingest.nope") is False
    assert len(conn.calls) == 1


def test_column_exists_probes_once():
    conn = _Connection()
    assert brief._column_exists(conn, "ingest.x", "c") is True
    assert brief._column_exists(conn, "ingest.x", "c") is True
    assert len(conn.calls) == 1
