"""
Evaluation Judges Module

Different methods to judge cache quality
"""
from typing import Dict, Optional
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
        # margin 0 → confidence 0.5 (uncertain)
        # margin 0.1 → confidence 0.95
        # margin 0.2+ → confidence 1.0
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


class LLMJudge:
    """
    LLM-as-a-judge for cache quality

    Uses an LLM to evaluate whether a cached response is appropriate
    More expensive but more accurate

    This is a placeholder for future implementation
    """

    def __init__(self, model_name: str = "gpt-4"):
        self.model_name = model_name
        logger.warning("LLMJudge is not yet implemented - falling back to rule-based")

    def judge_with_response(
        self,
        prompt_a: str,
        prompt_b: str,
        cached_response: str
    ) -> Dict:
        """
        Judge whether cached_response is appropriate for prompt_b

        Args:
            prompt_a: Original prompt that generated cached response
            prompt_b: New prompt being evaluated
            cached_response: The cached response from prompt_a

        Returns:
            Dict with judgment results

        Future implementation would:
        1. Send prompt to LLM: "Is this cached answer valid for the new question?"
        2. Parse LLM's yes/no + reasoning
        3. Return structured judgment
        """
        raise NotImplementedError(
            "LLMJudge requires LLM API integration. "
            "Use RuleBasedJudge for MVP."
        )


class ManualFeedbackJudge:
    """
    Manual feedback-based judge

    Collects human feedback on cache quality
    Most accurate but not scalable

    Placeholder for future implementation
    """

    def __init__(self):
        logger.warning("ManualFeedbackJudge is not yet implemented")

    def collect_feedback(
        self,
        request_id: str,
        was_helpful: bool,
        feedback_text: Optional[str] = None
    ):
        """
        Collect user feedback on cache hit quality

        Future implementation would:
        1. Store feedback in database
        2. Link to cache_event
        3. Aggregate for quality metrics
        """
        raise NotImplementedError(
            "ManualFeedbackJudge requires feedback collection system"
        )


def get_judge(judge_type: str = "rule_based", **kwargs):
    """
    Factory function to get appropriate judge

    Args:
        judge_type: 'rule_based', 'llm', or 'manual'
        **kwargs: Judge-specific parameters

    Returns:
        Judge instance
    """
    if judge_type == "rule_based":
        threshold = kwargs.get("threshold", 0.90)
        return RuleBasedJudge(threshold=threshold)
    elif judge_type == "llm":
        model_name = kwargs.get("model_name", "gpt-4")
        return LLMJudge(model_name=model_name)
    elif judge_type == "manual":
        return ManualFeedbackJudge()
    else:
        raise ValueError(f"Unknown judge type: {judge_type}")
