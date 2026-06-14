"""
Remediation Policy

Decision rules for supervisor agent orchestration
"""
from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)


class RemediationPolicy:
    """
    Encodes decision logic for infrastructure remediation

    Keeps supervisor agent explainable and maintainable
    """

    def diagnose_problem(self, system_state: Dict[str, Any]) -> Tuple[str, str]:
        """
        Diagnose what's wrong with the system

        Args:
            system_state: Current system metrics

        Returns:
            (diagnosis, diagnosis_details)
        """
        drift_severity = system_state.get("drift_severity", "no_drift")
        precision = system_state.get("precision", 1.0)
        recall = system_state.get("recall", 1.0)
        false_hit_rate = system_state.get("false_hit_rate", 0.0)
        false_miss_rate = system_state.get("false_miss_rate", 0.0)
        stale_vector_ratio = system_state.get("stale_vector_ratio", 0.0)
        cache_hit_rate = system_state.get("cache_hit_rate", 0.0)

        # Priority 1: Dangerous - High false hits
        if false_hit_rate > 0.08:
            return "cache_precision_degradation", f"False hit rate {false_hit_rate:.1%} is dangerous"

        # Priority 2: Quality degradation
        if precision < 0.88:
            return "low_cache_precision", f"Precision {precision:.1%} below threshold"

        # Priority 3: High drift
        if drift_severity == "high_drift":
            if precision < 0.92:
                return "drift_with_quality_issues", "High drift affecting cache quality"
            else:
                return "high_drift_stable_quality", "High drift but quality stable (monitor only)"

        # Priority 4: Stale index
        if stale_vector_ratio > 0.25:
            return "stale_index", f"Index {stale_vector_ratio:.1%} stale"

        # Priority 5: Missing savings
        if false_miss_rate > 0.40 and false_hit_rate < 0.05:
            return "low_cache_recall", f"Missing {false_miss_rate:.1%} savings opportunities"

        # Priority 6: Moderate drift
        if drift_severity == "moderate_drift":
            return "moderate_drift", "Semantic distribution shifting"

        # No major issues
        return "healthy", "System operating normally"

    def recommend_action(
        self,
        diagnosis: str,
        system_state: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Recommend remediation actions based on diagnosis

        Args:
            diagnosis: Problem diagnosis
            system_state: Current system state

        Returns:
            List of recommended actions in priority order
        """
        actions = []

        if diagnosis == "cache_precision_degradation":
            # High false hits - raise threshold immediately
            actions.append({
                "agent": "threshold_optimizer",
                "action": "optimize_threshold",
                "priority": "urgent",
                "reason": "High false hit rate requires threshold increase",
                "expected_outcome": "Reduced false hits, improved precision"
            })

        elif diagnosis == "low_cache_precision":
            # Low precision - try threshold first
            actions.append({
                "agent": "threshold_optimizer",
                "action": "optimize_threshold",
                "priority": "high",
                "reason": "Low precision suggests threshold too low",
                "expected_outcome": "Improved precision"
            })

        elif diagnosis == "drift_with_quality_issues":
            # Drift + quality issues - try threshold, then index
            actions.append({
                "agent": "threshold_optimizer",
                "action": "optimize_threshold",
                "priority": "high",
                "reason": "High drift with quality degradation",
                "expected_outcome": "Improved quality metrics"
            })
            actions.append({
                "agent": "index_rebuilder",
                "action": "rebuild_index",
                "priority": "medium",
                "reason": "If threshold optimization fails, rebuild may be needed",
                "expected_outcome": "Fresh index with updated embeddings",
                "condition": "threshold_optimization_failed"
            })

        elif diagnosis == "high_drift_stable_quality":
            # Monitor only - don't overreact
            actions.append({
                "agent": "monitor",
                "action": "monitor_only",
                "priority": "low",
                "reason": "Drift high but quality stable",
                "expected_outcome": "Continued monitoring"
            })

        elif diagnosis == "stale_index":
            # Stale index - rebuild needed
            actions.append({
                "agent": "index_rebuilder",
                "action": "rebuild_index",
                "priority": "high",
                "reason": f"Index {system_state.get('stale_vector_ratio', 0):.1%} stale",
                "expected_outcome": "Cleaner index with active entries only"
            })

        elif diagnosis == "low_cache_recall":
            # Missing savings - lower threshold
            actions.append({
                "agent": "threshold_optimizer",
                "action": "optimize_threshold",
                "priority": "medium",
                "reason": "High false miss rate indicates threshold too high",
                "expected_outcome": "Increased cache hit rate"
            })

        elif diagnosis == "moderate_drift":
            # Monitor for now
            actions.append({
                "agent": "monitor",
                "action": "monitor_only",
                "priority": "low",
                "reason": "Moderate drift, watch for quality impact",
                "expected_outcome": "Early detection if issues develop"
            })

        else:
            # Healthy - no action
            actions.append({
                "agent": "none",
                "action": "no_action",
                "priority": "none",
                "reason": "System healthy",
                "expected_outcome": "Continued stable operation"
            })

        return actions

    def should_continue_remediation(
        self,
        actions_taken: List[Dict[str, Any]],
        validation_result: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Decide if more remediation steps are needed

        Args:
            actions_taken: Actions executed so far
            validation_result: Validation of last action

        Returns:
            (should_continue, reason)
        """
        if not actions_taken:
            return True, "No actions taken yet"

        last_action = actions_taken[-1]
        validation_passed = validation_result.get("passed", False)

        # If last action succeeded, we're done
        if validation_passed:
            return False, "Last action resolved the issue"

        # If threshold optimization failed and we haven't tried rebuild yet
        if last_action.get("agent") == "threshold_optimizer" and not validation_passed:
            rebuild_attempted = any(a.get("agent") == "index_rebuilder" for a in actions_taken)
            if not rebuild_attempted:
                return True, "Threshold optimization failed, attempting index rebuild"

        # If we've tried multiple actions, stop
        if len(actions_taken) >= 3:
            return False, "Maximum remediation attempts reached"

        return False, "No additional actions recommended"

    def validate_remediation(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any],
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate that remediation improved the system

        Args:
            before_state: Metrics before action
            after_state: Metrics after action
            action: Action that was taken

        Returns:
            Validation result
        """
        improvements = []
        degradations = []

        # Check precision
        precision_before = before_state.get("precision", 0)
        precision_after = after_state.get("precision", 0)
        precision_delta = precision_after - precision_before

        if abs(precision_delta) > 0.01:
            if precision_delta > 0:
                improvements.append(f"Precision improved by {precision_delta:+.1%}")
            else:
                degradations.append(f"Precision degraded by {precision_delta:+.1%}")

        # Check recall
        recall_before = before_state.get("recall", 0)
        recall_after = after_state.get("recall", 0)
        recall_delta = recall_after - recall_before

        if abs(recall_delta) > 0.01:
            if recall_delta > 0:
                improvements.append(f"Recall improved by {recall_delta:+.1%}")
            else:
                degradations.append(f"Recall changed by {recall_delta:+.1%}")

        # Check false hit rate
        fhr_before = before_state.get("false_hit_rate", 0)
        fhr_after = after_state.get("false_hit_rate", 0)
        fhr_delta = fhr_after - fhr_before

        if abs(fhr_delta) > 0.01:
            if fhr_delta < 0:  # Lower is better
                improvements.append(f"False hit rate reduced by {-fhr_delta:.1%}")
            else:
                degradations.append(f"False hit rate increased by {fhr_delta:+.1%}")

        # Determine if validation passed
        passed = len(improvements) > 0 and len(degradations) == 0

        return {
            "passed": passed,
            "improvements": improvements,
            "degradations": degradations,
            "precision_delta": precision_delta,
            "recall_delta": recall_delta,
            "false_hit_rate_delta": fhr_delta,
        }
