"""
Evaluation Judges Module

Different methods to judge cache quality
"""
from dataclasses import dataclass
import logging

from app.evaluation.datasets import PromptPair, EquivalenceLabel

logger = logging.getLogger(__name__)


@dataclass
class JudgmentResult:
    """Result of judging a cache decision"""
    is_correct: bool
    predicted_label: EquivalenceLabel
    true_label: EquivalenceLabel
    confidence: float
    similarity_score: float
    threshold_margin: float
    notes: str = ""


class RuleBasedJudge:
    """
    Rule-based cache quality judge

    Uses similarity scores and thresholds to judge decisions
    Fast and deterministic
    """

    def __init__(self, threshold: float = 0.90):
        self.threshold = threshold

    def judge_decision(
        self,
        pair: PromptPair,
        similarity_score: float
    ) -> JudgmentResult:
        """
        Judge whether cache decision was correct

        Args:
            pair: Test prompt pair with ground truth label
            similarity_score: Computed similarity between prompts

        Returns:
            JudgmentResult with correctness assessment
        """
        # Cache system's prediction based on threshold
        cache_would_hit = similarity_score >= self.threshold

        if cache_would_hit:
            predicted_label = EquivalenceLabel.EQUIVALENT
        else:
            predicted_label = EquivalenceLabel.NOT_EQUIVALENT

        # Check against ground truth
        true_label = pair.label
        is_correct = (predicted_label == true_label)

        # Calculate margin and confidence
        threshold_margin = similarity_score - self.threshold
        confidence = self._calculate_confidence(similarity_score, threshold_margin)

        # Generate notes
        notes = self._generate_notes(
            is_correct, cache_would_hit, similarity_score, threshold_margin
        )

        return JudgmentResult(
            is_correct=is_correct,
            predicted_label=predicted_label,
            true_label=true_label,
            confidence=confidence,
            similarity_score=similarity_score,
            threshold_margin=threshold_margin,
            notes=notes
        )

    def _calculate_confidence(
        self,
        similarity_score: float,
        threshold_margin: float
    ) -> float:
        """
        Calculate confidence in the decision

        Decisions far from threshold are more confident
        """
        # Confidence based on distance from threshold
        margin_abs = abs(threshold_margin)

        # Map margin to confidence (0.5 - 1.0)
        # margin 0 -> confidence 0.5 (uncertain)
        # margin 0.1 -> confidence 0.95
        # margin 0.2+ -> confidence 1.0
        confidence = 0.5 + min(margin_abs / 0.2, 0.5)

        return confidence

    def _generate_notes(
        self,
        is_correct: bool,
        cache_would_hit: bool,
        similarity_score: float,
        threshold_margin: float
    ) -> str:
        """Generate human-readable notes about the judgment"""
        if is_correct:
            if cache_would_hit:
                if threshold_margin < 0.02:
                    return f"Correct HIT but weak (margin={threshold_margin:.3f})"
                else:
                    return f"Correct HIT with good margin (margin={threshold_margin:.3f})"
            else:
                if abs(threshold_margin) < 0.02:
                    return f"Correct MISS but close (margin={threshold_margin:.3f})"
                else:
                    return f"Correct MISS, well below threshold"
        else:
            if cache_would_hit:
                # False positive (bad cache hit)
                return f"FALSE HIT - cached when shouldn't (sim={similarity_score:.3f})"
            else:
                # False negative (missed opportunity)
                return f"FALSE MISS - missed caching opportunity (sim={similarity_score:.3f})"
