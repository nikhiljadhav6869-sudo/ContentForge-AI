"""Rehearse a trusted ContentForge backup in a disposable, network-isolated database."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import time
import uuid

IMAGE = "postgres:16-alpine"
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
REQUIRED_TABLES = {"users", "workspaces", "workflow_runs", "artifact_versions", "checkpoints", "alembic_version"}
INSPECT_SQL = """
CREATE TEMP TABLE restore_counts (name text, rows bigint);
DO $$ DECLARE t record; n bigint;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('SELECT count(*) FROM public.%I', t.tablename) INTO n;
    INSERT INTO restore_counts VALUES (t.tablename, n);
  END LOOP;
END $$;
SELECT json_build_object(
  'revision', (SELECT version_num FROM public.alembic_version),
  'tables', (SELECT json_object_agg(name, rows) FROM restore_counts)
);
"""


class RestoreError(RuntimeError):
    """Redacted operator-facing failure."""


def command(args, *, stdin=None, timeout=60):
    return subprocess.run(
        ["docker", *args], stdin=stdin, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout, check=False,
    )


def require_success(result, message):
    if result.returncode:
        raise RestoreError(message)
    return result.stdout


def check_restore(archive: Path, checksum: str, expected_revision: str = "0005") -> dict:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", checksum):
        raise RestoreError("Provide the SHA-256 recorded when the backup was created.")
    if not re.fullmatch(r"[0-9]{4}", expected_revision):
        raise RestoreError("Expected revision must be a four-digit migration ID.")
    container = None
    cleanup_failed = False
    try:
        # Copy to a private snapshot so concurrent source changes cannot alter the restore input.
        fd = os.open(archive, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb", buffering=0) as source, tempfile.TemporaryFile(buffering=0) as snapshot:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise RestoreError("Archive must be an owner-only regular file owned by this account; symlinks are rejected.")
            if not 5 <= info.st_size <= MAX_ARCHIVE_BYTES:
                raise RestoreError("Archive must be nonempty and at most 512 MiB for this small-backup rehearsal.")
            copied = 0
            digest = hashlib.sha256()
            while chunk := source.read(1024 * 1024):
                copied += len(chunk)
                if copied > MAX_ARCHIVE_BYTES:
                    raise RestoreError("Archive exceeded the rehearsal size limit.")
                digest.update(chunk)
                snapshot.write(chunk)
            if digest.hexdigest() != checksum.lower():
                raise RestoreError("Archive checksum does not match; no database was created.")
            snapshot.seek(0)
            if snapshot.read(5) != b"PGDMP":
                raise RestoreError("Expected a PostgreSQL custom-format archive.")
            snapshot.seek(0)
            created = command([
                "create", "--pull=never", "--name", f"contentforge-restore-{uuid.uuid4().hex}",
                "--network=none", "--memory=1g", "--cpus=1", "--pids-limit=128",
                "--security-opt=no-new-privileges:true",
                "--tmpfs=/var/lib/postgresql/data:rw,noexec,nosuid,nodev,size=768m",
                "-e", "POSTGRES_USER=contentforge", "-e", "POSTGRES_DB=contentforge",
                "-e", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE,
            ])
            identifier = require_success(created, "Could not create the test container. Ensure Docker and the local PostgreSQL 16 image are available.").decode().strip()
            if not re.fullmatch(r"[0-9a-f]{64}", identifier):
                raise RestoreError("Docker returned an invalid container ID; inspect containers manually.")
            container = identifier
            require_success(command(["start", container]), "Could not start the test database.")
            for _ in range(60):
                # TCP becomes available after the image's temporary initialization server exits.
                ready = command(["exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "contentforge", "-d", "contentforge"], timeout=5)
                if ready.returncode == 0:
                    break
                time.sleep(0.5)
            else:
                raise RestoreError("The isolated database did not become ready.")
            require_success(command([
                "exec", "-i", container, "pg_restore", "--username=contentforge",
                "--dbname=contentforge", "--no-owner", "--no-acl",
                "--single-transaction", "--exit-on-error",
            ], stdin=snapshot, timeout=900), "Restore failed; the archive or available rehearsal resources may be unsuitable.")
            raw = require_success(command([
                "exec", container, "psql", "-U", "contentforge", "-d", "contentforge",
                "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-c", INSPECT_SQL,
            ], timeout=120), "Could not inspect the restored database.")
            data = json.loads(raw)
            tables = data.get("tables") if isinstance(data, dict) else None
            if (
                not isinstance(tables, dict) or not REQUIRED_TABLES <= tables.keys()
                or any(not isinstance(k, str) or type(v) is not int or v < 0 for k, v in tables.items())
                or data.get("revision") != expected_revision
            ):
                raise RestoreError("Restored tables or migration revision did not match expectations.")
            result = {
                "status": "passed", "sha256": digest.hexdigest(), "bytes": copied,
                "revision": data["revision"], "table_count": len(tables),
                "row_counts": tables, "restore_verified": True,
                "scope": "Archive restored transactionally in an isolated PostgreSQL 16 database; required tables, revision, and table counts checked.",
                "not_verified": ["Application startup or workflow resumption", "Record-by-record comparison with the source", "Redis, configuration, secrets, or TLS recovery"],
            }
    except RestoreError:
        raise
    except (OSError, subprocess.SubprocessError, ValueError):
        raise RestoreError("Restore check failed. Check private archive access, Docker availability, and resources; raw details are omitted.") from None
    finally:
        if container:
            try:
                cleanup_failed = command(["rm", "--force", container]).returncode != 0
            except (OSError, subprocess.SubprocessError):
                cleanup_failed = True
            if cleanup_failed:
                raise RestoreError(f"Test container cleanup failed. Remove only this rehearsal container: {container}") from None
    return {**result, "test_container_removed": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--sha256", required=True, help="Previously recorded backup checksum")
    parser.add_argument("--expected-revision", default="0005")
    args = parser.parse_args(argv)
    try:
        result = check_restore(args.archive, args.sha256, args.expected_revision)
    except RestoreError as exc:
        print(json.dumps({"status": "failed", "restore_verified": False, "message": str(exc)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
