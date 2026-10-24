import hashlib
import ssl
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Response
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import password_recovery as recovery
from app.auth import check_password, issue_session
from app.config import settings
from app.db import PasswordReset, Session, SessionToken, User
from app.main import app

EMAIL = "recovery@example.com"
OLD = "original-password-123"
NEW = "replacement-password-456"


@pytest.fixture
def mailbox(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "mail.example.com")
    monkeypatch.setattr(settings, "smtp_from", "noreply@example.com")
    monkeypatch.setattr(settings, "smtp_username", "")
    monkeypatch.setattr(settings, "smtp_password", "")
    monkeypatch.setattr(settings, "frontend_origin", "https://studio.example.com")
    sent = []
    monkeypatch.setattr(recovery, "deliver", lambda email, token: sent.append((email, token)))
    assert client.post("/api/auth/register", json={"email": EMAIL, "password": OLD}).status_code == 200
    return sent


def request_token(client, mailbox):
    assert client.post("/api/auth/forgot-password", json={"email": EMAIL}).status_code == 202
    return mailbox[-1][1]


def test_complete_reset_revokes_sessions_preserves_workspace_and_requires_login(client, mailbox):
    original = client.get("/api/me").json()
    second = TestClient(app)
    second.post("/api/auth/login", json={"email": EMAIL, "password": OLD})
    token = request_token(client, mailbox)
    with Session() as db:
        row = db.scalar(select(PasswordReset))
        assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert token not in str(row.__dict__)
    result = client.post("/api/auth/reset-password", json={"token": token, "password": NEW})
    assert result.status_code == 200
    assert client.get("/api/me").status_code == second.get("/api/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": EMAIL, "password": OLD}).status_code == 401
    assert client.post("/api/auth/login", json={"email": EMAIL, "password": NEW}).status_code == 200
    assert client.get("/api/me").json() == original
    assert client.post("/api/auth/reset-password", json={"token": token, "password": OLD}).status_code == 400


def test_request_is_uniform_normalized_throttled_and_does_not_change_password(client, mailbox):
    known = client.post("/api/auth/forgot-password", json={"email": EMAIL.upper()})
    unknown = client.post("/api/auth/forgot-password", json={"email": "unknown@example.com"})
    repeated = client.post("/api/auth/forgot-password", json={"email": EMAIL})
    assert known.status_code == unknown.status_code == repeated.status_code == 202
    assert known.json() == unknown.json() == repeated.json()
    assert len(mailbox) == 1 and mailbox[0][0] == EMAIL
    assert mailbox[0][1] not in known.text
    assert client.post("/api/auth/login", json={"email": EMAIL, "password": OLD}).status_code == 200


def test_latest_link_supersedes_previous_after_cooldown(client, mailbox):
    old = request_token(client, mailbox)
    with Session.begin() as db:
        row = db.scalar(select(PasswordReset))
        row.requested_at = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    new = request_token(client, mailbox)
    assert new != old
    assert client.post("/api/auth/reset-password", json={"token": old, "password": NEW}).status_code == 400
    assert client.post("/api/auth/reset-password", json={"token": new, "password": NEW}).status_code == 200


def test_expired_invalid_and_cross_origin_attempts_do_not_change_credentials(client, mailbox):
    token = request_token(client, mailbox)
    blocked = client.post(
        "/api/auth/reset-password",
        json={"token": token, "password": NEW},
        headers={"Origin": "https://other.example.com"},
    )
    assert blocked.status_code == 403
    assert (
        client.post(
            "/api/auth/forgot-password", json={"email": EMAIL}, headers={"Origin": "https://other.example.com"}
        ).status_code
        == 403
    )
    assert client.post("/api/auth/reset-password", json={"token": "x" * 43, "password": NEW}).status_code == 400
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "short"}).status_code == 422
    with Session.begin() as db:
        db.scalar(select(PasswordReset)).expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    assert client.post("/api/auth/reset-password", json={"token": token, "password": NEW}).status_code == 400
    assert client.post("/api/auth/login", json={"email": EMAIL, "password": OLD}).status_code == 200


def test_delivery_failure_is_redacted_invalidates_link_and_keeps_cooldown(client, mailbox, monkeypatch, caplog):
    def fail(email, token):
        mailbox.append((email, token))
        raise RuntimeError("smtp-password-secret " + token + " " + email)

    monkeypatch.setattr(recovery, "deliver", fail)
    token = request_token(client, mailbox)
    assert client.post("/api/auth/reset-password", json={"token": token, "password": NEW}).status_code == 400
    request_token(client, mailbox)
    assert len(mailbox) == 1
    assert "delivery could not complete" in caplog.text
    assert all(value not in caplog.text for value in [token, EMAIL, "smtp-password-secret"])


