"""
Redis Cache Store

Handles all Redis-specific cache operations for the online serving layer.

Redis stores:
1. Cached response text (fast retrieval)
2. Cache metadata (validation)
3. Recent similarity scores (metrics)
4. Hit/miss counters (analytics)
"""
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from redis.asyncio import Redis

from app.models.cache_schemas import CachedResponse, CacheStats
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisStore:
    """
    Redis-based cache store for online serving

    Stores hot cached responses with TTL for fast retrieval
    """

    # Redis key prefixes
    CACHE_RESPONSE_PREFIX = "cache:response:"
    CACHE_METADATA_PREFIX = "cache:metadata:"
    METRICS_HITS_KEY = "metrics:cache_hits"
    METRICS_MISSES_KEY = "metrics:cache_misses"
    METRICS_SIMILARITY_SCORES_KEY = "metrics:recent_similarity_scores"
    STATS_KEY = "cache:stats"

    def __init__(self, redis_client: Redis):
        """
        Initialize Redis store

        Args:
            redis_client: Redis client instance
        """
        self.redis = redis_client
        logger.info("RedisStore initialized")

    async def set_cached_response(
        self,
        cache_id: str,
        response: CachedResponse,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """
        Store a cached response in Redis

        Args:
            cache_id: Unique cache ID
            response: CachedResponse to store
            ttl_seconds: Time-to-live in seconds (defaults to settings)
        """
        ttl = ttl_seconds or settings.CACHE_TTL_SECONDS

        # Store response data
        response_key = self._response_key(cache_id)
        response_data = {
            "cache_id": response.cache_id,
            "response_text": response.response_text,
            "model_name": response.model_name,
            "created_at": response.created_at.isoformat(),
            "expires_at": response.expires_at.isoformat() if response.expires_at else None,
            "cache_hits": response.cache_hits,
            "tenant_id": response.tenant_id,
            "user_id": response.user_id,
        }

        await self.redis.setex(
            response_key,
            ttl,
            json.dumps(response_data)
        )

        # Store metadata separately (lighter weight for lookups)
        metadata_key = self._metadata_key(cache_id)
        metadata = {
            "prompt_text": response.prompt_text,
            "system_prompt": response.system_prompt,
            "model_name": response.model_name,
            "similarity_threshold": settings.SIMILARITY_THRESHOLD,
            "tenant_id": response.tenant_id,
            "ttl_seconds": ttl,
            "request_params": response.request_params,
        }

        await self.redis.setex(
            metadata_key,
            ttl,
            json.dumps(metadata)
        )

        logger.debug(f"Stored cache response: {cache_id[:8]}... (ttl={ttl}s)")

    async def get_cached_response(self, cache_id: str) -> Optional[CachedResponse]:
        """
        Get a cached response from Redis

        Args:
            cache_id: Cache entry ID

        Returns:
            CachedResponse or None if not found/expired
        """
        response_key = self._response_key(cache_id)
        metadata_key = self._metadata_key(cache_id)

        # Get response and metadata
        response_data = await self.redis.get(response_key)
        metadata_data = await self.redis.get(metadata_key)

        if not response_data or not metadata_data:
            logger.debug(f"Cache miss: {cache_id[:8]}... not found in Redis")
            return None

        # Parse JSON
        response_dict = json.loads(response_data)
        metadata_dict = json.loads(metadata_data)

        # Combine into CachedResponse
        cached_response = CachedResponse(
            cache_id=response_dict["cache_id"],
            prompt_text=metadata_dict["prompt_text"],
            system_prompt=metadata_dict.get("system_prompt"),
            response_text=response_dict["response_text"],
            model_name=response_dict["model_name"],
            embedding_vector=[],  # Not needed for retrieval
            created_at=datetime.fromisoformat(response_dict["created_at"]),
            expires_at=datetime.fromisoformat(response_dict["expires_at"]) if response_dict.get("expires_at") else None,
            cache_hits=response_dict.get("cache_hits", 0),
            tenant_id=response_dict.get("tenant_id", "default"),
            user_id=response_dict.get("user_id"),
            request_params=metadata_dict.get("request_params", {}),
        )

        logger.debug(f"Cache hit: {cache_id[:8]}... retrieved from Redis")
        return cached_response

    async def delete_cached_response(self, cache_id: str) -> bool:
        """
        Delete a cached response from Redis

        Args:
            cache_id: Cache entry ID

        Returns:
            True if deleted, False if not found
        """
        response_key = self._response_key(cache_id)
        metadata_key = self._metadata_key(cache_id)

        # Delete both keys
        deleted = await self.redis.delete(response_key, metadata_key)

        if deleted > 0:
            logger.debug(f"Deleted cache entry: {cache_id[:8]}...")
            return True

        return False

    async def increment_cache_hit(self, cache_id: Optional[str] = None) -> None:
        """
        Record a cache hit

        Args:
            cache_id: Optional cache ID to update hit count
        """
        # Increment global hit counter
        await self.redis.incr(self.METRICS_HITS_KEY)

        # Update response hit count if cache_id provided
        if cache_id:
            response_key = self._response_key(cache_id)
            response_data = await self.redis.get(response_key)

            if response_data:
                data = json.loads(response_data)
                data["cache_hits"] = data.get("cache_hits", 0) + 1
                data["last_accessed"] = datetime.utcnow().isoformat()

                # Get TTL and preserve it
                ttl = await self.redis.ttl(response_key)
                if ttl > 0:
                    await self.redis.setex(
                        response_key,
                        ttl,
                        json.dumps(data)
                    )

        logger.debug("Recorded cache hit")

    async def increment_cache_miss(self) -> None:
        """Record a cache miss"""
        await self.redis.incr(self.METRICS_MISSES_KEY)
        logger.debug("Recorded cache miss")

    async def record_similarity_score(self, score: float) -> None:
        """
        Record a similarity score for metrics

        Args:
            score: Similarity score [0, 1]
        """
        # Keep last 1000 similarity scores
        await self.redis.lpush(
            self.METRICS_SIMILARITY_SCORES_KEY,
            str(score)
        )
        await self.redis.ltrim(
            self.METRICS_SIMILARITY_SCORES_KEY,
            0,
            999
        )

    async def get_recent_similarity_scores(self, limit: int = 100) -> List[float]:
        """
        Get recent similarity scores

        Args:
            limit: Maximum number of scores to return

        Returns:
            List of recent similarity scores
        """
        scores = await self.redis.lrange(
            self.METRICS_SIMILARITY_SCORES_KEY,
            0,
            limit - 1
        )
        return [float(s) for s in scores]

    async def get_stats(self) -> CacheStats:
        """
        Get cache statistics from Redis

        Returns:
            CacheStats object
        """
        # Get counters
        hits = await self.redis.get(self.METRICS_HITS_KEY)
        misses = await self.redis.get(self.METRICS_MISSES_KEY)

        cache_hits = int(hits) if hits else 0
        cache_misses = int(misses) if misses else 0

        # Get recent similarity scores for average
        scores = await self.get_recent_similarity_scores(limit=1000)
        avg_similarity = sum(scores) / len(scores) if scores else 0.0

        stats = CacheStats(
            total_requests=cache_hits + cache_misses,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            average_similarity=avg_similarity,
        )

        return stats

    async def clear_all(self) -> None:
        """Clear all cache data"""
        # Find all cache keys
        cursor = 0
        pattern = f"{self.CACHE_RESPONSE_PREFIX}*"

        while True:
            cursor, keys = await self.redis.scan(
                cursor=cursor,
                match=pattern,
                count=100
            )

            if keys:
                await self.redis.delete(*keys)

            if cursor == 0:
                break

        # Clear metadata
        cursor = 0
        pattern = f"{self.CACHE_METADATA_PREFIX}*"

        while True:
            cursor, keys = await self.redis.scan(
                cursor=cursor,
                match=pattern,
                count=100
            )

            if keys:
                await self.redis.delete(*keys)

            if cursor == 0:
                break

        # Clear metrics
        await self.redis.delete(
            self.METRICS_HITS_KEY,
            self.METRICS_MISSES_KEY,
            self.METRICS_SIMILARITY_SCORES_KEY,
            self.STATS_KEY
        )

        logger.info("Cleared all cache data from Redis")

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Redis health

        Returns:
            Health status dict
        """
        try:
            # Test connection
            await self.redis.ping()

            # Get basic stats
            stats = await self.get_stats()

            # Get Redis info
            info = await self.redis.info("stats")

            return {
                "status": "healthy",
                "connected": True,
                "total_requests": stats.total_requests,
                "hit_rate": stats.hit_rate,
                "redis_ops": info.get("total_commands_processed", 0),
            }

        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
            }

    def _response_key(self, cache_id: str) -> str:
        """Generate Redis key for cached response"""
        return f"{self.CACHE_RESPONSE_PREFIX}{cache_id}"

    def _metadata_key(self, cache_id: str) -> str:
        """Generate Redis key for cache metadata"""
        return f"{self.CACHE_METADATA_PREFIX}{cache_id}"

    async def count(self) -> int:
        """
        Count active cached responses

        Returns:
            Number of cached responses
        """
        cursor = 0
        count = 0
        pattern = f"{self.CACHE_RESPONSE_PREFIX}*"

        while True:
            cursor, keys = await self.redis.scan(
                cursor=cursor,
                match=pattern,
                count=100
            )

            count += len(keys)

            if cursor == 0:
                break

        return count

    def __repr__(self) -> str:
        return f"RedisStore(host={settings.REDIS_HOST}, port={settings.REDIS_PORT})"


# Global instance
_redis_store: Optional[RedisStore] = None


async def get_redis_store() -> RedisStore:
    """
    Get global RedisStore instance

    Returns:
        RedisStore singleton
    """
    global _redis_store

    if _redis_store is None:
        from app.core.redis import get_redis
        redis_client = await get_redis()
        _redis_store = RedisStore(redis_client)

    return _redis_store
