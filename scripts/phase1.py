"""Prepare dependencies and an isolated database BEFORE the offline pytest process."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".harness"
UV_VERSION = "0.13.0"


def run(command, *, capture=False, content=None, environment=None):
    result = subprocess.run(
        command,
        cwd=ROOT,
        input=content,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        check=True,
        env=environment,
    )
    return result.stdout.strip() if capture else ""


def uv_executable():
    supplied = os.environ.get("INVES_COG_UV")
    if supplied:
        return supplied
    tools = STATE / "tools"
    binary = tools / "bin/uv"
    if not binary.is_file():
        run([sys.executable, "-m", "venv", str(tools)])
        run([str(tools / "bin/python"), "-m", "pip", "install", f"uv=={UV_VERSION}"])
    return str(binary)


def prepare_database(compose):
    run(compose + ["up", "-d", "--wait", "--wait-timeout", "90"])
    psql = compose + [
        "exec",
        "-T",
        "database",
        "psql",
        "-X",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "inves_cog_admin",
        "-d",
        "inves_cog",
        "-At",
    ]
    migrations = sorted((ROOT / "migrations").glob("*.sql"))
    for path in migrations:
        run(psql, content=path.read_text())
    facts = run(
        psql
        + [
            "-c",
            "SELECT current_database(); SELECT current_user; SHOW server_version_num; SELECT extversion FROM pg_extension WHERE extname='vector';",
        ],
        capture=True,
    ).splitlines()
    if len(facts) != 4:
        raise RuntimeError("Database identity/version probe returned incomplete data")
    # Probe future table defaults in the disposable database, never in production.
    sys.path.insert(0, str(ROOT))
    from tests.harness.tools.permissions import OWNERS, READS

    ddl = "\n".join(f"CREATE TABLE {schema}.__m0_permission_probe (value integer);" for schema in OWNERS)
    run(psql, content=ddl)
    roles = ",".join("('" + role + "')" for role in READS)
    schemas = ",".join("('" + schema + "')" for schema in OWNERS)
    query = f"""SELECT json_build_object('role', r.name, 'schema', s.name,
        'select', has_table_privilege(r.name, s.name || '.__m0_permission_probe', 'SELECT'),
        'insert', has_table_privilege(r.name, s.name || '.__m0_permission_probe', 'INSERT'),
        'update', has_table_privilege(r.name, s.name || '.__m0_permission_probe', 'UPDATE'),
        'delete', has_table_privilege(r.name, s.name || '.__m0_permission_probe', 'DELETE'))
        FROM (VALUES {roles}) r(name) CROSS JOIN (VALUES {schemas}) s(name);"""
    permissions = [json.loads(line) for line in run(psql + ["-c", query], capture=True).splitlines()]
    for row in permissions:
        owns = OWNERS[row["schema"]] == row["role"]
        readable = owns or row["schema"] in READS[row["role"]]
        if row["select"] != readable or any(row[p] != owns for p in ("insert", "update", "delete")):
            raise RuntimeError("FR-M0-11: actual future-table permission mismatch: " + json.dumps(row))
    (STATE / "database-permissions.json").write_text(json.dumps(permissions, indent=2) + "\n")
    return dict(
        database=facts[0],
        database_user=facts[1],
        postgres_version=facts[2],
        pgvector_version=facts[3],
        migrations=[p.name for p in migrations],
        temporary_database=True,
        clean_container=Path("/.dockerenv").is_file(),
    )


def main():
    mark = sys.argv[1] if len(sys.argv) == 2 else ""
    if mark not in {"phase1_blocking", "phase1_replay", "phase1_cases"}:
        raise SystemExit("Expected phase1_blocking, phase1_replay or phase1_cases")
    if not shutil.which("docker"):
        raise SystemExit("Docker with docker compose is required for the clean-environment entry point")
    STATE.mkdir(exist_ok=True)
    uv = uv_executable()
    run([uv, "sync", "--frozen", "--python", "3.11", "--group", "dev"])
    python = str(ROOT / ".venv/bin/python")
    compose = [
        "docker",
        "compose",
        "-p",
        "inves-cog-test-" + uuid.uuid4().hex[:12],
        "-f",
        str(ROOT / "docker-compose.yml"),
    ]
    try:
        facts = prepare_database(compose)
        facts.update(
            python_version=run([python, "-c", "import platform; print(platform.python_version())"], capture=True),
            lock_frozen=True,
        )
        (STATE / "bootstrap.json").write_text(json.dumps(facts, indent=2) + "\n")
        env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", INVES_COG_LIVE="0")
        return subprocess.run(
            [python, "-m", "pytest", "-m", mark, "--junitxml=" + str(STATE / (mark + ".xml"))], cwd=ROOT, env=env
        ).returncode
    finally:
        run(compose + ["down", "-v", "--remove-orphans"])


if __name__ == "__main__":
    raise SystemExit(main())
