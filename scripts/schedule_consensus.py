"""Poll the durable A020 quota; credentials stay in the private environment."""

import json
import time

from inves_cog.clock import SystemClock
from inves_cog.ingest.earnings_data import scheduled as earnings_scheduled
from inves_cog.ingest.market import NY
from inves_cog.ingest.settings import read_environment
from inves_cog.valuation_v1.consensus_cli import scheduled


def main():
    clock = SystemClock()
    while True:
        try:
            values = read_environment()
            earnings = earnings_scheduled(clock=clock, values=values)
            local = clock.now_utc().astimezone(NY)
            # Keep bounded Alpha batches out of the 15:50 sampling slot.
            alpha = (
                {"status": "deferred_for_options"}
                if (15, 10) <= (local.hour, local.minute) < (15, 59)
                else scheduled(clock=clock, values=values)
            )
            result = {"earnings_data": earnings, "alpha": alpha}
        except Exception as exc:
            result = {"status": "failed", "error_type": type(exc).__name__}
        print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
