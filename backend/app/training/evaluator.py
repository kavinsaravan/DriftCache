"""
Model Evaluation Module

Evaluates fine-tuned embedding models using standard IR metrics:
- Precision@K
- Recall@K
- Mean Reciprocal Rank (MRR)
- Normalized Discounted Cumulative Gain (NDCG)
"""
import logging
from typing import List, Dict, Any, Tuple
import numpy as np
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer
import time

from app.models.training_pair import TrainingPair, PairType
from app.embeddings.utils import list_to_vector

logger = logging.getLogger(__name__)


class ModelEvaluator:
    """
    Evaluates embedding model performance on test data
    """

    def __init__(self, model: SentenceTransformer):
        """
        Initialize evaluator

        Args:
            model: Sentence transformer model to evaluate
        """
        self.model = model

    def compute_precision_at_k(
        self,
        predictions: List[int],
        ground_truth: List[int],
        k: int
    ) -> float:
        """
        Compute Precision@K

        Args:
            predictions: Ranked list of predicted item indices
            ground_truth: List of relevant item indices
            k: Cutoff rank

        Returns:
            Precision at rank K
        """
        if k == 0:
            return 0.0

        # Get top K predictions
        top_k_preds = predictions[:k]

        # Count how many are relevant
        num_relevant = sum(1 for pred in top_k_preds if pred in ground_truth)

        return num_relevant / k

    def compute_recall_at_k(
        self,
        predictions: List[int],
        ground_truth: List[int],
        k: int
    ) -> float:
        """
        Compute Recall@K

        Args:
            predictions: Ranked list of predicted item indices
            ground_truth: List of relevant item indices
            k: Cutoff rank

        Returns:
            Recall at rank K
        """
        if len(ground_truth) == 0:
            return 0.0

        # Get top K predictions
        top_k_preds = predictions[:k]

        # Count how many relevant items were retrieved
        num_retrieved = sum(1 for pred in top_k_preds if pred in ground_truth)

        return num_retrieved / len(ground_truth)

    def compute_mrr(
        self,
        predictions: List[int],
        ground_truth: List[int]
    ) -> float:
        """
        Compute Mean Reciprocal Rank

        Args:
            predictions: Ranked list of predicted item indices
            ground_truth: List of relevant item indices

        Returns:
            Reciprocal rank of first relevant item
        """
        for rank, pred in enumerate(predictions, start=1):
            if pred in ground_truth:
                return 1.0 / rank

        return 0.0

    def compute_ndcg(
        self,
        predictions: List[int],
        ground_truth: List[int],
        k: int
    ) -> float:
        """
        Compute Normalized Discounted Cumulative Gain

        Args:
            predictions: Ranked list of predicted item indices
            ground_truth: List of relevant item indices
            k: Cutoff rank

        Returns:
            NDCG at rank K
        """
        # Get top K predictions
        top_k_preds = predictions[:k]

        # Compute DCG
        dcg = 0.0
        for rank, pred in enumerate(top_k_preds, start=1):
            if pred in ground_truth:
                # Relevance = 1 if in ground truth
                dcg += 1.0 / np.log2(rank + 1)

        # Compute ideal DCG (best possible ranking)
        num_relevant = min(len(ground_truth), k)
        idcg = sum(1.0 / np.log2(rank + 1) for rank in range(1, num_relevant + 1))

        if idcg == 0:
            return 0.0

        return dcg / idcg

    def evaluate_on_test_set(
        self,
        db: Session,
        test_size: int = 200,
        k_values: List[int] = [1, 5, 10]
    ) -> Dict[str, Any]:
        """
        Evaluate model on test set from database

        Args:
            db: Database session
            test_size: Number of test queries
            k_values: K values for precision/recall/NDCG

        Returns:
            Dictionary with evaluation metrics
        """
        logger.info(f"Evaluating model on test set (size={test_size})")

        # Get test pairs (use positive pairs as ground truth)
        test_pairs = db.query(TrainingPair).filter(
            TrainingPair.pair_type == PairType.POSITIVE
        ).limit(test_size).all()

        if not test_pairs:
            raise ValueError("No test pairs found")

        logger.info(f"Loaded {len(test_pairs)} test pairs")

        # Track metrics
        precisions = {k: [] for k in k_values}
        recalls = {k: [] for k in k_values}
        ndcgs = {k: [] for k in k_values}
        mrrs = []

        # Track similarity scores
        positive_similarities = []
        negative_similarities = []

        # Track latency
        latencies = []

        # Evaluate each query
        for i, pair in enumerate(test_pairs):
            if i % 50 == 0:
                logger.info(f"Evaluated {i}/{len(test_pairs)} queries")

            # Measure latency
            start_time = time.time()

            # Encode query
            query_emb = self.model.encode(
                pair.anchor_text,
                convert_to_numpy=True,
                normalize_embeddings=True
            )

            # Encode all candidates (for simplicity, use other test pairs)
            candidate_texts = [p.comparison_text for p in test_pairs]
            candidate_embs = self.model.encode(
                candidate_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False
            )

            # Compute similarities
            similarities = np.dot(candidate_embs, query_emb)

            # Rank candidates by similarity
            ranked_indices = np.argsort(similarities)[::-1].tolist()

            latency = (time.time() - start_time) * 1000  # Convert to ms
            latencies.append(latency)

            # Ground truth: the matching pair
            ground_truth = [i]  # Index of the matching pair

            # Compute metrics for each K
            for k in k_values:
                precisions[k].append(
                    self.compute_precision_at_k(ranked_indices, ground_truth, k)
                )
                recalls[k].append(
                    self.compute_recall_at_k(ranked_indices, ground_truth, k)
                )
                ndcgs[k].append(
                    self.compute_ndcg(ranked_indices, ground_truth, k)
                )

            # Compute MRR
            mrrs.append(self.compute_mrr(ranked_indices, ground_truth))

            # Track similarity for positive pair
            positive_sim = similarities[i]
            positive_similarities.append(positive_sim)

            # Track average similarity for negatives
            negative_sims = [similarities[j] for j in range(len(similarities)) if j != i]
            if negative_sims:
                negative_similarities.append(np.mean(negative_sims))

        # Aggregate metrics
        metrics = {
            "precision_at_1": np.mean(precisions[1]),
            "precision_at_5": np.mean(precisions[5]) if 5 in k_values else None,
            "precision_at_10": np.mean(precisions[10]) if 10 in k_values else None,
            "recall_at_1": np.mean(recalls[1]),
            "recall_at_5": np.mean(recalls[5]) if 5 in k_values else None,
            "recall_at_10": np.mean(recalls[10]) if 10 in k_values else None,
            "mrr": np.mean(mrrs),
            "ndcg": np.mean(ndcgs[5]) if 5 in k_values else np.mean(ndcgs[1]),
            "avg_similarity_positive": np.mean(positive_similarities),
            "avg_similarity_negative": np.mean(negative_similarities),
            "avg_latency_ms": np.mean(latencies),
            "test_set_size": len(test_pairs),
        }

        logger.info("Evaluation complete")
        logger.info(f"Metrics: {metrics}")

        return metrics

    def compare_models(
        self,
        baseline_model: SentenceTransformer,
        db: Session,
        test_size: int = 200
    ) -> Dict[str, Any]:
        """
        Compare this model against a baseline

        Args:
            baseline_model: Baseline model to compare against
            db: Database session
            test_size: Size of test set

        Returns:
            Dictionary with comparison results
        """
        logger.info("Comparing models")

        # Evaluate baseline
        baseline_evaluator = ModelEvaluator(baseline_model)
        baseline_metrics = baseline_evaluator.evaluate_on_test_set(db, test_size)

        # Evaluate this model
        finetuned_metrics = self.evaluate_on_test_set(db, test_size)

        # Compute improvements
        improvements = {}
        for metric_name in baseline_metrics:
            if metric_name == "test_set_size":
                continue

            baseline_val = baseline_metrics[metric_name]
            finetuned_val = finetuned_metrics[metric_name]

            if baseline_val is not None and finetuned_val is not None:
                if baseline_val > 0:
                    improvement_pct = ((finetuned_val - baseline_val) / baseline_val) * 100
                    improvements[f"{metric_name}_improvement_pct"] = improvement_pct

        result = {
            "baseline_metrics": baseline_metrics,
            "finetuned_metrics": finetuned_metrics,
            "improvements": improvements,
        }

        logger.info(f"Model comparison complete: {improvements}")

        return result
