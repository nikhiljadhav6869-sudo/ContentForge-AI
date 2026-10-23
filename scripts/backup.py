"""Create a private PostgreSQL custom archive from the standard Compose stack."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BackupError(RuntimeError):
    """A redacted operational failure safe to report to the operator."""


def create_backup(target: Path, production: bool = False, root: Path = ROOT) -> dict:
    if os.path.lexists(target):
        raise BackupError("Destination already exists; choose a new archive filename.")
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    command = [
        "docker",
        "compose",
        "--project-name",
        "contentforge-production" if production else "contentforge",
        "--env-file",
        str(root / (".env.production" if production else ".env")),
        "-f",
        str(root / "compose.yaml"),
    ]
    if production:
        command += ["-f", str(root / "compose.production.yaml")]
    command += ["exec", "-T", "postgres"]
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            buffering=0,
            prefix=".backup-",
            suffix=".partial",
            dir=target.parent,
            delete=False,
        ) as archive:
            temporary = Path(archive.name)
            result = subprocess.run(
                command
                + [
                    "pg_dump",
                    "--username=contentforge",
                    "--dbname=contentforge",
                    "--format=custom",
                    "--no-owner",
                    "--no-acl",
                ],
                cwd=root,
                stdout=archive,
                stderr=subprocess.PIPE,
                check=False,
                timeout=900,
            )
            if result.returncode:
                raise BackupError(
                    "PostgreSQL backup failed. Check the selected Compose stack and database availability."
                )
            archive.flush()
            os.fsync(archive.fileno())
            archive.seek(0)
            if archive.read(5) != b"PGDMP":
                raise BackupError(
                    "Database command did not produce a PostgreSQL custom archive."
                )
            archive.seek(0)
            checked = subprocess.run(
                command + ["pg_restore", "--list"],
                cwd=root,
                stdin=archive,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=60,
            )
            if checked.returncode:
                raise BackupError(
                    "PostgreSQL could not read the archive catalog; no backup was published."
                )
            archive.seek(0)
            checksum = hashlib.file_digest(archive, "sha256").hexdigest()
            size = os.fstat(archive.fileno()).st_size
        # Atomic publication without replacing a file or symlink created concurrently.
        os.link(temporary, target)
        return {
            "status": "created",
            "file": str(target),
            "bytes": size,
            "sha256": checksum,
            "project": "contentforge-production" if production else "contentforge",
            "scope": "PostgreSQL application data and checkpoints in the standard Compose database",
            "restore_verified": False,
        }
    except subprocess.TimeoutExpired:
        raise BackupError(
            "Database backup or catalog validation timed out; no backup was published."
        ) from None
    except FileExistsError:
        raise BackupError(
            "Destination appeared during backup; the existing file was preserved."
        ) from None
    except OSError:
        raise BackupError(
            "Backup could not complete. Check Docker access, output directory permissions, and free space."
        ) from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New archive path, for example .data/backups/release.dump",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Read the contentforge-production stack using .env.production",
    )
    args = parser.parse_args()
    try:
        print(json.dumps(create_backup(args.output, args.production)))
    except (BackupError, OSError) as exc:
        print(
            str(exc)
            if isinstance(exc, BackupError)
            else "Could not access the backup destination."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
