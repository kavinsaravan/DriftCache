"""
API Authentication

Simple API key authentication for DriftCache
"""
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from app.core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Verify API key from request header

    Args:
        api_key: API key from X-API-Key header

    Returns:
        The validated API key

    Raises:
        HTTPException: If API key is invalid or missing
    """
    # Skip check if not required (development mode)
    if not settings.REQUIRE_API_KEY:
        return "dev-mode"

    # Check if API key is configured
    if not settings.API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API key not configured on server"
        )

    # Check if API key was provided
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Missing API key. Include X-API-Key header in your request.",
                    "type": "authentication_error",
                    "code": "missing_api_key"
                }
            }
        )

    # Verify API key matches
    if api_key != settings.API_KEY:
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

    return api_key
