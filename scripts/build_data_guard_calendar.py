"""Generate a small offline XNYS calendar from the project's existing calendar dependency."""

import json
from pathlib import Path

import exchange_calendars


def main():
    calendar = exchange_calendars.get_calendar("XNYS", start="2024-01-01", end="2030-12-31")
    sessions = {
        str(day.date()): [calendar.session_open(day).isoformat(), calendar.session_close(day).isoformat()]
        for day in calendar.sessions
    }
    path = Path(__file__).resolve().parents[1] / "src/inves_cog/dataguard/sessions.json"
    path.write_text(
        json.dumps(
            {
                "source": "exchange_calendars XNYS",
                "version": exchange_calendars.__version__,
                "start": "2024-01-01",
                "end": "2030-12-31",
                "sessions": sessions,
            },
            separators=(",", ":"),
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
