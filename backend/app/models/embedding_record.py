"""
Embedding Record Model

Metadata about embeddings linking FAISS vectors to database records
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime

from app.database.base import Base


class EmbeddingRecord(Base):
    """
    Embedding records table

    Links FAISS vector IDs to cache entries

    FAISS knows: vector 417 is similar to vector 102
    PostgreSQL knows: vector 102 belongs to cache_id xyz, created on date X
    """
    __tablename__ = "embedding_records"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Cache linkage
    cache_id = Column(String(36), nullable=False, index=True)

    # FAISS linkage
    faiss_vector_id = Column(Integer, nullable=False, unique=True, index=True)

    # Embedding metadata
    embedding_model = Column(String(100), nullable=False)  # e.g., "all-MiniLM-L6-v2"
    embedding_dimension = Column(Integer, nullable=False)  # e.g., 384

    # Future: Store full vector with pgvector
    # embedding_vector = Column(Vector(384))  # Requires pgvector extension

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<EmbeddingRecord(id={self.id}, faiss_id={self.faiss_vector_id}, cache_id={self.cache_id[:8]}...)>"
