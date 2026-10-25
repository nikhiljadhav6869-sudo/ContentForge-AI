import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    scheduled = importlib.import_module("scheduled_backup")
    configure = importlib.import_module("configure_backup_schedule")
finally:
    sys.path.pop(0)

ARCHIVE = b"PGDMP synthetic scheduled backup"
NOW = datetime(2026, 10, 26, 2, 0, tzinfo=timezone.utc)


@pytest.fixture
def archive_writer(monkeypatch):
    calls = []

    def create(path, production):
        calls.append((path, production))
        with path.open("xb") as output:
            output.write(ARCHIVE)
        path.chmod(0o600)
        return {"bytes": len(ARCHIVE), "sha256": hashlib.sha256(ARCHIVE).hexdigest()}

    monkeypatch.setattr(scheduled, "create_backup", create)
    monkeypatch.setattr(scheduled, "utc_now", lambda: NOW)
    return calls


@pytest.mark.parametrize("production", [False, True])
def test_archive_manifest_latest_pointer_and_freshness_are_private(tmp_path, archive_writer, production):
    directory = tmp_path / "private"
    result = scheduled.run_backup(directory, production)
    assert result["status"] == "created" and result["restore_verified"] is False
    assert result["project"] == scheduled.project_name(production)
    assert archive_writer[0][1] is production
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in directory.iterdir())
    assert (directory / result["archive"]).read_bytes() == ARCHIVE
    record = json.loads((directory / (result["archive"] + ".json")).read_text())
    assert record["bytes"] == len(ARCHIVE) and record["sha256"] == hashlib.sha256(ARCHIVE).hexdigest()
    checked = scheduled.check_backup(directory, production)
    assert checked["status"] == "fresh" and checked["age_hours"] == 0 and checked["restore_verified"] is False
    assert not list(directory.glob("*.partial"))


def test_repeat_runs_preserve_archives_and_keep_local_and_production_pointers_separate(tmp_path, archive_writer):
    first = scheduled.run_backup(tmp_path)
    second = scheduled.run_backup(tmp_path)
    production = scheduled.run_backup(tmp_path, True)
    assert len({result["archive"] for result in [first, second, production]}) == 3
    assert scheduled.check_backup(tmp_path)["archive"] == second["archive"]
    assert scheduled.check_backup(tmp_path, True)["archive"] == production["archive"]
    assert all((tmp_path / result["archive"]).read_bytes() == ARCHIVE for result in [first, second, production])
    assert len(list(tmp_path.glob("*.dump"))) == 3


def test_failed_dump_preserves_previous_success_and_is_detected_as_stale(tmp_path, archive_writer, monkeypatch):
    first = scheduled.run_backup(tmp_path)
    pointer = tmp_path / "contentforge-latest.json"
    before = pointer.read_bytes()
    monkeypatch.setattr(scheduled, "utc_now", lambda: NOW + timedelta(hours=27))

    def fail(*args):
        raise scheduled.BackupError("Database backup failed.")

    monkeypatch.setattr(scheduled, "create_backup", fail)
    with pytest.raises(scheduled.BackupError):
        scheduled.run_backup(tmp_path)
    assert pointer.read_bytes() == before
    assert (tmp_path / first["archive"]).exists()
    with pytest.raises(scheduled.BackupError, match="stale"):
        scheduled.check_backup(tmp_path)


@pytest.mark.parametrize("failure", ["manifest", "pointer"])
def test_metadata_publication_failure_never_advances_success(tmp_path, archive_writer, monkeypatch, failure):
    scheduled.run_backup(tmp_path)
    pointer = tmp_path / "contentforge-latest.json"
    before = pointer.read_bytes()
    publish = scheduled.publish_json

    def fail(path, value, **kwargs):
        if (path.name.endswith("latest.json")) == (failure == "pointer"):
            raise OSError("secret-sentinel")
        return publish(path, value, **kwargs)

    monkeypatch.setattr(scheduled, "publish_json", fail)
    with pytest.raises(OSError):
        scheduled.run_backup(tmp_path)
    assert pointer.read_bytes() == before
    assert len(list(tmp_path.glob("*.dump"))) == 2  # Completed data is never removed.


def test_overlapping_process_cannot_begin_another_dump(tmp_path, archive_writer):
    scheduled.private_directory(tmp_path)
    with scheduled.backup_lock(tmp_path):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/scheduled_backup.py"), "--directory", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 1 and "already running" in result.stdout
    assert archive_writer == [] and list(tmp_path.glob("*.dump")) == []
    scheduled.run_backup(tmp_path)


@pytest.mark.parametrize("target", ["lock", "latest", "directory"])
def test_symlink_targets_are_preserved_without_starting_dump(tmp_path, archive_writer, target):
    directory = tmp_path / "backups"
    directory.mkdir(mode=0o700)
    original = tmp_path / "keep"
    original.write_text("preserve")
    if target == "directory":
        link = tmp_path / "linked-backups"
        link.symlink_to(directory, target_is_directory=True)
        directory = link
    else:
        name = ".scheduled-backup.lock" if target == "lock" else "contentforge-latest.json"
        (directory / name).symlink_to(original)
    with pytest.raises((scheduled.BackupError, OSError)):
        scheduled.run_backup(directory)
    assert original.read_text() == "preserve" and archive_writer == []


