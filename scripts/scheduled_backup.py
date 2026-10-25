"""Create or check a scheduled PostgreSQL backup without deleting older archives."""

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import secrets
import stat
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from backup import BackupError, create_backup


def utc_now():
    return datetime.now(UTC)


def project_name(production):
    return "contentforge-production" if production else "contentforge"


def private_directory(directory, *, create=False):
    if create:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = directory.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) & 0o077
    ):
        raise BackupError(
            "Use a private backup directory owned by the current user, with mode 0700 and no directory symlink."
        )


def private_file(path, *, flags=os.O_RDONLY):
    descriptor = os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077
            or info.st_nlink != 1
        ):
            raise BackupError(
                "Backup metadata, locks, and archives must be private regular files owned by the current user."
            )
        return os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise


def read_json(path):
    with private_file(path) as source:
        if os.fstat(source.fileno()).st_size > 65536:
            raise BackupError("Backup metadata is too large.")
        return json.load(source)


def sync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish_json(path, value, *, replace=False):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=".metadata-",
            suffix=".partial",
            dir=path.parent,
            delete=False,
        ) as output:
            temporary = Path(output.name)
            json.dump(value, output, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
        # Drop the temporary hard link before readers enforce single-link files.
        temporary.unlink(missing_ok=True)
        temporary = None
        sync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def backup_lock(directory):
    with private_file(
        directory / ".scheduled-backup.lock", flags=os.O_RDWR | os.O_CREAT
    ) as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BackupError(
                "Another scheduled backup is already running in this directory."
            ) from None
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def manifest_name(pointer, project):
    if (
        not isinstance(pointer, dict)
        or pointer.get("schema") != 1
        or pointer.get("project") != project
        or not isinstance(pointer.get("manifest"), str)
        or not re.fullmatch(
            re.escape(project) + r"-\d{8}T\d{6}Z-[a-f0-9]{16}\.dump\.json",
            pointer["manifest"],
        )
    ):
        raise BackupError(
            "Latest-backup metadata is invalid or belongs to a different stack."
        )
    return pointer["manifest"]


def run_backup(directory, production=False):
    directory = Path(directory).absolute()
    private_directory(directory, create=True)
    project = project_name(production)
    latest = directory / f"{project}-latest.json"
    with backup_lock(directory):
        if os.path.lexists(latest):
            manifest_name(read_json(latest), project)
        name = f"{project}-{utc_now():%Y%m%dT%H%M%SZ}-{secrets.token_hex(8)}.dump"
        result = create_backup(directory / name, production)
        manifest = {
            "schema": 1,
            "project": project,
            "archive": name,
            "completed_at": utc_now().isoformat(),
            "bytes": result["bytes"],
            "sha256": result["sha256"],
            "restore_verified": False,
        }
        publish_json(directory / (name + ".json"), manifest)
        publish_json(
            latest,
            {"schema": 1, "project": project, "manifest": name + ".json"},
            replace=True,
        )
    return {"status": "created", **manifest}


def check_backup(directory, production=False, max_age_hours=26):
    if not math.isfinite(max_age_hours) or max_age_hours <= 0:
        raise BackupError(
            "Maximum backup age must be a finite positive number of hours."
        )
    directory = Path(directory).absolute()
    private_directory(directory)
    project = project_name(production)
    name = manifest_name(read_json(directory / f"{project}-latest.json"), project)
    record = read_json(directory / name)
    if (
        not isinstance(record, dict)
        or record.get("schema") != 1
        or record.get("project") != project
        or record.get("archive") != name.removesuffix(".json")
        or type(record.get("bytes")) is not int
        or record["bytes"] < 5
        or not isinstance(record.get("sha256"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", record["sha256"])
        or record.get("restore_verified") is not False
        or not isinstance(record.get("completed_at"), str)
    ):
        raise BackupError(
            "Backup manifest is invalid or belongs to a different archive."
        )
    completed = datetime.fromisoformat(record["completed_at"])
    if completed.tzinfo is None:
        raise BackupError("Backup timestamp must include a timezone.")
    age = (utc_now() - completed).total_seconds()
    if age < 0 or age > max_age_hours * 3600:
        raise BackupError(
            "Latest backup is stale or has a future timestamp. Check the timer, clock, and backup logs."
        )
    with private_file(directory / record["archive"]) as archive:
        size = os.fstat(archive.fileno()).st_size
        checksum = hashlib.file_digest(archive, "sha256").hexdigest()
    if size != record["bytes"] or checksum != record["sha256"]:
        raise BackupError("Latest backup size or checksum does not match its manifest.")
    return {
        "status": "fresh",
        **record,
        "age_hours": round(age / 3600, 3),
        "max_age_hours": max_age_hours,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory",
        type=Path,
        required=True,
        help="Private archive directory; older files are never deleted",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Use the contentforge-production stack",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Read-only freshness and full-file checksum check; no Docker calls",
    )
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=26,
        help="Maximum age for --check (default: 26)",
    )
    args = parser.parse_args(argv)
    try:
        result = (
            check_backup(args.directory, args.production, args.max_age_hours)
            if args.check
            else run_backup(args.directory, args.production)
        )
        print(json.dumps(result))
        return 0
    except (BackupError, OSError, ValueError, TypeError, KeyboardInterrupt) as error:
        message = (
            str(error)
            if isinstance(error, BackupError)
            else "Backup operation failed. Check private directory access, metadata, Docker access, and available space; raw details are omitted."
        )
        print(json.dumps({"status": "failed", "message": message}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
