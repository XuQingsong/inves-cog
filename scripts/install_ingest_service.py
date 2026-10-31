"""Install the user-owned Supervisor service without putting keys in service files."""

import argparse
import os
import platform
import plistlib
import shlex
import subprocess
from pathlib import Path


def configuration(root, python):
    state = root / ".harness/service"
    text = f"""[unix_http_server]
file={state}/supervisor.sock
chmod=0700
[supervisord]
logfile={state}/supervisord.log
pidfile={state}/supervisord.pid
childlogdir={state}
umask=077
nodaemon=true
[rpcinterface:supervisor]
supervisor.rpcinterface_factory=supervisor.rpcinterface:make_main_rpcinterface
[supervisorctl]
serverurl=unix://{state}/supervisor.sock
"""
    programs = {
        "scheduler": [
            "-m",
            "inves_cog.ingest.cli",
            "schedule",
            "--tasks",
            "bars_prefill",
            "bars_full",
            "wide_universe",
            "sec_submissions",
            "sec_index",
            "sec_atom",
            "m6_market_inputs",
            "issuer_profiles",
            "news_prefill",
            "news_full",
            "news_poll",
            "news_watchdog",
            "vix_daily",
            "earnings_calendar",
            "econ_calendar",
            "fred",
            "cboe",
            "finra",
            "fed_news",
        ],
        "iex_snapshots": ["-m", "inves_cog.ingest.cli", "schedule", "--tasks", "iex_intraday"],
        "stock_snapshots": ["-m", "inves_cog.ingest.cli", "schedule", "--tasks", "intraday_snapshots"],
        "macro_snapshots": ["-m", "inves_cog.ingest.cli", "schedule", "--tasks", "yahoo_intraday"],
        "wide_snapshots": ["-m", "inves_cog.ingest.cli", "schedule", "--tasks", "wide_snapshots"],
        "daily_modules": [
            str(root / "scripts/schedule_daily_modules.py"),
            "--tasks",
            "market_structure",
            "rule_a_scores",
        ],
        "anomaly_daily": [
            str(root / "scripts/schedule_daily_modules.py"),
            "--tasks",
            "anomaly_daily",
            "premarket_review",
        ],
        "valuation_v1": [str(root / "scripts/schedule_daily_modules.py"), "--tasks", "valuation_v1"],
        "consensus_snapshots": [str(root / "scripts/schedule_consensus.py")],
        "paper_plan": [str(root / "scripts/schedule_daily_modules.py"), "--tasks", "paper_plan"],
        "m9": [str(root / "scripts/schedule_m9.py")],
        "morning_page": [str(root / "scripts/schedule_morning_page.py")],
        "attribution_tracks": [str(root / "scripts/schedule_attribution_stage.py"), "--task", "attribution_tracks"],
        "attribution_labels": [str(root / "scripts/schedule_attribution_stage.py"), "--task", "attribution_labels"],
        "financials": [str(root / "scripts/schedule_financials.py")],
        "watchdog": ["-m", "inves_cog.ingest.service"],
        "embedding": ["-m", "inves_cog.ingest.embedding_backfill", "--model", "text-embedding-async-v1"],
        "news_translate": [str(root / "scripts/schedule_translate.py")],
        "flows": [str(root / "scripts/schedule_flows.py")],
    }
    for name, arguments in programs.items():
        restart = "unexpected" if name == "embedding" else "true"
        text += f"""
[program:{name}]
command={shlex.join([str(python), "-u", *arguments])}
directory={root}
autostart=true
autorestart={restart}
startsecs=3
startretries=100000
stopasgroup=true
killasgroup=true
stopwaitsecs=15
stdout_logfile={state}/{name}.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=3
redirect_stderr=true
environment=PYTHONUNBUFFERED="1"
"""
    if platform.system() == "Darwin":
        text += f"""
[program:awake]
command=/usr/bin/caffeinate -i -s
autostart=true
autorestart=true
stdout_logfile={state}/awake.log
redirect_stderr=true
"""
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    state = root / ".harness/service"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    python = root / ".venv/bin/python"
    config = state / "supervisord.conf"
    config.write_text(configuration(root, python))
    command = [str(python), "-m", "supervisor.supervisord", "-c", str(config)]
    if platform.system() == "Darwin":
        destination = Path.home() / "Library/LaunchAgents/com.inves-cog.ingest.plist"
        payload = {
            "Label": "com.inves-cog.ingest",
            "ProgramArguments": command,
            "WorkingDirectory": str(root),
            "RunAtLoad": True,
            "KeepAlive": True,
            "ThrottleInterval": 10,
            "StandardOutPath": str(state / "launchd.log"),
            "StandardErrorPath": str(state / "launchd.log"),
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(plistlib.dumps(payload))
        if args.install:
            exists = (
                subprocess.run(
                    ["launchctl", "print", f"gui/{os.getuid()}/com.inves-cog.ingest"], capture_output=True
                ).returncode
                == 0
            )
            if not exists:
                subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(destination)], check=True)
            subprocess.run(["launchctl", "enable", f"gui/{os.getuid()}/com.inves-cog.ingest"], check=True)
            if exists:
                control = [str(python), "-m", "supervisor.supervisorctl", "-c", str(config)]
                subprocess.run([*control, "reread"], check=True)
                subprocess.run([*control, "update"], check=True)
        print(f"macOS login autostart: {destination}; Supervisor autorestart enabled")
    else:
        destination = Path.home() / ".config/systemd/user/inves-cog-ingest.service"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            "[Unit]\nDescription=Inves Cog ingestion supervisor\n"
            "[Service]\nExecStart=" + shlex.join(command) + "\nRestart=always\nRestartSec=10\n"
            "[Install]\nWantedBy=default.target\n"
        )
        if args.install:
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "--user", "enable", "--now", "inves-cog-ingest"], check=True)
        print(f"systemd user autostart: {destination}; enable linger for unattended boot")


if __name__ == "__main__":
    main()
