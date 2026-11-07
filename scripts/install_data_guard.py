"""Install only the accepted data_guard stanza; preserve every existing Supervisor program."""

import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path

ENV_TEMPLATE = """# Owner-only server settings. No credentials belong in Git.
INVES_SMTP_HOST=smtp.gmail.com
INVES_SMTP_PORT=587
INVES_SMTP_USER=
INVES_SMTP_PASSWORD=
INVES_SMTP_FROM=
INVES_ALERT_TO=
INVES_DATAGUARD_BACKFILL=0
"""


def stanza(root):
    env = root.parent / "inves-cog-data/dataguard.env"
    command = shlex.join([str(root / ".venv/bin/python"), "-u", "-m", "inves_cog.dataguard.service"])
    return f'''[program:data_guard]
command={command}
directory={root}
autostart=true
autorestart=true
startsecs=3
startretries=3
stopasgroup=true
killasgroup=true
stopwaitsecs=15
stdout_logfile={root}/.harness/service/data_guard.log
stdout_logfile_maxbytes=5MB
stdout_logfile_backups=3
redirect_stderr=true
environment=PYTHONUNBUFFERED="1",INVES_DATAGUARD_ENV_FILE="{env}"
'''


def append_program(existing, root):
    wanted = stanza(root)
    if "[program:data_guard]" in existing:
        if wanted.strip() not in existing:
            raise ValueError("Existing data_guard stanza differs; review explicitly before changing it")
        return existing
    return existing + ("\n" if existing.endswith("\n") else "\n\n") + wanted


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--write-config", action="store_true")
    p.add_argument("--prepare-env", action="store_true")
    args = p.parse_args()
    root = args.root.resolve()
    if args.write_config or args.prepare_env:
        # An unmerged feature checkout cannot be used as an installation source.
        subprocess.run(["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"], cwd=root, check=True)
    if args.prepare_env:
        target = root.parent / "inves-cog-data/dataguard.env"
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            print("Owner settings file already exists; preserved")
        else:
            with os.fdopen(fd, "w") as stream:
                stream.write(ENV_TEMPLATE)
            print("Prepared owner-only settings file; credentials remain unset")
    if args.write_config:
        path = root / ".harness/service/supervisord.conf"
        original = path.read_text()
        new = append_program(original, root)
        if new != original:
            temporary = path.with_name("supervisord.conf.data_guard.new")
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as stream:
                stream.write(new)
            if path.read_text() != original:
                temporary.unlink()
                raise RuntimeError("Supervisor configuration changed concurrently; preserved")
            os.replace(temporary, path)
        print(
            json.dumps(
                {
                    "program": "data_guard",
                    "preserved_existing_programs": True,
                    "next": "Capture all statuses, reread, add data_guard; restart pages only. Never update.",
                }
            )
        )
    elif not args.prepare_env:
        print(stanza(root))


if __name__ == "__main__":
    main()
