"""
Cache Quality Evaluator

Evaluates whether semantic cache decisions are reliable
"""
from typing import List, Dict, Optional
import time
import logging
import numpy as np

from app.evaluation.datasets import EvaluationDataset, PromptPair, EquivalenceLabel
from app.evaluation.judges import RuleBasedJudge, JudgmentResult
from app.cache.embeddings import get_embedding_service

logger = logging.getLogger(__name__)


class CacheQualityMetrics:
    """Container for evaluation metrics"""

    def __init__(
        self,
        total_test_cases: int,
        true_positives: int,
        true_negatives: int,
        false_positives: int,
        false_negatives: int,
        threshold_used: float,
        hit_similarities: List[float],
        miss_similarities: List[float],
        hit_margins: List[float]
    ):
        self.total_test_cases = total_test_cases
        self.true_positives = true_positives
        self.true_negatives = true_negatives
        self.false_positives = false_positives
        self.false_negatives = false_negatives
        self.threshold_used = threshold_used

        # Calculate core metrics
        total_hits = true_positives + false_positives
        total_reusable = true_positives + false_negatives

        self.precision = true_positives / total_hits if total_hits > 0 else 0.0
        self.recall = true_positives / total_reusable if total_reusable > 0 else 0.0

        # F1 score (harmonic mean of precision and recall)
        if self.precision + self.recall > 0:
            self.f1_score = 2 * (self.precision * self.recall) / (self.precision + self.recall)
        else:
            self.f1_score = 0.0

        # Error rates
        self.false_hit_rate = false_positives / total_hits if total_hits > 0 else 0.0
        self.false_miss_rate = false_negatives / total_reusable if total_reusable > 0 else 0.0

        # Hit quality metrics
        self.avg_hit_similarity = np.mean(hit_similarities) if hit_similarities else 0.0
        self.min_hit_similarity = min(hit_similarities) if hit_similarities else 0.0
        self.max_hit_similarity = max(hit_similarities) if hit_similarities else 0.0
        self.avg_hit_margin = np.mean(hit_margins) if hit_margins else 0.0

        # Miss analysis
        self.avg_miss_similarity = np.mean(miss_similarities) if miss_similarities else 0.0
        self.near_miss_count = sum(1 for sim in miss_similarities if abs(sim - threshold_used) < 0.05)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "threshold": round(self.threshold_used, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "false_hit_rate": round(self.false_hit_rate, 4),
            "false_miss_rate": round(self.false_miss_rate, 4),
            "total_test_cases": self.total_test_cases,
            "true_positives": self.true_positives,
            "true_negatives": self.true_negatives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "hit_quality": {
                "avg_similarity": round(self.avg_hit_similarity, 4),
                "min_similarity": round(self.min_hit_similarity, 4),
                "max_similarity": round(self.max_hit_similarity, 4),
                "avg_margin": round(self.avg_hit_margin, 4),
            },
            "miss_analysis": {
                "avg_similarity": round(self.avg_miss_similarity, 4),
                "near_misses": self.near_miss_count,
            }
        }


