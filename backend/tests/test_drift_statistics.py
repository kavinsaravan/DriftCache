"""Unit tests for the statistical signals used by drift detection."""

import numpy as np
import pytest

from app.drift.statistics import DriftStatistics


def test_centroid_shift_detects_direction_change():
    reference = [np.array([1.0, 0.0]), np.array([1.0, 0.0])]
    unchanged = [np.array([2.0, 0.0]), np.array([3.0, 0.0])]
    shifted = [np.array([0.0, 1.0]), np.array([0.0, 2.0])]

    assert DriftStatistics.calculate_centroid_shift(reference, unchanged) == pytest.approx(0.0)
    assert DriftStatistics.calculate_centroid_shift(reference, shifted) == pytest.approx(1.0)


def test_distribution_signals_distinguish_stable_and_shifted_samples():
    reference = [0.88, 0.89, 0.90, 0.91, 0.92]
    shifted = [0.55, 0.57, 0.59, 0.61, 0.63]

    ks_result = DriftStatistics.run_ks_test(reference, shifted)

    assert ks_result["statistic"] == pytest.approx(1.0)
    assert ks_result["p_value"] < 0.05
    assert DriftStatistics.calculate_similarity_drop(reference, shifted) == pytest.approx(0.31)


@pytest.mark.parametrize(
    ("score", "severity"),
    [(0.0, "low"), (0.25, "medium"), (0.5, "high"), (0.75, "critical")],
)
def test_drift_severity_boundaries(score, severity):
    assert DriftStatistics.classify_severity(score) == severity


def test_combined_drift_score_is_bounded():
    score = DriftStatistics.calculate_drift_score(
        centroid_shift=1.0,
        variance_shift=4.0,
        ks_p_value=0.0,
        similarity_drop=1.0,
        hit_rate_drop=1.0,
    )

    assert score == pytest.approx(1.0)

