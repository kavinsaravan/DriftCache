"""Project API keys provide isolated tenant identities without storing plaintext."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints.projects import router as projects_router
from app.core import auth
from app.database.base import Base
from app.database.session import get_db
from app.models.project import Project, ProjectAPIKey
from app.services.api_keys import (
    authenticate_project_key,
    create_project_with_key,
    hash_api_key,
)


def test_project_key_is_hashed_and_resolves_tenant():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        project, stored_key, raw_key = create_project_with_key(session, "Example app")

        assert raw_key.startswith("dc_live_")
        assert stored_key.key_hash == hash_api_key(raw_key)
        assert raw_key != stored_key.key_hash

        context = authenticate_project_key(session, raw_key)
        assert context is not None
        assert context.project_id == project.id
        assert context.tenant_id == project.tenant_id
        assert stored_key.last_used_at is not None
    finally:
        session.close()
        engine.dispose()


def test_revoked_project_key_is_rejected():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        _, stored_key, raw_key = create_project_with_key(session, "Example app")
        stored_key.is_active = False
        session.commit()

        assert authenticate_project_key(session, raw_key) is None
    finally:
        session.close()
        engine.dispose()


def test_admin_can_create_project_and_key_is_returned_once(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app = FastAPI()
    app.include_router(projects_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(auth.settings, "REQUIRE_API_KEY", True)
    monkeypatch.setattr(auth.settings, "API_KEY", "admin-secret")

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/projects",
                json={"name": "Support assistant"},
                headers={"Authorization": "Bearer admin-secret"},
            )

        assert response.status_code == 201
        body = response.json()
        assert body["api_key"].startswith("dc_live_")

        with TestClient(app) as client:
            key_list_response = client.get(
                f"/api/v1/projects/{body['project_id']}/keys",
                headers={"Authorization": "Bearer admin-secret"},
            )
        assert key_list_response.status_code == 200
        listed_key = key_list_response.json()[0]
        assert listed_key["key_prefix"] == body["api_key"][:16]
        assert "api_key" not in listed_key
        assert "key_hash" not in listed_key

        with session_factory() as session:
            stored_key = session.query(ProjectAPIKey).one()
            assert stored_key.key_hash == hash_api_key(body["api_key"])
            assert body["api_key"] not in stored_key.key_hash
    finally:
        engine.dispose()
