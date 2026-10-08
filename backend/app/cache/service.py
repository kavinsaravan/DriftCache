"""
Cache Service

Orchestrates the complete semantic caching flow:
1. Generate embedding
2. Search FAISS vector index
3. Evaluate match quality
4. Return cached response or miss
5. Store new responses in Redis and PostgreSQL
"""
import logging
from typing import Optional, List
from datetime import datetime, timedelta
import uuid
import numpy as np

from app.cache.decision import get_decision_engine, CacheDecisionEngine
from app.cache.redis_store import get_redis_store, RedisStore
from app.vectorstore.search import get_search_service, SemanticSearchService
from app.embeddings.service import get_embedding_service, EmbeddingService
from app.models.cache_schemas import (
    CacheDecision,
    CacheDecisionResult,
    CachedResponse,
    CacheStoreResult,
    CacheConfig,
    CacheKey,
)
from app.models.schemas import Message
from app.core.config import settings
from app.database.session import get_db_manager
from app.services.threshold_config import get_active_threshold

logger = logging.getLogger(__name__)


class CacheService:
    """
    Main cache service

    Coordinates embedding, search, decision, and storage

    Architecture:
    - Redis for online serving (fast retrieval)
    - FAISS for semantic vector search
    """

    def __init__(
        self,
        decision_engine: Optional[CacheDecisionEngine] = None,
        redis_store: Optional[RedisStore] = None,
        search_service: Optional[SemanticSearchService] = None,
        embedding_service: Optional[EmbeddingService] = None
    ):
        """
        Initialize cache service

        Args:
            decision_engine: Cache decision engine
            redis_store: Redis store (online serving)
            search_service: Vector search service
            embedding_service: Embedding service
        """
        self.decision_engine = decision_engine or get_decision_engine()
        self.redis_store = redis_store  # Will be initialized async
        self.search_service = search_service or get_search_service()
        self.embedding_service = embedding_service or get_embedding_service()

        # In-memory threshold cache to avoid DB query on every request
        self._threshold_cache: dict = {}  # {tenant_id: (threshold, timestamp)}
        self._threshold_cache_ttl = 30  # seconds

        logger.info("CacheService initialized (Redis mode)")

    def _get_cached_threshold(self, tenant_id: str) -> float:
        """
        Get threshold from memory cache or DB

        Caches threshold for 30 seconds to avoid DB query on every request.

        Args:
            tenant_id: Tenant ID

        Returns:
            Active threshold value
        """
        now = datetime.utcnow()

        # Check cache
        if tenant_id in self._threshold_cache:
            threshold, timestamp = self._threshold_cache[tenant_id]
            age_seconds = (now - timestamp).total_seconds()

            if age_seconds < self._threshold_cache_ttl:
                return threshold

        # Cache miss or expired - query DB
        db_manager = get_db_manager()
        with db_manager.session_scope() as db:
            threshold = get_active_threshold(db, tenant_id=tenant_id)

        # Update cache
        self._threshold_cache[tenant_id] = (threshold, now)

        logger.debug(f"Threshold cache refreshed for tenant {tenant_id}: {threshold}")
        return threshold

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

        # A deployment in another worker publishes an atomic marker after the
        # shared index is ready. Refresh lazily before serving the next request.
        from fastapi.concurrency import run_in_threadpool
        from app.training.deployment import refresh_deployed_model
        await run_in_threadpool(refresh_deployed_model)

        # Ensure Redis store is initialized
        if self.redis_store is None:
            self.redis_store = await get_redis_store()

        # Extract cache key
        cache_key = self._extract_cache_key(messages, model_name, tenant_id)

        # Get active threshold from cached value if no config provided
        threshold = None
        if config:
            threshold = config.similarity_threshold
        else:
            # Get from memory cache (refreshed from DB every 30s)
            threshold = self._get_cached_threshold(tenant_id=tenant_id)

        # Generate embedding (wrapped in threadpool to avoid blocking async event loop)
        embedding_text = cache_key.to_embedding_text(
            include_system=config.include_system_prompt if config else True
        )
        embedding = await run_in_threadpool(
            self.embedding_service.embed_text,
            embedding_text,
            model_name,
            user_id
        )

        # Search for similar cached responses in FAISS
        # Pass filter parameters to retrieve top-k and filter for valid matches
        cache_entry = self.search_service.get_cache_entry(
            query_embedding=embedding,
            threshold=threshold,
            model_name=model_name,
            tenant_id=tenant_id,
            system_prompt=cache_key.system_prompt,
            conversation_history=cache_key.conversation_history,
            require_same_model=config.require_same_model if config else False
        )

        # Get cached response from Redis if found
        cached_response = None
        similarity = None
        retrieval_source = None

        if cache_entry:
            similarity = cache_entry.similarity

            # Use the cache key hash from the matched entry's metadata
            # This is critical: FAISS does semantic matching, then we use the
            # matched entry's stored hash to look up the exact response
            stored_cache_key_hash = cache_entry.metadata.cache_key_hash

            if stored_cache_key_hash:
                # Try Redis first (online serving layer)
                cached_response = await self.redis_store.get_cached_response(
                    stored_cache_key_hash
                )
                retrieval_source = "redis"

                # Fallback to response_text from metadata if not in Redis
                if not cached_response:
                    # The response is already in the metadata, use it directly
                    cached_response = CachedResponse(
                        cache_id=self._persistent_cache_id(cache_entry),
                        prompt_text=cache_entry.prompt_text,
                        response_text=cache_entry.response_text,
                        model_name=cache_entry.metadata.model_name,
                        embedding_vector=[],  # Not needed for serving
                        created_at=cache_entry.metadata.timestamp,
                        expires_at=cache_entry.metadata.timestamp + timedelta(seconds=settings.CACHE_TTL_SECONDS),
                        tenant_id=cache_entry.metadata.tenant_id,
                        system_prompt=cache_entry.metadata.system_prompt
                    )
                    retrieval_source = "metadata"
                    logger.debug(f"Redis miss, using metadata for {stored_cache_key_hash[:8]}...")
            else:
                # Old entry without cache_key_hash, fall back to metadata
                cached_response = CachedResponse(
                    cache_id=self._persistent_cache_id(cache_entry),
                    prompt_text=cache_entry.prompt_text,
                    response_text=cache_entry.response_text,
                    model_name=cache_entry.metadata.model_name,
                    embedding_vector=[],
                    created_at=cache_entry.metadata.timestamp,
                    expires_at=cache_entry.metadata.timestamp + timedelta(seconds=settings.CACHE_TTL_SECONDS),
                    tenant_id=cache_entry.metadata.tenant_id,
                    system_prompt=cache_entry.metadata.system_prompt
                )
                retrieval_source = "metadata_legacy"
                logger.debug("Using metadata for entry without cache_key_hash")

        # Make decision
        decision_result = self.decision_engine.evaluate(
            cached_response=cached_response,
            similarity=similarity,
            requested_model=model_name,
            requested_system_prompt=cache_key.system_prompt,
            tenant_id=tenant_id,
            threshold=threshold
        )
        decision_result.retrieval_source = retrieval_source

        # Calculate latency
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Record statistics
        if decision_result.is_hit():
            # Record hit in Redis (primary metrics store)
            await self.redis_store.increment_cache_hit(cached_response.cache_id)

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
            # Record miss in Redis (primary metrics store)
            await self.redis_store.increment_cache_miss()

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
    ) -> CacheStoreResult:
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
            Cache and vector identifiers for the stored response
        """
        from fastapi.concurrency import run_in_threadpool
        from app.training.deployment import refresh_deployed_model
        await run_in_threadpool(refresh_deployed_model)

        # Ensure Redis store is initialized
        if self.redis_store is None:
            self.redis_store = await get_redis_store()

        # Extract cache key
        cache_key = self._extract_cache_key(messages, model_name, tenant_id)

        # Generate embedding (wrapped in threadpool to avoid blocking async event loop)
        from fastapi.concurrency import run_in_threadpool

        embedding_text = cache_key.to_embedding_text(include_system=True)
        embedding = await run_in_threadpool(
            self.embedding_service.embed_text,
            embedding_text,
            model_name,
            user_id
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

        cache_key_hash = cache_key.to_cache_key_hash()

        # Persist the searchable entry before exposing it through Redis. This
        # closes the window where a process crash could leave a hot response
        # with no durable FAISS vector.
        vector_id = self.search_service.add_to_index(
            embedding=embedding,
            response_text=response_text,
            model_name=model_name,
            cache_id=cache_id,
            tenant_id=tenant_id,
            system_prompt=cache_key.system_prompt,
            conversation_history=cache_key.conversation_history,
            cache_key_hash=cache_key_hash,
        )
        try:
            self.search_service.save_index()
        except Exception:
            self.search_service.faiss_index.remove_vectors(
                np.asarray([vector_id], dtype=np.int64)
            )
            self.search_service.metadata_store.delete(vector_id)
            raise

        # Use the full request-derived hash as the Redis lookup key. The value
        # itself retains the persistent UUID used by PostgreSQL analytics.
        await self.redis_store.set_cached_response(
            cache_id=cache_key_hash,
            response=cached_response,
            ttl_seconds=ttl,
        )

        logger.info(
            f"Stored response in cache: cache_id={cache_id[:8]}..., "
            f"ttl={ttl}s, stored=[redis+faiss+disk]"
        )

        return CacheStoreResult(cache_id=cache_id, vector_id=vector_id)

    @staticmethod
    def _persistent_cache_id(cache_entry) -> str:
        """Return the database UUID, with a lookup for pre-migration metadata."""
        if cache_entry.metadata.cache_id:
            return cache_entry.metadata.cache_id

        try:
            from app.models.embedding_record import EmbeddingRecord

            with get_db_manager().session_scope() as session:
                record = session.query(EmbeddingRecord).filter(
                    EmbeddingRecord.faiss_vector_id == cache_entry.vector_id
                ).first()
                if record:
                    cache_entry.metadata.cache_id = record.cache_id
                    return record.cache_id
        except Exception:
            logger.exception(
                "Could not resolve persistent cache ID for vector %s",
                cache_entry.vector_id,
            )

        # Old indexes created before persistent IDs were stored can still be
        # served, but their historical hit counter cannot be linked.
        return cache_entry.prompt_id

    def _extract_cache_key(
        self,
        messages: List[Message],
        model_name: str,
        tenant_id: str
    ) -> CacheKey:
        """
        Extract cache key from messages

        Includes conversation history (assistant messages) for proper
        multi-turn conversation matching.

        Args:
            messages: Chat messages
            model_name: Model name
            tenant_id: Tenant ID

        Returns:
            CacheKey
        """
        # Extract system prompt
        system_prompt = None
        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
                break  # Only one system message expected

        # Find the last user message (the current query)
        last_user_idx = None
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].role == "user":
                last_user_idx = i
                break

        if last_user_idx is None:
            # No user message found, shouldn't happen but handle gracefully
            return CacheKey(
                prompt_text="",
                system_prompt=system_prompt,
                conversation_history=None,
                model_name=model_name,
                tenant_id=tenant_id
            )

        # The last user message is the query
        prompt_text = messages[last_user_idx].content

        # Build conversation history from all messages BEFORE the last user message
        conversation_parts = []
        for i, msg in enumerate(messages[:last_user_idx]):
            if msg.role == "user":
                conversation_parts.append(f"[USER] {msg.content}")
            elif msg.role == "assistant":
                conversation_parts.append(f"[ASSISTANT] {msg.content}")
            # Skip system messages (already extracted separately)

        conversation_history = " ".join(conversation_parts) if conversation_parts else None

        return CacheKey(
            prompt_text=prompt_text,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            model_name=model_name,
            tenant_id=tenant_id
        )

    async def get_stats(self) -> dict:
        """
        Get comprehensive cache statistics

        Returns:
            Dictionary with cache stats from Redis and FAISS
        """
        # Ensure Redis store is initialized
        if self.redis_store is None:
            self.redis_store = await get_redis_store()

        # Get stats from all sources
        redis_stats = await self.redis_store.get_stats()
        search_stats = self.search_service.get_stats()

        # Get recent similarity scores
        recent_scores = await self.redis_store.get_recent_similarity_scores(limit=100)

        return {
            "redis": redis_stats.model_dump(),
            "search": search_stats,
            "summary": {
                "total_cached_responses": await self.redis_store.count(),
                "hit_rate": redis_stats.hit_rate,
                "total_requests": redis_stats.total_requests,
                "average_similarity": redis_stats.average_similarity,
                "recent_similarity_scores": recent_scores,
            }
        }

    async def clear_cache(self) -> None:
        """Clear all cache data from Redis and FAISS"""
        # Ensure Redis store is initialized
        if self.redis_store is None:
            self.redis_store = await get_redis_store()

        # Clear all stores
        await self.redis_store.clear_all()
        self.search_service.clear_index()
        self.search_service.save_index()

        logger.info("Cleared all cache data (Redis + FAISS)")

    def clear_expired(self) -> int:
        """
        Clear expired vectors from FAISS index

        Note: Redis handles TTL expiration automatically

        Returns:
            Number of entries cleared
        """
        removed = self.search_service.remove_expired_vectors()
        if removed:
            self.search_service.save_index()
        return removed

    def save_cache(self) -> None:
        """Save FAISS index to disk"""
        self.search_service.save_index()
        logger.info("Saved FAISS index to disk")

    def load_cache(self) -> None:
        """Load FAISS index from disk"""
        self.search_service.load_index()
        logger.info("Loaded FAISS index from disk")


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
