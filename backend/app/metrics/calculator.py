"""
Metrics Calculator

Turns raw database logs into useful aggregated metrics

This is what powers the dashboard visualizations
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.cache_event import CacheEvent, CacheStatus
from app.models.provider_call import ProviderCall

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """
    Calculates aggregated metrics from historical data

    Transforms raw logs into dashboard-ready numbers
    """

    def __init__(self, session: Session):
        """
        Initialize calculator

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def calculate_summary(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate summary metrics

        Returns:
            {
                "total_requests": 1200,
                "cache_hits": 720,
                "cache_misses": 480,
                "cache_hit_rate": 0.60,
                "estimated_cost_saved_usd": 42.73,
                "calls_avoided": 720
            }
        """
        # Build base query
        query = self.session.query(CacheEvent)

        if since:
            query = query.filter(CacheEvent.created_at >= since)
        if until:
            query = query.filter(CacheEvent.created_at <= until)
        if tenant_id:
            query = query.filter(CacheEvent.tenant_id == tenant_id)

        # Total requests
        total_requests = query.count()

        # Cache hits
        cache_hits = query.filter(
            CacheEvent.cache_status == CacheStatus.HIT
        ).count()

        # Cache misses
        cache_misses = total_requests - cache_hits

        # Hit rate
        hit_rate = cache_hits / total_requests if total_requests > 0 else 0.0

        cost_query = self.session.query(
            func.avg(ProviderCall.estimated_cost)
        ).filter(ProviderCall.estimated_cost.isnot(None))
        if since:
            cost_query = cost_query.filter(ProviderCall.created_at >= since)
        if until:
            cost_query = cost_query.filter(ProviderCall.created_at <= until)
        if tenant_id:
            cost_query = cost_query.filter(ProviderCall.tenant_id == tenant_id)
        average_provider_cost = cost_query.scalar() or 0.0

        return {
            "total_requests": total_requests,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_hit_rate": round(hit_rate, 4),
            "estimated_cost_saved_usd": round(cache_hits * average_provider_cost, 2),
            "calls_avoided": cache_hits,
        }

    def calculate_dashboard_latency(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculate the cache/provider latency comparison used by Dashboard."""
        cache_query = self.session.query(func.avg(CacheEvent.latency_ms)).filter(
            CacheEvent.cache_status == CacheStatus.HIT,
            CacheEvent.latency_ms.isnot(None),
        )
        provider_query = self.session.query(func.avg(ProviderCall.latency_ms)).filter(
            ProviderCall.latency_ms.isnot(None)
        )

        if since:
            cache_query = cache_query.filter(CacheEvent.created_at >= since)
            provider_query = provider_query.filter(ProviderCall.created_at >= since)
        if until:
            cache_query = cache_query.filter(CacheEvent.created_at <= until)
            provider_query = provider_query.filter(ProviderCall.created_at <= until)
        if tenant_id:
            cache_query = cache_query.filter(CacheEvent.tenant_id == tenant_id)
            provider_query = provider_query.filter(ProviderCall.tenant_id == tenant_id)

        cache_average = cache_query.scalar() or 0.0
        provider_average = provider_query.scalar() or 0.0
        speedup = provider_average / cache_average if cache_average > 0 else 0.0

        return {
            "cache_average_ms": round(cache_average, 2),
            "provider_average_ms": round(provider_average, 2),
            "speedup_factor": round(speedup, 2),
        }

    def calculate_similarity_distribution(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        tenant_id: Optional[str] = None,
        bins: int = 10
    ) -> Dict[str, int]:
        """
        Calculate similarity score distribution

        Returns bucket counts like:
        {
            "0.70-0.80": 42,
            "0.80-0.90": 108,
            "0.90-1.00": 350
        }
        """
        query = self.session.query(CacheEvent.similarity_score).filter(
            CacheEvent.similarity_score.isnot(None)
        )

        if since:
            query = query.filter(CacheEvent.created_at >= since)
        if until:
            query = query.filter(CacheEvent.created_at <= until)
        if tenant_id:
            query = query.filter(CacheEvent.tenant_id == tenant_id)

        scores = [s[0] for s in query.all()]

        if bins <= 0:
            raise ValueError("bins must be greater than zero")

        if not scores:
            return {}

        # Use fixed [0, 1] buckets so distributions are comparable across
        # periods. Clamp out-of-range historical data, and include 1.0 in the
        # final bucket.
        bin_width = 1.0 / bins
        counts = [0] * bins
        for score in scores:
            clamped_score = max(0.0, min(1.0, score))
            bucket = min(int(clamped_score * bins), bins - 1)
            counts[bucket] += 1

        distribution = {}
        for i, count in enumerate(counts):
            bin_min = i * bin_width
            bin_max = (i + 1) * bin_width
            label = f"{bin_min:.2f}-{bin_max:.2f}"
            distribution[label] = count

        return distribution

    def calculate_top_cached_prompts(
        self,
        limit: int = 10,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get top cached prompts by hit count

        Returns list sorted by cache_hits descending
        """
        from app.models.cache_entry import CacheEntry

        query = self.session.query(CacheEntry)

        if since:
            query = query.filter(CacheEntry.created_at >= since)
        if until:
            query = query.filter(CacheEntry.created_at <= until)
        if tenant_id:
            query = query.filter(CacheEntry.tenant_id == tenant_id)

        entries = query.order_by(CacheEntry.cache_hits.desc()).limit(limit).all()

        return [
            {
                "cache_id": entry.cache_id,
                "prompt": entry.prompt_text[:100] + "..." if len(entry.prompt_text) > 100 else entry.prompt_text,
                "response": entry.response_text[:100] + "..." if len(entry.response_text) > 100 else entry.response_text,
                "hit_count": entry.cache_hits,
                "model": entry.model,
                "created_at": entry.created_at.isoformat()
            }
            for entry in entries
        ]

    def calculate_time_series(
        self,
        metric: str,
        since: datetime,
        until: datetime,
        interval_minutes: int = 60,
        tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Calculate time series data for a metric

        Args:
            metric: "hit_rate" or "requests"
            since: Start time
            until: End time
            interval_minutes: Bucket size
            tenant_id: Optional tenant filter

        Returns:
            List of time buckets with metric values
        """
        if metric not in {"hit_rate", "requests"}:
            raise ValueError("metric must be 'hit_rate' or 'requests'")

        time_series = []
        current = since

        while current < until:
            bucket_end = current + timedelta(minutes=interval_minutes)

            if metric == "hit_rate":
                value = self._calculate_hit_rate_for_period(
                    current, bucket_end, tenant_id
                )
            elif metric == "requests":
                value = self._calculate_requests_for_period(
                    current, bucket_end, tenant_id
                )
            time_series.append({
                "timestamp": current.isoformat(),
                "value": value
            })

            current = bucket_end

        return time_series

    def _calculate_hit_rate_for_period(
        self,
        start: datetime,
        end: datetime,
        tenant_id: Optional[str]
    ) -> float:
        """Calculate hit rate for a specific time period"""
        query = self.session.query(CacheEvent).filter(
            CacheEvent.created_at >= start,
            CacheEvent.created_at < end
        )

        if tenant_id:
            query = query.filter(CacheEvent.tenant_id == tenant_id)

        total = query.count()
        if total == 0:
            return 0.0

        hits = query.filter(CacheEvent.cache_status == CacheStatus.HIT).count()
        return hits / total

    def _calculate_requests_for_period(
        self,
        start: datetime,
        end: datetime,
        tenant_id: Optional[str]
    ) -> int:
        """Calculate request count for a specific time period"""
        query = self.session.query(
            func.count(CacheEvent.id)
        ).filter(
            CacheEvent.created_at >= start,
            CacheEvent.created_at < end
        )

        if tenant_id:
            query = query.filter(CacheEvent.tenant_id == tenant_id)

        return query.scalar() or 0