def test_simultaneous_consumption_has_exactly_one_winner(client, mailbox):
    token = request_token(client, mailbox)

    def consume(password):
        try:
            recovery.confirm_reset(token, password)
            return password
        except HTTPException as exc:
            assert exc.status_code == 400
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(consume, [NEW, "another-password-789"]))
    winners = [result for result in results if result]
    assert len(winners) == 1
    with Session() as db:
        user = db.scalar(select(User).where(User.email == EMAIL))
        assert check_password(winners[0], user.password_hash)
        assert db.scalar(select(PasswordReset)) is None
        assert db.scalar(select(SessionToken).where(SessionToken.user_id == user.id)) is None


def test_old_password_login_cannot_issue_a_session_after_reset(client, mailbox):
    with Session() as db:
        user = db.scalar(select(User).where(User.email == EMAIL))
        old_hash, user_id = user.password_hash, user.id
    recovery.confirm_reset(request_token(client, mailbox), NEW)
    with pytest.raises(HTTPException) as error:
        issue_session(Response(), user_id, expected_password_hash=old_hash)
    assert error.value.status_code == 401


def test_other_account_session_and_password_are_preserved(client, mailbox):
    other = TestClient(app)
    other.post("/api/auth/register", json={"email": "other@example.com", "password": OLD})
    recovery.confirm_reset(request_token(client, mailbox), NEW)
    assert other.get("/api/me").status_code == 200
    assert other.post("/api/auth/login", json={"email": "other@example.com", "password": OLD}).status_code == 200


def test_unconfigured_recovery_is_honest_and_never_sends(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(recovery, "deliver", lambda *args: pytest.fail("Unexpected delivery"))
    assert client.get("/api/auth/options").json() == {"password_reset": False}
    result = client.post("/api/auth/forgot-password", json={"email": EMAIL})
    assert result.status_code == 503 and "unavailable" in result.json()["detail"]


@pytest.mark.parametrize("email", ["a@b.com,c@d.com", "a@b.com\nBcc:x@y.com", "x<y>@example.com"])
def test_recovery_rejects_header_and_recipient_injection(client, email):
    assert client.post("/api/auth/forgot-password", json={"email": email}).status_code == 422


@pytest.mark.parametrize("mode", ["starttls", "ssl"])
def test_smtp_uses_verified_tls_before_auth_and_fragment_links(monkeypatch, mode):
    monkeypatch.setattr(settings, "smtp_security", mode)
    monkeypatch.setattr(settings, "smtp_host", "mail.example.com")
    monkeypatch.setattr(settings, "smtp_from", "noreply@example.com")
    monkeypatch.setattr(settings, "smtp_username", "mail-user")
    monkeypatch.setattr(settings, "smtp_password", "secret-sentinel")
    monkeypatch.setattr(settings, "frontend_origin", "https://studio.example.com")
    connection = MagicMock()
    constructor = MagicMock(return_value=connection)
    monkeypatch.setattr(recovery.smtplib, "SMTP_SSL" if mode == "ssl" else "SMTP", constructor)
    recovery.deliver(EMAIL, "token-sentinel")
    smtp = connection.__enter__.return_value
    context = constructor.call_args.kwargs["context"] if mode == "ssl" else smtp.starttls.call_args.kwargs["context"]
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    if mode == "starttls":
        assert [call[0] for call in smtp.method_calls][:2] == ["starttls", "login"]
    message = smtp.send_message.call_args.args[0]
    assert "https://studio.example.com/reset-password#token=token-sentinel" in message.get_content()
    assert "secret-sentinel" not in message.as_string()
    assert smtp.send_message.call_args.kwargs["to_addrs"] == [EMAIL]


@pytest.mark.parametrize(
    "origin",
    [
        "http://public.example.com",
        "https://studio.example.com/path",
        "https://user@studio.example.com",
        "http://localhost:bad",
        "http://@localhost",
        "http://localhost:0",
        "http://localhost?",
    ],
)
def test_misconfigured_origin_disables_recovery(monkeypatch, origin):
    monkeypatch.setattr(settings, "smtp_host", "mail.example.com")
    monkeypatch.setattr(settings, "smtp_from", "noreply@example.com")
    monkeypatch.setattr(settings, "frontend_origin", origin)
    assert recovery.available() is False
