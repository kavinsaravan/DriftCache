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

        logger.info("CacheService initialized (Redis mode)")

    async def check_cache(
        self,
        messages: List[Message],
        model_name: str,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        config: Optional[CacheConfig] = None,
        request_params: Optional[dict] = None,
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
        cache_key = self._extract_cache_key(
            messages, model_name, tenant_id, request_params=request_params
        )

        if config:
            threshold = config.similarity_threshold
        else:
            threshold = settings.SIMILARITY_THRESHOLD

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
            request_params=cache_key.request_params,
            require_same_model=config.require_same_model if config else True,
            include_below_threshold=True
        )

        # Get cached response from Redis if found
        cached_response = None
        similarity = None
        retrieval_source = None

        if cache_entry:
            similarity = cache_entry.similarity

        if cache_entry and cache_entry.similarity >= threshold:
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
                        expires_at=cache_entry.metadata.expiration_time(),
                        tenant_id=cache_entry.metadata.tenant_id,
                        system_prompt=cache_entry.metadata.system_prompt,
                        request_params=cache_entry.metadata.request_params,
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
                    expires_at=cache_entry.metadata.expiration_time(),
                    tenant_id=cache_entry.metadata.tenant_id,
                    system_prompt=cache_entry.metadata.system_prompt,
                    request_params=cache_entry.metadata.request_params,
                )
                retrieval_source = "metadata_legacy"
                logger.debug("Using metadata for entry without cache_key_hash")

        # Make decision
        if similarity is not None and similarity < threshold:
            # Preserve the observation without fetching or serving its response.
            decision_result = CacheDecisionResult(
                decision=CacheDecision.THRESHOLD_NOT_MET,
                similarity=similarity,
                reason=f"Similarity {similarity:.3f} < threshold {threshold}",
            )
        else:
            decision_result = self.decision_engine.evaluate(
                cached_response=cached_response,
                similarity=similarity,
                requested_model=model_name,
                requested_system_prompt=cache_key.system_prompt,
                tenant_id=tenant_id,
                threshold=threshold,
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
        cache_key = self._extract_cache_key(
            messages, model_name, tenant_id, request_params=request_params
        )

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
        ttl = settings.CACHE_TTL_SECONDS if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            raise ValueError("Cache TTL must be positive")

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

        # Store the hot response first. If Redis rejects the write, do not add
        # a searchable vector that would look successfully cached.
        await self.redis_store.set_cached_response(
            cache_id=cache_key_hash,
            response=cached_response,
            ttl_seconds=ttl,
        )

        # The journal makes this vector durable without rewriting the complete
        # FAISS index and metadata file for every cache miss.
        try:
            vector_id = self.search_service.add_to_index(
                embedding=embedding,
                response_text=response_text,
                model_name=model_name,
                cache_id=cache_id,
                tenant_id=tenant_id,
                system_prompt=cache_key.system_prompt,
                conversation_history=cache_key.conversation_history,
                cache_key_hash=cache_key_hash,
                request_params=cache_key.request_params,
                expires_at=cached_response.expires_at,
            )
        except Exception:
            try:
                await self.redis_store.delete_cached_response(cache_key_hash)
            except Exception:
                logger.exception("Failed to remove partial Redis cache write")
            raise

        logger.info(
            f"Stored response in cache: cache_id={cache_id[:8]}..., "
            f"ttl={ttl}s, stored=[redis+faiss+journal]"
        )

        return CacheStoreResult(cache_id=cache_id, vector_id=vector_id, expires_at=cached_response.expires_at)

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
        tenant_id: str,
        request_params: Optional[dict] = None,
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
        # Preserve every system message and its position. Structured encoding
        # keeps message boundaries distinct even when content contains delimiters.
        import json

        system_messages = [
            {"position": index, "content": msg.content}
            for index, msg in enumerate(messages)
            if msg.role == "system"
        ]
        system_prompt = (
            json.dumps(system_messages, ensure_ascii=False, separators=(",", ":"))
            if system_messages else None
        )

        # Find the last user message (the current query)
        last_user_idx = None
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].role == "user":
                last_user_idx = i
                break

        prompt_text = messages[last_user_idx].content if last_user_idx is not None else ""

        # Only the current query is semantically matched. Everything else is
        # exact context, including message roles, boundaries, order, and any
        # assistant continuation after the last user message. The placeholder
        # preserves the current query's position without requiring its exact text.
        context_messages = [
            {"role": msg.role, "content": None if index == last_user_idx else msg.content}
            for index, msg in enumerate(messages)
        ]
        conversation_history = json.dumps(
            {"version": 2, "query_index": last_user_idx, "messages": context_messages},
            ensure_ascii=False, separators=(",", ":"), sort_keys=True,
        )

        return CacheKey(
            prompt_text=prompt_text,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            model_name=model_name,
            tenant_id=tenant_id,
            request_params=request_params or {},
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
