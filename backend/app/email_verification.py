"""Explicit, authenticated email ownership verification."""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from email.headerregistry import Address
from email.message import EmailMessage

from fastapi import HTTPException
from sqlalchemy import delete, select, update

from . import password_recovery as mail
from .config import settings
from .db import EmailVerification, Session, User

logger = logging.getLogger(__name__)
INVALID = "This verification link is invalid, expired, or belongs to another account. Request a new link in Settings."


def status(user_id):
    with Session() as db:
        user = db.get(User, user_id)
        demo_address = user.email.endswith("@contentforge.local")
        return {
            "email": user.email,
            "verified_at": user.email_verified_at,
            "demo_address": demo_address,
            "delivery_available": mail.available(),
        }


def deliver(email, token):
    message = EmailMessage()
    message["From"] = Address(addr_spec=settings.smtp_from)
    message["To"] = Address(addr_spec=email)
    message["Subject"] = "Verify your ContentForge AI email"
    message.set_content(
        "You requested email verification for your ContentForge AI account.\n\n"
        + settings.frontend_origin
        + "/verify-email#token="
        + token
        + "\n\nSign in to the account that requested this link, then confirm verification. "
        "The link expires in 24 hours and can be used once. Only the latest link works.\n"
        "If you did not request this email, ignore it.\n"
    )
    mail.send_email(message, email)


def request_verification(user_id):
    token_hash = None
    try:
        with Session.begin() as db:
            locked = db.scalar(
                update(User).where(User.id == user_id).values(password_hash=User.password_hash).returning(User.id)
            )
            if not locked:
                return
            user = db.get(User, user_id)
            if user.email_verified_at or user.email.endswith("@contentforge.local"):
                return
            current = datetime.now(timezone.utc)
            row = db.get(EmailVerification, user_id)
            if row and datetime.fromisoformat(row.requested_at) > current - timedelta(seconds=60):
                return
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            if row is None:
                row = EmailVerification(user_id=user_id)
                db.add(row)
            row.email, row.token_hash = user.email, token_hash
            row.requested_at = current.isoformat()
            row.expires_at = (current + timedelta(hours=24)).isoformat()
            email = user.email
        deliver(email, token)
    except Exception:
        if token_hash:
            try:
                with Session.begin() as db:
                    db.execute(
                        update(EmailVerification)
                        .where(EmailVerification.token_hash == token_hash)
                        .values(expires_at=datetime.now(timezone.utc).isoformat())
                    )
            except Exception:
                logger.warning("Email verification cleanup could not complete.")
        logger.warning("Email verification delivery could not complete.")


def confirm(user_id, token):
    digest = hashlib.sha256(token.encode()).hexdigest()
    with Session.begin() as db:
        locked = db.scalar(
            update(User).where(User.id == user_id).values(password_hash=User.password_hash).returning(User.id)
        )
        if not locked:
            raise HTTPException(400, INVALID)
        user = db.get(User, user_id)
        consumed = db.execute(
            delete(EmailVerification).where(
                EmailVerification.user_id == user_id,
                EmailVerification.email == user.email,
                EmailVerification.token_hash == digest,
                EmailVerification.expires_at > datetime.now(timezone.utc).isoformat(),
            )
        ).rowcount
        if not consumed:
            raise HTTPException(400, INVALID)
        user.email_verified_at = datetime.now(timezone.utc).isoformat()
