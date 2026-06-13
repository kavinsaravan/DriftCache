"""
Evaluation Reports Module

Generates and manages cache quality evaluation reports
"""
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
import uuid
import logging

from app.evaluation.cache_quality import CacheQualityEvaluator, CacheQualityMetrics
from app.evaluation.datasets import EvaluationDataset, get_dataset
from app.models.evaluation_result import EvaluationResult

logger = logging.getLogger(__name__)


class EvaluationReportGenerator:
    """Generates and persists evaluation reports"""

    def __init__(self, session: Session):
        self.session = session

    def run_evaluation(
        self,
        dataset_name: str = "default",
        threshold: float = 0.90,
        tenant_id: Optional[str] = None,
        save_to_db: bool = True
    ) -> EvaluationResult:
        """
        Run cache quality evaluation and generate report

        Args:
            dataset_name: Which test dataset to use
            threshold: Similarity threshold to evaluate
            tenant_id: Optional tenant isolation
            save_to_db: Whether to persist results

        Returns:
            EvaluationResult with complete metrics
        """
        logger.info(
            f"Running evaluation: dataset={dataset_name}, "
            f"threshold={threshold}, tenant_id={tenant_id}"
        )

        # Load dataset
        dataset = get_dataset(dataset_name)

        # Create evaluator
        evaluator = CacheQualityEvaluator(threshold=threshold)

        # Run evaluation
        import time
        start_time = time.time()
        metrics = evaluator.evaluate(dataset, tenant_id=tenant_id)
        execution_time_ms = (time.time() - start_time) * 1000

        # Get recommendation
        recommendation = evaluator.recommend_threshold_adjustment(metrics)

        # Create evaluation result
        evaluation_run_id = f"eval_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        result = EvaluationResult(
            evaluation_run_id=evaluation_run_id,
            dataset_name=dataset.name,
            dataset_size=len(dataset),
            threshold_used=threshold,
            precision=metrics.precision,
            recall=metrics.recall,
            f1_score=metrics.f1_score,
            false_hit_rate=metrics.false_hit_rate,
            false_miss_rate=metrics.false_miss_rate,
            total_test_cases=metrics.total_test_cases,
            true_positives=metrics.true_positives,
            true_negatives=metrics.true_negatives,
            false_positives=metrics.false_positives,
            false_negatives=metrics.false_negatives,
            avg_hit_margin=metrics.avg_hit_margin,
            avg_hit_similarity=metrics.avg_hit_similarity,
            min_hit_similarity=metrics.min_hit_similarity,
            max_hit_similarity=metrics.max_hit_similarity,
            avg_miss_similarity=metrics.avg_miss_similarity,
            near_miss_count=metrics.near_miss_count,
            recommended_action=recommendation["action"],
            recommendation_confidence=recommendation["confidence"],
            recommendation_details=recommendation["details"],
            execution_time_ms=execution_time_ms,
            evaluation_type="rule_based",
            tenant_id=tenant_id
        )

        # Save to database
        if save_to_db:
            try:
                self.session.add(result)
                self.session.commit()
                self.session.refresh(result)
                logger.info(f"Saved evaluation result: {result.evaluation_run_id}")
            except Exception as e:
                logger.error(f"Failed to save evaluation result: {e}")
                self.session.rollback()
                raise

        return result

    def get_latest_evaluation(
        self,
        tenant_id: Optional[str] = None
    ) -> Optional[EvaluationResult]:
        """
        Get most recent evaluation result

        Args:
            tenant_id: Optional tenant isolation

        Returns:
            Latest EvaluationResult or None
        """
        query = self.session.query(EvaluationResult)

        if tenant_id:
            query = query.filter(EvaluationResult.tenant_id == tenant_id)

        result = query.order_by(EvaluationResult.created_at.desc()).first()

        return result

    def get_evaluation_history(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 50
    ) -> List[EvaluationResult]:
        """
        Get evaluation history

        Args:
            tenant_id: Optional tenant isolation
            limit: Maximum results to return

        Returns:
            List of EvaluationResult objects
        """
        query = self.session.query(EvaluationResult)

        if tenant_id:
            query = query.filter(EvaluationResult.tenant_id == tenant_id)

        results = query.order_by(EvaluationResult.created_at.desc()).limit(limit).all()

        return results

    def compare_evaluations(
        self,
        evaluation_ids: List[int]
    ) -> dict:
        """
        Compare multiple evaluation results

        Args:
            evaluation_ids: List of evaluation result IDs to compare

        Returns:
            Comparison dictionary
        """
        evaluations = self.session.query(EvaluationResult).filter(
            EvaluationResult.id.in_(evaluation_ids)
        ).all()

        if not evaluations:
            return {"error": "No evaluations found"}

        comparison = {
            "evaluations": [],
            "best_f1": None,
            "best_precision": None,
            "best_recall": None,
        }

        best_f1_score = 0
        best_precision = 0
        best_recall = 0

        for eval_result in evaluations:
            eval_data = {
                "id": eval_result.id,
                "run_id": eval_result.evaluation_run_id,
                "threshold": eval_result.threshold_used,
                "precision": eval_result.precision,
                "recall": eval_result.recall,
                "f1_score": eval_result.f1_score,
                "created_at": eval_result.created_at.isoformat()
            }
            comparison["evaluations"].append(eval_data)

            # Track best metrics
            if eval_result.f1_score > best_f1_score:
                best_f1_score = eval_result.f1_score
                comparison["best_f1"] = eval_data

            if eval_result.precision > best_precision:
                best_precision = eval_result.precision
                comparison["best_precision"] = eval_data

            if eval_result.recall > best_recall:
                best_recall = eval_result.recall
                comparison["best_recall"] = eval_data

        return comparison

    def analyze_threshold_trend(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 10
    ) -> dict:
        """
        Analyze how metrics change with different thresholds

        Args:
            tenant_id: Optional tenant isolation
            limit: Number of recent evaluations to analyze

        Returns:
            Trend analysis
        """
        evaluations = self.get_evaluation_history(tenant_id=tenant_id, limit=limit)

        if not evaluations:
            return {"error": "No evaluation history"}

        # Group by threshold
        threshold_groups = {}
        for eval_result in evaluations:
            threshold = round(eval_result.threshold_used, 2)
            if threshold not in threshold_groups:
                threshold_groups[threshold] = []
            threshold_groups[threshold].append({
                "precision": eval_result.precision,
                "recall": eval_result.recall,
                "f1_score": eval_result.f1_score,
            })

        # Calculate averages per threshold
        threshold_analysis = []
        for threshold, results in threshold_groups.items():
            avg_precision = sum(r["precision"] for r in results) / len(results)
            avg_recall = sum(r["recall"] for r in results) / len(results)
            avg_f1 = sum(r["f1_score"] for r in results) / len(results)

            threshold_analysis.append({
                "threshold": threshold,
                "avg_precision": round(avg_precision, 4),
                "avg_recall": round(avg_recall, 4),
                "avg_f1_score": round(avg_f1, 4),
                "sample_count": len(results)
            })

        # Sort by threshold
        threshold_analysis.sort(key=lambda x: x["threshold"])

        return {
            "threshold_analysis": threshold_analysis,
            "total_evaluations": len(evaluations),
            "threshold_range": [
                min(t["threshold"] for t in threshold_analysis),
                max(t["threshold"] for t in threshold_analysis)
            ]
        }


# Context manager for report generator
from contextlib import contextmanager


@contextmanager
def get_report_generator(session: Session):
    """
    Context manager for EvaluationReportGenerator

    Usage:
        with get_report_generator(session) as generator:
            result = generator.run_evaluation()
    """
    generator = EvaluationReportGenerator(session)
    try:
        yield generator
    finally:
        pass
