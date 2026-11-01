"""The generated supervisord.conf must contain every program running live.

Regression for the 2026-11-01 incident: regenerating the conf dropped
pages/review/live_perception and `supervisorctl update` stopped them,
taking the website down ~7h.
"""

import re
from pathlib import Path

LIVE_PROGRAMS = {
    "scheduler",
    "iex_snapshots",
    "stock_snapshots",
    "macro_snapshots",
    "wide_snapshots",
    "daily_modules",
    "anomaly_daily",
    "valuation_v1",
    "consensus_snapshots",
    "paper_plan",
    "m9",
    "morning_page",
    "attribution_tracks",
    "attribution_labels",
    "financials",
    "watchdog",
    "embedding",
    "news_translate",
    "flows",
    "pages",
    "review",
    "live_perception",
}


def _generated(tmp_path):
    root = Path(__file__).resolve().parents[2]
    import sys

    sys.path.insert(0, str(root / "scripts"))
    import install_ingest_service

    text = install_ingest_service.configuration(root, root / ".venv/bin/python")
    return set(re.findall(r"\[program:([^\]]+)\]", text))


def test_generated_covers_live_programs(tmp_path):
    generated = _generated(tmp_path)
    missing = LIVE_PROGRAMS - generated
    assert not missing, f"installer would drop live programs: {sorted(missing)}"
