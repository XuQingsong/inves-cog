"""Post-merge only: apply the reviewed EPS-only dry-run artifact, never run automatically."""

import argparse
import json
import subprocess
from pathlib import Path

from inves_cog.ingest.cli import connect
from inves_cog.ingest.fundamentals.eps_repair import persist_eps_patches
from inves_cog.ingest.settings import read_environment


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("patch", type=Path)
    p.add_argument("--approved-head", required=True)
    p.add_argument("--writer-env", type=Path, required=True)
    a = p.parse_args()
    branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
    if branch != "main" or subprocess.run(["git", "merge-base", "--is-ancestor", a.approved_head, "HEAD"]).returncode:
        p.error("approved implementation must already be merged into the installed main checkout")
    data = json.loads(a.patch.read_text())
    if data.get("status") != "dry_run_only_no_database_writes":
        p.error("expected the reviewed dry-run artifact")
    with connect(read_environment(a.writer_env)) as db:
        db.execute("SET statement_timeout='5000ms'")
        print(json.dumps(persist_eps_patches(db, data["changes"])))


if __name__ == "__main__":
    main()
