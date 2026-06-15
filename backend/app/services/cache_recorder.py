"""
Cache Recorder Service

Wraps cache operations with PostgreSQL historical recording

This is the glue between:
- CacheService (Redis + FAISS)
- PostgreSQL (historical analytics)
"""
import logging
import uuid
from typing import List, Optional
from datetime import datetime

from app.cache.service import CacheService, get_cache_service
from app.models.cache_schemas import CacheDecisionResult, CacheDecision
from app.models.schemas import Message
from app.models.cache_event import CacheStatus
from app.database.session import get_db_manager
from app.repositories.request_repo import RequestRepository
from app.repositories.cache_repo import CacheRepository
from app.repositories.provider_repo import ProviderRepository
from app.repositories.threshold_repo import ThresholdRepository
from app.embeddings.utils import create_prompt_hash
from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheRecorder:
    """
    Cache recorder service

    Coordinates cache operations with database recording

    Flow:
    1. Record incoming request
    2. Check cache (Redis + FAISS)
    3. Record cache event
    4. If miss: record provider call
    5. Store response in cache + database
    """

    def __init__(self, cache_service: Optional[CacheService] = None):
        """
        Initialize cache recorder

        Args:
            cache_service: Optional cache service instance
        """
        self.cache_service = cache_service or get_cache_service()
        logger.info("CacheRecorder initialized")

    async def check_and_record(
        self,
        messages: List[Message],
        model_name: str,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        stream: bool = False
    ) -> tuple[str, CacheDecisionResult]:
        """
        Check cache and record request + event in database

        Args:
            messages: Chat messages
            model_name: Model name
            tenant_id: Tenant namespace
            user_id: Optional user ID
            stream: Whether streaming is enabled

        Returns:
            Tuple of (request_id, CacheDecisionResult)
        """
        start_time = datetime.utcnow()
        request_id = str(uuid.uuid4())

        # Extract prompt data
        prompt_text = " ".join([m.content for m in messages if m.role == "user"])
        system_prompt = next((m.content for m in messages if m.role == "system"), None)
        prompt_hash = create_prompt_hash(prompt_text)

        # Record request in database
        try:
            db_manager = get_db_manager()
            with db_manager.session_scope() as session:
                request_repo = RequestRepository(session)
                request_repo.create(
                    request_id=request_id,
                    tenant_id=tenant_id,
                    model=model_name,
                    messages_json=[m.model_dump() for m in messages],
                    prompt_text=prompt_text,
                    prompt_hash=prompt_hash,
                    system_prompt=system_prompt,
                    user_id=user_id,
                    stream=stream
                )
                logger.debug(f"Recorded request: {request_id}")
        except Exception as e:
            logger.error(f"Failed to record request: {e}")
            # Continue even if database recording fails

        # Check cache
        decision_result = await self.cache_service.check_cache(
            messages=messages,
            model_name=model_name,
            tenant_id=tenant_id,
            user_id=user_id
        )

        # Calculate latency
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Get current threshold and index version for point-in-time tracking
        threshold_used = settings.SIMILARITY_THRESHOLD
        threshold_version_id = None
        index_version_id = None
        embedding_model = settings.EMBEDDING_MODEL
        provider_model = None

        try:
            with db_manager.session_scope() as session:
                threshold_repo = ThresholdRepository(session)
                current_threshold = threshold_repo.get_current()
                if current_threshold:
                    threshold_used = current_threshold.threshold_value
                    threshold_version_id = current_threshold.id

                # Get current index version
                from app.repositories.index_repo import IndexRepository
                index_repo = IndexRepository(session)
                current_index = index_repo.get_current()
                if current_index:
                    index_version_id = current_index.id
                    embedding_model = current_index.embedding_model

                # Get provider model from cached response (if HIT)
                if decision_result.cached_response:
                    provider_model = decision_result.cached_response.model_name

        except Exception as e:
            logger.warning(f"Failed to get current versions: {e}")

        # Record cache event with point-in-time versioning
        try:
            with db_manager.session_scope() as session:
                cache_repo = CacheRepository(session)

                # Map CacheDecision to CacheStatus
                cache_status = self._map_decision_to_status(decision_result.decision)

                # Create event with versioning info
                from app.models.cache_event import CacheEvent
                event = CacheEvent(
                    request_id=request_id,
                    cache_status=cache_status,
                    threshold_used=threshold_used,
                    tenant_id=tenant_id,
                    model=model_name,
                    matched_cache_id=decision_result.cached_response.cache_id if decision_result.cached_response else None,
                    similarity_score=decision_result.similarity,
                    latency_ms=latency_ms,
                    retrieval_source="redis" if decision_result.is_hit() else None,
                    threshold_version_id=threshold_version_id,
                    # Point-in-time versioning
                    embedding_model=embedding_model,
                    index_version_id=index_version_id,
                    provider_model=provider_model
                )

                session.add(event)
                session.commit()
                logger.debug(f"Recorded cache event: {cache_status.value} (with versioning)")
        except Exception as e:
            logger.error(f"Failed to record cache event: {e}")

        return request_id, decision_result

    async def store_and_record(
        self,
        request_id: str,
        messages: List[Message],
        response_text: str,
        model_name: str,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        request_params: Optional[dict] = None,
        provider: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        estimated_cost: Optional[float] = None,
        provider_latency_ms: Optional[float] = None
    ) -> str:
        """
        Store response in cache and record in database

        Args:
            request_id: Request ID
            messages: Chat messages
            response_text: LLM response
            model_name: Model name
            tenant_id: Tenant namespace
            user_id: Optional user ID
            ttl_seconds: Cache TTL
            request_params: Request parameters
            provider: Provider name (if this was an actual LLM call)
            input_tokens: Input token count
            output_tokens: Output token count
            estimated_cost: Estimated cost
            provider_latency_ms: Provider latency

        Returns:
            cache_id
        """
        # Store in cache (Redis + FAISS)
        cache_id = await self.cache_service.store_response(
            messages=messages,
            response_text=response_text,
            model_name=model_name,
            tenant_id=tenant_id,
            user_id=user_id,
            ttl_seconds=ttl_seconds,
            request_params=request_params
        )

        # Extract prompt data
        prompt_text = " ".join([m.content for m in messages if m.role == "user"])
        system_prompt = next((m.content for m in messages if m.role == "system"), None)
        prompt_hash = create_prompt_hash(prompt_text)
        system_prompt_hash = create_prompt_hash(system_prompt) if system_prompt else None

        # Record in database
        try:
            db_manager = get_db_manager()

            # Record cache entry
            with db_manager.session_scope() as session:
                cache_repo = CacheRepository(session)

                # Calculate expiration
                ttl = ttl_seconds or settings.CACHE_TTL_SECONDS
                from datetime import timedelta
                expires_at = datetime.utcnow() + timedelta(seconds=ttl)

                cache_repo.create_entry(
                    cache_id=cache_id,
                    prompt_text=prompt_text,
                    prompt_hash=prompt_hash,
                    response_text=response_text,
                    model=model_name,
                    tenant_id=tenant_id,
                    system_prompt=system_prompt,
                    system_prompt_hash=system_prompt_hash,
                    user_id=user_id,
                    request_params=request_params,
                    expires_at=expires_at
                )
                logger.debug(f"Recorded cache entry: {cache_id}")

            # Record embedding (link FAISS vector to cache entry)
            # Note: We need to get the FAISS vector ID from the search service
            try:
                with db_manager.session_scope() as session:
                    cache_repo = CacheRepository(session)

                    # Get latest vector ID from FAISS
                    # This assumes vectors are added sequentially
                    faiss_index = self.cache_service.search_service.faiss_index
                    if faiss_index.index is not None and faiss_index.index.ntotal > 0:
                        faiss_vector_id = faiss_index.index.ntotal - 1

                        cache_repo.create_embedding_record(
                            cache_id=cache_id,
                            faiss_vector_id=faiss_vector_id,
                            embedding_model=settings.EMBEDDING_MODEL,
                            embedding_dimension=settings.EMBEDDING_DIMENSION
                        )
                        logger.debug(f"Recorded embedding: FAISS ID {faiss_vector_id} -> cache {cache_id}")
                    else:
                        logger.warning(f"FAISS index is empty, cannot record embedding for cache {cache_id}")
            except Exception as e:
                logger.error(f"Failed to record embedding: {e}", exc_info=True)

            # Record provider call (if this was an actual LLM call)
            if provider:
                with db_manager.session_scope() as session:
                    provider_repo = ProviderRepository(session)

                    total_tokens = (input_tokens or 0) + (output_tokens or 0) if (input_tokens or output_tokens) else None

                    provider_repo.create(
                        request_id=request_id,
                        provider=provider,
                        model=model_name,
                        tenant_id=tenant_id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        estimated_cost=estimated_cost,
                        latency_ms=provider_latency_ms,
                        user_id=user_id
                    )
                    logger.debug(f"Recorded provider call: {provider}/{model_name}")

        except Exception as e:
            logger.error(f"Failed to record cache entry/provider call: {e}")

        return cache_id

    def _map_decision_to_status(self, decision: CacheDecision) -> CacheStatus:
        """
        Map CacheDecision to CacheStatus enum

        Args:
            decision: CacheDecision

        Returns:
            CacheStatus
        """
        mapping = {
            CacheDecision.HIT: CacheStatus.HIT,
            CacheDecision.MISS: CacheStatus.MISS,
            CacheDecision.EXPIRED: CacheStatus.EXPIRED,
            CacheDecision.THRESHOLD_NOT_MET: CacheStatus.THRESHOLD_NOT_MET,
            CacheDecision.MODEL_MISMATCH: CacheStatus.MODEL_MISMATCH,
            CacheDecision.SYSTEM_MISMATCH: CacheStatus.SYSTEM_MISMATCH,
            CacheDecision.ERROR: CacheStatus.ERROR,
        }

        return mapping.get(decision, CacheStatus.MISS)


# Global instance
_cache_recorder: Optional[CacheRecorder] = None


def get_cache_recorder() -> CacheRecorder:
    """
    Get global cache recorder instance

    Returns:
        CacheRecorder singleton
    """
    global _cache_recorder

    if _cache_recorder is None:
        _cache_recorder = CacheRecorder()

    return _cache_recorder
