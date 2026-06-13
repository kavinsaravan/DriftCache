"""
Cache Service

Orchestrates the complete semantic caching flow:
1. Generate embedding
2. Search FAISS
3. Evaluate match
4. Return cached response or miss
5. Store new responses

Week 3 Update: Now uses Redis for online serving layer
"""
import logging
import time
from typing import Optional, List
from datetime import datetime, timedelta
import uuid

from app.cache.decision import get_decision_engine, CacheDecisionEngine
from app.cache.store import get_cache_store, CacheStore
from app.cache.redis_store import get_redis_store, RedisStore
from app.vectorstore.search import get_search_service, SemanticSearchService
from app.embeddings.service import get_embedding_service, EmbeddingService
from app.models.cache_schemas import (
    CacheDecision,
    CacheDecisionResult,
    CachedResponse,
    CacheConfig,
    CacheRequest,
    CacheStoreRequest,
    CacheKey,
)
from app.models.schemas import Message
from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """
    Main cache service

    Coordinates embedding, search, decision, and storage

    Week 3 Update:
    - Redis for online serving (fast retrieval)
    - Legacy store for fallback
    """

    def __init__(
        self,
        decision_engine: Optional[CacheDecisionEngine] = None,
        cache_store: Optional[CacheStore] = None,
        redis_store: Optional[RedisStore] = None,
        search_service: Optional[SemanticSearchService] = None,
        embedding_service: Optional[EmbeddingService] = None
    ):
        """
        Initialize cache service

        Args:
            decision_engine: Cache decision engine
            cache_store: Cache store (legacy/fallback)
            redis_store: Redis store (online serving)
            search_service: Vector search service
            embedding_service: Embedding service
        """
        self.decision_engine = decision_engine or get_decision_engine()
        self.cache_store = cache_store or get_cache_store()
        self.redis_store = redis_store  # Will be initialized async
        self.search_service = search_service or get_search_service()
        self.embedding_service = embedding_service or get_embedding_service()

        logger.info("CacheService initialized (Redis mode)")

    async def check_cache(
        self,
        messages: List[Message],
        model_name: str,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        config: Optional[CacheConfig] = None
    ) -> CacheDecisionResult:
        """
        Check if a request can be served from cache

        This is the main entry point for cache lookup

        Flow:
        1. Generate embedding
        2. Search FAISS for similar vector
        3. Retrieve cached response from Redis
        4. Evaluate decision
        5. Record metrics

        Args:
            messages: Chat messages
            model_name: Requested model
            tenant_id: Tenant namespace
            user_id: Optional user ID
            config: Optional cache configuration

        Returns:
            CacheDecisionResult (hit or miss)
        """
        start_time = datetime.utcnow()

        # Ensure Redis store is initialized
        if self.redis_store is None:
            self.redis_store = await get_redis_store()

        # Extract cache key
        cache_key = self._extract_cache_key(messages, model_name, tenant_id)

        # Generate embedding
        embedding_text = cache_key.to_embedding_text(
            include_system=config.include_system_prompt if config else True
        )
        embedding = self.embedding_service.embed_text(
            text=embedding_text,
            model_name=model_name,
            user_id=user_id
        )

        # Search for similar cached responses in FAISS
        cache_entry = self.search_service.get_cache_entry(
            query_embedding=embedding,
            threshold=config.similarity_threshold if config else None
        )

        # Get cached response from Redis if found
        cached_response = None
        similarity = None
        retrieval_source = None

        if cache_entry:
            similarity = cache_entry.similarity

            # Try Redis first (online serving layer)
            cached_response = await self.redis_store.get_cached_response(
                cache_entry.prompt_id
            )
            retrieval_source = "redis"

            # Fallback to legacy store if not in Redis
            if not cached_response:
                cached_response = self.cache_store.get(cache_entry.prompt_id)
                retrieval_source = "legacy"
                logger.debug(f"Redis miss, using legacy store for {cache_entry.prompt_id[:8]}...")

        # Make decision
        decision_result = self.decision_engine.evaluate(
            cached_response=cached_response,
            similarity=similarity,
            requested_model=model_name,
            requested_system_prompt=cache_key.system_prompt,
            tenant_id=tenant_id
        )

        # Calculate latency
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Record statistics
        if decision_result.is_hit():
            # Record hit in both stores
            await self.redis_store.increment_cache_hit(cached_response.cache_id)
            self.cache_store.record_hit(cached_response.cache_id)

            # Record similarity score
            if similarity:
                await self.redis_store.record_similarity_score(similarity)

            logger.info(
                f"✓ CACHE HIT: similarity={similarity:.3f}, "
                f"source={retrieval_source}, "
                f"latency={latency_ms:.1f}ms, "
                f"cache_id={cached_response.cache_id[:8]}..."
            )
        else:
            # Record miss
            await self.redis_store.increment_cache_miss()
            miss_type = self._get_miss_type(decision_result.decision)
            self.cache_store.record_miss(miss_type)

            logger.info(
                f"✗ CACHE MISS: {decision_result.reason}, "
                f"latency={latency_ms:.1f}ms"
            )

        return decision_result

    async def store_response(
        self,
        messages: List[Message],
        response_text: str,
        model_name: str,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        request_params: Optional[dict] = None
    ) -> str:
        """
        Store a new LLM response in cache

        Flow:
        1. Generate embedding
        2. Create cache entry
        3. Store in Redis (online serving)
        4. Store in legacy (backup)
        5. Add to FAISS index

        Args:
            messages: Chat messages
            response_text: LLM response
            model_name: Model that generated response
            tenant_id: Tenant namespace
            user_id: Optional user ID
            ttl_seconds: Time-to-live (defaults to settings)
            request_params: Optional request parameters

        Returns:
            cache_id of stored response
        """
        # Ensure Redis store is initialized
        if self.redis_store is None:
            self.redis_store = await get_redis_store()

        # Extract cache key
        cache_key = self._extract_cache_key(messages, model_name, tenant_id)

        # Generate embedding
        embedding_text = cache_key.to_embedding_text(include_system=True)
        embedding = self.embedding_service.embed_text(
            text=embedding_text,
            model_name=model_name,
            user_id=user_id
        )

        # Create cache entry
        cache_id = str(uuid.uuid4())
        ttl = ttl_seconds or settings.CACHE_TTL_SECONDS

        cached_response = CachedResponse(
            cache_id=cache_id,
            prompt_text=cache_key.prompt_text,
            system_prompt=cache_key.system_prompt,
            response_text=response_text,
            model_name=model_name,
            embedding_vector=embedding.vector,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=ttl),
            tenant_id=tenant_id,
            user_id=user_id,
            request_params=request_params or {}
        )

        # Store in Redis (online serving layer)
        await self.redis_store.set_cached_response(
            cache_id=cache_id,
            response=cached_response,
            ttl_seconds=ttl
        )

        # Store in legacy cache (backup/fallback)
        self.cache_store.add(cached_response)

        # Add to FAISS vector index
        self.search_service.add_to_index(
            embedding=embedding,
            response_text=response_text,
            model_name=model_name
        )

        logger.info(
            f"Stored response in cache: cache_id={cache_id[:8]}..., "
            f"ttl={ttl}s, stored=[redis+legacy+faiss]"
        )

        return cache_id

    def _extract_cache_key(
        self,
        messages: List[Message],
        model_name: str,
        tenant_id: str
    ) -> CacheKey:
        """
        Extract cache key from messages

        Args:
            messages: Chat messages
            model_name: Model name
            tenant_id: Tenant ID

        Returns:
            CacheKey
        """
        # Extract system prompt
        system_prompt = None
        user_messages = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            elif msg.role == "user":
                user_messages.append(msg.content)

        # Combine user messages
        prompt_text = " ".join(user_messages)

        return CacheKey(
            prompt_text=prompt_text,
            system_prompt=system_prompt,
            model_name=model_name,
            tenant_id=tenant_id
        )

    def _get_miss_type(self, decision: CacheDecision) -> str:
        """Map decision to miss type for statistics"""
        if decision == CacheDecision.THRESHOLD_NOT_MET:
            return "threshold"
        elif decision == CacheDecision.MODEL_MISMATCH:
            return "model"
        elif decision == CacheDecision.SYSTEM_MISMATCH:
            return "system"
        elif decision == CacheDecision.EXPIRED:
            return "expired"
        else:
            return "general"

    async def get_stats(self) -> dict:
        """
        Get comprehensive cache statistics

        Returns:
            Dictionary with cache stats from Redis and legacy stores
        """
        # Ensure Redis store is initialized
        if self.redis_store is None:
            self.redis_store = await get_redis_store()

        # Get stats from all sources
        redis_stats = await self.redis_store.get_stats()
        cache_stats = self.cache_store.get_stats()
        search_stats = self.search_service.get_stats()

        # Get recent similarity scores
        recent_scores = await self.redis_store.get_recent_similarity_scores(limit=100)

        return {
            "redis": redis_stats.model_dump(),
            "cache": cache_stats.model_dump(),
            "search": search_stats,
            "summary": {
                "total_cached_responses_redis": await self.redis_store.count(),
                "total_cached_responses_legacy": self.cache_store.count(),
                "hit_rate": redis_stats.hit_rate,
                "total_requests": redis_stats.total_requests,
                "average_similarity": redis_stats.average_similarity,
                "recent_similarity_scores": recent_scores,
            }
        }

    async def clear_cache(self) -> None:
        """Clear all cache data from Redis and legacy stores"""
        # Ensure Redis store is initialized
        if self.redis_store is None:
            self.redis_store = await get_redis_store()

        # Clear all stores
        await self.redis_store.clear_all()
        self.cache_store.clear()
        self.search_service.clear_index()

        logger.info("Cleared all cache data (Redis + legacy + FAISS)")

    def clear_expired(self) -> int:
        """
        Clear expired cache entries from legacy store

        Note: Redis handles TTL expiration automatically

        Returns:
            Number of entries cleared
        """
        return self.cache_store.clear_expired()

    def save_cache(self) -> None:
        """Save legacy cache to disk"""
        self.cache_store.save()
        self.search_service.save_index()
        logger.info("Saved legacy cache and FAISS index to disk")

    def load_cache(self) -> None:
        """Load legacy cache from disk"""
        self.cache_store.load()
        self.search_service.load_index()
        logger.info("Loaded legacy cache and FAISS index from disk")


# Global instance
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """
    Get global cache service instance

    Returns:
        CacheService singleton
    """
    global _cache_service

    if _cache_service is None:
        _cache_service = CacheService()

    return _cache_service
