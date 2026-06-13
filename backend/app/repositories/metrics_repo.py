"""
Metrics Repository

Aggregates analytics and metrics from historical data
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.cache_event import CacheEvent, CacheStatus
from app.models.provider_call import ProviderCall
from app.models.request import Request
from app.models.cache_entry import CacheEntry

logger = logging.getLogger(__name__)


class MetricsRepository:
    """Repository for metrics and analytics queries"""

    def __init__(self, session: Session):
        """
        Initialize repository

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def get_cache_hit_rate(
        self,
        tenant_id: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate cache hit rate

        Args:
            tenant_id: Optional tenant filter
            since: Optional minimum timestamp

        Returns:
            Dictionary with hit rate metrics
        """
        query = self.session.query(CacheEvent)

        if tenant_id:
            query = query.filter(CacheEvent.tenant_id == tenant_id)
        if since:
            query = query.filter(CacheEvent.created_at >= since)

        total = query.count()

        if total == 0:
            return {
                "total_requests": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "hit_rate": 0.0
            }

        hits = query.filter(CacheEvent.cache_status == CacheStatus.HIT).count()
        misses = total - hits

        return {
            "total_requests": total,
            "cache_hits": hits,
            "cache_misses": misses,
            "hit_rate": hits / total if total > 0 else 0.0
        }

    def get_average_similarity_score(
        self,
        tenant_id: Optional[str] = None,
        since: Optional[datetime] = None,
        only_hits: bool = True
    ) -> float:
        """
        Calculate average similarity score

        Args:
            tenant_id: Optional tenant filter
            since: Optional minimum timestamp
            only_hits: Only include cache hits

        Returns:
            Average similarity score
        """
        query = self.session.query(func.avg(CacheEvent.similarity_score))

        if tenant_id:
            query = query.filter(CacheEvent.tenant_id == tenant_id)
        if since:
            query = query.filter(CacheEvent.created_at >= since)
        if only_hits:
            query = query.filter(CacheEvent.cache_status == CacheStatus.HIT)

        # Filter out NULL similarity scores
        query = query.filter(CacheEvent.similarity_score.isnot(None))

        result = query.scalar()
        return float(result) if result else 0.0

    def get_similarity_score_distribution(
        self,
        tenant_id: Optional[str] = None,
        since: Optional[datetime] = None,
        bins: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get similarity score distribution

        Args:
            tenant_id: Optional tenant filter
            since: Optional minimum timestamp
            bins: Number of bins for histogram

        Returns:
            List of distribution buckets
        """
        query = self.session.query(CacheEvent.similarity_score)

        if tenant_id:
            query = query.filter(CacheEvent.tenant_id == tenant_id)
        if since:
            query = query.filter(CacheEvent.created_at >= since)

        query = query.filter(CacheEvent.similarity_score.isnot(None))

        scores = [s[0] for s in query.all()]

        if not scores:
            return []

        # Create histogram
        min_score = min(scores)
        max_score = max(scores)
        bin_width = (max_score - min_score) / bins

        distribution = []
        for i in range(bins):
            bin_min = min_score + (i * bin_width)
            bin_max = bin_min + bin_width
            count = sum(1 for s in scores if bin_min <= s < bin_max)

            distribution.append({
                "bin_min": round(bin_min, 3),
                "bin_max": round(bin_max, 3),
                "count": count
            })

        return distribution

    def get_miss_breakdown(
        self,
        tenant_id: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Get breakdown of cache miss types

        Args:
            tenant_id: Optional tenant filter
            since: Optional minimum timestamp

        Returns:
            Dictionary mapping miss type to count
        """
        query = self.session.query(
            CacheEvent.cache_status,
            func.count(CacheEvent.id)
        )

        if tenant_id:
            query = query.filter(CacheEvent.tenant_id == tenant_id)
        if since:
            query = query.filter(CacheEvent.created_at >= since)

        # Exclude HITs
        query = query.filter(CacheEvent.cache_status != CacheStatus.HIT)

        # Group by status
        query = query.group_by(CacheEvent.cache_status)

        results = query.all()

        return {status.value: count for status, count in results}

    def get_cost_savings(
        self,
        tenant_id: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate cost savings from cache hits

        Args:
            tenant_id: Optional tenant filter
            since: Optional minimum timestamp

        Returns:
            Dictionary with cost savings metrics
        """
        # Total requests
        total_requests_query = self.session.query(func.count(Request.id))
        if tenant_id:
            total_requests_query = total_requests_query.filter(Request.tenant_id == tenant_id)
        if since:
            total_requests_query = total_requests_query.filter(Request.created_at >= since)
        total_requests = total_requests_query.scalar() or 0

        # Actual provider calls
        provider_calls_query = self.session.query(func.count(ProviderCall.id))
        if tenant_id:
            provider_calls_query = provider_calls_query.filter(ProviderCall.tenant_id == tenant_id)
        if since:
            provider_calls_query = provider_calls_query.filter(ProviderCall.created_at >= since)
        actual_calls = provider_calls_query.scalar() or 0

        # Calls avoided
        calls_avoided = total_requests - actual_calls

        # Total cost
        cost_query = self.session.query(func.sum(ProviderCall.estimated_cost))
        if tenant_id:
            cost_query = cost_query.filter(ProviderCall.tenant_id == tenant_id)
        if since:
            cost_query = cost_query.filter(ProviderCall.created_at >= since)
        total_cost = cost_query.scalar() or 0.0

        # Estimated cost per call
        cost_per_call = total_cost / actual_calls if actual_calls > 0 else 0.0

        # Estimated savings
        estimated_savings = calls_avoided * cost_per_call

        return {
            "total_requests": total_requests,
            "actual_provider_calls": actual_calls,
            "calls_avoided": calls_avoided,
            "total_cost_usd": round(total_cost, 2),
            "estimated_savings_usd": round(estimated_savings, 2),
            "savings_rate": calls_avoided / total_requests if total_requests > 0 else 0.0
        }

    def get_latency_stats(
        self,
        tenant_id: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get cache latency statistics

        Args:
            tenant_id: Optional tenant filter
            since: Optional minimum timestamp

        Returns:
            Dictionary with latency metrics
        """
        query = self.session.query(
            func.avg(CacheEvent.latency_ms),
            func.min(CacheEvent.latency_ms),
            func.max(CacheEvent.latency_ms)
        )

        if tenant_id:
            query = query.filter(CacheEvent.tenant_id == tenant_id)
        if since:
            query = query.filter(CacheEvent.created_at >= since)

        query = query.filter(CacheEvent.latency_ms.isnot(None))

        avg, min_lat, max_lat = query.first()

        return {
            "average_ms": round(avg, 2) if avg else 0.0,
            "min_ms": round(min_lat, 2) if min_lat else 0.0,
            "max_ms": round(max_lat, 2) if max_lat else 0.0
        }

    def get_top_cached_responses(
        self,
        limit: int = 10,
        tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get most frequently used cached responses

        Args:
            limit: Maximum results
            tenant_id: Optional tenant filter

        Returns:
            List of top cache entries
        """
        query = self.session.query(CacheEntry)

        if tenant_id:
            query = query.filter(CacheEntry.tenant_id == tenant_id)

        entries = query.order_by(CacheEntry.cache_hits.desc()).limit(limit).all()

        return [
            {
                "cache_id": e.cache_id,
                "prompt_text": e.prompt_text[:100] + "..." if len(e.prompt_text) > 100 else e.prompt_text,
                "model": e.model,
                "cache_hits": e.cache_hits,
                "created_at": e.created_at.isoformat()
            }
            for e in entries
        ]

    def get_dashboard_summary(
        self,
        tenant_id: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive dashboard summary

        Args:
            tenant_id: Optional tenant filter
            since: Optional minimum timestamp

        Returns:
            Dictionary with all key metrics
        """
        return {
            "hit_rate": self.get_cache_hit_rate(tenant_id, since),
            "average_similarity": self.get_average_similarity_score(tenant_id, since),
            "miss_breakdown": self.get_miss_breakdown(tenant_id, since),
            "cost_savings": self.get_cost_savings(tenant_id, since),
            "latency": self.get_latency_stats(tenant_id, since),
            "top_cached": self.get_top_cached_responses(limit=5, tenant_id=tenant_id)
        }
