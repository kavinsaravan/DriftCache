"""
Point-in-Time Evaluation System

Evaluates cache decisions using only data/configuration that existed at decision time

This prevents evaluation from "cheating" by using future knowledge
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.cache_event import CacheEvent, CacheStatus
from app.models.cache_entry import CacheEntry
from app.models.request import Request
from app.models.threshold_version import ThresholdVersion
from app.models.index_version import IndexVersion
from app.database.session import get_db_manager

logger = logging.getLogger(__name__)


class PointInTimeEvaluator:
    """
    Point-in-time evaluation service

    Key principle: When evaluating a past cache decision,
    use ONLY the data/config that existed at that time

    Example:
    - July 1: threshold=0.88, model=all-MiniLM-L6-v2, cache HIT
    - July 15: threshold=0.94, model changed, FAISS rebuilt

    To evaluate the July 1 decision, you MUST use July 1 conditions,
    NOT July 15 conditions. Otherwise you're cheating.
    """

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize evaluator

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

    def evaluate_cache_decision(
        self,
        cache_event_id: int
    ) -> Dict[str, Any]:
        """
        Evaluate a cache decision at the point in time it was made

        This retrieves:
        - The request
        - The matched cached response (if HIT)
        - The threshold used at that time
        - The embedding model used
        - The similarity score recorded
        - The timestamp

        Args:
            cache_event_id: ID of cache event to evaluate

        Returns:
            Evaluation report dictionary
        """
        # Get cache event
        cache_event = self.session.query(CacheEvent).filter(
            CacheEvent.id == cache_event_id
        ).first()

        if not cache_event:
            raise ValueError(f"Cache event {cache_event_id} not found")

        # Get request
        request = self.session.query(Request).filter(
            Request.request_id == cache_event.request_id
        ).first()

        if not request:
            logger.warning(f"Request {cache_event.request_id} not found")

        # Get matched cache entry (if HIT)
        cached_response = None
        if cache_event.matched_cache_id:
            cached_response = self.session.query(CacheEntry).filter(
                CacheEntry.cache_id == cache_event.matched_cache_id
            ).first()

        # Get threshold version
        threshold_version = None
        if cache_event.threshold_version_id:
            threshold_version = self.session.query(ThresholdVersion).filter(
                ThresholdVersion.id == cache_event.threshold_version_id
            ).first()

        # Get index version
        index_version = None
        if cache_event.index_version_id:
            index_version = self.session.query(IndexVersion).filter(
                IndexVersion.id == cache_event.index_version_id
            ).first()

        # Build evaluation report
        report = {
            "cache_event_id": cache_event_id,
            "decision_time": cache_event.created_at.isoformat(),

            # Decision details
            "decision": cache_event.cache_status.value,
            "similarity_score": cache_event.similarity_score,
            "threshold_used": cache_event.threshold_used,

            # Versioning (Point-in-Time)
            "threshold_version": {
                "id": threshold_version.id if threshold_version else None,
                "value": threshold_version.threshold_value if threshold_version else cache_event.threshold_used,
                "reason": threshold_version.reason if threshold_version else None,
            } if threshold_version else {
                "id": None,
                "value": cache_event.threshold_used,
                "reason": "No threshold version recorded"
            },

            "embedding_model": cache_event.embedding_model or "unknown",

            "index_version": {
                "id": index_version.id if index_version else None,
                "version_name": index_version.version_name if index_version else None,
                "embedding_model": index_version.embedding_model if index_version else None,
            } if index_version else {
                "id": None,
                "version_name": None,
                "embedding_model": cache_event.embedding_model
            },

            # Request details
            "request": {
                "prompt_text": request.prompt_text[:200] + "..." if request and len(request.prompt_text) > 200 else (request.prompt_text if request else None),
                "model": cache_event.model,
                "tenant_id": cache_event.tenant_id,
            },

            # Match details (if HIT)
            "matched_cache": {
                "cache_id": cache_event.matched_cache_id,
                "response_text": cached_response.response_text[:200] + "..." if cached_response and len(cached_response.response_text) > 200 else (cached_response.response_text if cached_response else None),
                "created_at": cached_response.created_at.isoformat() if cached_response else None,
                "cache_hits": cached_response.cache_hits if cached_response else None,
            } if cache_event.matched_cache_id else None,

            # Performance
            "latency_ms": cache_event.latency_ms,
            "retrieval_source": cache_event.retrieval_source,

            # Validation
            "validation": self._validate_decision(cache_event)
        }

        return report

    def _validate_decision(self, cache_event: CacheEvent) -> Dict[str, Any]:
        """
        Validate if cache decision was correct at the time

        Args:
            cache_event: CacheEvent to validate

        Returns:
            Validation results
        """
        validation = {
            "threshold_met": None,
            "valid_under_current_conditions": None,
            "notes": []
        }

        # Check if similarity met threshold
        if cache_event.similarity_score is not None:
            validation["threshold_met"] = cache_event.similarity_score >= cache_event.threshold_used

            if cache_event.cache_status == CacheStatus.HIT and not validation["threshold_met"]:
                validation["notes"].append("WARNING: Cache HIT but similarity below threshold")
            elif cache_event.cache_status == CacheStatus.THRESHOLD_NOT_MET and validation["threshold_met"]:
                validation["notes"].append("WARNING: MISS due to threshold but similarity was above threshold")

        # Check if decision was consistent
        if cache_event.cache_status == CacheStatus.HIT:
            if cache_event.matched_cache_id is None:
                validation["notes"].append("ERROR: HIT status but no matched_cache_id")
            if cache_event.similarity_score is None:
                validation["notes"].append("ERROR: HIT status but no similarity_score")

        return validation

    def evaluate_batch(
        self,
        cache_event_ids: list[int]
    ) -> list[Dict[str, Any]]:
        """
        Evaluate multiple cache decisions

        Args:
            cache_event_ids: List of cache event IDs

        Returns:
            List of evaluation reports
        """
        return [
            self.evaluate_cache_decision(event_id)
            for event_id in cache_event_ids
        ]

    def evaluate_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        tenant_id: Optional[str] = None,
        limit: int = 100
    ) -> list[Dict[str, Any]]:
        """
        Evaluate all cache decisions in a time range

        Args:
            start_time: Start of time range
            end_time: End of time range
            tenant_id: Optional tenant filter
            limit: Maximum results

        Returns:
            List of evaluation reports
        """
        query = self.session.query(CacheEvent).filter(
            CacheEvent.created_at >= start_time,
            CacheEvent.created_at <= end_time
        )

        if tenant_id:
            query = query.filter(CacheEvent.tenant_id == tenant_id)

        events = query.order_by(CacheEvent.created_at.desc()).limit(limit).all()

        return [
            self.evaluate_cache_decision(event.id)
            for event in events
        ]


def get_point_in_time_evaluator(session: Optional[Session] = None) -> PointInTimeEvaluator:
    """
    Get point-in-time evaluator instance

    Args:
        session: Optional SQLAlchemy session

    Returns:
        PointInTimeEvaluator instance
    """
    return PointInTimeEvaluator(session=session)
