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

        # Get active threshold from DB if no config provided
        threshold = None
        if config:
            threshold = config.similarity_threshold
        else:
            # Get from database using proper context manager
            db_manager = get_db_manager()
            with db_manager.session_scope() as db:
                threshold = get_active_threshold(db, tenant_id=tenant_id)

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
                        cache_id=cache_entry.prompt_id,
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
                    cache_id=cache_entry.prompt_id,
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
        # IMPORTANT: Use cache_key hash that includes tenant, model, system, history, and prompt
        # This prevents key collisions when different conversations end with the same question
        cache_key_hash = cache_key.to_cache_key_hash()
        await self.redis_store.set_cached_response(
            cache_id=cache_key_hash,
            response=cached_response,
            ttl_seconds=ttl
        )

        # Store in legacy cache (backup/fallback)
        self.cache_store.add(cached_response)

        # Add to FAISS vector index
        self.search_service.add_to_index(
            embedding=embedding,
            response_text=response_text,
            model_name=model_name,
            tenant_id=tenant_id,
            system_prompt=cache_key.system_prompt,
            conversation_history=cache_key.conversation_history,
            cache_key_hash=cache_key_hash
        )

        # Persist FAISS index to disk so it survives restarts
        self.search_service.save_index()

        logger.info(
            f"Stored response in cache: cache_id={cache_id[:8]}..., "
            f"ttl={ttl}s, stored=[redis+legacy+faiss+disk]"
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
