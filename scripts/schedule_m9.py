"""Native M9 polling entry point. Installation/ordering awaits the approved OPS contract."""

import json
import time

from inves_cog.clock import SystemClock
from inves_cog.ingest.settings import read_environment
from inves_cog.shadow.cli import scheduled


def main():
    clock = SystemClock()
    while True:
        try:
            result = scheduled(clock=clock, values=read_environment())
        except Exception as exc:
            result = {"status": "failed", "error_type": type(exc).__name__}
        print(json.dumps(result, ensure_ascii=False, default=str, allow_nan=False), flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
