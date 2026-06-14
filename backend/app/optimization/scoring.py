"""
Threshold Scoring Module

Defines the objective function for threshold optimization
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ScoringWeights:
    """
    Weights for multi-objective threshold optimization

    These control the tradeoff between quality, cost, and latency
    """
    precision: float = 0.45  # Safety first - correctness matters most
    recall: float = 0.25  # Coverage - how many opportunities we capture
    cost_savings: float = 0.20  # Economic efficiency
    latency: float = 0.10  # Performance

    def __post_init__(self):
        """Validate weights sum to 1.0"""
        total = self.precision + self.recall + self.cost_savings + self.latency
        if abs(total - 1.0) > 0.01:
            logger.warning(f"Scoring weights sum to {total}, not 1.0")


class ThresholdScorer:
    """
    Scores candidate thresholds based on multiple objectives

    This is the heart of the optimization - it encodes what "better" means
    """

    def __init__(self, weights: Optional[ScoringWeights] = None):
        self.weights = weights or ScoringWeights()

    def score_threshold(
        self,
        threshold: float,
        metrics: Dict[str, float]
    ) -> float:
        """
        Calculate optimization score for a threshold

        Args:
            threshold: Threshold value being scored
            metrics: Quality and performance metrics at this threshold

        Returns:
            Optimization score (0-1, higher is better)
        """
        precision = metrics.get("precision", 0)
        recall = metrics.get("recall", 0)
        false_hit_rate = metrics.get("false_hit_rate", 1)
        false_miss_rate = metrics.get("false_miss_rate", 1)
        cache_hit_rate = metrics.get("cache_hit_rate", 0)
        speedup_factor = metrics.get("speedup_factor", 1)

        # Precision component (0-1)
        # High precision is good, but we penalize false hits heavily
        precision_score = precision * (1 - false_hit_rate * 2)  # Double penalty for false hits
        precision_score = max(0, min(1, precision_score))  # Clip to [0,1]

        # Recall component (0-1)
        # High recall is good, captures savings opportunities
        recall_score = recall

        # Cost savings component (0-1)
        # Estimated from cache hit rate
        # More hits = more savings, but only if precision is acceptable
        if precision < 0.85:
            # If precision is too low, don't reward cache hits
            cost_score = 0
        else:
            cost_score = cache_hit_rate

        # Latency component (0-1)
        # Higher speedup factor is better
        # Typical speedup: 10-100x, normalize to 0-1
        latency_score = min(speedup_factor / 100, 1.0)

        # Weighted combination
        total_score = (
            self.weights.precision * precision_score +
            self.weights.recall * recall_score +
            self.weights.cost_savings * cost_score +
            self.weights.latency * latency_score
        )

        logger.debug(
            f"Threshold {threshold:.3f}: "
            f"precision_score={precision_score:.3f}, "
            f"recall_score={recall_score:.3f}, "
            f"cost_score={cost_score:.3f}, "
            f"latency_score={latency_score:.3f}, "
            f"total={total_score:.3f}"
        )

        return total_score

    def compare_thresholds(
        self,
        threshold_a: float,
        metrics_a: Dict[str, float],
        threshold_b: float,
        metrics_b: Dict[str, float]
    ) -> tuple[float, str]:
        """
        Compare two thresholds and explain which is better

        Args:
            threshold_a: First threshold
            metrics_a: Metrics for first threshold
            threshold_b: Second threshold
            metrics_b: Metrics for second threshold

        Returns:
            (score_difference, explanation)
        """
        score_a = self.score_threshold(threshold_a, metrics_a)
        score_b = self.score_threshold(threshold_b, metrics_b)

        diff = score_b - score_a

        if abs(diff) < 0.01:
            explanation = f"Thresholds {threshold_a:.3f} and {threshold_b:.3f} are essentially equivalent"
        elif diff > 0:
            explanation = (
                f"Threshold {threshold_b:.3f} is better (score: {score_b:.3f} vs {score_a:.3f}). "
                f"Improvement: {diff:.3f}"
            )
        else:
            explanation = (
                f"Threshold {threshold_a:.3f} is better (score: {score_a:.3f} vs {score_b:.3f}). "
                f"Degradation: {diff:.3f}"
            )

        return diff, explanation

    def rank_candidates(
        self,
        candidates: Dict[float, Dict[str, float]]
    ) -> list[tuple[float, float, Dict[str, float]]]:
        """
        Rank candidate thresholds by score

        Args:
            candidates: Dict mapping threshold -> metrics

        Returns:
            List of (threshold, score, metrics) tuples, sorted by score descending
        """
        ranked = []
        for threshold, metrics in candidates.items():
            score = self.score_threshold(threshold, metrics)
            ranked.append((threshold, score, metrics))

        # Sort by score descending
        ranked.sort(key=lambda x: x[1], reverse=True)

        logger.info(f"Ranked {len(ranked)} candidates:")
        for i, (threshold, score, metrics) in enumerate(ranked[:5]):  # Top 5
            logger.info(
                f"  {i+1}. Threshold {threshold:.3f}: score={score:.3f}, "
                f"precision={metrics.get('precision', 0):.3f}, "
                f"recall={metrics.get('recall', 0):.3f}"
            )

        return ranked

    def explain_score(
        self,
        threshold: float,
        metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Provide detailed breakdown of how a score was calculated

        Useful for debugging and explaining agent decisions
        """
        precision = metrics.get("precision", 0)
        recall = metrics.get("recall", 0)
        false_hit_rate = metrics.get("false_hit_rate", 1)
        cache_hit_rate = metrics.get("cache_hit_rate", 0)
        speedup_factor = metrics.get("speedup_factor", 1)

        # Recalculate component scores
        precision_score = max(0, min(1, precision * (1 - false_hit_rate * 2)))
        recall_score = recall
        cost_score = cache_hit_rate if precision >= 0.85 else 0
        latency_score = min(speedup_factor / 100, 1.0)

        total_score = (
            self.weights.precision * precision_score +
            self.weights.recall * recall_score +
            self.weights.cost_savings * cost_score +
            self.weights.latency * latency_score
        )

        return {
            "threshold": threshold,
            "total_score": round(total_score, 4),
            "components": {
                "precision": {
                    "raw_value": precision,
                    "component_score": round(precision_score, 4),
                    "weight": self.weights.precision,
                    "contribution": round(self.weights.precision * precision_score, 4),
                },
                "recall": {
                    "raw_value": recall,
                    "component_score": round(recall_score, 4),
                    "weight": self.weights.recall,
                    "contribution": round(self.weights.recall * recall_score, 4),
                },
                "cost_savings": {
                    "cache_hit_rate": cache_hit_rate,
                    "component_score": round(cost_score, 4),
                    "weight": self.weights.cost_savings,
                    "contribution": round(self.weights.cost_savings * cost_score, 4),
                },
                "latency": {
                    "speedup_factor": speedup_factor,
                    "component_score": round(latency_score, 4),
                    "weight": self.weights.latency,
                    "contribution": round(self.weights.latency * latency_score, 4),
                },
            },
            "input_metrics": metrics,
        }

    def get_weights_dict(self) -> Dict[str, float]:
        """Get current scoring weights as dictionary"""
        return {
            "precision": self.weights.precision,
            "recall": self.weights.recall,
            "cost_savings": self.weights.cost_savings,
            "latency": self.weights.latency,
        }
