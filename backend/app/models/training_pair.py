"""
Training Pair Model

Stores positive and negative pairs for contrastive learning
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Enum
from sqlalchemy.sql import func
import enum

from app.database.base import Base


class PairType(str, enum.Enum):
    """Type of training pair"""
    POSITIVE = "positive"  # Semantically similar queries
    HARD_NEGATIVE = "hard_negative"  # Medium similarity, should not match
    EASY_NEGATIVE = "easy_negative"  # Random dissimilar queries


class TrainingPair(Base):
    """
    Training pairs for contrastive learning

    Generated from cache interactions:
    - Positive: High similarity queries that resulted in cache hits
    - Hard negatives: Medium similarity that shouldn't match
    - Easy negatives: Random dissimilar queries
    """
    __tablename__ = "training_pairs"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Anchor and comparison texts
    anchor_text = Column(Text, nullable=False)
    comparison_text = Column(Text, nullable=False)

    # Pair metadata
    pair_type = Column(Enum(PairType), nullable=False, index=True)
    similarity_score = Column(Float, nullable=True)  # Original similarity if available

    # Source information
    anchor_cache_id = Column(String(36), nullable=True, index=True)
    comparison_cache_id = Column(String(36), nullable=True, index=True)

    # Data quality
    is_validated = Column(Integer, default=0)  # 0=not validated, 1=human validated
    quality_score = Column(Float, nullable=True)  # Optional quality metric

    # Training metadata
    used_in_training = Column(Integer, default=0)  # How many times used
    last_used = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<TrainingPair(id={self.id}, type={self.pair_type}, similarity={self.similarity_score:.3f if self.similarity_score else 'N/A'})>"
