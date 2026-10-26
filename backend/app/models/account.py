"""User identities, revocable sessions and shared authentication throttles."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func
from app.database.base import Base


class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True)
    email = Column(String(254), nullable=False, unique=True, index=True)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserSession(Base):
    __tablename__ = "user_sessions"
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)


class AuthAttempt(Base):
    __tablename__ = "auth_attempts"
    id = Column(Integer, primary_key=True)
    client_hash = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
