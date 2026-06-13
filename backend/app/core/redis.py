"""
Redis Connection Manager

Manages Redis client connection and provides shared instance.
"""
import logging
from typing import Optional
import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import RedisError, ConnectionError

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisManager:
    """
    Redis connection manager

    Handles connection lifecycle and provides singleton access
    """

    def __init__(self):
        """Initialize Redis manager"""
        self.client: Optional[Redis] = None
        self._connected: bool = False

    async def connect(self) -> None:
        """
        Connect to Redis server

        Raises:
            ConnectionError: If connection fails
        """
        if self._connected and self.client:
            logger.info("Redis already connected")
            return

        try:
            # Create Redis client
            self.client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50
            )

            # Test connection
            await self.client.ping()

            self._connected = True
            logger.info(
                f"Connected to Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}"
            )

        except ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            raise

        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}")
            self._connected = False
            raise

    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self.client:
            await self.client.aclose()
            self._connected = False
            logger.info("Disconnected from Redis")

    async def health_check(self) -> bool:
        """
        Check Redis connection health

        Returns:
            True if connected and healthy, False otherwise
        """
        if not self.client or not self._connected:
            return False

        try:
            await self.client.ping()
            return True
        except RedisError:
            return False

    def get_client(self) -> Redis:
        """
        Get Redis client

        Returns:
            Redis client instance

        Raises:
            RuntimeError: If not connected
        """
        if not self._connected or not self.client:
            raise RuntimeError(
                "Redis not connected. Call connect() first."
            )

        return self.client

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        return self._connected


# Global Redis manager instance
_redis_manager: Optional[RedisManager] = None


async def get_redis_manager() -> RedisManager:
    """
    Get global Redis manager instance

    Returns:
        RedisManager singleton
    """
    global _redis_manager

    if _redis_manager is None:
        _redis_manager = RedisManager()
        await _redis_manager.connect()

    return _redis_manager


async def get_redis() -> Redis:
    """
    Get Redis client

    Convenience function for dependency injection

    Returns:
        Redis client
    """
    manager = await get_redis_manager()
    return manager.get_client()


async def shutdown_redis() -> None:
    """Shutdown Redis connection"""
    global _redis_manager

    if _redis_manager:
        await _redis_manager.disconnect()
        _redis_manager = None
