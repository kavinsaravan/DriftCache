"""Projects and their scoped API credentials."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.base import Base


class Project(Base):
    """An isolated DriftCache cache and analytics namespace."""

    __tablename__ = "projects"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    tenant_id = Column(String(100), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    api_keys = relationship(
        "ProjectAPIKey",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ProjectAPIKey(Base):
    """A hashed API credential belonging to one project."""

    __tablename__ = "project_api_keys"

    id = Column(String(36), primary_key=True)
    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False, default="default")
    key_prefix = Column(String(16), nullable=False, index=True)
    key_hash = Column(String(64), unique=True, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="api_keys")
