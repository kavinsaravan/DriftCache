"""
Index Version Model

Tracks FAISS index versions for point-in-time evaluation and autonomous rebuilds
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean
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
    - Autonomous index rebuild tracking
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
    created_by = Column(String(100), nullable=True)  # "manual", "agent:index_rebuilder", etc.

    # Rebuild tracking
    rebuild_job_id = Column(Integer, nullable=True)  # Link to rebuild job
    file_path = Column(String(500), nullable=True)  # Path to index file
    is_active = Column(Boolean, nullable=False, server_default='false')  # Currently active index

    # Validity period
    active_from = Column(DateTime(timezone=True), nullable=False, index=True)
    active_until = Column(DateTime(timezone=True), nullable=True, index=True)  # NULL = currently active

    # Tenant isolation
    tenant_id = Column(String(100), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<IndexVersion(id={self.id}, version={self.version_name}, model={self.embedding_model})>"

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "version_name": self.version_name,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "index_type": self.index_type,
            "vector_count": self.vector_count,
            "reason": self.reason,
            "created_by": self.created_by,
            "rebuild_job_id": self.rebuild_job_id,
            "file_path": self.file_path,
            "is_active": self.is_active,
            "active_from": self.active_from.isoformat(),
            "active_until": self.active_until.isoformat() if self.active_until else None,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat(),
        }
