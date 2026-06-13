"""
Drift Detector Module

Main drift detection logic combining multiple signals
"""
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from app.drift.windows import EmbeddingWindow
from app.drift.statistics import DriftStatistics

logger = logging.getLogger(__name__)


class DriftResult:
    """Container for drift detection results"""

    def __init__(
        self,
        drift_score: float,
        severity: str,
        centroid_shift: float,
        variance_shift: float,
        ks_p_value: float,
        avg_similarity_recent: float,
        avg_similarity_reference: float,
        similarity_drop: float,
        cache_hit_rate_recent: float,
        cache_hit_rate_reference: float,
        hit_rate_drop: float,
        recommended_action: str,
        action_details: str,
        reference_window_start: datetime,
        reference_window_end: datetime,
        reference_sample_size: int,
        recent_window_start: datetime,
        recent_window_end: datetime,
        recent_sample_size: int
    ):
        self.drift_score = drift_score
        self.severity = severity
        self.centroid_shift = centroid_shift
        self.variance_shift = variance_shift
        self.ks_p_value = ks_p_value
        self.avg_similarity_recent = avg_similarity_recent
        self.avg_similarity_reference = avg_similarity_reference
        self.similarity_drop = similarity_drop
        self.cache_hit_rate_recent = cache_hit_rate_recent
        self.cache_hit_rate_reference = cache_hit_rate_reference
        self.hit_rate_drop = hit_rate_drop
        self.recommended_action = recommended_action
        self.action_details = action_details
        self.reference_window_start = reference_window_start
        self.reference_window_end = reference_window_end
        self.reference_sample_size = reference_sample_size
        self.recent_window_start = recent_window_start
        self.recent_window_end = recent_window_end
        self.recent_sample_size = recent_sample_size

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "drift_score": round(self.drift_score, 4),
            "severity": self.severity,
            "signals": {
                "centroid_shift": round(self.centroid_shift, 4),
                "variance_shift": round(self.variance_shift, 4),
                "ks_p_value": round(self.ks_p_value, 4),
            },
            "similarity_metrics": {
                "avg_similarity_recent": round(self.avg_similarity_recent, 4),
                "avg_similarity_reference": round(self.avg_similarity_reference, 4),
                "similarity_drop": round(self.similarity_drop, 4),
            },
            "cache_metrics": {
                "cache_hit_rate_recent": round(self.cache_hit_rate_recent, 4),
                "cache_hit_rate_reference": round(self.cache_hit_rate_reference, 4),
                "hit_rate_drop": round(self.hit_rate_drop, 4),
            },
            "windows": {
                "reference": {
                    "start": self.reference_window_start.isoformat(),
                    "end": self.reference_window_end.isoformat(),
                    "sample_size": self.reference_sample_size,
                },
                "recent": {
                    "start": self.recent_window_start.isoformat(),
                    "end": self.recent_window_end.isoformat(),
                    "sample_size": self.recent_sample_size,
                }
            },
            "recommendation": {
                "action": self.recommended_action,
                "details": self.action_details,
            }
        }

    def __repr__(self):
        return (
            f"<DriftResult(score={self.drift_score:.3f}, "
            f"severity={self.severity}, action={self.recommended_action})>"
        )


