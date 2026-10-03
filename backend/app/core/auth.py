"""
API Authentication

OpenAI-compatible API key authentication for DriftCache
Accepts both Authorization: Bearer and X-API-Key headers
"""
import secrets
from typing import Optional
from fastapi import HTTPException, Security, Header
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

# Support both OpenAI-style Bearer tokens and X-API-Key
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    x_api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
) -> str:
    """
    Verify API key from request header

    Accepts both formats for OpenAI compatibility:
    - Authorization: Bearer <api_key>  (OpenAI SDK, LangChain, LlamaIndex)
    - X-API-Key: <api_key>             (Alternative)

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
        return "dev-mode"

    # Check if API key is configured on server
    if not settings.API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API key not configured on server"
        )

    # Extract API key from either header
    provided_key = None
    if bearer and bearer.credentials:
        provided_key = bearer.credentials
    elif x_api_key:
        provided_key = x_api_key

    # Check if API key was provided
    if not provided_key:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Missing API key. Provide Authorization: Bearer <key> or X-API-Key: <key> header.",
                    "type": "authentication_error",
                    "code": "missing_api_key"
                }
            }
        )

    # Verify API key matches (timing-safe comparison)
    if not secrets.compare_digest(provided_key, settings.API_KEY):
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Invalid API key",
                    "type": "authentication_error",
                    "code": "invalid_api_key"
                }
            }
        )

    return provided_key
