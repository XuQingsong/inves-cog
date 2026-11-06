"""_bars window bound — 730 calendar days; older rows do not change technicals."""

from datetime import date


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Connection:
    def __init__(self, rows=()):
        self.statements = []
        self._rows = list(rows)

    def execute(self, statement, params=None):
        self.statements.append((" ".join(statement.split()), params))
        return _Cursor(self._rows)


def test_bars_query_has_lower_bound():
    from inves_cog.web.brief import _bars

    conn = _Connection()
    _bars(conn, date(2026, 11, 5), ["AAPL"])
    sql, params = conn.statements[0]
    assert "trade_date > %s - 730" in sql
    assert params == (["AAPL"], date(2026, 11, 5), date(2026, 11, 5))


def test_technicals_unchanged_when_older_bars_dropped():
    from inves_cog.perception.technical import technicals

    # 350 sessions of mildly trending data with noise
    closes = [100 + i * 0.08 + ((i * 7919) % 13 - 6) * 0.3 for i in range(350)]
    volumes = [1_000_000 + (i * 104729) % 200_000 for i in range(350)]
    full = technicals(closes, volumes)
    windowed = technicals(closes[-250:], volumes[-250:])
    assert full["shape"] == windowed["shape"]
    assert full["signals"] == windowed["signals"]
    if full["rsi"] is not None:
        assert abs(full["rsi"] - windowed["rsi"]) < 0.05  # display precision
