import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import preflight


@pytest.fixture
def configured():
    return SimpleNamespace(
        frontend_origin="https://studio.example.com",
        secure_cookies=True,
        demo_auth=False,
        registration_enabled=False,
        database_url="postgresql+psycopg://user:secret-sentinel@db/app",
        checkpoint_url="postgresql://user:secret-sentinel@db/checkpoints",
        redis_url="redis://:secret-sentinel@queue/0",
        openai_api_key="secret-sentinel",
        openai_model="model",
        openai_base_url="https://provider.example.com/v1",
        gemini_api_key="",
        gemini_model="model",
        ollama_base_url="http://ollama:11434",
        ollama_model="model",
    )


def statuses(result):
    return {item["id"]: item["status"] for item in result["checks"]}


def test_offline_is_explicit_and_never_runs_probes(configured, monkeypatch):
    def unexpected(*args):
        pytest.fail("offline mode contacted a service")

    for name in ["database_checks", "checkpoint_checks", "queue_checks"]:
        monkeypatch.setattr(preflight, name, unexpected)
    result = preflight.report(configured, "openai", offline=True)
    assert result["passed"] and result["scope"] == "configuration_only"
    assert statuses(result)["database"] == "skipped"
    assert "generation" in result["not_verified"][0]
    assert "secret-sentinel" not in json.dumps(result)
    configured.demo_auth = True
    configured.registration_enabled = True
    configured.secure_cookies = False
    configured.openai_api_key = ""
    result = preflight.report(configured, "openai", offline=True)
    assert not result["passed"]
    assert all(
        statuses(result)[key] == "fail"
        for key in ["guest_access", "public_registration", "secure_cookies", "provider_config"]
    )


@pytest.mark.parametrize(
    "origin",
    [
        "http://studio.example.com",
        "https://localhost",
        "https://127.0.0.1",
        "https://127.1",
        "https://0177.0.0.1",
        "https://127.0.0.0x1",
        "https://[::1]",
        "https://studio.example.com/",
        "https://studio.example.com?",
        "https://studio.example.com:443",
        "https://Studio.example.com",
        "https://@studio.example.com",
        "https://studio.example.com/path",
        "https://user:secret-sentinel@studio.example.com",
        "https://studio.example.com?token=secret-sentinel",
        "https://studio.example.com#token",
        "https://studio.example.com:bad",
        "https://bad..example.com",
        "https://service.internal",
    ],
)
def test_origin_requires_exact_public_https_syntax(configured, origin):
    configured.frontend_origin = origin
    result = preflight.report(configured, "openai", offline=True)
    assert statuses(result)["frontend_origin"] == "fail"
    assert "secret-sentinel" not in json.dumps(result)


def test_provider_selection_and_connection_validation(configured):
    assert statuses(preflight.report(configured, "gemini", True))["provider_config"] == "fail"
    assert statuses(preflight.report(configured, "ollama", True))["provider_config"] == "pass"
    configured.database_url = "sqlite:///local.db"
    configured.checkpoint_url = ""
    configured.redis_url = "not a URL containing secret-sentinel"
    result = preflight.report(configured, "openai")
    assert not result["passed"]
    assert all(statuses(result)[key] == "fail" for key in ["database_config", "checkpoint_config", "queue_config"])
    assert all(statuses(result)[key] == "skipped" for key in ["database", "checkpoints", "redis"])


def test_probe_errors_are_redacted_and_other_checks_continue(configured, monkeypatch):
    def failure(*args):
        raise RuntimeError(configured.database_url)

    monkeypatch.setattr(preflight, "database_checks", failure)
    monkeypatch.setattr(preflight, "checkpoint_checks", lambda _: [preflight.check("checkpoints", True, "Checked", "")])
    monkeypatch.setattr(preflight, "queue_checks", lambda _: [preflight.check("redis", True, "Checked", "")])
    result = preflight.report(configured, "openai")
    assert statuses(result)["database"] == "fail"
    assert statuses(result)["checkpoints"] == statuses(result)["redis"] == "pass"
    assert "secret-sentinel" not in json.dumps(result)


