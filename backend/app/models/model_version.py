"""
Model Version Model

Tracks different versions of the embedding model
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Float, JSON, Boolean
from sqlalchemy.sql import func

from app.database.base import Base


class ModelVersion(Base):
    """
    Model version registry

    Tracks all embedding model versions with their metadata and performance
    """
    __tablename__ = "model_versions"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(String(50), unique=True, nullable=False, index=True)

    # Model identification
    model_name = Column(String(200), nullable=False)  # Local path or HF Hub name
    base_model = Column(String(100), nullable=False)  # Original model
    is_finetuned = Column(Boolean, default=False)

    # Training info
    training_job_id = Column(String(36), nullable=True, index=True)  # Link to training job
    huggingface_url = Column(String(500), nullable=True)  # HF Hub URL if uploaded

    # Performance metrics
    performance_metrics = Column(JSON, default={})  # Precision, recall, latency, etc.

    # A/B testing
    is_active = Column(Boolean, default=False)  # Currently in production
    traffic_percentage = Column(Float, default=0.0)  # % of traffic routed to this model

    # Model metadata
    dimension = Column(Integer, nullable=False)
    model_size_mb = Column(Float, nullable=True)
    description = Column(Text, nullable=True)

    # Deployment info
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    deprecated_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"<ModelVersion(version={self.version_id}, status={status}, traffic={self.traffic_percentage}%)>"
