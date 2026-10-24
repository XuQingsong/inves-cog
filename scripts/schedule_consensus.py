"""Poll the durable A020 quota; credentials stay in the private environment."""

import json
import time

from inves_cog.clock import SystemClock
from inves_cog.ingest.settings import read_environment
from inves_cog.valuation_v1.consensus_cli import scheduled


def main():
    clock = SystemClock()
    while True:
        try:
            result = scheduled(clock=clock, values=read_environment())
        except Exception as exc:
            result = {"status": "failed", "error_type": type(exc).__name__}
        print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
