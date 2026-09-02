"""
Training Job Model

Tracks fine-tuning jobs and their status
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Float, JSON, Enum
from sqlalchemy.sql import func
import enum

from app.database.base import Base


class JobStatus(str, enum.Enum):
    """Training job status"""
    PENDING = "pending"
    COLLECTING_DATA = "collecting_data"
    TRAINING = "training"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"


class TrainingJob(Base):
    """
    Training job tracking table

    Records all fine-tuning attempts with their parameters and results
    """
    __tablename__ = "training_jobs"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(36), unique=True, nullable=False, index=True)

    # Job metadata
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True)
    base_model = Column(String(100), nullable=False)  # e.g., "all-MiniLM-L6-v2"
    output_model_name = Column(String(100), nullable=True)  # e.g., "all-MiniLM-L6-v2-driftcache-v1"

    # Training configuration
    training_config = Column(JSON, default={})  # Learning rate, batch size, etc.

    # Dataset info
    num_training_pairs = Column(Integer, nullable=True)
    num_positive_pairs = Column(Integer, nullable=True)
    num_negative_pairs = Column(Integer, nullable=True)

    # Training metrics
    final_loss = Column(Float, nullable=True)
    num_epochs_completed = Column(Integer, default=0)
    training_time_seconds = Column(Float, nullable=True)

    # Evaluation metrics
    eval_metrics = Column(JSON, default={})  # Precision, recall, MRR, etc.

    # Error handling
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<TrainingJob(id={self.job_id}, status={self.status}, model={self.output_model_name})>"
