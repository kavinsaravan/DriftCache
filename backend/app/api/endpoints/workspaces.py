"""Key-based self-service workspaces; names are labels, never identities."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import field_validator
from sqlalchemy.orm import Session
from app.core.model_catalog import integration_configuration
from app.database.session import get_db
from app.models.project import Project, ProjectAPIKey
from app.models.request import Request as RequestRecord
from app.models.project_schemas import (
    ProjectCreate, ProjectCredentialResponse, ProjectKeyCreate, ProjectKeyResponse,
    ProjectKeySummary, ProjectSummary,
)
from app.api.endpoints.accounts import IntegrationConfiguration, throttle
from app.services.accounts import bearer
from app.services.api_keys import (
    AuthContext, authenticate_project_key, create_project_key, create_project_with_key,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceCreate(ProjectCreate):
    @field_validator("name", "key_name", mode="before")
    @classmethod
    def strip_label(cls, value):
        return value.strip() if isinstance(value, str) else value


def workspace_identity(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer),
    db: Session = Depends(get_db),
) -> AuthContext:
    # Always validate a project key, even with development auth bypass enabled.
    context = authenticate_project_key(db, credentials.credentials if credentials else "")
    if context is None:
        raise HTTPException(401, "Connect with a valid workspace API key")
    return context


@router.post("", response_model=ProjectCredentialResponse, status_code=201)
def create_workspace(body: WorkspaceCreate, request: Request, response: Response, db: Session = Depends(get_db)):
    throttle(request, db)
    project, key, raw = create_project_with_key(db, body.name, body.key_name)
    response.headers["Cache-Control"] = "no-store"
    return ProjectCredentialResponse(project_id=project.id, project_name=project.name, tenant_id=project.tenant_id,
        api_key_id=key.id, api_key_name=key.name, api_key=raw, created_at=key.created_at)


@router.get("/current", response_model=ProjectSummary)
def current_workspace(response: Response, identity: AuthContext = Depends(workspace_identity), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return db.get(Project, identity.project_id)


@router.delete("/current/requests")
def clear_requests(identity: AuthContext = Depends(workspace_identity), db: Session = Depends(get_db)):
    """Delete this workspace's request history, preserving cache and aggregate metrics."""
    try:
        deleted = db.query(RequestRecord).filter(
            RequestRecord.tenant_id == identity.tenant_id,
        ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"deleted_requests": deleted}


@router.get("/integration", response_model=IntegrationConfiguration)
def integration(identity: AuthContext = Depends(workspace_identity)):
    return integration_configuration()


@router.get("/current/keys", response_model=list[ProjectKeySummary])
def list_keys(response: Response, identity: AuthContext = Depends(workspace_identity), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return db.query(ProjectAPIKey).filter(ProjectAPIKey.project_id == identity.project_id).order_by(ProjectAPIKey.created_at.desc()).all()


@router.post("/current/keys", response_model=ProjectKeyResponse, status_code=201)
def new_key(body: ProjectKeyCreate, response: Response, identity: AuthContext = Depends(workspace_identity), db: Session = Depends(get_db)):
    project = db.get(Project, identity.project_id)
    key, raw = create_project_key(db, project, body.name)
    response.headers["Cache-Control"] = "no-store"
    return ProjectKeyResponse(project_id=project.id, api_key_id=key.id, api_key_name=key.name, api_key=raw, created_at=key.created_at)


@router.delete("/current/keys/{key_id}", status_code=204)
def revoke_key(key_id: str, identity: AuthContext = Depends(workspace_identity), db: Session = Depends(get_db)):
    key = db.query(ProjectAPIKey).filter(ProjectAPIKey.id == key_id, ProjectAPIKey.project_id == identity.project_id).first()
    if key is None:
        raise HTTPException(404, "Key not found")
    if key.id == identity.api_key_id:
        raise HTTPException(409, "Connect with another key before revoking the key you are using")
    key.is_active = False
    key.revoked_at = datetime.now(timezone.utc)
    db.commit()
