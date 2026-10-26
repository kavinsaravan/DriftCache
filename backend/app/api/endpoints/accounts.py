"""Self-service accounts and ownership-checked application credentials."""
import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.account import AuthAttempt, User, UserSession
from app.models.project import Project, ProjectAPIKey
from app.models.project_schemas import (
    ProjectCreate, ProjectKeyCreate, ProjectCredentialResponse,
    ProjectKeyResponse, ProjectKeySummary, ProjectSummary,
)
from app.services.accounts import (
    DUMMY_HASH, bearer, create_session, current_user, hash_password, verify_password,
)
from app.services.api_keys import create_project_key, create_project_with_key, hash_api_key

router = APIRouter(prefix="/account", tags=["account"])


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


class AccountResponse(BaseModel):
    id: str
    email: str


class SessionResponse(BaseModel):
    token: str
    user: AccountResponse


def throttle(request: Request, db: Session) -> None:
    # Use the trusted ASGI client address, never a client-supplied forwarded header.
    client_hash = hashlib.sha256((request.client.host if request.client else "unknown").encode()).hexdigest()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    db.query(AuthAttempt).filter(AuthAttempt.created_at < cutoff).delete()
    attempts = db.query(AuthAttempt).filter(AuthAttempt.client_hash == client_hash).count()
    if attempts >= 20:
        db.commit()
        raise HTTPException(429, "Too many sign-in attempts. Try again in 15 minutes.", headers={"Retry-After": "900"})
    db.add(AuthAttempt(client_hash=client_hash, created_at=datetime.now(timezone.utc)))
    db.commit()


def session_response(db: Session, user: User, response: Response) -> SessionResponse:
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(token=create_session(db, user), user=AccountResponse(id=user.id, email=user.email))


@router.post("/register", response_model=SessionResponse, status_code=201)
def register(body: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    throttle(request, db)
    user = User(id=str(uuid.uuid4()), email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Unable to create account with this email. Try signing in.")
    return session_response(db, user, response)


@router.post("/login", response_model=SessionResponse)
def login(body: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    throttle(request, db)
    user = db.query(User).filter(User.email == body.email).first()
    valid = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "Incorrect email or password")
    return session_response(db, user, response)


@router.get("/me", response_model=AccountResponse)
def me(user: User = Depends(current_user)):
    return AccountResponse(id=user.id, email=user.email)


@router.post("/logout", status_code=204)
def logout(user: User = Depends(current_user), credentials: HTTPAuthorizationCredentials = Security(bearer), db: Session = Depends(get_db)):
    db.query(UserSession).filter(UserSession.token_hash == hash_api_key(credentials.credentials)).delete()
    db.commit()


def owned_project(db: Session, user: User, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == user.id, Project.is_active.is_(True)).first()
    if project is None:
        raise HTTPException(404, "Application not found")
    return project


@router.get("/projects", response_model=list[ProjectSummary])
def projects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.query(Project).filter(Project.owner_id == user.id, Project.is_active.is_(True)).order_by(Project.created_at).all()


@router.post("/projects", response_model=ProjectCredentialResponse, status_code=201)
def new_project(body: ProjectCreate, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project, key, raw = create_project_with_key(db, body.name, body.key_name, owner_id=user.id)
    response.headers["Cache-Control"] = "no-store"
    return ProjectCredentialResponse(project_id=project.id, project_name=project.name, tenant_id=project.tenant_id,
        api_key_id=key.id, api_key_name=key.name, api_key=raw, created_at=key.created_at)


@router.get("/projects/{project_id}/keys", response_model=list[ProjectKeySummary])
def keys(project_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_project(db, user, project_id)
    return db.query(ProjectAPIKey).filter(ProjectAPIKey.project_id == project_id).order_by(ProjectAPIKey.created_at.desc()).all()


@router.post("/projects/{project_id}/keys", response_model=ProjectKeyResponse, status_code=201)
def new_key(project_id: str, body: ProjectKeyCreate, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = owned_project(db, user, project_id)
    key, raw = create_project_key(db, project, body.name)
    response.headers["Cache-Control"] = "no-store"
    return ProjectKeyResponse(project_id=project.id, api_key_id=key.id, api_key_name=key.name, api_key=raw, created_at=key.created_at)


@router.delete("/projects/{project_id}/keys/{key_id}", status_code=204)
def revoke_key(project_id: str, key_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_project(db, user, project_id)
    key = db.query(ProjectAPIKey).filter(ProjectAPIKey.id == key_id, ProjectAPIKey.project_id == project_id).first()
    if key is None:
        raise HTTPException(404, "Key not found")
    key.is_active = False
    key.revoked_at = datetime.now(timezone.utc)
    db.commit()
