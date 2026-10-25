"""Single-use recovery links. No tokens or SMTP errors are logged or returned."""

import hashlib
import logging
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.headerregistry import Address
from email.errors import HeaderParseError
from email.message import EmailMessage
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy import delete, select, update

from .auth import hash_password
from .config import settings
from .db import PasswordReset, Session, SessionToken, User
from .preflight import web_url

logger = logging.getLogger(__name__)
RESET_MESSAGE = "If an account matches that address, a reset link will arrive shortly. Check your spam folder too."


def available():
    try:
        origin = urlsplit(settings.frontend_origin)
        host = f"[{origin.hostname}]" if origin.hostname == "::1" else origin.hostname
        port = f":{origin.port}" if origin.port not in (None, 80) else ""
        local = (
            origin.scheme == "http"
            and origin.hostname in {"localhost", "127.0.0.1", "::1"}
            and origin.port != 0
            and settings.frontend_origin == f"http://{host}{port}"
        )
        sender = Address(addr_spec=settings.smtp_from)
        return bool(
            settings.smtp_host
            and sender.domain
            and sender.username
            and 0 < settings.smtp_port < 65536
            and (bool(settings.smtp_username) == bool(settings.smtp_password))
            and (local or web_url(settings.frontend_origin, public_origin=True))
        )
    except (ValueError, HeaderParseError):
        return False


def deliver(email, token):
    message = EmailMessage()
    message["From"] = Address(addr_spec=settings.smtp_from)
    message["To"] = Address(addr_spec=email)
    message["Subject"] = "Reset your ContentForge AI password"
    # A fragment keeps the bearer token out of HTTP request URLs and access logs.
    link = settings.frontend_origin + "/reset-password#token=" + token
    message.set_content(
        "A password reset was requested for your ContentForge AI account.\n\n"
        + link
        + "\n\nThis link expires in 30 minutes and can be used once. "
        "Only the most recently requested link works.\n"
        "If you did not request this, you can ignore this email. Your password has not changed.\n"
    )
    send_email(message, email)


def send_email(message, email):
    """Shared verified-TLS transport for account emails."""
    context = ssl.create_default_context()
    if settings.smtp_security == "ssl":
        connection = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10, context=context)
    else:
        connection = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
    with connection as smtp:
        if settings.smtp_security == "starttls":
            smtp.starttls(context=context)
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message, from_addr=settings.smtp_from, to_addrs=[email])


def request_reset(email):
    """Run after the uniform HTTP response; delivery remains best effort."""
    token_hash = None
    try:
        current = datetime.now(timezone.utc)
        with Session.begin() as db:
            # Lock the account before inspecting/updating its single recovery row.
            user_id = db.scalar(
                update(User).where(User.email == email).values(password_hash=User.password_hash).returning(User.id)
            )
            if not user_id:
                return
            row = db.get(PasswordReset, user_id)
            if row and datetime.fromisoformat(row.requested_at) > current - timedelta(seconds=60):
                return
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            if row is None:
                row = PasswordReset(user_id=user_id)
                db.add(row)
            row.token_hash = token_hash
            row.requested_at = current.isoformat()
            row.expires_at = (current + timedelta(minutes=30)).isoformat()
        deliver(email, token)
    except Exception:
        # Keep the cooldown, but invalidate only the link whose delivery failed.
        if token_hash:
            try:
                with Session.begin() as db:
                    db.execute(
                        update(PasswordReset)
                        .where(PasswordReset.token_hash == token_hash)
                        .values(expires_at=datetime.now(timezone.utc).isoformat())
                    )
            except Exception:
                logger.warning("Password recovery cleanup could not complete.")
        logger.warning("Password recovery delivery could not complete.")


def confirm_reset(token, password):
    digest = hashlib.sha256(token.encode()).hexdigest()
    encoded = hash_password(password)
    with Session.begin() as db:
        # The write locks the user before consuming the token, so only one reset
        # wins and session issuance cannot race past revocation.
        user_id = db.scalar(
            update(User)
            .where(
                User.id
                == select(PasswordReset.user_id)
                .where(
                    PasswordReset.token_hash == digest,
                    PasswordReset.expires_at > datetime.now(timezone.utc).isoformat(),
                )
                .scalar_subquery()
            )
            .values(password_hash=User.password_hash)
            .returning(User.id)
        )
        if not user_id:
            raise HTTPException(400, "This reset link is invalid or expired. Request a new link.")
        consumed = db.execute(
            delete(PasswordReset).where(
                PasswordReset.user_id == user_id,
                PasswordReset.token_hash == digest,
                PasswordReset.expires_at > datetime.now(timezone.utc).isoformat(),
            )
        ).rowcount
        if not consumed:
            raise HTTPException(400, "This reset link is invalid or expired. Request a new link.")
        db.execute(update(User).where(User.id == user_id).values(password_hash=encoded))
        db.execute(delete(SessionToken).where(SessionToken.user_id == user_id))
