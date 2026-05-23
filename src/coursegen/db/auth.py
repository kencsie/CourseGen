"""User registration / password / session-token helpers.

Read/write is gated at the UI entry point: app shows a login screen until
session_state.authenticated is True. Tokens are stored in browser localStorage
(same mechanism as Phase 1 API keys) and resolved against user_sessions table
on app startup.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from sqlalchemy.orm import Session

from coursegen.db.models import User, UserSession

EXAMPLE_USER_ID = "example"
SESSION_LIFETIME_DAYS = 30


def user_exists(session: Session, user_id: str) -> bool:
    return (
        session.query(User).filter(User.user_id == user_id).first() is not None
    )


def register_user(session: Session, user_id: str, password: str) -> None:
    """Create a new user. Raises ValueError if user already exists or reserved."""
    if user_id == EXAMPLE_USER_ID:
        raise ValueError("'example' is reserved for the demo user")
    if user_exists(session, user_id):
        raise ValueError(f"user '{user_id}' already exists")
    hash_bytes = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    session.add(
        User(user_id=user_id, password_hash=hash_bytes.decode("utf-8"))
    )


def verify_password(session: Session, user_id: str, password: str) -> bool:
    user = session.query(User).filter(User.user_id == user_id).first()
    if not user:
        return False
    return bcrypt.checkpw(
        password.encode("utf-8"), user.password_hash.encode("utf-8")
    )


def create_session(session: Session, user_id: str) -> str:
    """Issue a new session token, persist it, return the token string."""
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(days=SESSION_LIFETIME_DAYS)
    session.add(UserSession(token=token, user_id=user_id, expires_at=expires))
    return token


def resolve_session(session: Session, token: str) -> str | None:
    """Return the user_id for a valid, unexpired token; None otherwise.

    Lazily removes expired rows on lookup — no separate cleanup job needed
    until the table grows large enough to warrant one.
    """
    if not token:
        return None
    row = session.query(UserSession).filter(UserSession.token == token).first()
    if not row:
        return None
    now = datetime.now(UTC)
    expires = row.expires_at
    # Postgres returns timezone-aware; SQLite returns naive — normalize before compare
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < now:
        session.delete(row)
        return None
    return row.user_id


def revoke_session(session: Session, token: str) -> None:
    """Delete a session token (logout). No-op if token doesn't exist."""
    if not token:
        return
    session.query(UserSession).filter(UserSession.token == token).delete()
