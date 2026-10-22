"""
Search Schemas

Data models for vector search operations and results
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, ConfigDict, Field


class SearchQuery(BaseModel):
    """Query for vector search"""
    vector: List[float] = Field(..., description="Query embedding vector")
    top_k: int = Field(default=5, ge=1, le=100, description="Number of results to return")
    threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold"
    )
    filter_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata filters"
    )


class SearchResult(BaseModel):
    """Single search result"""
    vector_id: int = Field(..., description="FAISS vector ID")
    prompt_id: str = Field(..., description="Unique prompt identifier")
    similarity: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    distance: float = Field(..., description="L2 distance from query")
    prompt_text: str = Field(..., description="Original prompt text")
    response_text: Optional[str] = Field(None, description="Cached response")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SearchResults(BaseModel):
    """Collection of search results"""
    query_vector: List[float]
    results: List[SearchResult]
    total_found: int
    search_time_ms: float
    threshold_applied: Optional[float] = None

    def get_best_match(self) -> Optional[SearchResult]:
        """Get the best (highest similarity) result"""
        if not self.results:
            return None
        return self.results[0]

    def filter_by_threshold(self, threshold: float) -> "SearchResults":
        """Filter results by minimum similarity threshold"""
        filtered = [r for r in self.results if r.similarity >= threshold]
        return SearchResults(
            query_vector=self.query_vector,
            results=filtered,
            total_found=len(filtered),
            search_time_ms=self.search_time_ms,
            threshold_applied=threshold
        )


class VectorMetadata(BaseModel):
    """
    Metadata associated with a vector in the index

    FAISS only stores vectors. We need to map vector_id -> metadata
    """
    vector_id: int = Field(..., description="FAISS vector ID")
    cache_id: Optional[str] = Field(
        None,
        description="Persistent cache entry UUID",
    )
    prompt_id: str = Field(..., description="Unique prompt identifier (hash)")
    prompt_text: str = Field(..., description="Original prompt")
    response_text: Optional[str] = Field(None, description="Cached response")
    model_name: str = Field(..., description="Model used for generation")
    embedding_model: str = Field(..., description="Embedding model used")
    tenant_id: str = Field(default="default", description="Tenant namespace")
    system_prompt: Optional[str] = Field(None, description="System prompt used")
    conversation_history: Optional[str] = Field(None, description="Conversation context")
    cache_key_hash: Optional[str] = Field(None, description="Redis cache key hash")
    expires_at: Optional[datetime] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_params: Dict[str, Any] = Field(default_factory=dict)
    cache_hits: int = Field(default=0, description="Number of times this was reused")
    last_accessed: Optional[datetime] = None

    def expiration_time(self, ttl_seconds: Optional[int] = None) -> datetime:
        """Explicit deadlines take precedence over maintenance/global defaults."""
        if self.expires_at is not None:
            return self.expires_at
        from app.core.config import settings
        ttl = settings.CACHE_TTL_SECONDS if ttl_seconds is None else ttl_seconds
        return self.timestamp + timedelta(seconds=ttl)

    def is_expired(self, now: Optional[datetime] = None, ttl_seconds: Optional[int] = None) -> bool:
        deadline = self.expiration_time(ttl_seconds)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now >= deadline

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "vector_id": self.vector_id,
            "cache_id": self.cache_id,
            "prompt_id": self.prompt_id,
            "prompt_text": self.prompt_text,
            "response_text": self.response_text,
            "model_name": self.model_name,
            "embedding_model": self.embedding_model,
            "tenant_id": self.tenant_id,
            "system_prompt": self.system_prompt,
            "conversation_history": self.conversation_history,
            "cache_key_hash": self.cache_key_hash,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expiration_time().isoformat(),
            "request_params": self.request_params,
            "cache_hits": self.cache_hits,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VectorMetadata":
        """Create from dictionary"""
        data = dict(data)
        # Old persisted entries have no recoverable per-entry TTL. Expire them
        # conservatively rather than extending an unknown original deadline.
        if not data.get("expires_at"):
            data["expires_at"] = data.get("timestamp", datetime.now(timezone.utc))
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if data.get("last_accessed") and isinstance(data["last_accessed"], str):
            data["last_accessed"] = datetime.fromisoformat(data["last_accessed"])

        # Provide defaults for new fields (for backward compatibility with old cache)
        data.setdefault("tenant_id", "default")
        data.setdefault("cache_id", None)
        data.setdefault("system_prompt", None)
        data.setdefault("conversation_history", None)
        data.setdefault("cache_key_hash", None)

        return cls(**data)


class CacheEntry(BaseModel):
    """
    Complete cache entry returned from vector search

    Represents a cached response retrieved from FAISS similarity search
    """
    vector_id: int
    prompt_id: str
    prompt_text: str
    response_text: str
    similarity: float
    metadata: VectorMetadata
    is_cache_hit: bool = True

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "vector_id": 42,
                "prompt_id": "abc123...",
                "prompt_text": "What is Redis?",
                "response_text": "Redis is an in-memory...",
                "similarity": 0.92,
                "metadata": {"model_name": "gpt-4", "cache_hits": 5},
                "is_cache_hit": True
            }
        }
    )
