"""
Minimal test to verify imports and basic setup work
"""
import pytest


def test_imports():
    """Test that all required modules can be imported"""
    from app.cache.service import CacheService
    from app.models.schemas import Message
    from app.core.config import settings
    assert True


def test_settings_loaded():
    """Test that settings are loaded correctly"""
    from app.core.config import settings
    assert settings.PROJECT_NAME == "DriftCache"
    assert settings.CACHE_TTL_SECONDS > 0


@pytest.mark.asyncio
async def test_cache_service_init():
    """Test that CacheService can be initialized"""
    from app.cache.service import CacheService
    cache_service = CacheService()
    assert cache_service is not None

    # Check if redis connection works
    if cache_service.redis_store is None:
        from app.cache.redis_store import get_redis_store
        cache_service.redis_store = await get_redis_store()

    assert cache_service.redis_store is not None
