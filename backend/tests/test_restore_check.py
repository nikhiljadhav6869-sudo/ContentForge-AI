import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_restore", ROOT / "scripts/check_restore.py")
restore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore)
ARCHIVE = b"PGDMPsynthetic restore archive"
DIGEST = hashlib.sha256(ARCHIVE).hexdigest()
CONTAINER = "a" * 64


@pytest.fixture
def archive(tmp_path):
    path = tmp_path / "snapshot.dump"
    path.write_bytes(ARCHIVE)
    path.chmod(0o600)
    return path


def fake_docker(calls, failure=None, data=None):
    def run(args, **kwargs):
        calls.append(args)
        if args[0] == "create":
            if failure == "create":
                return SimpleNamespace(returncode=1, stdout=b"secret-sentinel")
            return SimpleNamespace(returncode=0, stdout=CONTAINER.encode())
        if failure == "timeout" and "pg_restore" in args:
            raise subprocess.TimeoutExpired("secret-sentinel", 1)
        if "pg_restore" in args:
            # Subprocesses read the descriptor offset, not a Python buffer's position.
            assert os.read(kwargs["stdin"].fileno(), len(ARCHIVE)) == ARCHIVE
        if "pg_isready" in args:
            assert args[args.index("-h") + 1] == "127.0.0.1"
        if "psql" in args:
            output = data if data is not None else {
                "revision": "0005", "tables": {name: 2 for name in restore.REQUIRED_TABLES},
            }
            return SimpleNamespace(returncode=0, stdout=json.dumps(output).encode())
        bad = failure == args[0] or failure in args
        return SimpleNamespace(returncode=int(bad), stdout=b"secret-sentinel" if bad else b"")
    return run


def test_isolated_restore_checks_snapshot_and_cleans_only_created_container(archive, monkeypatch):
    calls = []
    monkeypatch.setattr(restore, "command", fake_docker(calls))
    result = restore.check_restore(archive, DIGEST)
    assert result["restore_verified"] and result["test_container_removed"]
    assert result["sha256"] == DIGEST
    assert result["table_count"] == len(restore.REQUIRED_TABLES)
    create = calls[0]
    assert "--network=none" in create and "--pull=never" in create
    assert "--memory=1g" in create and "--pids-limit=128" in create
    assert not any(arg in create for arg in ["-v", "--mount", "-p", "--privileged"])
    assert calls[-1] == ["rm", "--force", CONTAINER]
    assert archive.read_bytes() == ARCHIVE
    assert "--single-transaction" in next(c for c in calls if "pg_restore" in c)


@pytest.mark.parametrize("case", ["checksum", "digest_format", "permissions", "symlink", "directory", "oversize", "header", "revision"])
def test_rejects_unsafe_archive_before_docker(archive, monkeypatch, case):
    digest = DIGEST
    revision = "0005"
    if case == "checksum":
        digest = "0" * 64
    if case == "digest_format":
        digest = "not a checksum"
    if case == "permissions":
        archive.chmod(0o644)
    if case == "symlink":
        link = archive.with_suffix(".link")
        link.symlink_to(archive)
        archive = link
    if case == "directory":
        archive = archive.parent
    if case == "oversize":
        monkeypatch.setattr(restore, "MAX_ARCHIVE_BYTES", 5)
    if case == "header":
        archive.write_bytes(b"invalid archive")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if case == "revision":
        revision = "malformed"
    monkeypatch.setattr(restore, "command", lambda *a, **k: pytest.fail("Docker called"))
    with pytest.raises(restore.RestoreError):
        restore.check_restore(archive, digest, revision)


@pytest.mark.parametrize("failure", ["create", "start", "pg_restore", "timeout", "rm"])
def test_failed_operations_redact_details_and_cleanup(archive, monkeypatch, failure):
    calls = []
    monkeypatch.setattr(restore, "command", fake_docker(calls, failure))
    with pytest.raises(restore.RestoreError) as error:
        restore.check_restore(archive, DIGEST)
    assert "secret-sentinel" not in str(error.value)
    if failure == "create":
        assert len(calls) == 1
    else:
        assert calls[-1] == ["rm", "--force", CONTAINER]
    if failure == "rm":
        assert CONTAINER in str(error.value)


@pytest.mark.parametrize("data", [
    {"revision": "0004", "tables": {name: 1 for name in restore.REQUIRED_TABLES}},
    {"revision": "0005", "tables": {"users": 1}},
    {"revision": "0005", "tables": {name: -1 for name in restore.REQUIRED_TABLES}},
    [],
])
def test_schema_mismatch_cannot_report_success(archive, monkeypatch, data):
    calls = []
    monkeypatch.setattr(restore, "command", fake_docker(calls, data=data))
    with pytest.raises(restore.RestoreError, match="expectations"):
        restore.check_restore(archive, DIGEST)
    assert calls[-1] == ["rm", "--force", CONTAINER]


def test_readiness_is_bounded_and_cleanup_runs(archive, monkeypatch):
    calls = []
    monkeypatch.setattr(restore, "command", fake_docker(calls, "pg_isready"))
    monkeypatch.setattr(restore.time, "sleep", lambda _: None)
    with pytest.raises(restore.RestoreError, match="ready"):
        restore.check_restore(archive, DIGEST)
    assert sum("pg_isready" in c for c in calls) == 60
    assert calls[-1] == ["rm", "--force", CONTAINER]


def test_cli_json_failure_and_success(archive, monkeypatch, capsys):
    monkeypatch.setattr(restore, "command", fake_docker([]))
    assert restore.main(["--archive", str(archive), "--sha256", DIGEST]) == 0
    assert json.loads(capsys.readouterr().out)["restore_verified"] is True
    assert restore.main(["--archive", str(archive), "--sha256", "0" * 64]) == 1
    assert json.loads(capsys.readouterr().out)["restore_verified"] is False
