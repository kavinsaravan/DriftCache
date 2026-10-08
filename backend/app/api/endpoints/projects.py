"""Administrative project and API-key lifecycle endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import verify_admin_key
from app.database.session import get_db
from app.models.project import Project, ProjectAPIKey
from app.models.project_schemas import (
    ProjectCreate,
    ProjectCredentialResponse,
    ProjectKeyCreate,
    ProjectKeyResponse,
    ProjectKeySummary,
    ProjectSummary,
)
from app.services.api_keys import create_project_key, create_project_with_key


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectCredentialResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    request: ProjectCreate,
    _: str = Depends(verify_admin_key),
    db: Session = Depends(get_db),
):
    project, api_key, raw_key = create_project_with_key(
        db,
        name=request.name,
        key_name=request.key_name,
    )
    return ProjectCredentialResponse(
        project_id=project.id,
        project_name=project.name,
        tenant_id=project.tenant_id,
        api_key_id=api_key.id,
        api_key_name=api_key.name,
        api_key=raw_key,
        created_at=api_key.created_at,
    )


@router.get("", response_model=list[ProjectSummary])
def list_projects(
    _: str = Depends(verify_admin_key),
    db: Session = Depends(get_db),
):
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.post("/{project_id}/keys", response_model=ProjectKeyResponse, status_code=status.HTTP_201_CREATED)
def add_project_key(
    project_id: str,
    request: ProjectKeyCreate,
    _: str = Depends(verify_admin_key),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id, Project.is_active.is_(True)).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    api_key, raw_key = create_project_key(db, project=project, name=request.name)
    return ProjectKeyResponse(
        project_id=project.id,
        api_key_id=api_key.id,
        api_key_name=api_key.name,
        api_key=raw_key,
        created_at=api_key.created_at,
    )


@router.get("/{project_id}/keys", response_model=list[ProjectKeySummary])
def list_project_keys(
    project_id: str,
    _: str = Depends(verify_admin_key),
    db: Session = Depends(get_db),
):
    if db.query(Project.id).filter(Project.id == project_id).first() is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return db.query(ProjectAPIKey).filter(
        ProjectAPIKey.project_id == project_id,
    ).order_by(ProjectAPIKey.created_at.desc()).all()


@router.delete("/{project_id}/keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_project_key(
    project_id: str,
    api_key_id: str,
    _: str = Depends(verify_admin_key),
    db: Session = Depends(get_db),
):
    api_key = db.query(ProjectAPIKey).filter(
        ProjectAPIKey.id == api_key_id,
        ProjectAPIKey.project_id == project_id,
    ).first()
    if api_key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key.is_active = False
    api_key.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return None
