"""Run integration only against explicitly named, labelled disposable containers.

No cloud services or real voter data. Output contains results, never DB dumps/keys.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import psycopg2
from psycopg2 import sql


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def run(command, env=None, cwd=BACKEND, input_bytes=None):
    result = subprocess.run(command, env=env, cwd=cwd, input=input_bytes, capture_output=True)
    if result.returncode:
        # Commands carry only names and synthetic configuration, no API secrets.
        sys.stdout.write(result.stdout.decode("utf-8", errors="replace"))
        sys.stderr.write(result.stderr.decode("utf-8", errors="replace"))
        raise RuntimeError(f"Verification failed: {command[0:3]}")
    return result.stdout


def port(container, internal):
    label = run(["docker", "inspect", "--format", '{{index .Config.Labels "theogen.task"}}', container]).decode().strip()
    if label != "sprint2-local":
        raise RuntimeError("Refusing an unlabelled container")
    mapping = run(["docker", "port", container, str(internal)]).decode().strip()
    host, value = mapping.split(":")
    if host != "127.0.0.1":
        raise RuntimeError("Integration requires a loopback-only container")
    return int(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--postgres-container", required=True)
    parser.add_argument("--redis-container", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    pg_port = port(args.postgres_container, 5432)
    redis_port = port(args.redis_container, 6379)
    prefix = "s2_" + uuid4().hex[:12]
    names = {kind: prefix + "_" + kind for kind in ("main", "concurrency", "empty", "populated", "privacy", "restored")}
    env = os.environ.copy()
    env.update(ENVIRONMENT="test", SECRET_KEY="synthetic_s2_jwt_key_" + "a" * 40,
               VOTE_HMAC_KEY="synthetic_s2_vote_key_" + "b" * 40,
               ENTITLEMENT_HMAC_KEY="synthetic_s2_entitlement_key_" + "c" * 40,
               REDIS_URL=f"redis://127.0.0.1:{redis_port}/0", SEED_DEMO_DATA="false",
               REQUIRE_S2_SERVICES="1", PYTHONUTF8="1")
    connection = psycopg2.connect(host="127.0.0.1", port=pg_port, dbname="postgres",
                                  user="postgres", password="s2_synthetic_only")
    connection.autocommit = True
    with connection.cursor() as cursor:
        cursor.execute("SHOW server_version_num")
        if int(cursor.fetchone()[0]) // 10000 != 16:
            raise RuntimeError("PostgreSQL 16 is required")
        for name in names.values():
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    connection.close()
    def url(kind):
        return f"postgresql+psycopg2://postgres:s2_synthetic_only@127.0.0.1:{pg_port}/{names[kind]}"
    env.update(DATABASE_URL=url("main"), S2_CONCURRENCY_DATABASE_URL=url("concurrency"),
               S2_EMPTY_MIGRATION_DATABASE_URL=url("empty"), S2_MIGRATION_DATABASE_URL=url("populated"),
               S2_PRIVACY_DATABASE_URL=url("privacy"))
    run([sys.executable, "-m", "alembic", "upgrade", "head"], env)
    populated_env = {**env, "DATABASE_URL": url("populated")}
    run([sys.executable, "-m", "alembic", "upgrade", "e5f6a7b8c9d0"], populated_env)
    run([sys.executable, "tests/prepare_s2_migration_data.py"], env)
    run([sys.executable, "-m", "alembic", "upgrade", "head"], populated_env)
    started = time.monotonic()
    junit = Path(args.output).resolve().with_suffix(".xml")
    junit.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "-rs", "--disable-warnings",
                             "-p", "no:cacheprovider", f"--junitxml={junit}"],
                            cwd=BACKEND, env=env, capture_output=True)
    output = result.stdout.decode("utf-8", errors="replace")
    sys.stdout.write(output)
    if result.returncode:
        sys.stderr.write(result.stderr.decode("utf-8", errors="replace"))
        raise RuntimeError("Backend integration failed")
    import xml.etree.ElementTree as ET
    suites = ET.parse(junit).getroot()
    cases = list(suites.iter("testcase"))
    if any(case.find("skipped") is not None for case in cases):
        raise RuntimeError("Required integration cannot pass with skipped cases")
    dump = run(["docker", "exec", args.postgres_container, "pg_dump", "-U", "postgres", "--no-owner", "--clean", "--if-exists", names["populated"]])
    run(["docker", "exec", "-i", args.postgres_container, "psql", "-U", "postgres", "-d", names["restored"], "-v", "ON_ERROR_STOP=1"], input_bytes=dump)
    # Exact table contents include consumed states and opaque identifiers, not only counts.
    tables = ("elections", "voting_entitlements", "votes", "audit_logs", "audit_chain_heads")
    def snapshot(kind):
        with psycopg2.connect(url(kind).replace("postgresql+psycopg2://", "postgresql://", 1)) as db:
            with db.cursor() as cursor:
                result = {}
                for table in tables:
                    cursor.execute(sql.SQL("SELECT row_to_json(t)::text FROM (SELECT * FROM {} ORDER BY id) t").format(sql.Identifier(table)))
                    result[table] = cursor.fetchall()
                return result
    if snapshot("populated") != snapshot("restored"):
        raise RuntimeError("Backup restored different data")
    report = {"scope": "local synthetic PostgreSQL16/Redis7; not remote CI or production",
              "head": run(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
              "working_tree": True, "test_cases": len(cases), "skipped": 0, "failures": 0,
              "duration_seconds": round(time.monotonic() - started, 2),
              "junit_sha256": hashlib.sha256(junit.read_bytes()).hexdigest(),
              "backup_sha256": hashlib.sha256(dump).hexdigest(), "restored_exactly": True,
              "external_email_sent": False, "independent_custody": False}
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
