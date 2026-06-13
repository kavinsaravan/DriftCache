"""
Cache Repository

Handles database operations for cache entries, events, and embeddings
"""
import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.cache_entry import CacheEntry
from app.models.cache_event import CacheEvent, CacheStatus
from app.models.embedding_record import EmbeddingRecord

logger = logging.getLogger(__name__)


class CacheRepository:
    """Repository for cache-related records"""

    def __init__(self, session: Session):
        """
        Initialize repository

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    # Cache Entry Operations

    def create_entry(
        self,
        cache_id: str,
        prompt_text: str,
        prompt_hash: str,
        response_text: str,
        model: str,
        tenant_id: str,
        system_prompt: Optional[str] = None,
        system_prompt_hash: Optional[str] = None,
        user_id: Optional[str] = None,
        request_params: Optional[dict] = None,
        expires_at: Optional[datetime] = None
    ) -> CacheEntry:
        """
        Create a new cache entry

        Args:
            cache_id: Unique cache ID
            prompt_text: Prompt text
            prompt_hash: SHA256 hash of prompt
            response_text: LLM response
            model: Model name
            tenant_id: Tenant namespace
            system_prompt: Optional system prompt
            system_prompt_hash: Optional system prompt hash
            user_id: Optional user ID
            request_params: Optional request parameters
            expires_at: Optional expiration timestamp

        Returns:
            Created CacheEntry object
        """
        entry = CacheEntry(
            cache_id=cache_id,
            prompt_text=prompt_text,
            prompt_hash=prompt_hash,
            response_text=response_text,
            model=model,
            tenant_id=tenant_id,
            system_prompt=system_prompt,
            system_prompt_hash=system_prompt_hash,
            user_id=user_id,
            request_params=request_params or {},
            expires_at=expires_at
        )

        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)

        logger.debug(f"Created cache entry: {cache_id}")
        return entry

    def get_entry(self, cache_id: str) -> Optional[CacheEntry]:
        """
        Get cache entry by ID

        Args:
            cache_id: Cache ID

        Returns:
            CacheEntry object or None
        """
        return self.session.query(CacheEntry).filter(
            CacheEntry.cache_id == cache_id
        ).first()

    def increment_entry_hits(self, cache_id: str) -> None:
        """
        Increment cache hit counter

        Args:
            cache_id: Cache ID
        """
        entry = self.get_entry(cache_id)
        if entry:
            entry.cache_hits += 1
            entry.last_accessed = datetime.utcnow()
            self.session.commit()

    # Cache Event Operations

    def create_event(
        self,
        request_id: str,
        cache_status: CacheStatus,
        threshold_used: float,
        tenant_id: str,
        model: str,
        matched_cache_id: Optional[str] = None,
        similarity_score: Optional[float] = None,
        latency_ms: Optional[float] = None,
        retrieval_source: Optional[str] = None,
        threshold_version_id: Optional[int] = None
    ) -> CacheEvent:
        """
        Create a cache event record

        Args:
            request_id: Request ID
            cache_status: Cache decision status
            threshold_used: Threshold at time of decision
            tenant_id: Tenant namespace
            model: Model name
            matched_cache_id: Matched cache ID (for hits)
            similarity_score: Similarity score (for hits)
            latency_ms: Cache lookup latency
            retrieval_source: "redis" or "legacy"
            threshold_version_id: Link to threshold version

        Returns:
            Created CacheEvent object
        """
        event = CacheEvent(
            request_id=request_id,
            cache_status=cache_status,
            threshold_used=threshold_used,
            tenant_id=tenant_id,
            model=model,
            matched_cache_id=matched_cache_id,
            similarity_score=similarity_score,
            latency_ms=latency_ms,
            retrieval_source=retrieval_source,
            threshold_version_id=threshold_version_id
        )

        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)

        logger.debug(f"Created cache event: {cache_status.value} for request {request_id}")
        return event

    def get_events_by_request(self, request_id: str) -> List[CacheEvent]:
        """
        Get cache events for a request

        Args:
            request_id: Request ID

        Returns:
            List of CacheEvent objects
        """
        return self.session.query(CacheEvent).filter(
            CacheEvent.request_id == request_id
        ).all()

    def get_recent_events(
        self,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[CacheEvent]:
        """
        Get recent cache events

        Args:
            limit: Maximum results
            since: Optional minimum timestamp

        Returns:
            List of CacheEvent objects
        """
        query = self.session.query(CacheEvent)

        if since:
            query = query.filter(CacheEvent.created_at >= since)

        return query.order_by(CacheEvent.created_at.desc()).limit(limit).all()

    # Embedding Record Operations

    def create_embedding_record(
        self,
        cache_id: str,
        faiss_vector_id: int,
        embedding_model: str,
        embedding_dimension: int
    ) -> EmbeddingRecord:
        """
        Create an embedding record

        Links FAISS vector ID to cache entry

        Args:
            cache_id: Cache ID
            faiss_vector_id: FAISS vector index
            embedding_model: Embedding model name
            embedding_dimension: Vector dimension

        Returns:
            Created EmbeddingRecord object
        """
        record = EmbeddingRecord(
            cache_id=cache_id,
            faiss_vector_id=faiss_vector_id,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension
        )

        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)

        logger.debug(f"Created embedding record: FAISS ID {faiss_vector_id} → cache {cache_id}")
        return record

    def get_embedding_by_faiss_id(self, faiss_vector_id: int) -> Optional[EmbeddingRecord]:
        """
        Get embedding record by FAISS vector ID

        Args:
            faiss_vector_id: FAISS vector index

        Returns:
            EmbeddingRecord object or None
        """
        return self.session.query(EmbeddingRecord).filter(
            EmbeddingRecord.faiss_vector_id == faiss_vector_id
        ).first()

    def get_embedding_by_cache_id(self, cache_id: str) -> Optional[EmbeddingRecord]:
        """
        Get embedding record by cache ID

        Args:
            cache_id: Cache ID

        Returns:
            EmbeddingRecord object or None
        """
        return self.session.query(EmbeddingRecord).filter(
            EmbeddingRecord.cache_id == cache_id
        ).first()
