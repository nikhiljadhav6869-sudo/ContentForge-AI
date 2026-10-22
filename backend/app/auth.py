import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Cookie, HTTPException
from sqlalchemy import select
from .config import settings
from .db import Session, SessionToken, User, Workspace


def hash_password(password):
    salt = secrets.token_bytes(16)
    result = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + ":" + result.hex()


def check_password(password, stored):
    try:
        salt, expected = stored.split(":")
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(actual.hex(), expected)
    except ValueError:
        return False


def issue_session(response, user_id):
    token = secrets.token_urlsafe(32)
    with Session.begin() as db:
        db.add(
            SessionToken(
                user_id=user_id,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                expires_at=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            )
        )
    response.set_cookie(
        "cf_session", token, httponly=True, secure=settings.secure_cookies, samesite="lax", max_age=604800, path="/"
    )


def identity(cf_session: str | None = Cookie(default=None)):
    if not cf_session:
        raise HTTPException(401, "Please sign in.")
    with Session() as db:
        session = db.scalar(
            select(SessionToken).where(SessionToken.token_hash == hashlib.sha256(cf_session.encode()).hexdigest())
        )
        if not session or datetime.fromisoformat(session.expires_at) < datetime.now(timezone.utc):
            raise HTTPException(401, "Session expired. Please sign in.")
        user = db.get(User, session.user_id)
        workspace = db.scalar(select(Workspace).where(Workspace.owner_id == user.id))
        return {
            "user_id": user.id,
            "workspace_id": workspace.id,
            "name": user.name,
            "email": user.email,
            "workspace": workspace.name,
        }
