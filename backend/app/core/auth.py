"""
API Authentication

OpenAI-compatible API key authentication for DriftCache
Accepts both Authorization: Bearer and X-API-Key headers
"""
import secrets
import logging
from typing import Optional
from fastapi import HTTPException, Security
from fastapi.concurrency import run_in_threadpool
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
from app.database.session import get_db_manager
from app.services.api_keys import AuthContext, KEY_PREFIX, authenticate_project_key


logger = logging.getLogger(__name__)

# Support both OpenAI-style Bearer tokens and X-API-Key
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def _extract_api_key(
    x_api_key: Optional[str],
    bearer: Optional[HTTPAuthorizationCredentials],
) -> Optional[str]:
    if bearer and bearer.credentials:
        return bearer.credentials
    return x_api_key


def _matches(candidate: str, configured: str) -> bool:
    return bool(configured) and secrets.compare_digest(
        candidate.encode("utf-8"),
        configured.encode("utf-8"),
    )


def _invalid_key() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={
            "error": {
                "message": "Invalid API key",
                "type": "authentication_error",
                "code": "invalid_api_key",
            }
        },
    )


def _missing_key() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={
            "error": {
                "message": "Missing API key. Provide Authorization: Bearer <key> or X-API-Key: <key> header.",
                "type": "authentication_error",
                "code": "missing_api_key",
            }
        },
    )


def _project_context(provided_key: str) -> Optional[AuthContext]:
    """Look up a project credential while treating database failures as failed auth."""
    if not provided_key.startswith(KEY_PREFIX):
        return None
    try:
        with get_db_manager().session_scope() as session:
            return authenticate_project_key(session, provided_key)
    except Exception:
        logger.exception("Project API key lookup failed")
        return None


async def verify_api_key(
    x_api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
) -> AuthContext:
    """
    Verify API key from request header

    Accepts both formats for OpenAI compatibility:
    - Authorization: Bearer <api_key>  (OpenAI SDK, LangChain, LlamaIndex)
    - X-API-Key: <api_key>             (Alternative)

    Args:
        x_api_key: API key from X-API-Key header
        bearer: API key from Authorization: Bearer header

    Returns:
        The verified project/tenant identity

    Raises:
        HTTPException: If API key is invalid or missing
    """
    # Skip check if not required (development mode)
    if not settings.REQUIRE_API_KEY:
        return AuthContext(tenant_id="default", is_admin=True)

    provided_key = _extract_api_key(x_api_key, bearer)
    if not provided_key:
        raise _missing_key()

    # Preserve the existing static key as the bootstrap/admin credential and
    # default tenant so existing installations remain compatible.
    if _matches(provided_key, settings.API_KEY):
        return AuthContext(
            tenant_id="default",
            is_admin=True,
        )

    context = await run_in_threadpool(_project_context, provided_key)
    if context is not None:
        return context
    raise _invalid_key()


async def verify_admin_key(
    x_api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> str:
    """Require the bootstrap key for project and credential administration."""
    if not settings.REQUIRE_API_KEY:
        return "dev-mode"
    if not settings.API_KEY:
        raise HTTPException(status_code=500, detail="Administrator API key not configured on server")
    provided_key = _extract_api_key(x_api_key, bearer)
    if not provided_key:
        raise _missing_key()
    if not _matches(provided_key, settings.API_KEY):
        raise HTTPException(status_code=403, detail="Administrator API key required")
    return provided_key


async def verify_metrics_key(
    x_api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
) -> AuthContext:
    """
    Verify API key for metrics/dashboard endpoints (read-only)

    Accepts:
    - Main API_KEY (full access)
    - METRICS_API_KEY (read-only access to the default tenant)
    - Project API keys (read-only access to their own tenant)

    Args:
        x_api_key: API key from X-API-Key header
        bearer: API key from Authorization: Bearer header

    Returns:
        The validated API key

    Raises:
        HTTPException: If API key is invalid or missing
    """
    # Skip check if not required (development mode)
    if not settings.REQUIRE_API_KEY:
        return AuthContext(tenant_id="default", is_admin=True)

    # Extract API key from either header
    provided_key = _extract_api_key(x_api_key, bearer)

    # Check if API key was provided
    if not provided_key:
        raise _missing_key()

    if _matches(provided_key, settings.API_KEY):
        return AuthContext(tenant_id="default", is_admin=True)
    if _matches(provided_key, settings.METRICS_API_KEY):
        return AuthContext(tenant_id="default", is_metrics_only=True)

    context = await run_in_threadpool(_project_context, provided_key)
    if context is not None:
        return context

    raise _invalid_key()
