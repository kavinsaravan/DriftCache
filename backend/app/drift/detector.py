"""Small, deterministic detector for cache-similarity distribution drift."""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import ks_2samp, wasserstein_distance

from app.drift.schemas import DriftConfig, DriftReport, SimilaritySamples


class SimilarityDriftDetector:
    """Compare reference and recent score distributions with explainable tests."""

    def __init__(self, config: DriftConfig | None = None):
        self.config = config or DriftConfig()

    def detect(
        self,
        reference: SimilaritySamples,
        recent: SimilaritySamples,
    ) -> DriftReport:
        if (
            len(reference.scores) < self.config.minimum_samples
            or len(recent.scores) < self.config.minimum_samples
        ):
            return self._insufficient_report(reference, recent)

        reference_scores = np.asarray(reference.scores, dtype=np.float64)
        recent_scores = np.asarray(recent.scores, dtype=np.float64)

        ks_result = ks_2samp(reference_scores, recent_scores, method="auto")
        distance = float(wasserstein_distance(reference_scores, recent_scores))
        reference_mean = float(np.mean(reference_scores))
        recent_mean = float(np.mean(recent_scores))
        mean_shift = recent_mean - reference_mean
        reference_variance = float(np.var(reference_scores))
        recent_variance = float(np.var(recent_scores))
        variance_ratio = self._variance_ratio(reference_variance, recent_variance)

        effects: list[str] = []
        if distance >= self.config.wasserstein_threshold:
            effects.append(
                f"Wasserstein distance {distance:.3f} exceeds "
                f"{self.config.wasserstein_threshold:.3f}"
            )
        if abs(mean_shift) >= self.config.mean_shift_threshold:
            effects.append(
                f"Mean similarity shifted by {mean_shift:+.3f}, exceeding "
                f"±{self.config.mean_shift_threshold:.3f}"
            )
        if not (
            self.config.variance_ratio_lower
            <= variance_ratio
            <= self.config.variance_ratio_upper
        ):
            effects.append(
                f"Variance ratio {variance_ratio:.3f} is outside "
                f"[{self.config.variance_ratio_lower:.3f}, "
                f"{self.config.variance_ratio_upper:.3f}]"
            )

        statistically_significant = float(ks_result.pvalue) < self.config.significance_level
        drift_detected = statistically_significant and bool(effects)
        if drift_detected:
            reasons = [
                f"KS test p-value {float(ks_result.pvalue):.4g} is below "
                f"{self.config.significance_level:.3f}",
                *effects,
            ]
        elif effects:
            reasons = [
                "Effect-size thresholds were crossed, but the KS test was not significant; "
                "continue monitoring"
            ]
        else:
            reasons = ["No statistically significant similarity-distribution shift detected"]

        drift_score = self._score(float(ks_result.pvalue), distance, mean_shift, variance_ratio)
        severity = self._severity(drift_detected, drift_score)

        return DriftReport(
            status="drift_detected" if drift_detected else "stable",
            drift_detected=drift_detected,
            severity=severity,
            drift_score=drift_score,
            reference_sample_size=len(reference.scores),
            recent_sample_size=len(recent.scores),
            reference_window_start=reference.start,
            reference_window_end=reference.end,
            recent_window_start=recent.start,
            recent_window_end=recent.end,
            ks_statistic=float(ks_result.statistic),
            ks_p_value=float(ks_result.pvalue),
            wasserstein_distance=distance,
            reference_mean=reference_mean,
            recent_mean=recent_mean,
            mean_shift=mean_shift,
            reference_variance=reference_variance,
            recent_variance=recent_variance,
            variance_ratio=variance_ratio,
            reasons=reasons,
        )

    @staticmethod
    def _variance_ratio(reference_variance: float, recent_variance: float) -> float:
        epsilon = 1e-12
        if reference_variance <= epsilon and recent_variance <= epsilon:
            return 1.0
        return float((recent_variance + epsilon) / (reference_variance + epsilon))

    def _score(
        self,
        ks_p_value: float,
        distance: float,
        mean_shift: float,
        variance_ratio: float,
    ) -> float:
        ks_strength = max(
            0.0,
            1.0 - (ks_p_value / self.config.significance_level),
        )
        distance_strength = min(1.0, distance / self.config.wasserstein_threshold)
        mean_strength = min(1.0, abs(mean_shift) / self.config.mean_shift_threshold)
        if variance_ratio <= 0:
            variance_strength = 1.0
        else:
            variance_strength = min(
                1.0,
                abs(math.log(variance_ratio))
                / max(abs(math.log(self.config.variance_ratio_lower)), math.log(self.config.variance_ratio_upper)),
            )
        effect_strength = max(distance_strength, mean_strength, variance_strength)
        return float(min(1.0, max(0.0, 0.5 * ks_strength + 0.5 * effect_strength)))

    @staticmethod
    def _severity(drift_detected: bool, drift_score: float) -> str:
        if not drift_detected:
            return "none"
        if drift_score < 0.5:
            return "low"
        if drift_score < 0.75:
            return "medium"
        return "high"

    @staticmethod
    def _insufficient_report(
        reference: SimilaritySamples,
        recent: SimilaritySamples,
    ) -> DriftReport:
        return DriftReport(
            status="insufficient_data",
            drift_detected=False,
            severity="none",
            drift_score=0.0,
            reference_sample_size=len(reference.scores),
            recent_sample_size=len(recent.scores),
            reference_window_start=reference.start,
            reference_window_end=reference.end,
            recent_window_start=recent.start,
            recent_window_end=recent.end,
            ks_statistic=0.0,
            ks_p_value=1.0,
            wasserstein_distance=0.0,
            reference_mean=0.0,
            recent_mean=0.0,
            mean_shift=0.0,
            reference_variance=0.0,
            recent_variance=0.0,
            variance_ratio=1.0,
            reasons=["Both windows need the configured minimum number of similarity scores"],
        )
