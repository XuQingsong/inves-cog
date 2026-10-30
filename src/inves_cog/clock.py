"""The only business entry point for wall-clock time."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol
from zoneinfo import ZoneInfo


class Clock(Protocol):
    def now_utc(self) -> datetime: ...
    def today_trade_date(self) -> date: ...


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def today_trade_date(self) -> date:
        return self.now_utc().astimezone(ZoneInfo("America/New_York")).date()


@dataclass(frozen=True)
class FrozenClock:
    instant: datetime

    def __post_init__(self):
        if self.instant.tzinfo is None or self.instant.utcoffset() is None:
            raise ValueError("FrozenClock requires a timezone-aware timestamp")

    def now_utc(self) -> datetime:
        return self.instant.astimezone(timezone.utc)

    def today_trade_date(self) -> date:
        return self.now_utc().astimezone(ZoneInfo("America/New_York")).date()
