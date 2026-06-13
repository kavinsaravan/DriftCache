"""
Evaluation Result Model

Stores cache quality evaluation results over time
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.database.base import Base


class EvaluationResult(Base):
    """
    Records cache quality evaluation metrics

    Tracks precision, recall, false hit/miss rates to measure
    whether semantic cache decisions are reliable
    """
    __tablename__ = "evaluation_results"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Evaluation metadata
    evaluation_run_id = Column(String(100), nullable=False, unique=True, index=True)
    dataset_name = Column(String(100), nullable=False, index=True)
    dataset_size = Column(Integer, nullable=False)

    # Cache configuration at time of evaluation
    threshold_used = Column(Float, nullable=False, index=True)
    embedding_model = Column(String(100), nullable=True)
    index_version = Column(String(100), nullable=True)

    # Core metrics
    precision = Column(Float, nullable=False)  # valid_hits / total_hits
    recall = Column(Float, nullable=False)     # correct_hits / all_reusable
    f1_score = Column(Float, nullable=False)   # harmonic mean of precision & recall

    # Error rates
    false_hit_rate = Column(Float, nullable=False)   # bad_hits / total_hits
    false_miss_rate = Column(Float, nullable=False)  # missed_opportunities / all_reusable

    # Detailed counts
    total_test_cases = Column(Integer, nullable=False)
    true_positives = Column(Integer, nullable=False)   # correct cache hits
    true_negatives = Column(Integer, nullable=False)   # correct cache misses
    false_positives = Column(Integer, nullable=False)  # bad cache hits
    false_negatives = Column(Integer, nullable=False)  # missed cache opportunities

    # Hit quality metrics
    avg_hit_margin = Column(Float, nullable=True)      # avg (similarity - threshold)
    avg_hit_similarity = Column(Float, nullable=True)  # avg similarity for hits
    min_hit_similarity = Column(Float, nullable=True)  # weakest hit
    max_hit_similarity = Column(Float, nullable=True)  # strongest hit

    # Miss analysis
    avg_miss_similarity = Column(Float, nullable=True)  # avg similarity for misses
    near_miss_count = Column(Integer, nullable=True)    # misses close to threshold

    # Recommendation
    recommended_action = Column(String(100), nullable=True)
    recommendation_confidence = Column(Float, nullable=True)
    recommendation_details = Column(Text, nullable=True)

    # Performance impact estimates
    estimated_cost_impact = Column(Float, nullable=True)      # cost change if threshold adjusted
    estimated_quality_impact = Column(Float, nullable=True)   # quality change estimate

    # Evaluation execution
    execution_time_ms = Column(Float, nullable=True)
    evaluation_type = Column(String(50), nullable=False, default="rule_based")  # rule_based, llm_judge, manual

    # Status
    is_baseline = Column(Boolean, default=False)  # Mark as baseline evaluation
    notes = Column(Text, nullable=True)

    # Tenant isolation
    tenant_id = Column(String(100), nullable=True, index=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    def __repr__(self):
        return (
            f"<EvaluationResult(id={self.id}, "
            f"precision={self.precision:.3f}, recall={self.recall:.3f}, "
            f"threshold={self.threshold_used})>"
        )

    def to_summary_dict(self):
        """Convert to summary dictionary"""
        return {
            "evaluation_run_id": self.evaluation_run_id,
            "dataset": self.dataset_name,
            "threshold": self.threshold_used,
            "metrics": {
                "precision": round(self.precision, 4),
                "recall": round(self.recall, 4),
                "f1_score": round(self.f1_score, 4),
                "false_hit_rate": round(self.false_hit_rate, 4),
                "false_miss_rate": round(self.false_miss_rate, 4),
            },
            "recommendation": {
                "action": self.recommended_action,
                "confidence": round(self.recommendation_confidence, 4) if self.recommendation_confidence else None,
                "details": self.recommendation_details,
            },
            "created_at": self.created_at.isoformat()
        }
