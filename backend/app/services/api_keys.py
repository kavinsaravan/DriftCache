"""Generate and verify high-entropy project API keys."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.project import Project, ProjectAPIKey


KEY_PREFIX = "dc_live_"
LOOKUP_PREFIX_LENGTH = 16


@dataclass(frozen=True)
class AuthContext:
    """Identity derived from a verified credential."""

    tenant_id: str
    project_id: str | None = None
    api_key_id: str | None = None
    is_admin: bool = False
    is_metrics_only: bool = False


def hash_api_key(api_key: str) -> str:
    """Return a deterministic hash; API keys contain enough entropy for SHA-256 storage."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    """Generate a credential that is shown to its owner only once."""
    return f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"


def create_project_with_key(
    session: Session,
    name: str,
    key_name: str = "default",
) -> tuple[Project, ProjectAPIKey, str]:
    """Create an isolated project and its first API key."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name=name,
        tenant_id=f"project:{project_id}",
    )
    raw_key = generate_api_key()
    api_key = ProjectAPIKey(
        id=str(uuid.uuid4()),
        project=project,
        name=key_name,
        key_prefix=raw_key[:LOOKUP_PREFIX_LENGTH],
        key_hash=hash_api_key(raw_key),
    )
    session.add(project)
    session.add(api_key)
    session.commit()
    session.refresh(project)
    session.refresh(api_key)
    return project, api_key, raw_key


def create_project_key(
    session: Session,
    project: Project,
    name: str,
) -> tuple[ProjectAPIKey, str]:
    """Add another credential to an existing project."""
    raw_key = generate_api_key()
    api_key = ProjectAPIKey(
        id=str(uuid.uuid4()),
        project_id=project.id,
        name=name,
        key_prefix=raw_key[:LOOKUP_PREFIX_LENGTH],
        key_hash=hash_api_key(raw_key),
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    return api_key, raw_key


def authenticate_project_key(session: Session, raw_key: str) -> AuthContext | None:
    """Resolve an active project key without storing or logging its plaintext value."""
    if not raw_key.startswith(KEY_PREFIX):
        return None

    candidates = (
        session.query(ProjectAPIKey)
        .join(Project)
        .filter(
            ProjectAPIKey.key_prefix == raw_key[:LOOKUP_PREFIX_LENGTH],
            ProjectAPIKey.is_active.is_(True),
            Project.is_active.is_(True),
        )
        .all()
    )
    candidate_hash = hash_api_key(raw_key)
    api_key = next(
        (item for item in candidates if secrets.compare_digest(item.key_hash, candidate_hash)),
        None,
    )
    if api_key is None:
        return None

    api_key.last_used_at = datetime.now(timezone.utc)
    session.commit()
    return AuthContext(
        tenant_id=api_key.project.tenant_id,
        project_id=api_key.project_id,
        api_key_id=api_key.id,
    )
