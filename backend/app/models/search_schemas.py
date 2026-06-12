"""
Search Schemas

Data models for vector search operations and results
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


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

    FAISS only stores vectors. We need to map vector_id → metadata
    """
    vector_id: int = Field(..., description="FAISS vector ID")
    prompt_id: str = Field(..., description="Unique prompt identifier (hash)")
    prompt_text: str = Field(..., description="Original prompt")
    response_text: Optional[str] = Field(None, description="Cached response")
    model_name: str = Field(..., description="Model used for generation")
    embedding_model: str = Field(..., description="Embedding model used")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_params: Dict[str, Any] = Field(default_factory=dict)
    cache_hits: int = Field(default=0, description="Number of times this was reused")
    last_accessed: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "vector_id": self.vector_id,
            "prompt_id": self.prompt_id,
            "prompt_text": self.prompt_text,
            "response_text": self.response_text,
            "model_name": self.model_name,
            "embedding_model": self.embedding_model,
            "timestamp": self.timestamp.isoformat(),
            "request_params": self.request_params,
            "cache_hits": self.cache_hits,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VectorMetadata":
        """Create from dictionary"""
        # Convert ISO timestamps back to datetime
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if data.get("last_accessed") and isinstance(data["last_accessed"], str):
            data["last_accessed"] = datetime.fromisoformat(data["last_accessed"])
        return cls(**data)


class IndexStats(BaseModel):
    """Statistics about the vector index"""
    total_vectors: int
    dimension: int
    index_type: str
    memory_usage_mb: float
    is_trained: bool = True
    created_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None


class CacheEntry(BaseModel):
    """
    Complete cache entry (vector + metadata + response)

    This is what gets returned to the cache decision layer
    """
    vector_id: int
    prompt_id: str
    prompt_text: str
    response_text: str
    similarity: float
    metadata: VectorMetadata
    is_cache_hit: bool = True

    class Config:
        json_schema_extra = {
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
