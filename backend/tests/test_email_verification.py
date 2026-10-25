import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import email_verification as verification, password_recovery
from app.config import settings
from app.db import EmailVerification, Session, User
from app.main import app

EMAIL = "verification@example.com"


@pytest.fixture
def mailbox(client, monkeypatch):
    monkeypatch.setattr(password_recovery, "available", lambda: True)
    sent = []
    monkeypatch.setattr(verification, "deliver", lambda email, token: sent.append((email, token)))
    assert (
        client.post("/api/auth/register", json={"email": EMAIL, "password": "original-password-123"}).status_code == 200
    )
    return sent


def request(client, mailbox):
    result = client.post("/api/auth/email-verification/request")
    assert result.status_code == 202
    return mailbox[-1][1]


def test_complete_verification_preserves_session_and_workspace(client, mailbox):
    before = client.get("/api/me").json()
    assert client.get("/api/auth/email-verification").json()["verified_at"] is None
    token = request(client, mailbox)
    with Session() as db:
        row = db.scalar(select(EmailVerification))
        assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert token not in str(row.__dict__)
        assert row.email == EMAIL
    result = client.post("/api/auth/email-verification/confirm", json={"token": token})
    assert result.status_code == 200
    assert client.get("/api/me").json() == before
    status = client.get("/api/auth/email-verification").json()
    assert status["verified_at"] and status["email"] == EMAIL
    assert token not in str(status)
    assert client.post("/api/auth/email-verification/confirm", json={"token": token}).status_code == 400
    assert client.post("/api/auth/email-verification/request").status_code == 202
    assert len(mailbox) == 1


def test_authentication_and_account_binding(client, mailbox):
    token = request(client, mailbox)
    other = TestClient(app)
    assert other.get("/api/auth/email-verification").status_code == 401
    assert other.post("/api/auth/email-verification/request").status_code == 401
    assert other.post("/api/auth/email-verification/confirm", json={"token": token}).status_code == 401
    other.post("/api/auth/register", json={"email": "other@example.com", "password": "password-for-other"})
    assert other.post("/api/auth/email-verification/confirm", json={"token": token}).status_code == 400
    assert client.post("/api/auth/email-verification/confirm", json={"token": token}).status_code == 200
    assert other.get("/api/auth/email-verification").json()["verified_at"] is None


def test_recipient_is_derived_from_session_and_cooldown_persists(client, mailbox):
    result = client.post(
        "/api/auth/email-verification/request", json={"email": "attacker@example.com", "user_id": "other"}
    )
    assert result.status_code == 202
    assert mailbox[0][0] == EMAIL
    request(client, mailbox)
    assert len(mailbox) == 1
    old = mailbox[0][1]
    with Session.begin() as db:
        db.scalar(select(EmailVerification)).requested_at = (
            datetime.now(timezone.utc) - timedelta(minutes=2)
        ).isoformat()
    new = request(client, mailbox)
    assert new != old
    assert client.post("/api/auth/email-verification/confirm", json={"token": old}).status_code == 400
    assert client.post("/api/auth/email-verification/confirm", json={"token": new}).status_code == 200


@pytest.mark.parametrize("reason", ["expired", "address_changed", "random"])
def test_invalid_links_do_not_verify_accounts(client, mailbox, reason):
    token = request(client, mailbox)
    with Session.begin() as db:
        row = db.scalar(select(EmailVerification))
        if reason == "expired":
            row.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        elif reason == "address_changed":
            db.get(User, row.user_id).email = "changed@example.com"
        else:
            token = "x" * 43
    assert client.post("/api/auth/email-verification/confirm", json={"token": token}).status_code == 400
    assert client.get("/api/auth/email-verification").json()["verified_at"] is None


def test_failed_delivery_invalidates_link_without_leaking_details(client, mailbox, monkeypatch, caplog):
    def fail(email, token):
        mailbox.append((email, token))
        raise RuntimeError("smtp-secret " + token + email)

    monkeypatch.setattr(verification, "deliver", fail)
    token = request(client, mailbox)
    assert client.post("/api/auth/email-verification/confirm", json={"token": token}).status_code == 400
    request(client, mailbox)
    assert len(mailbox) == 1
    assert "delivery could not complete" in caplog.text
    assert all(value not in caplog.text for value in ["smtp-secret", token, EMAIL])


def test_cross_origin_requests_are_blocked(client, mailbox):
    headers = {"Origin": "https://other.example.com"}
    assert client.post("/api/auth/email-verification/request", headers=headers).status_code == 403
    token = request(client, mailbox)
    assert (
        client.post("/api/auth/email-verification/confirm", headers=headers, json={"token": token}).status_code == 403
    )
    assert client.get("/api/auth/email-verification").json()["verified_at"] is None


def test_reset_and_verification_tokens_cannot_be_exchanged(client, mailbox, monkeypatch):
    reset = []
    monkeypatch.setattr(password_recovery, "deliver", lambda email, token: reset.append(token))
    verification_token = request(client, mailbox)
    client.post("/api/auth/forgot-password", json={"email": EMAIL})
    assert client.post("/api/auth/email-verification/confirm", json={"token": reset[0]}).status_code == 400
    assert (
        client.post(
            "/api/auth/reset-password", json={"token": verification_token, "password": "new-password-123"}
        ).status_code
        == 400
    )
    assert client.post("/api/auth/email-verification/confirm", json={"token": verification_token}).status_code == 200


def test_concurrent_confirmation_has_one_winner(client, mailbox):
    token = request(client, mailbox)
    user_id = client.get("/api/me").json()["user_id"]

    def consume(_):
        try:
            verification.confirm(user_id, token)
            return True
        except HTTPException as error:
            assert error.status_code == 400
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(consume, range(2))) == 1


def test_unconfigured_mail_and_demo_addresses_are_explained(client, monkeypatch):
    monkeypatch.setattr(password_recovery, "available", lambda: False)
    assert client.get("/api/auth/email-verification").json()["demo_address"] is True
    assert client.post("/api/auth/email-verification/request").status_code == 400
    client.post("/api/auth/register", json={"email": EMAIL, "password": "password-for-test"})
    result = client.post("/api/auth/email-verification/request")
    assert result.status_code == 503
    assert "unavailable" in result.text


def test_email_uses_fragment_link_and_shared_transport(monkeypatch):
    send = MagicMock()
    monkeypatch.setattr(password_recovery, "send_email", send)
    monkeypatch.setattr(settings, "smtp_from", "noreply@example.com")
    monkeypatch.setattr(settings, "frontend_origin", "https://studio.example.com")
    verification.deliver(EMAIL, "token-sentinel")
    message, recipient = send.call_args.args
    assert recipient == EMAIL
    assert "Verify your" in message["Subject"]
    assert "https://studio.example.com/verify-email#token=token-sentinel" in message.get_content()
    assert "24 hours" in message.get_content()
