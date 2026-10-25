import getpass
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError

from app import create_account as provision
from app.auth import check_password, create_account
from app.config import settings
from app.db import Session, SessionToken, User, Workspace
from app.schemas import Credentials

EMAIL = "controlled@example.com"
PASSWORD = "private-provision-password-2026"


def counts():
    with Session() as db:
        return tuple(db.scalar(select(func.count()).select_from(model)) for model in (User, Workspace, SessionToken))


def terminal(monkeypatch, passwords=(PASSWORD, PASSWORD)):
    monkeypatch.setattr(provision.sys.stdin, "isatty", lambda: True)
    inputs = iter(passwords)
    monkeypatch.setattr(provision.getpass, "getpass", lambda prompt: next(inputs))


def test_closed_registration_rejects_direct_requests_without_writes_or_session_changes(client, monkeypatch):
    original = client.get("/api/me").json()
    before = counts()
    monkeypatch.setattr(settings, "registration_enabled", False)
    monkeypatch.setattr(settings, "demo_auth", False)
    assert client.get("/api/auth/options").json()["registration"] is False
    assert client.get("/api/auth/options").json()["demo"] is False
    for email in [EMAIL, original["email"]]:
        result = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
        assert result.status_code == 403
        assert "registration is closed" in result.json()["detail"]
        assert "set-cookie" not in result.headers
    assert client.post("/api/auth/demo").status_code == 403
    assert counts() == before
    assert client.get("/api/me").json() == original


def test_operator_account_can_sign_in_while_closed_without_automatic_verification(client, monkeypatch, capsys):
    monkeypatch.setattr(settings, "registration_enabled", False)
    before = counts()
    terminal(monkeypatch)
    assert provision.main(["--email", EMAIL.upper(), "--name", "New creator"]) == 0
    assert PASSWORD not in capsys.readouterr().out
    assert counts() == (before[0] + 1, before[1] + 1, before[2])
    with Session() as db:
        user = db.scalar(select(User).where(User.email == EMAIL))
        assert user.email_verified_at is None
        assert user.password_hash != PASSWORD and check_password(PASSWORD, user.password_hash)
        workspace = db.scalar(select(Workspace).where(Workspace.owner_id == user.id))
        assert workspace.name == "New creator’s workspace"
    assert client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 200
    assert client.get("/api/me").json()["workspace_id"] == workspace.id


def test_duplicate_operator_account_preserves_credentials_workspace_and_session(client, monkeypatch, capsys):
    assert client.post("/api/auth/register", json={"email": EMAIL, "password": PASSWORD}).status_code == 200
    original = client.get("/api/me").json()
    before = counts()
    terminal(monkeypatch, ("different-password-123",) * 2)
    assert provision.main(["--email", EMAIL.upper()]) == 1
    assert "Existing accounts were preserved" in capsys.readouterr().out
    assert counts() == before and client.get("/api/me").json() == original
    assert client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 200


@pytest.mark.parametrize(
    "email,name,passwords",
    [
        (EMAIL, "Creator", (PASSWORD, "different")),
        (EMAIL, "Creator", ("short", "short")),
        ("invalid", "Creator", (PASSWORD, PASSWORD)),
        (EMAIL, "", (PASSWORD, PASSWORD)),
    ],
)
def test_invalid_operator_input_never_writes_or_discloses_password(client, monkeypatch, capsys, email, name, passwords):
    before = counts()
    terminal(monkeypatch, passwords)
    assert provision.main(["--email", email, "--name", name]) == 1
    assert counts() == before
    output = capsys.readouterr().out
    assert all(secret not in output for secret in passwords)


def test_noninteractive_input_is_rejected_without_reading_password(client, monkeypatch, capsys):
    before = counts()
    monkeypatch.setattr(provision.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(provision.getpass, "getpass", lambda prompt: pytest.fail("Read noninteractive input"))
    assert provision.main(["--email", EMAIL]) == 1
    assert "interactive terminal is required" in capsys.readouterr().out
    assert counts() == before


@pytest.mark.parametrize("error", [EOFError(), KeyboardInterrupt(), getpass.GetPassWarning("echo unsafe")])
def test_unavailable_secure_input_aborts_without_writes(client, monkeypatch, capsys, error):
    before = counts()
    terminal(monkeypatch)

    def fail(prompt):
        raise error

    monkeypatch.setattr(provision.getpass, "getpass", fail)
    assert provision.main(["--email", EMAIL]) == 1
    assert "secure password input is required" in capsys.readouterr().out
    assert counts() == before


def test_database_errors_are_redacted(client, monkeypatch, capsys):
    terminal(monkeypatch)

    def fail(credentials):
        raise OperationalError("secret-database-host", {"password": PASSWORD}, RuntimeError("secret-connection"))

    monkeypatch.setattr(provision, "create_account", fail)
    assert provision.main(["--email", EMAIL]) == 1
    output = capsys.readouterr().out
    assert "Check database access" in output
    assert not any(secret in output for secret in [PASSWORD, "secret-database-host", "secret-connection"])


def test_concurrent_provisioning_has_one_account_and_one_workspace(client):
    before = counts()

    def create(_):
        try:
            return create_account(Credentials(email=EMAIL, password=PASSWORD))
        except IntegrityError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, range(2)))
    assert len([result for result in results if result]) == 1
    assert counts() == (before[0] + 1, before[1] + 1, before[2])


def test_registration_can_be_reopened_and_demo_policy_is_independent(client, monkeypatch):
    monkeypatch.setattr(settings, "registration_enabled", False)
    assert client.post("/api/auth/demo").status_code == 200
    monkeypatch.setattr(settings, "registration_enabled", True)
    monkeypatch.setattr(settings, "demo_auth", False)
    result = client.post("/api/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert result.status_code == 200
    assert client.get("/api/me").json()["email"] == EMAIL
    assert client.post("/api/auth/demo").status_code == 403