class CacheQualityEvaluator:
    """Evaluates cache decision quality on test datasets"""

    def __init__(self, threshold: float = 0.90):
        self.threshold = threshold
        self.embedding_service = get_embedding_service()
        self.judge = RuleBasedJudge(threshold=threshold)

    def evaluate(
        self,
        dataset: EvaluationDataset,
        tenant_id: Optional[str] = None
    ) -> CacheQualityMetrics:
        """
        Run complete evaluation on dataset

        Args:
            dataset: Test dataset with ground truth labels
            tenant_id: Optional tenant isolation

        Returns:
            CacheQualityMetrics with all evaluation results
        """
        logger.info(f"Starting evaluation on dataset '{dataset.name}' with {len(dataset)} pairs")
        start_time = time.time()

        # Track results
        true_positives = 0
        true_negatives = 0
        false_positives = 0
        false_negatives = 0

        hit_similarities = []
        miss_similarities = []
        hit_margins = []

        judgments: List[JudgmentResult] = []

        # Evaluate each pair
        for pair in dataset.pairs:
            # Get embeddings for both prompts
            embedding_a = self.embedding_service.get_embedding(pair.prompt_a)
            embedding_b = self.embedding_service.get_embedding(pair.prompt_b)

            # Calculate similarity
            similarity_score = self._cosine_similarity(embedding_a, embedding_b)

            # Judge the decision
            judgment = self.judge.judge_decision(pair, similarity_score)
            judgments.append(judgment)

            # Track decision outcome
            cache_would_hit = similarity_score >= self.threshold

            if judgment.is_correct:
                if cache_would_hit:
                    true_positives += 1
                    hit_similarities.append(similarity_score)
                    hit_margins.append(judgment.threshold_margin)
                else:
                    true_negatives += 1
                    miss_similarities.append(similarity_score)
            else:
                if cache_would_hit:
                    # False positive (bad cache hit)
                    false_positives += 1
                    hit_similarities.append(similarity_score)
                    hit_margins.append(judgment.threshold_margin)
                    logger.warning(f"False HIT: '{pair.prompt_a}' vs '{pair.prompt_b}' (sim={similarity_score:.3f})")
                else:
                    # False negative (missed opportunity)
                    false_negatives += 1
                    miss_similarities.append(similarity_score)
                    logger.info(f"False MISS: '{pair.prompt_a}' vs '{pair.prompt_b}' (sim={similarity_score:.3f})")

        # Create metrics object
        metrics = CacheQualityMetrics(
            total_test_cases=len(dataset),
            true_positives=true_positives,
            true_negatives=true_negatives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            threshold_used=self.threshold,
            hit_similarities=hit_similarities,
            miss_similarities=miss_similarities,
            hit_margins=hit_margins
        )

        execution_time = (time.time() - start_time) * 1000  # ms
        logger.info(
            f"Evaluation complete: precision={metrics.precision:.3f}, "
            f"recall={metrics.recall:.3f}, f1={metrics.f1_score:.3f} "
            f"({execution_time:.1f}ms)"
        )

        return metrics

    def _cosine_similarity(self, embedding_a: List[float], embedding_b: List[float]) -> float:
        """Calculate cosine similarity between two embeddings"""
        vec_a = np.array(embedding_a)
        vec_b = np.array(embedding_b)

        dot_product = np.dot(vec_a, vec_b)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        similarity = dot_product / (norm_a * norm_b)
        return float(similarity)

    def evaluate_threshold_sweep(
        self,
        dataset: EvaluationDataset,
        thresholds: List[float],
        tenant_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Evaluate multiple thresholds to find optimal setting

        Args:
            dataset: Test dataset
            thresholds: List of thresholds to test
            tenant_id: Optional tenant isolation

        Returns:
            List of metrics for each threshold
        """
        logger.info(f"Running threshold sweep with {len(thresholds)} thresholds")
        results = []

        for threshold in thresholds:
            # Create evaluator with this threshold
            evaluator = CacheQualityEvaluator(threshold=threshold)
            metrics = evaluator.evaluate(dataset, tenant_id=tenant_id)

            result = metrics.to_dict()
            result["threshold"] = threshold
            results.append(result)

        # Find best threshold (highest F1 score)
        best_result = max(results, key=lambda r: r["f1_score"])
        logger.info(
            f"Best threshold: {best_result['threshold']} "
            f"(F1={best_result['f1_score']:.3f})"
        )

        return results

    def recommend_threshold_adjustment(
        self,
        metrics: CacheQualityMetrics
    ) -> Dict:
        """
        Recommend threshold adjustment based on metrics

        Args:
            metrics: Current evaluation metrics

        Returns:
            Dict with recommendation and confidence
        """
        precision = metrics.precision
        recall = metrics.recall
        false_hit_rate = metrics.false_hit_rate
        false_miss_rate = metrics.false_miss_rate
        avg_hit_margin = metrics.avg_hit_margin

        # Decision logic
        if false_hit_rate > 0.1:
            # Too many bad cache hits - dangerous
            action = "increase_threshold"
            confidence = min(false_hit_rate * 2, 1.0)
            details = f"High false hit rate ({false_hit_rate:.1%}) risks serving wrong answers. Increase threshold to improve precision."

        elif false_miss_rate > 0.4 and false_hit_rate < 0.05:
            # Missing too many opportunities, but precision is good
            action = "decrease_threshold"
            confidence = min(false_miss_rate, 1.0)
            details = f"High false miss rate ({false_miss_rate:.1%}) means missing savings. Decrease threshold to improve recall."

        elif avg_hit_margin < 0.02:
            # Hits are barely above threshold - risky
            action = "increase_threshold_slightly"
            confidence = 0.6
            details = f"Cache hits have weak margins (avg={avg_hit_margin:.3f}). Slight increase would improve confidence."

        elif precision > 0.95 and recall < 0.7:
            # Very high precision but low recall - room to improve
            action = "decrease_threshold_slightly"
            confidence = 0.7
            details = f"Excellent precision ({precision:.1%}) with room to improve recall ({recall:.1%}). Can safely decrease threshold."

        elif precision > 0.9 and recall > 0.8:
            # Well balanced
            action = "keep_current_threshold"
            confidence = 0.9
            details = f"Well balanced: precision={precision:.1%}, recall={recall:.1%}. Current threshold is optimal."

        else:
            # Moderate performance
            action = "monitor"
            confidence = 0.5
            details = f"Moderate performance: precision={precision:.1%}, recall={recall:.1%}. Continue monitoring."

        return {
            "action": action,
            "confidence": confidence,
            "details": details,
            "current_metrics": {
                "precision": precision,
                "recall": recall,
                "f1_score": metrics.f1_score
            }
        }
