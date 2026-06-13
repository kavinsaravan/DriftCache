"""
Index Version Model

Tracks FAISS index versions for point-in-time evaluation
"""
from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.sql import func
from datetime import datetime

from app.database.base import Base


class IndexVersion(Base):
    """
    Index versions table

    Records changes to FAISS index and embedding model

    Why this matters:
    When evaluating a cache decision from the past, you need to know:
    "Which embedding model was used to generate that vector?"
    "Which FAISS index version was active?"

    This enables:
    - Point-in-time evaluation
    - Embedding model A/B testing
    - Historical consistency verification
    - Prevention of data leakage in evaluation
    """
    __tablename__ = "index_versions"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Version identification
    version_name = Column(String(100), nullable=False, unique=True, index=True)

    # Embedding configuration
    embedding_model = Column(String(100), nullable=False)  # e.g., "all-MiniLM-L6-v2"
    embedding_dimension = Column(Integer, nullable=False)  # e.g., 384

    # FAISS configuration
    index_type = Column(String(50), nullable=False)  # e.g., "FLAT", "IVF", "HNSW"
    vector_count = Column(Integer, default=0)  # Number of vectors in this version

    # Change metadata
    reason = Column(Text, nullable=True)  # Why this version was created
    created_by = Column(String(100), nullable=True)  # "manual", "agent:drift_detector", etc.

    # Validity period
    active_from = Column(DateTime(timezone=True), nullable=False, index=True)
    active_until = Column(DateTime(timezone=True), nullable=True, index=True)  # NULL = currently active

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<IndexVersion(id={self.id}, version={self.version_name}, model={self.embedding_model})>"