class DriftDetector:
    """Main drift detection engine"""

    def __init__(self):
        self.stats = DriftStatistics()

    def detect_drift(
        self,
        reference_window: EmbeddingWindow,
        recent_window: EmbeddingWindow
    ) -> Optional[DriftResult]:
        """
        Run drift detection comparing two windows

        Args:
            reference_window: Baseline window
            recent_window: Recent window

        Returns:
            DriftResult with all metrics, or None if insufficient data
        """
        # Validate windows have data
        if not self._validate_windows(reference_window, recent_window):
            logger.warning("Insufficient data for drift detection")
            return None

        # Calculate all drift signals
        centroid_shift = self._calculate_centroid_shift(
            reference_window, recent_window
        )

        variance_shift = self._calculate_variance_shift(
            reference_window, recent_window
        )

        ks_result = self._run_ks_test(
            reference_window, recent_window
        )
        ks_p_value = ks_result["p_value"]

        similarity_drop = self._calculate_similarity_drop(
            reference_window, recent_window
        )

        hit_rate_drop = self._calculate_hit_rate_drop(
            reference_window, recent_window
        )

        # Calculate combined drift score
        drift_score = self.stats.calculate_drift_score(
            centroid_shift=centroid_shift,
            variance_shift=variance_shift,
            ks_p_value=ks_p_value,
            similarity_drop=similarity_drop,
            hit_rate_drop=hit_rate_drop
        )

        # Classify severity
        severity = self.stats.classify_severity(drift_score)

        # Get recommendation
        recommended_action = self.stats.recommend_action(
            drift_score=drift_score,
            centroid_shift=centroid_shift,
            variance_shift=variance_shift,
            similarity_drop=similarity_drop
        )

        # Generate action details
        action_details = self._generate_action_details(
            centroid_shift, variance_shift, similarity_drop, hit_rate_drop
        )

        # Average similarities
        avg_similarity_reference = (
            sum(reference_window.similarity_scores) / len(reference_window.similarity_scores)
            if reference_window.similarity_scores else 0.0
        )
        avg_similarity_recent = (
            sum(recent_window.similarity_scores) / len(recent_window.similarity_scores)
            if recent_window.similarity_scores else 0.0
        )

        # Create result
        result = DriftResult(
            drift_score=drift_score,
            severity=severity,
            centroid_shift=centroid_shift,
            variance_shift=variance_shift,
            ks_p_value=ks_p_value,
            avg_similarity_recent=avg_similarity_recent,
            avg_similarity_reference=avg_similarity_reference,
            similarity_drop=similarity_drop,
            cache_hit_rate_recent=recent_window.cache_hit_rate,
            cache_hit_rate_reference=reference_window.cache_hit_rate,
            hit_rate_drop=hit_rate_drop,
            recommended_action=recommended_action,
            action_details=action_details,
            reference_window_start=reference_window.start_time,
            reference_window_end=reference_window.end_time,
            reference_sample_size=reference_window.sample_size,
            recent_window_start=recent_window.start_time,
            recent_window_end=recent_window.end_time,
            recent_sample_size=recent_window.sample_size
        )

        logger.info(
            f"Drift detection complete: score={drift_score:.3f}, "
            f"severity={severity}, action={recommended_action}"
        )

        return result

    def _validate_windows(
        self,
        reference_window: EmbeddingWindow,
        recent_window: EmbeddingWindow
    ) -> bool:
        """Check if windows have sufficient data"""
        # Need at least some embeddings in both windows
        if reference_window.sample_size < 10:
            logger.warning(f"Reference window too small: {reference_window.sample_size}")
            return False

        if recent_window.sample_size < 5:
            logger.warning(f"Recent window too small: {recent_window.sample_size}")
            return False

        # Need similarity scores
        if not reference_window.similarity_scores or not recent_window.similarity_scores:
            logger.warning("Missing similarity scores")
            return False

        return True

    def _calculate_centroid_shift(
        self,
        reference_window: EmbeddingWindow,
        recent_window: EmbeddingWindow
    ) -> float:
        """Calculate centroid shift between windows"""
        if not reference_window.embeddings or not recent_window.embeddings:
            return 0.0

        return self.stats.calculate_centroid_shift(
            reference_window.embeddings,
            recent_window.embeddings
        )

    def _calculate_variance_shift(
        self,
        reference_window: EmbeddingWindow,
        recent_window: EmbeddingWindow
    ) -> float:
        """Calculate variance shift between windows"""
        if not reference_window.embeddings or not recent_window.embeddings:
            return 0.0

        return self.stats.calculate_variance_shift(
            reference_window.embeddings,
            recent_window.embeddings
        )

    def _run_ks_test(
        self,
        reference_window: EmbeddingWindow,
        recent_window: EmbeddingWindow
    ) -> Dict[str, float]:
        """Run KS test on similarity distributions"""
        return self.stats.run_ks_test(
            reference_window.similarity_scores,
            recent_window.similarity_scores
        )

    def _calculate_similarity_drop(
        self,
        reference_window: EmbeddingWindow,
        recent_window: EmbeddingWindow
    ) -> float:
        """Calculate drop in average similarity"""
        return self.stats.calculate_similarity_drop(
            reference_window.similarity_scores,
            recent_window.similarity_scores
        )

    def _calculate_hit_rate_drop(
        self,
        reference_window: EmbeddingWindow,
        recent_window: EmbeddingWindow
    ) -> float:
        """Calculate drop in cache hit rate"""
        return reference_window.cache_hit_rate - recent_window.cache_hit_rate

    def _generate_action_details(
        self,
        centroid_shift: float,
        variance_shift: float,
        similarity_drop: float,
        hit_rate_drop: float
    ) -> str:
        """Generate human-readable action details"""
        details = []

        if centroid_shift > 0.3:
            details.append(
                f"High centroid shift ({centroid_shift:.2f}): "
                "Query topics have changed significantly"
            )

        if variance_shift > 0.5:
            details.append(
                f"Increased variance ({variance_shift:.2f}): "
                "Query diversity has increased"
            )
        elif variance_shift < -0.5:
            details.append(
                f"Decreased variance ({variance_shift:.2f}): "
                "Queries are becoming more similar"
            )

        if similarity_drop > 0.15:
            details.append(
                f"Similarity drop ({similarity_drop:.2f}): "
                "Cache matches are weaker"
            )

        if hit_rate_drop > 0.1:
            details.append(
                f"Hit rate drop ({hit_rate_drop:.2%}): "
                "Cache effectiveness has decreased"
            )

        if not details:
            details.append("No significant drift detected")

        return " | ".join(details)
