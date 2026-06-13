"""
Drift Statistics Module

Statistical methods for detecting embedding drift
"""
from typing import List, Dict
import numpy as np
from scipy import stats
from scipy.spatial.distance import cosine


class DriftStatistics:
    """Statistical functions for drift detection"""

    @staticmethod
    def calculate_centroid(embeddings: List[np.ndarray]) -> np.ndarray:
        """
        Calculate centroid (mean) of embedding vectors

        Args:
            embeddings: List of embedding vectors

        Returns:
            Centroid vector (mean across all embeddings)
        """
        if not embeddings:
            return np.array([])

        # Stack all embeddings and compute mean
        embedding_matrix = np.stack(embeddings)
        centroid = np.mean(embedding_matrix, axis=0)

        return centroid

    @staticmethod
    def calculate_centroid_shift(
        reference_embeddings: List[np.ndarray],
        recent_embeddings: List[np.ndarray]
    ) -> float:
        """
        Calculate cosine distance between reference and recent centroids

        Args:
            reference_embeddings: Baseline embeddings
            recent_embeddings: Recent embeddings

        Returns:
            Cosine distance between centroids (0-1, higher = more drift)
        """
        if not reference_embeddings or not recent_embeddings:
            return 0.0

        reference_centroid = DriftStatistics.calculate_centroid(reference_embeddings)
        recent_centroid = DriftStatistics.calculate_centroid(recent_embeddings)

        # Calculate cosine distance (1 - cosine similarity)
        distance = cosine(reference_centroid, recent_centroid)

        return float(distance)

    @staticmethod
    def calculate_variance(embeddings: List[np.ndarray]) -> float:
        """
        Calculate average variance across embedding dimensions

        Args:
            embeddings: List of embedding vectors

        Returns:
            Average variance across all dimensions
        """
        if not embeddings or len(embeddings) < 2:
            return 0.0

        embedding_matrix = np.stack(embeddings)
        # Calculate variance for each dimension
        variances = np.var(embedding_matrix, axis=0)
        # Return mean variance
        avg_variance = np.mean(variances)

        return float(avg_variance)

    @staticmethod
    def calculate_variance_shift(
        reference_embeddings: List[np.ndarray],
        recent_embeddings: List[np.ndarray]
    ) -> float:
        """
        Calculate relative change in variance

        Args:
            reference_embeddings: Baseline embeddings
            recent_embeddings: Recent embeddings

        Returns:
            Relative variance change (positive = increased spread)
        """
        reference_variance = DriftStatistics.calculate_variance(reference_embeddings)
        recent_variance = DriftStatistics.calculate_variance(recent_embeddings)

        if reference_variance == 0:
            return 0.0

        # Calculate relative change
        variance_shift = (recent_variance - reference_variance) / reference_variance

        return float(variance_shift)

    @staticmethod
    def run_ks_test(
        reference_scores: List[float],
        recent_scores: List[float]
    ) -> Dict[str, float]:
        """
        Run Kolmogorov-Smirnov test on similarity score distributions

        Args:
            reference_scores: Reference similarity scores
            recent_scores: Recent similarity scores

        Returns:
            Dict with 'statistic' and 'p_value'
            Low p-value (< 0.05) indicates distributions differ significantly
        """
        if not reference_scores or not recent_scores:
            return {"statistic": 0.0, "p_value": 1.0}

        if len(reference_scores) < 2 or len(recent_scores) < 2:
            return {"statistic": 0.0, "p_value": 1.0}

        # Run two-sample KS test
        statistic, p_value = stats.ks_2samp(reference_scores, recent_scores)

        return {
            "statistic": float(statistic),
            "p_value": float(p_value)
        }

    @staticmethod
    def calculate_similarity_drop(
        reference_scores: List[float],
        recent_scores: List[float]
    ) -> float:
        """
        Calculate drop in average similarity score

        Args:
            reference_scores: Reference similarity scores
            recent_scores: Recent similarity scores

        Returns:
            Difference in mean similarity (positive = recent scores are lower)
        """
        if not reference_scores or not recent_scores:
            return 0.0

        reference_mean = np.mean(reference_scores)
        recent_mean = np.mean(recent_scores)

        # Positive value means recent similarities are lower
        similarity_drop = reference_mean - recent_mean

        return float(similarity_drop)

    @staticmethod
    def calculate_distribution_distance(
        reference_embeddings: List[np.ndarray],
        recent_embeddings: List[np.ndarray],
        method: str = "wasserstein"
    ) -> float:
        """
        Calculate distance between embedding distributions

        Args:
            reference_embeddings: Baseline embeddings
            recent_embeddings: Recent embeddings
            method: Distance metric ('wasserstein' or 'hellinger')

        Returns:
            Distribution distance (higher = more drift)
        """
        if not reference_embeddings or not recent_embeddings:
            return 0.0

        # For simplicity, calculate distance on first principal component
        # (In production, you'd use full dimensionality reduction)

        # Flatten to 1D by taking norm of each embedding
        reference_norms = [np.linalg.norm(emb) for emb in reference_embeddings]
        recent_norms = [np.linalg.norm(emb) for emb in recent_embeddings]

        if method == "wasserstein":
            # Wasserstein distance (Earth Mover's Distance)
            distance = stats.wasserstein_distance(reference_norms, recent_norms)
        else:
            # Default to simple mean difference
            distance = abs(np.mean(reference_norms) - np.mean(recent_norms))

        return float(distance)

    @staticmethod
    def calculate_percentile_shift(
        reference_scores: List[float],
        recent_scores: List[float],
        percentiles: List[int] = [50, 75, 90, 95]
    ) -> Dict[str, float]:
        """
        Calculate shift in similarity score percentiles

        Args:
            reference_scores: Reference similarity scores
            recent_scores: Recent similarity scores
            percentiles: Which percentiles to compare

        Returns:
            Dict mapping percentile to shift amount
        """
        if not reference_scores or not recent_scores:
            return {}

        shifts = {}
        for p in percentiles:
            ref_value = np.percentile(reference_scores, p)
            recent_value = np.percentile(recent_scores, p)
            shifts[f"p{p}_shift"] = float(ref_value - recent_value)

        return shifts

    @staticmethod
    def calculate_drift_score(
        centroid_shift: float,
        variance_shift: float,
        ks_p_value: float,
        similarity_drop: float,
        hit_rate_drop: float
    ) -> float:
        """
        Combine multiple drift signals into single score

        Args:
            centroid_shift: Centroid distance (0-1)
            variance_shift: Variance change ratio
            ks_p_value: KS test p-value
            similarity_drop: Mean similarity decrease
            hit_rate_drop: Cache hit rate decrease

        Returns:
            Combined drift score (0-1, higher = more drift)
        """
        # Weighted combination of signals
        # These weights can be tuned based on your use case

        # Centroid shift (weight: 0.3)
        centroid_component = min(centroid_shift * 3.0, 1.0) * 0.3

        # Variance shift (weight: 0.2)
        # Normalize to 0-1 range
        variance_component = min(abs(variance_shift), 1.0) * 0.2

        # KS test significance (weight: 0.2)
        # Low p-value means significant drift
        ks_component = (1.0 - ks_p_value) * 0.2

        # Similarity drop (weight: 0.15)
        # Normalize assuming max drop is 0.2
        similarity_component = min(similarity_drop / 0.2, 1.0) * 0.15

        # Hit rate drop (weight: 0.15)
        # Normalize assuming max drop is 0.3 (30%)
        hit_rate_component = min(hit_rate_drop / 0.3, 1.0) * 0.15

        # Sum components
        drift_score = (
            centroid_component +
            variance_component +
            ks_component +
            similarity_component +
            hit_rate_component
        )

        # Clamp to [0, 1]
        return max(0.0, min(1.0, drift_score))

    @staticmethod
    def classify_severity(drift_score: float) -> str:
        """
        Classify drift severity based on score

        Args:
            drift_score: Combined drift score (0-1)

        Returns:
            Severity level: 'low', 'medium', 'high', or 'critical'
        """
        if drift_score < 0.25:
            return "low"
        elif drift_score < 0.50:
            return "medium"
        elif drift_score < 0.75:
            return "high"
        else:
            return "critical"

    @staticmethod
    def recommend_action(
        drift_score: float,
        centroid_shift: float,
        variance_shift: float,
        similarity_drop: float
    ) -> str:
        """
        Recommend action based on drift pattern

        Args:
            drift_score: Overall drift score
            centroid_shift: Centroid movement
            variance_shift: Variance change
            similarity_drop: Similarity decrease

        Returns:
            Recommended action string
        """
        if drift_score < 0.25:
            return "monitor"

        # High centroid shift = semantic topic change
        if centroid_shift > 0.3:
            return "rebuild_index_with_recent_data"

        # High variance increase = more diverse queries
        if variance_shift > 0.5:
            return "lower_similarity_threshold"

        # High similarity drop = cache less effective
        if similarity_drop > 0.15:
            return "increase_cache_ttl_or_rebuild"

        # Default moderate drift
        if drift_score < 0.50:
            return "monitor_closely"
        elif drift_score < 0.75:
            return "adjust_threshold_or_retrain"
        else:
            return "urgent_rebuild_required"
