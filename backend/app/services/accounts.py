"""Password hashing and opaque, expiring account sessions."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.account import User, UserSession
from app.services.api_keys import hash_api_key

SESSION_PREFIX = "dc_session_"
PASSWORD_ITERATIONS = 600_000
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


# Login uses the same work even when the email does not exist.
DUMMY_HASH = hash_password("not-a-real-user-password")


def verify_password(password: str, encoded: str) -> bool:
    _, iterations, salt, expected = encoded.split("$")
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
    return secrets.compare_digest(actual.hex(), expected)


def create_session(db: Session, user: User) -> str:
    token = SESSION_PREFIX + secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.query(UserSession).filter(UserSession.expires_at <= now).delete()
    db.add(UserSession(token_hash=hash_api_key(token), user_id=user.id, expires_at=now + timedelta(days=7)))
    db.commit()
    return token


def session_user(db: Session, token: str) -> User:
    if not token.startswith(SESSION_PREFIX):
        raise HTTPException(401, "Sign in to your account")
    session = db.query(UserSession).filter(
        UserSession.token_hash == hash_api_key(token),
        UserSession.expires_at > datetime.now(timezone.utc),
    ).first()
    user = db.get(User, session.user_id) if session else None
    if user is None:
        raise HTTPException(401, "Session expired. Please sign in again.")
    return user


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer),
    db: Session = Depends(get_db),
) -> User:
    return session_user(db, credentials.credentials if credentials else "")
