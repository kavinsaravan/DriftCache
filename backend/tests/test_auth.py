"""Authentication behavior for full-access and read-only API keys."""

import pytest
from fastapi import HTTPException

from app.core import auth


@pytest.mark.asyncio
async def test_auth_is_bypassed_only_when_explicitly_disabled(monkeypatch):
    monkeypatch.setattr(auth.settings, "REQUIRE_API_KEY", False)

    context = await auth.verify_api_key(x_api_key=None, bearer=None)
    assert context.tenant_id == "default"
    assert context.is_admin is True


@pytest.mark.asyncio
async def test_missing_api_key_is_rejected(monkeypatch):
    monkeypatch.setattr(auth.settings, "REQUIRE_API_KEY", True)
    monkeypatch.setattr(auth.settings, "API_KEY", "server-secret")

    with pytest.raises(HTTPException) as exc_info:
        await auth.verify_api_key(x_api_key=None, bearer=None)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_full_access_key_accepts_header_value(monkeypatch):
    monkeypatch.setattr(auth.settings, "REQUIRE_API_KEY", True)
    monkeypatch.setattr(auth.settings, "API_KEY", "server-secret")

    context = await auth.verify_api_key(x_api_key="server-secret", bearer=None)
    assert context.tenant_id == "default"
    assert context.is_admin is True


@pytest.mark.asyncio
async def test_metrics_endpoint_accepts_read_only_key(monkeypatch):
    monkeypatch.setattr(auth.settings, "REQUIRE_API_KEY", True)
    monkeypatch.setattr(auth.settings, "API_KEY", "server-secret")
    monkeypatch.setattr(auth.settings, "METRICS_API_KEY", "metrics-secret")

    context = await auth.verify_metrics_key(x_api_key="metrics-secret", bearer=None)
    assert context.tenant_id == "default"
    assert context.is_metrics_only is True


@pytest.mark.asyncio
async def test_invalid_key_is_rejected(monkeypatch):
    monkeypatch.setattr(auth.settings, "REQUIRE_API_KEY", True)
    monkeypatch.setattr(auth.settings, "API_KEY", "server-secret")
    monkeypatch.setattr(auth, "_project_context", lambda _: None)

    with pytest.raises(HTTPException) as exc_info:
        await auth.verify_api_key(x_api_key="wrong-secret", bearer=None)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_project_key_uses_its_project_tenant(monkeypatch):
    monkeypatch.setattr(auth.settings, "REQUIRE_API_KEY", True)
    monkeypatch.setattr(auth.settings, "API_KEY", "server-secret")
    expected = auth.AuthContext(
        tenant_id="project:123",
        project_id="123",
        api_key_id="key-123",
    )
    monkeypatch.setattr(auth, "_project_context", lambda _: expected)

    context = await auth.verify_api_key(x_api_key="dc_live_project-key", bearer=None)

    assert context == expected


@pytest.mark.asyncio
async def test_project_key_does_not_gain_unscoped_metrics_access(monkeypatch):
    monkeypatch.setattr(auth.settings, "REQUIRE_API_KEY", True)
    monkeypatch.setattr(auth.settings, "API_KEY", "server-secret")
    monkeypatch.setattr(auth.settings, "METRICS_API_KEY", "metrics-secret")

    with pytest.raises(HTTPException) as exc_info:
        await auth.verify_metrics_key(x_api_key="dc_live_project-key", bearer=None)

    assert exc_info.value.status_code == 401
