"""Sort immutable close histories once per replay, preserving exact PIT prefixes."""

from bisect import bisect_right


class CloseHistory:
    def __init__(self, rows):
        self.days = sorted(rows)
        self.closes = [rows[day]["close"] for day in self.days]

    def at(self, day):
        return self.closes[: bisect_right(self.days, day)]