def test_shared_directory_is_rejected_without_changing_permissions(tmp_path, archive_writer):
    tmp_path.chmod(0o755)
    with pytest.raises(scheduled.BackupError, match="private backup directory"):
        scheduled.run_backup(tmp_path)
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o755 and archive_writer == []


@pytest.mark.parametrize(
    "mutation",
    [
        "checksum",
        "size",
        "missing",
        "archive_symlink",
        "manifest_symlink",
        "future",
        "naive",
        "path",
        "scope",
        "version",
        "invalid_json",
        "oversize",
    ],
)
def test_check_rejects_unusable_records_and_archives(tmp_path, archive_writer, mutation):
    result = scheduled.run_backup(tmp_path)
    archive = tmp_path / result["archive"]
    manifest = tmp_path / (result["archive"] + ".json")
    pointer = tmp_path / "contentforge-latest.json"
    record = json.loads(manifest.read_text())
    if mutation == "checksum":
        archive.write_bytes(b"X" * len(ARCHIVE))
    elif mutation == "size":
        archive.write_bytes(ARCHIVE + b"extra")
    elif mutation == "missing":
        archive.unlink()
    elif mutation in {"archive_symlink", "manifest_symlink"}:
        selected = archive if mutation == "archive_symlink" else manifest
        saved = tmp_path / "original"
        selected.rename(saved)
        selected.symlink_to(saved)
    elif mutation == "invalid_json":
        pointer.write_text("invalid secret-sentinel")
    elif mutation == "oversize":
        pointer.write_text("x" * 65537)
    else:
        if mutation == "future":
            record["completed_at"] = (NOW + timedelta(hours=1)).isoformat()
        elif mutation == "naive":
            record["completed_at"] = NOW.replace(tzinfo=None).isoformat()
        elif mutation == "path":
            record["archive"] = "../outside.dump"
        elif mutation == "scope":
            record["project"] = "contentforge-production"
        elif mutation == "version":
            record["schema"] = 2
        manifest.write_text(json.dumps(record))
    with pytest.raises((scheduled.BackupError, OSError, ValueError)):
        scheduled.check_backup(tmp_path)


@pytest.mark.parametrize("hours", [0, -1, float("nan"), float("inf")])
def test_invalid_freshness_window_is_rejected(tmp_path, hours):
    with pytest.raises(scheduled.BackupError, match="finite positive"):
        scheduled.check_backup(tmp_path, max_age_hours=hours)


def test_check_is_read_only_and_does_not_contact_docker(tmp_path, archive_writer, monkeypatch):
    scheduled.run_backup(tmp_path)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    monkeypatch.setattr(scheduled, "create_backup", lambda *args: pytest.fail("Backup called by check"))
    scheduled.check_backup(tmp_path)
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before
    missing = tmp_path / "absent"
    with pytest.raises(OSError):
        scheduled.check_backup(missing)
    assert not missing.exists()


def test_cli_redacts_unexpected_errors_and_returns_failure(tmp_path, monkeypatch, capsys):
    def fail(*args):
        raise OSError("secret-sentinel")

    monkeypatch.setattr(scheduled, "run_backup", fail)
    assert scheduled.main(["--directory", str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "failed" and "secret-sentinel" not in output


@pytest.mark.parametrize("production", [False, True])
def test_generated_units_use_exact_paths_scope_private_permissions_and_utc_timer(tmp_path, production):
    root = tmp_path / "repo with spaces"
    destination = tmp_path / "backups with spaces"
    output = tmp_path / "units"
    unit = configure.generate(output, destination, production, 4, root)
    service = (output / (unit + ".service")).read_text()
    timer = (output / (unit + ".timer")).read_text()
    assert f"WorkingDirectory={root}" in service
    assert f'--directory "{destination}"' in service
    assert (" --production " in service) == production
    assert "UMask=0077" in service and "TimeoutStartSec=20min" in service
    assert "04:00:00 UTC" in timer and "Persistent=true" in timer and "RandomizedDelaySec=10min" in timer
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in output.iterdir())
    assert not root.exists() and not destination.exists()
    if shutil.which("systemd-analyze"):
        result = subprocess.run(
            ["systemd-analyze", "verify", str(output / (unit + ".service")), str(output / (unit + ".timer"))],
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("suffix", ["\nInjected=true", '"', "$HOME", "%h", "\\", "\x7f"])
def test_unit_paths_reject_directive_or_expansion_injection(tmp_path, suffix):
    output = tmp_path / "units"
    with pytest.raises(ValueError):
        configure.generate(output, tmp_path / ("bad" + suffix))
    assert not output.exists()


def test_existing_units_and_symlinks_are_never_replaced(tmp_path):
    output = tmp_path / "units"
    configure.generate(output, tmp_path / "backups")
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    with pytest.raises(FileExistsError):
        configure.generate(output, tmp_path / "different")
    link = tmp_path / "link"
    link.symlink_to(output, target_is_directory=True)
    with pytest.raises(FileExistsError):
        configure.generate(link, tmp_path / "different")
    assert {path.name: path.read_bytes() for path in output.iterdir()} == before


def test_invalid_schedule_hour_creates_nothing(tmp_path):
    for hour in [-1, 24]:
        with pytest.raises(ValueError):
            configure.generate(tmp_path / "units", tmp_path / "backups", hour_utc=hour)
    assert list(tmp_path.iterdir()) == []
