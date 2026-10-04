"""Tests for threshold evaluation and candidate selection."""

import pytest

from app.optimization.policy import OptimizationConstraints, OptimizationPolicy
from app.optimization.threshold_search import ThresholdSearcher


@pytest.fixture
def evaluation_pairs():
    return [
        {"similarity": 0.95, "should_cache": True},
        {"similarity": 0.85, "should_cache": True},
        {"similarity": 0.92, "should_cache": False},
        {"similarity": 0.40, "should_cache": False},
    ]


def test_threshold_evaluation_counts_false_hits_and_misses(evaluation_pairs):
    metrics = ThresholdSearcher()._evaluate_threshold(0.90, evaluation_pairs)

    assert metrics["true_positives"] == 1
    assert metrics["false_positives"] == 1
    assert metrics["true_negatives"] == 1
    assert metrics["false_negatives"] == 1
    assert metrics["precision"] == pytest.approx(0.5)
    assert metrics["recall"] == pytest.approx(0.5)


def test_higher_threshold_removes_false_hit(evaluation_pairs):
    metrics = ThresholdSearcher()._evaluate_threshold(0.93, evaluation_pairs)

    assert metrics["false_positives"] == 0
    assert metrics["precision"] == pytest.approx(1.0)
    assert metrics["recall"] == pytest.approx(0.5)


def test_candidate_selection_honors_safety_bounds():
    policy = OptimizationPolicy(
        OptimizationConstraints(min_threshold=0.80, max_threshold=0.90)
    )

    candidates = policy.get_candidate_thresholds(
        current_threshold=0.89,
        false_hit_rate=0.20,
    )

    assert candidates
    assert all(0.80 <= candidate <= 0.90 for candidate in candidates)
    assert candidates == sorted(set(candidates))

