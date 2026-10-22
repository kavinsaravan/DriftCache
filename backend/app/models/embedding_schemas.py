"""
Embedding Schemas

Data models for embeddings and related metadata
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
import hashlib


class EmbeddingMetadata(BaseModel):
    """Metadata associated with an embedding"""
    prompt_hash: str = Field(..., description="Hash of the normalized prompt")
    model_name: str = Field(..., description="Model used for generation")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_params: Dict[str, Any] = Field(default_factory=dict)

    @staticmethod
    def create_hash(text: str) -> str:
        """
        Create a deterministic hash of text

        Args:
            text: Text to hash

        Returns:
            SHA256 hash as hex string
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()


class Embedding(BaseModel):
    """
    An embedding vector with metadata

    This is the core data structure for semantic caching
    """
    vector: List[float] = Field(..., description="Embedding vector")
    dimension: int = Field(..., description="Vector dimension")
    text: str = Field(..., description="Original text")
    metadata: EmbeddingMetadata

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "vector": [0.13, -0.44, 0.82, 0.07],
                "dimension": 384,
                "text": "Explain Redis simply",
                "metadata": {
                    "prompt_hash": "abc123...",
                    "model_name": "all-MiniLM-L6-v2",
                    "timestamp": "2024-01-01T00:00:00",
                    "request_params": {}
                }
            }
        }
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "vector": self.vector,
            "dimension": self.dimension,
            "text": self.text,
            "metadata": self.metadata.model_dump()
        }


class EmbeddingBatch(BaseModel):
    """Batch of embeddings for bulk operations"""
    embeddings: List[Embedding]
    total_count: int
    model_name: str

    def __len__(self) -> int:
        return len(self.embeddings)