@pytest.mark.parametrize(
    "revisions, expected", [(["0004"], "pass"), (["0003"], "fail"), ([], "fail"), (["old"], "fail")]
)
def test_database_probe_checks_migration_without_writes(configured, monkeypatch, revisions, expected):
    import sqlalchemy

    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalars.return_value = revisions
    create = MagicMock(return_value=engine)
    monkeypatch.setattr(sqlalchemy, "create_engine", create)
    result = preflight.database_checks(configured)
    assert result[0]["status"] == "pass" and result[1]["status"] == expected
    assert "default_transaction_read_only=on" in create.call_args.kwargs["connect_args"]["options"]
    assert [str(call.args[0]) for call in connection.execute.call_args_list] == [
        "SELECT 1",
        "SELECT version_num FROM alembic_version",
    ]
    engine.dispose.assert_called_once()


@pytest.mark.parametrize(
    "tables, expected",
    [(("checkpoints", "checkpoint_blobs", "checkpoint_writes"), "pass"), ((None, None, None), "fail")],
)
def test_checkpoint_probe_only_reads_tables(configured, monkeypatch, tables, expected):
    import psycopg

    connect = MagicMock()
    cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = tables
    monkeypatch.setattr(psycopg, "connect", connect)
    assert preflight.checkpoint_checks(configured)[0]["status"] == expected
    assert "default_transaction_read_only=on" in connect.call_args.kwargs["options"]
    assert cursor.execute.call_args.args[0].startswith("SELECT to_regclass")


@pytest.mark.parametrize(
    "state, queue, age, ttl, expected",
    [
        ("idle", "contentforge", 400, 20, True),
        ("busy", "contentforge", 30, 100, True),
        ("idle", "other", 5, 20, False),
        ("suspended", "contentforge", 5, 20, False),
        ("idle", "contentforge", 451, 20, False),
        ("idle", "contentforge", 5, -2, False),
        ("idle", "contentforge", -60, 20, False),
    ],
)
def test_worker_must_be_active_on_correct_queue(state, queue, age, ttl, expected):
    current = datetime.now(timezone.utc)
    data = {"state": state, "queues": queue, "last_heartbeat": (current - timedelta(seconds=age)).isoformat()}
    assert preflight.active_worker(data, ttl, current) == expected
    assert not preflight.active_worker({}, ttl, current)


def test_redis_probe_reads_registrations_without_cleaning_them(configured, monkeypatch):
    from redis import Redis

    class ReadOnlyRedis:
        def ping(self):
            return True

        def smembers(self, key):
            assert key == "rq:workers:contentforge"
            return ["rq:worker:stale", "rq:worker:live"]

        def hgetall(self, key):
            return (
                {}
                if key.endswith("stale")
                else {
                    "state": "idle",
                    "queues": "contentforge",
                    "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                }
            )

        def ttl(self, key):
            return 30

        def close(self):
            pass

    monkeypatch.setattr(Redis, "from_url", lambda *args, **kwargs: ReadOnlyRedis())
    result = preflight.queue_checks(configured)
    assert [item["status"] for item in result] == ["pass", "pass"]


def test_connection_exceptions_do_not_disclose_secrets(configured, monkeypatch):
    import sqlalchemy
    import psycopg
    from redis import Redis

    def fail(*args, **kwargs):
        raise RuntimeError("secret-sentinel")

    monkeypatch.setattr(sqlalchemy, "create_engine", fail)
    monkeypatch.setattr(psycopg, "connect", fail)
    monkeypatch.setattr(Redis, "from_url", fail)
    result = preflight.report(configured, "openai")
    assert not result["passed"]
    assert all(statuses(result)[key] == "fail" for key in ["database", "checkpoints", "redis"])
    assert "secret-sentinel" not in json.dumps(result)


def test_cli_exit_codes_and_json(configured, monkeypatch, capsys):
    from app import config

    monkeypatch.setattr(config, "settings", configured)
    assert preflight.main(["--provider", "openai", "--offline", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["passed"] and result["scope"] == "configuration_only"
    configured.secure_cookies = False
    assert preflight.main(["--provider", "openai", "--offline", "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert not result["passed"]


def test_invalid_environment_is_redacted_before_settings_load():
    result = subprocess.run(
        [sys.executable, "-m", "app.preflight", "--provider", "openai", "--offline", "--json"],
        env={**os.environ, "SECURE_COOKIES": "secret-sentinel"},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 1
    assert not json.loads(result.stdout)["passed"]
    assert "secret-sentinel" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
