import argparse
import json
import os
import secrets
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote

root = Path(__file__).resolve().parents[1]
base = root / ".harness/local-postgres"
data = base / "data"
sock = base / "socket"
executable = shutil.which("pg_ctl")
if not executable:
    raise SystemExit("PostgreSQL executables must be installed and on PATH")
binary = Path(executable).parent
parser = argparse.ArgumentParser(description="Manage the independent inves-cog development database")
parser.add_argument("action", choices=("start", "status", "stop"), nargs="?", default="start")
action = parser.parse_args().action
if action in {"status", "stop"}:
    command = [str(binary / "pg_ctl"), "-D", str(data), action]
    if action == "stop":
        command.extend(["-m", "fast", "-w"])
    result = subprocess.run(command, capture_output=True, text=True)
    print(json.dumps({"action": action, "success": result.returncode == 0, "data_directory": str(data), "port": 15432}))
    raise SystemExit(result.returncode)
base.mkdir(parents=True, exist_ok=True, mode=0o700)
base.chmod(0o700)
sock.mkdir(exist_ok=True, mode=0o700)
sock.chmod(0o700)
passwords = base / "credentials.json"
if passwords.exists():
    credentials = json.loads(passwords.read_text())
else:
    credentials = {"admin": secrets.token_urlsafe(32), "ingest": secrets.token_urlsafe(32)}
    fd = os.open(passwords, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(credentials, stream)
passwords.chmod(0o600)


def run(args, *, content=None, environment=None):
    result = subprocess.run(
        [str(binary / args[0]), *args[1:]], input=content, capture_output=True, text=True, env=environment
    )
    if result.returncode:
        # Never return query text or credentials from a failed command.
        print(
            json.dumps(
                {
                    "operation": args[0],
                    "exit_code": result.returncode,
                    "diagnostic": result.stderr.replace(credentials["admin"], "<redacted>").replace(
                        credentials["ingest"], "<redacted>"
                    )[-1800:],
                }
            )
        )
        raise SystemExit(result.returncode)
    return result.stdout


if not (data / "PG_VERSION").exists():
    pw = base / "init-password"
    fd = os.open(pw, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(credentials["admin"] + "\n")
    try:
        run(
            [
                "initdb",
                "-D",
                str(data),
                "-U",
                "inves_cog_admin",
                "--encoding=UTF8",
                "--locale=C",
                "--auth-local=scram-sha-256",
                "--auth-host=scram-sha-256",
                "--pwfile=" + str(pw),
            ]
        )
    finally:
        pw.unlink(missing_ok=True)
    with (data / "postgresql.conf").open("a") as stream:
        stream.write(
            "\n# inves-cog independent development instance\n"
            "listen_addresses = '127.0.0.1'\nport = 15432\n"
            f"unix_socket_directories = '{sock}'\n"
            "password_encryption = 'scram-sha-256'\n"
        )

probe = subprocess.run([str(binary / "pg_ctl"), "-D", str(data), "status"], capture_output=True)
if probe.returncode:
    run(["pg_ctl", "-D", str(data), "-l", str(base / "server.log"), "-w", "start"])
environment = dict(os.environ, PGPASSWORD=credentials["admin"])
psql = [
    "psql",
    "-X",
    "-q",
    "-A",
    "-t",
    "-v",
    "ON_ERROR_STOP=1",
    "-h",
    str(sock),
    "-p",
    "15432",
    "-U",
    "inves_cog_admin",
]
exists = run(
    [*psql, "-d", "postgres", "-c", "SELECT 1 FROM pg_database WHERE datname='inves_cog';"], environment=environment
).strip()
if not exists:
    run(
        [*psql, "-d", "postgres"], content="CREATE DATABASE inves_cog OWNER inves_cog_admin;\n", environment=environment
    )
for migration in sorted((root / "migrations").glob("*.sql")):
    run([*psql, "-d", "inves_cog"], content=migration.read_text(), environment=environment)
role = run(
    [*psql, "-d", "postgres", "-c", "SELECT 1 FROM pg_roles WHERE rolname='inves_cog_ingest';"], environment=environment
).strip()
if not role:
    run(
        [*psql, "-d", "inves_cog"],
        content="CREATE ROLE inves_cog_ingest LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '"
        + credentials["ingest"]
        + "';\nGRANT role_ingest TO inves_cog_ingest;\n",
        environment=environment,
    )
run(
    [*psql, "-d", "inves_cog"],
    content=(
        "REVOKE CONNECT ON DATABASE inves_cog FROM PUBLIC;\nGRANT CONNECT ON DATABASE inves_cog TO inves_cog_ingest;\n"
    ),
    environment=environment,
)

env_path = root / ".env"
original = env_path.read_text() if env_path.exists() else ""
backup = base / "env-before-database"
if not backup.exists():
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(original)
dsn = "postgresql://inves_cog_ingest:" + quote(credentials["ingest"], safe="") + "@127.0.0.1:15432/inves_cog"
lines = original.splitlines()
updated = False
for index, line in enumerate(lines):
    if line.partition("=")[0].strip() == "INVES_COG_DATABASE_URL":
        lines[index] = "INVES_COG_DATABASE_URL=" + dsn
        updated = True
if not updated:
    lines.append("INVES_COG_DATABASE_URL=" + dsn)
env_path.write_text("\n".join(lines) + "\n")
env_path.chmod(0o600)
facts = run(
    [
        *psql,
        "-d",
        "inves_cog",
        "-c",
        (
            "SELECT json_build_object('database',current_database(),'postgres',curr"
            "ent_setting('server_version'),'pgvector',(SELECT extversion FROM pg_ex"
            "tension WHERE extname='vector'),'schemas',(SELECT count(*) FROM inform"
            "ation_schema.schemata WHERE schema_owner='inves_cog_admin'),'ingest_ta"
            "bles',(SELECT count(*) FROM information_schema.tables WHERE table_sche"
            "ma='ingest'),'role_trading_can_read_fundamentals',has_schema_privilege"
            "('role_trading','fundamentals','USAGE'),'role_ingest_can_read_graph',h"
            "as_schema_privilege('role_ingest','graph','USAGE'));"
        ),
    ],
    environment=environment,
)
ingest_environment = dict(os.environ, PGPASSWORD=credentials["ingest"])
connection = run(
    [
        "psql",
        "-X",
        "-q",
        "-A",
        "-t",
        "-v",
        "ON_ERROR_STOP=1",
        "-h",
        "127.0.0.1",
        "-p",
        "15432",
        "-U",
        "inves_cog_ingest",
        "-d",
        "inves_cog",
        "-c",
        "SELECT current_database(), current_user, (SELECT count(*) FROM ingest.source_health);",
    ],
    environment=ingest_environment,
)
print(
    json.dumps(
        {
            "facts": json.loads(facts),
            "application_login_verified": bool(connection.strip()),
            "host": "127.0.0.1",
            "port": 15432,
            "credentials_written_to_ignored_env": True,
            "data_directory": str(data),
            "migrations": [p.name for p in sorted((root / "migrations").glob("*.sql"))],
        },
        ensure_ascii=False,
    )
)
