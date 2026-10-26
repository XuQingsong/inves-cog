"""Resident B-064 translation loop: every 30 min on trading days, ET 04:00-16:00.

Deploy as a supervisor program named `news_translate` (see
scripts/install_ingest_service.py programs map).
"""

import time
from datetime import time as dtime

from inves_cog.clock import SystemClock
from inves_cog.ingest.market import NY, trading_day
from inves_cog.ingest.repository import json_text
from inves_cog.perception.news.translate import translate_day

WINDOW_START = dtime(4, 0)
WINDOW_END = dtime(16, 0)
INTERVAL = 30 * 60


def due(moment, last_run):
    now_et = moment.astimezone(NY)
    if not trading_day(now_et.date()) or not (WINDOW_START <= now_et.time() <= WINDOW_END):
        return False, None
    slot = moment.timestamp() // INTERVAL
    return slot != last_run, slot


def main():
    from inves_cog.ingest.cli import connect
    from inves_cog.ingest.settings import read_environment

    values = read_environment()
    clock = SystemClock()
    last_run = None
    while True:
        connection = None
        writer = None
        try:
            moment = clock.now_utc()
            ok, slot = due(moment, last_run)
            if ok:
                reader_url = values.get("INVES_COG_WEB_DATABASE_URL")
                connection = connect({"INVES_COG_DATABASE_URL": reader_url}) if reader_url else connect(values)
                writer_url = values.get("INVES_COG_PERCEPTION_DATABASE_URL")
                writer = connect({"INVES_COG_DATABASE_URL": writer_url}) if writer_url else None
                if writer is None:
                    print(json_text({"status": "skipped", "reason": "no perception dsn"}), flush=True)
                else:
                    from inves_cog.llm.client import Client

                    result = translate_day(
                        connection,
                        writer,
                        Client.from_environment(values),
                        moment.astimezone(NY).date(),
                        clock=clock,
                    )
                    last_run = slot
                    if result.get("status") not in {"skipped"}:
                        print(json_text(result), flush=True)
        except Exception as exc:  # noqa: BLE001 - resident loop must not die
            print(json_text({"status": "failed", "error_type": type(exc).__name__}), flush=True)
        finally:
            if writer is not None:
                writer.close()
            if connection is not None:
                connection.close()
        time.sleep(30)


if __name__ == "__main__":
    main()
