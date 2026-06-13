"""
Cache Schemas

Data models for cache entries, decisions, and configuration
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from enum import Enum


class CacheDecision(str, Enum):
    """Cache decision outcomes"""
    HIT = "hit"
    MISS = "miss"
    EXPIRED = "expired"
    MODEL_MISMATCH = "model_mismatch"
    SYSTEM_MISMATCH = "system_mismatch"
    THRESHOLD_NOT_MET = "threshold_not_met"
    ERROR = "error"


class CacheConfig(BaseModel):
    """Cache configuration"""
    similarity_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum similarity for cache hit"
    )
    ttl_seconds: int = Field(
        default=3600,
        ge=0,
        description="Time-to-live in seconds"
    )
    require_same_model: bool = Field(
        default=False,
        description="Whether cached response must be from same model"
    )
    include_system_prompt: bool = Field(
        default=True,
        description="Whether to include system prompt in cache key"
    )
    tenant_id: str = Field(
        default="default",
        description="Tenant/namespace for multi-tenancy"
    )


class CachedResponse(BaseModel):
    """
    A cached LLM response

    This is what gets stored in the cache
    """
    cache_id: str = Field(..., description="Unique cache entry ID")
    prompt_text: str = Field(..., description="Original user prompt")
    system_prompt: Optional[str] = Field(None, description="System prompt if any")
    response_text: str = Field(..., description="LLM response")
    model_name: str = Field(..., description="Model that generated response")
    embedding_vector: List[float] = Field(..., description="Prompt embedding")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    cache_hits: int = Field(default=0, description="Number of times reused")
    last_accessed: Optional[datetime] = None

    # Context
    tenant_id: str = Field(default="default")
    user_id: Optional[str] = None
    request_params: Dict[str, Any] = Field(default_factory=dict)

    # Quality
    similarity_score: Optional[float] = Field(
        None,
        description="Similarity score when this was retrieved"
    )

    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def increment_hit(self) -> None:
        """Increment cache hit counter"""
        self.cache_hits += 1
        self.last_accessed = datetime.utcnow()


class CacheDecisionResult(BaseModel):
    """
    Result of cache decision

    Contains the decision and reasoning
    """
    decision: CacheDecision
    cached_response: Optional[CachedResponse] = None
    similarity: Optional[float] = None
    reason: str

    # Decision factors
    similarity_threshold_met: bool = False
    model_compatible: bool = False
    not_expired: bool = False
    system_prompt_compatible: bool = False

    # Metadata
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    evaluation_time_ms: Optional[float] = None

    def is_hit(self) -> bool:
        """Check if this is a cache hit"""
        return self.decision == CacheDecision.HIT

    def is_miss(self) -> bool:
        """Check if this is a cache miss"""
        return self.decision in [
            CacheDecision.MISS,
            CacheDecision.THRESHOLD_NOT_MET,
            CacheDecision.MODEL_MISMATCH,
            CacheDecision.SYSTEM_MISMATCH,
            CacheDecision.EXPIRED
        ]


class CacheRequest(BaseModel):
    """Request to check cache"""
    prompt_text: str
    system_prompt: Optional[str] = None
    model_name: str
    tenant_id: str = "default"
    user_id: Optional[str] = None
    config: Optional[CacheConfig] = None


class CacheStoreRequest(BaseModel):
    """Request to store in cache"""
    prompt_text: str
    system_prompt: Optional[str] = None
    response_text: str
    model_name: str
    embedding_vector: List[float]
    tenant_id: str = "default"
    user_id: Optional[str] = None
    ttl_seconds: Optional[int] = None
    request_params: Optional[Dict[str, Any]] = None


class CacheStats(BaseModel):
    """Cache statistics"""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    # Hit rate
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    # Breakdown by decision type
    threshold_misses: int = 0
    model_misses: int = 0
    system_misses: int = 0
    expired_misses: int = 0

    # Performance
    average_similarity: float = 0.0
    total_tokens_saved: int = 0

    # Time range
    since: datetime = Field(default_factory=datetime.utcnow)


class CacheInvalidation(BaseModel):
    """Cache invalidation request"""
    cache_ids: Optional[List[str]] = None
    model_name: Optional[str] = None
    tenant_id: Optional[str] = None
    older_than: Optional[datetime] = None


class CacheKey(BaseModel):
    """
    Cache key components

    Used to generate a unique identifier for cache lookups
    """
    prompt_text: str
    system_prompt: Optional[str] = None
    model_name: Optional[str] = None  # Optional for flexible matching
    tenant_id: str = "default"

    def to_embedding_text(self, include_system: bool = True) -> str:
        """
        Convert to text for embedding generation

        Args:
            include_system: Whether to include system prompt

        Returns:
            Combined text for embedding
        """
        parts = [self.prompt_text]

        if include_system and self.system_prompt:
            parts.insert(0, f"[SYSTEM] {self.system_prompt}")

        return " ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "prompt_text": self.prompt_text,
            "system_prompt": self.system_prompt,
            "model_name": self.model_name,
            "tenant_id": self.tenant_id
        }
