"""
Optimization Policy Module

Defines safety rules and constraints for autonomous threshold optimization
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class OptimizationConstraints:
    """
    Safety constraints for threshold optimization

    These rules prevent the agent from making dangerous changes
    """
    # Threshold bounds
    min_threshold: float = 0.75  # Never go below this
    max_threshold: float = 0.98  # Never go above this
    max_change_per_step: float = 0.05  # Maximum single adjustment

    # Quality requirements
    min_precision: float = 0.85  # Minimum acceptable precision
    max_false_hit_rate: float = 0.15  # Maximum tolerable false hits
    min_recall: float = 0.50  # Minimum acceptable recall

    # Validation requirements
    require_validation: bool = True  # Must validate before deploying
    min_dataset_size: int = 50  # Minimum evaluation dataset size

    # Change frequency limits
    min_hours_between_changes: int = 6  # Prevent too frequent changes

    # Dry-run mode
    dry_run: bool = True  # Week 7 default: simulation only


class OptimizationPolicy:
    """
    Enforces safety policy for autonomous threshold optimization

    Production-grade agent systems need guardrails
    """

    def __init__(self, constraints: Optional[OptimizationConstraints] = None):
        self.constraints = constraints or OptimizationConstraints()

    def validate_candidate_threshold(
        self,
        candidate: float,
        current_threshold: float
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a candidate threshold is within safety bounds

        Returns:
            (is_valid, rejection_reason)
        """
        # Check absolute bounds
        if candidate < self.constraints.min_threshold:
            return False, f"Threshold {candidate} below minimum {self.constraints.min_threshold}"

        if candidate > self.constraints.max_threshold:
            return False, f"Threshold {candidate} above maximum {self.constraints.max_threshold}"

        # Check change magnitude
        change = abs(candidate - current_threshold)
        if change > self.constraints.max_change_per_step:
            return False, f"Change of {change:.3f} exceeds max allowed {self.constraints.max_change_per_step}"

        return True, None

    def validate_quality_metrics(
        self,
        precision: float,
        recall: float,
        false_hit_rate: float
    ) -> tuple[bool, Optional[str]]:
        """
        Check if predicted quality metrics meet safety requirements

        Returns:
            (is_acceptable, rejection_reason)
        """
        if precision < self.constraints.min_precision:
            return False, f"Precision {precision:.3f} below minimum {self.constraints.min_precision}"

        if false_hit_rate > self.constraints.max_false_hit_rate:
            return False, f"False hit rate {false_hit_rate:.3f} exceeds maximum {self.constraints.max_false_hit_rate}"

        if recall < self.constraints.min_recall:
            return False, f"Recall {recall:.3f} below minimum {self.constraints.min_recall}"

        return True, None

    def should_allow_optimization(
        self,
        current_metrics: Dict[str, float],
        last_change_hours_ago: Optional[float] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if optimization should run at all

        Args:
            current_metrics: Current cache quality metrics
            last_change_hours_ago: Hours since last threshold change

        Returns:
            (should_run, reason)
        """
        # Check if too soon since last change
        if last_change_hours_ago is not None:
            if last_change_hours_ago < self.constraints.min_hours_between_changes:
                return False, f"Only {last_change_hours_ago:.1f}h since last change (min: {self.constraints.min_hours_between_changes}h)"

        # Check if current quality is already excellent
        precision = current_metrics.get("precision", 0)
        recall = current_metrics.get("recall", 0)
        false_hit_rate = current_metrics.get("false_hit_rate", 1)

        if (precision > 0.95 and
            recall > 0.80 and
            false_hit_rate < 0.05):
            return False, "Current quality already excellent, no optimization needed"

        return True, None

    def get_candidate_thresholds(
        self,
        current_threshold: float,
        drift_severity: Optional[str] = None,
        false_hit_rate: Optional[float] = None
    ) -> List[float]:
        """
        Generate candidate thresholds to test

        Adapts candidates based on current conditions

        Args:
            current_threshold: Current active threshold
            drift_severity: Drift level (no_drift, moderate_drift, high_drift)
            false_hit_rate: Current false hit rate

        Returns:
            List of candidate thresholds to evaluate
        """
        candidates = []

        # Determine search range based on context
        if false_hit_rate and false_hit_rate > 0.10:
            # High false hits - bias toward higher thresholds
            logger.info("High false hit rate detected, biasing toward higher thresholds")
            candidates = [
                current_threshold + 0.02,
                current_threshold + 0.03,
                current_threshold + 0.05,
                current_threshold,
                current_threshold - 0.01,
            ]
        elif drift_severity == "high_drift":
            # High drift - test wider range
            logger.info("High drift detected, testing wider threshold range")
            candidates = [
                current_threshold - 0.03,
                current_threshold - 0.02,
                current_threshold,
                current_threshold + 0.02,
                current_threshold + 0.03,
                current_threshold + 0.05,
            ]
        else:
            # Normal case - test around current threshold
            candidates = [
                current_threshold - 0.03,
                current_threshold - 0.02,
                current_threshold,
                current_threshold + 0.02,
                current_threshold + 0.03,
            ]

        # Filter candidates to valid range
        candidates = [
            c for c in candidates
            if self.constraints.min_threshold <= c <= self.constraints.max_threshold
        ]

        # Remove duplicates and sort
        candidates = sorted(list(set(candidates)))

        logger.info(f"Generated {len(candidates)} candidate thresholds: {candidates}")
        return candidates

    def should_deploy_threshold(
        self,
        old_threshold: float,
        new_threshold: float,
        old_metrics: Dict[str, float],
        new_metrics: Dict[str, float],
        optimization_score: float
    ) -> tuple[bool, str]:
        """
        Final decision: should we deploy the new threshold?

        Args:
            old_threshold: Current threshold
            new_threshold: Proposed threshold
            old_metrics: Current quality metrics
            new_metrics: Predicted quality metrics with new threshold
            optimization_score: Score of new threshold

        Returns:
            (should_deploy, reason)
        """
        # If thresholds are the same, no change needed
        if abs(new_threshold - old_threshold) < 0.001:
            return False, "No meaningful change in threshold"

        # Validate candidate is within bounds
        is_valid, reason = self.validate_candidate_threshold(new_threshold, old_threshold)
        if not is_valid:
            return False, f"Safety validation failed: {reason}"

        # Validate quality metrics
        is_acceptable, reason = self.validate_quality_metrics(
            new_metrics.get("precision", 0),
            new_metrics.get("recall", 0),
            new_metrics.get("false_hit_rate", 1)
        )
        if not is_acceptable:
            return False, f"Quality validation failed: {reason}"

        # Check if new threshold is actually better
        old_score = self._estimate_score(old_metrics)
        if optimization_score <= old_score:
            return False, f"New score ({optimization_score:.3f}) not better than old ({old_score:.3f})"

        # Check if improvement is significant enough
        improvement = optimization_score - old_score
        if improvement < 0.01:  # Minimum 1% improvement
            return False, f"Improvement ({improvement:.3f}) not significant enough"

        # Dry-run mode check
        if self.constraints.dry_run:
            return False, "DRY RUN mode enabled - would deploy in production"

        # All checks passed
