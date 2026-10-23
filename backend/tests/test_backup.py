import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("backup", ROOT / "scripts/backup.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
ARCHIVE = b"PGDMPsynthetic archive for filesystem tests"


def fake_dump(command, **kwargs):
    if "pg_dump" in command:
        kwargs["stdout"].write(ARCHIVE)
    else:
        # Child processes inherit the descriptor offset, not Python's buffered position.
        assert os.read(kwargs["stdin"].fileno(), len(ARCHIVE)) == ARCHIVE
    return SimpleNamespace(returncode=0)


@pytest.mark.parametrize("production", [False, True])
def test_private_archive_checksum_scope_and_stack_selection(tmp_path, monkeypatch, production):
    calls = []

    def record(command, **kwargs):
        calls.append(command)
        return fake_dump(command, **kwargs)

    monkeypatch.setattr(backup.subprocess, "run", record)
    output = tmp_path / "backups" / "release.dump"
    result = backup.create_backup(output, production)
    assert output.read_bytes() == ARCHIVE
    assert result["sha256"] == hashlib.sha256(ARCHIVE).hexdigest()
    assert result["bytes"] == len(ARCHIVE)
    assert result["restore_verified"] is False
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert stat.S_IMODE(output.parent.stat().st_mode) == 0o700
    assert list(output.parent.iterdir()) == [output]
    assert calls[0][calls[0].index("--project-name") + 1] == result["project"]
    assert (str(ROOT / "compose.production.yaml") in calls[0]) == production


@pytest.mark.parametrize("kind", ["file", "symlink", "dangling_symlink"])
def test_existing_paths_are_preserved_without_contacting_database(tmp_path, monkeypatch, kind):
    original = tmp_path / "original"
    original.write_bytes(b"existing contents")
    target = tmp_path / "release.dump"
    if kind == "file":
        target.write_bytes(b"existing contents")
    else:
        target.symlink_to(original if kind == "symlink" else tmp_path / "missing")
    monkeypatch.setattr(backup.subprocess, "run", lambda *a, **k: pytest.fail("Database was contacted"))
    with pytest.raises(backup.BackupError, match="already exists"):
        backup.create_backup(target)
    assert original.read_bytes() == b"existing contents"
    assert target.is_symlink() if kind != "file" else target.read_bytes() == b"existing contents"


@pytest.mark.parametrize("failure", ["dump", "catalog", "invalid", "timeout", "disk"])
def test_failed_backup_never_publishes_partial_data_or_exception_secrets(tmp_path, monkeypatch, failure):
    def fail(command, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(["secret-sentinel"], 1)
        if failure == "disk":
            raise OSError("secret-sentinel")
        if "pg_dump" in command:
            kwargs["stdout"].write(b"bad output" if failure == "invalid" else ARCHIVE)
        return SimpleNamespace(
            returncode=int(failure == ("dump" if "pg_dump" in command else "catalog")), stderr=b"secret-sentinel"
        )

    monkeypatch.setattr(backup.subprocess, "run", fail)
    with pytest.raises(backup.BackupError) as error:
        backup.create_backup(tmp_path / "release.dump")
    assert "secret-sentinel" not in str(error.value)
    assert list(tmp_path.iterdir()) == []


def test_concurrent_destination_is_not_replaced(tmp_path, monkeypatch):
    target = tmp_path / "release.dump"

    def race(command, **kwargs):
        result = fake_dump(command, **kwargs)
        if "pg_restore" in command:
            target.write_bytes(b"concurrent backup")
        return result

    monkeypatch.setattr(backup.subprocess, "run", race)
    with pytest.raises(backup.BackupError, match="preserved"):
        backup.create_backup(target)
    assert target.read_bytes() == b"concurrent backup"
    assert list(tmp_path.iterdir()) == [target]
