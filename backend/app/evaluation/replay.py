"""
Cache Decision Replay System

Replays historical cache decisions under different conditions

This allows:
- "What if we used threshold 0.92 instead of 0.88?"
- "How would different embedding models perform?"
- A/B testing thresholds on historical data
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.cache_event import CacheEvent, CacheStatus
from app.models.threshold_version import ThresholdVersion
from app.database.session import get_db_manager

logger = logging.getLogger(__name__)


class CacheDecisionReplayer:
    """
    Replay cache decisions under different conditions

    Example use case:
    "If we had used threshold 0.92 instead of 0.88,
     how many HITs would have become MISSes?"

    This is critical for:
    - Threshold optimization
    - A/B testing
    - Understanding impact of config changes
    """

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize replayer

        Args:
            session: Optional SQLAlchemy session
        """
        self.session = session
        self._owns_session = session is None

    def __enter__(self):
        """Context manager entry"""
        if self._owns_session:
            db_manager = get_db_manager()
            self.session = db_manager.get_session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self._owns_session and self.session:
            self.session.close()

    def replay_with_threshold(
        self,
        cache_event_id: int,
        new_threshold: float
    ) -> Dict[str, Any]:
        """
        Replay a cache decision with a different threshold

        Args:
            cache_event_id: Cache event ID
            new_threshold: New threshold to test

        Returns:
            Replay result
        """
        # Get original cache event
        event = self.session.query(CacheEvent).filter(
            CacheEvent.id == cache_event_id
        ).first()

        if not event:
            raise ValueError(f"Cache event {cache_event_id} not found")

        # Determine new decision
        original_decision = event.cache_status.value
        new_decision = self._evaluate_threshold(event, new_threshold)

        return {
            "cache_event_id": cache_event_id,
            "decision_time": event.created_at.isoformat(),

            # Original conditions
            "original": {
                "threshold": event.threshold_used,
                "similarity_score": event.similarity_score,
                "decision": original_decision,
            },

            # New conditions
            "replay": {
                "threshold": new_threshold,
                "similarity_score": event.similarity_score,  # Same similarity
                "decision": new_decision,
            },

            # Comparison
            "changed": original_decision != new_decision,
            "impact": self._describe_impact(original_decision, new_decision)
        }

    def replay_batch_with_threshold(
        self,
        start_time: datetime,
        end_time: datetime,
        new_threshold: float,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Replay a batch of cache decisions with a different threshold

        This answers: "If we change threshold, what happens?"

        Args:
            start_time: Start of time range
            end_time: End of time range
            new_threshold: New threshold to test
            tenant_id: Optional tenant filter

        Returns:
            Batch replay summary
        """
        # Get all events in time range
        query = self.session.query(CacheEvent).filter(
            CacheEvent.created_at >= start_time,
            CacheEvent.created_at <= end_time
        )

        if tenant_id:
            query = query.filter(CacheEvent.tenant_id == tenant_id)

        events = query.all()

        # Replay each event
        results = []
        hits_to_misses = 0
        misses_to_hits = 0
        unchanged = 0

        for event in events:
            original_decision = event.cache_status.value
            new_decision = self._evaluate_threshold(event, new_threshold)

            if original_decision != new_decision:
                if original_decision == "HIT" and new_decision in ["MISS", "THRESHOLD_NOT_MET"]:
                    hits_to_misses += 1
                elif original_decision in ["MISS", "THRESHOLD_NOT_MET"] and new_decision == "HIT":
                    misses_to_hits += 1
            else:
                unchanged += 1

            results.append({
                "event_id": event.id,
                "original": original_decision,
                "replay": new_decision,
                "changed": original_decision != new_decision
            })

        # Calculate impact
        total = len(events)
        original_hit_rate = sum(1 for e in events if e.cache_status == CacheStatus.HIT) / total if total > 0 else 0

        # Estimate new hit rate
        new_hits = sum(1 for e in events if e.cache_status == CacheStatus.HIT) - hits_to_misses + misses_to_hits
        new_hit_rate = new_hits / total if total > 0 else 0

        return {
            "summary": {
                "total_events": total,
                "threshold_change": {
                    "from": events[0].threshold_used if events else None,
                    "to": new_threshold
                },
                "hit_rate_change": {
                    "original": round(original_hit_rate, 4),
                    "replay": round(new_hit_rate, 4),
                    "delta": round(new_hit_rate - original_hit_rate, 4)
                },
                "decision_changes": {
                    "hits_to_misses": hits_to_misses,
                    "misses_to_hits": misses_to_hits,
                    "unchanged": unchanged
                }
            },
            "events": results[:100]  # First 100 for details
        }

    def _evaluate_threshold(
        self,
        event: CacheEvent,
        threshold: float
    ) -> str:
        """
        Evaluate what decision would have been made with new threshold

        Args:
            event: Original cache event
            threshold: New threshold

        Returns:
            Decision status string
        """
        # If no similarity score, keep original decision
        if event.similarity_score is None:
            return event.cache_status.value

        # Evaluate threshold
        if event.similarity_score >= threshold:
            return "HIT"
        else:
            return "THRESHOLD_NOT_MET"

    def _describe_impact(
        self,
        original: str,
        new: str
    ) -> str:
        """
        Describe the impact of decision change

        Args:
            original: Original decision
            new: New decision

        Returns:
            Human-readable impact description
        """
        if original == new:
            return "No change"

        if original == "HIT" and new in ["MISS", "THRESHOLD_NOT_MET"]:
            return "Cache HIT -> MISS (stricter threshold reduces hit rate)"

        if original in ["MISS", "THRESHOLD_NOT_MET"] and new == "HIT":
            return "Cache MISS -> HIT (looser threshold increases hit rate)"

        return f"Decision changed: {original} -> {new}"

    def compare_thresholds(
        self,
        start_time: datetime,
        end_time: datetime,
        thresholds: List[float],
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compare multiple thresholds on the same historical data

        Args:
            start_time: Start of time range
            end_time: End of time range
            thresholds: List of thresholds to compare
            tenant_id: Optional tenant filter

        Returns:
            Comparison report
        """
        comparisons = []

        for threshold in thresholds:
            result = self.replay_batch_with_threshold(
                start_time=start_time,
                end_time=end_time,
                new_threshold=threshold,
                tenant_id=tenant_id
            )

            comparisons.append({
                "threshold": threshold,
                "hit_rate": result["summary"]["hit_rate_change"]["replay"],
                "hits_to_misses": result["summary"]["decision_changes"]["hits_to_misses"],
                "misses_to_hits": result["summary"]["decision_changes"]["misses_to_hits"]
            })

        # Find optimal threshold (highest hit rate)
        optimal = max(comparisons, key=lambda x: x["hit_rate"]) if comparisons else None

        return {
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            "thresholds_tested": thresholds,
            "comparisons": comparisons,
            "optimal_threshold": {
                "value": optimal["threshold"],
                "hit_rate": optimal["hit_rate"]
            } if optimal else None
        }


def get_cache_replayer(session: Optional[Session] = None) -> CacheDecisionReplayer:
    """
    Get cache decision replayer instance

    Args:
        session: Optional SQLAlchemy session

    Returns:
        CacheDecisionReplayer instance
    """
    return CacheDecisionReplayer(session=session)
