"""
Threshold Search Module

Tests multiple candidate thresholds and selects the optimal one
"""
from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime
import uuid

from app.optimization.scoring import ThresholdScorer, ScoringWeights
from app.optimization.policy import OptimizationPolicy, OptimizationConstraints

logger = logging.getLogger(__name__)


class ThresholdSearcher:
    """
    Searches for optimal similarity threshold

    Approach:
    1. Generate candidate thresholds
    2. Simulate cache decisions at each threshold
    3. Calculate quality metrics for each candidate
    4. Score candidates using objective function
    5. Select best threshold subject to safety constraints
    """

    def __init__(
        self,
        scorer: Optional[ThresholdScorer] = None,
        policy: Optional[OptimizationPolicy] = None
    ):
        self.scorer = scorer or ThresholdScorer()
        self.policy = policy or OptimizationPolicy()

    def search_optimal_threshold(
        self,
        current_threshold: float,
        evaluation_dataset: List[Dict[str, Any]],
        current_metrics: Dict[str, float],
        drift_severity: Optional[str] = None,
        false_hit_rate: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Search for optimal threshold across candidate space

        Args:
            current_threshold: Current active threshold
            evaluation_dataset: Test cases for evaluation
            current_metrics: Current cache quality metrics
            drift_severity: Current drift level
            false_hit_rate: Current false hit rate

        Returns:
            Optimization result with best threshold and metrics
        """
        run_id = f"opt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        started_at = datetime.utcnow()

        logger.info(f"[{run_id}] Starting threshold optimization")
        logger.info(f"  Current threshold: {current_threshold}")
        logger.info(f"  Evaluation dataset size: {len(evaluation_dataset)}")
        logger.info(f"  Drift severity: {drift_severity}")
        logger.info(f"  False hit rate: {false_hit_rate}")

        # Check if optimization should run
        should_run, reason = self.policy.should_allow_optimization(
            current_metrics,
            last_change_hours_ago=None  # TODO: Get from database
        )
        if not should_run:
            logger.info(f"[{run_id}] Optimization skipped: {reason}")
            return {
                "run_id": run_id,
                "decision": "no_change",
                "decision_reason": reason,
                "old_threshold": current_threshold,
                "new_threshold": current_threshold,
                "started_at": started_at.isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
            }

        # Generate candidate thresholds
        candidates = self.policy.get_candidate_thresholds(
            current_threshold,
            drift_severity=drift_severity,
            false_hit_rate=false_hit_rate
        )

        logger.info(f"[{run_id}] Testing {len(candidates)} candidate thresholds: {candidates}")

        # Evaluate each candidate
        candidate_results = {}
        for candidate in candidates:
            metrics = self._evaluate_threshold(candidate, evaluation_dataset)
            candidate_results[candidate] = metrics

        # Rank candidates by score
        ranked = self.scorer.rank_candidates(candidate_results)

        if not ranked:
            logger.error(f"[{run_id}] No valid candidates found")
            return {
                "run_id": run_id,
                "decision": "failed",
                "decision_reason": "No valid candidates",
                "old_threshold": current_threshold,
                "new_threshold": current_threshold,
                "started_at": started_at.isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
            }

        # Best candidate is first in ranked list
        best_threshold, best_score, best_metrics = ranked[0]

        logger.info(
            f"[{run_id}] Best threshold: {best_threshold:.3f} "
            f"(score: {best_score:.3f})"
        )

        # Decide whether to deploy
        should_deploy, deploy_reason = self.policy.should_deploy_threshold(
            old_threshold=current_threshold,
            new_threshold=best_threshold,
            old_metrics=current_metrics,
            new_metrics=best_metrics,
            optimization_score=best_score
        )

        decision = "deploy" if should_deploy else "no_change"
        if not should_deploy and "DRY RUN" in deploy_reason:
            decision = "simulated"

        completed_at = datetime.utcnow()
        execution_time_ms = (completed_at - started_at).total_seconds() * 1000

        result = {
            "run_id": run_id,
            "decision": decision,
            "decision_reason": deploy_reason,
            "old_threshold": current_threshold,
            "new_threshold": best_threshold,
            "optimization_score": best_score,
            "before": {
                "threshold": current_threshold,
                **current_metrics
            },
            "after_estimate": {
                "threshold": best_threshold,
                **best_metrics
            },
            "candidates_tested": candidates,
            "candidate_scores": {
                str(t): s for t, s, _ in ranked
            },
            "scoring_weights": self.scorer.get_weights_dict(),
            "constraints_applied": self.policy.get_constraints_summary(),
            "dataset_size": len(evaluation_dataset),
            "execution_time_ms": execution_time_ms,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
        }

        logger.info(f"[{run_id}] Optimization complete: {decision}")
        return result

    def _evaluate_threshold(
        self,
        threshold: float,
        evaluation_dataset: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Evaluate a threshold against evaluation dataset

        Args:
            threshold: Threshold to test
            evaluation_dataset: List of test cases

        Returns:
            Quality metrics at this threshold
        """
        if not evaluation_dataset:
            logger.warning("Empty evaluation dataset")
            return {
                "precision": 0.0,
                "recall": 0.0,
                "false_hit_rate": 1.0,
                "false_miss_rate": 1.0,
                "cache_hit_rate": 0.0,
                "speedup_factor": 1.0,
            }

        # Simulate cache decisions
        true_positives = 0
        true_negatives = 0
        false_positives = 0
        false_negatives = 0

        for test_case in evaluation_dataset:
            similarity = test_case.get("similarity", 0)
            should_cache = test_case.get("should_cache", False)

            # Simulate decision: cache if similarity >= threshold
            would_cache = similarity >= threshold

            if would_cache and should_cache:
                true_positives += 1
            elif not would_cache and not should_cache:
                true_negatives += 1
            elif would_cache and not should_cache:
                false_positives += 1  # False hit - dangerous!
            elif not would_cache and should_cache:
                false_negatives += 1  # False miss - missed savings

        total = len(evaluation_dataset)
        total_positive = true_positives + false_negatives
        total_negative = true_negatives + false_positives

        # Calculate metrics
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / total_positive if total_positive > 0 else 0
        false_hit_rate = false_positives / total_negative if total_negative > 0 else 0
        false_miss_rate = false_negatives / total_positive if total_positive > 0 else 0
        cache_hit_rate = (true_positives + false_positives) / total if total > 0 else 0

        # F1 score
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        # Estimated speedup (cache is ~50-100x faster)
        # Higher cache hit rate = better speedup
        estimated_speedup = 1 + (cache_hit_rate * 50)

        metrics = {
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "false_hit_rate": false_hit_rate,
            "false_miss_rate": false_miss_rate,
            "cache_hit_rate": cache_hit_rate,
            "speedup_factor": estimated_speedup,
            "true_positives": true_positives,
            "true_negatives": true_negatives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
        }

        logger.debug(
            f"Threshold {threshold:.3f}: "
            f"precision={precision:.3f}, recall={recall:.3f}, "
            f"FHR={false_hit_rate:.3f}, FMR={false_miss_rate:.3f}"
        )

        return metrics

    def explain_optimization(
        self,
        optimization_result: Dict[str, Any]
    ) -> str:
        """
        Generate human-readable explanation of optimization result

        Args:
            optimization_result: Result from search_optimal_threshold()

        Returns:
            Human-readable explanation
        """
        decision = optimization_result.get("decision")
        old_threshold = optimization_result.get("old_threshold")
        new_threshold = optimization_result.get("new_threshold")
        reason = optimization_result.get("decision_reason")

        before = optimization_result.get("before", {})
        after = optimization_result.get("after_estimate", {})

        if decision == "no_change":
            return f"No threshold change: {reason}"

        if decision == "simulated":
            explanation = f"SIMULATION: Would change threshold from {old_threshold:.3f} to {new_threshold:.3f}\n"
        else:
            explanation = f"Threshold changed from {old_threshold:.3f} to {new_threshold:.3f}\n"

        explanation += f"Reason: {reason}\n\n"

        explanation += "Expected improvements:\n"
