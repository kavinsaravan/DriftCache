"""
Metrics Calculator

Turns raw database logs into useful aggregated metrics

This is what powers the dashboard visualizations
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.cache_event import CacheEvent, CacheStatus
from app.models.provider_call import ProviderCall
from app.models.request import Request

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
                "estimated_cost_saved": 42.73,
                "average_latency_ms": 310,
                "total_provider_calls": 480
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

        # Average latency
        avg_latency = self.session.query(
            func.avg(CacheEvent.latency_ms)
        ).filter(
            CacheEvent.latency_ms.isnot(None)
        )

        if since:
            avg_latency = avg_latency.filter(CacheEvent.created_at >= since)
        if until:
            avg_latency = avg_latency.filter(CacheEvent.created_at <= until)
        if tenant_id:
            avg_latency = avg_latency.filter(CacheEvent.tenant_id == tenant_id)

        avg_latency = avg_latency.scalar() or 0.0

        # Total provider calls
        provider_query = self.session.query(func.count(ProviderCall.id))

        if since:
            provider_query = provider_query.filter(ProviderCall.created_at >= since)
        if until:
            provider_query = provider_query.filter(ProviderCall.created_at <= until)
        if tenant_id:
            provider_query = provider_query.filter(ProviderCall.tenant_id == tenant_id)

        total_provider_calls = provider_query.scalar() or 0

        # Estimated cost saved
        cost_saved = self._calculate_cost_saved(since, until, tenant_id)

        return {
            "total_requests": total_requests,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_hit_rate": round(hit_rate, 4),
            "estimated_cost_saved_usd": round(cost_saved, 2),
            "average_latency_ms": round(avg_latency, 2),
            "total_provider_calls": total_provider_calls,
            "calls_avoided": total_requests - total_provider_calls
        }

    def calculate_latency_breakdown(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate latency statistics

        Returns cache vs provider latency comparison
        """
        # Cache latency (HITs only)
        cache_latency_query = self.session.query(
            func.avg(CacheEvent.latency_ms),
            func.min(CacheEvent.latency_ms),
            func.max(CacheEvent.latency_ms)
        ).filter(
            CacheEvent.cache_status == CacheStatus.HIT,
            CacheEvent.latency_ms.isnot(None)
        )

        if since:
            cache_latency_query = cache_latency_query.filter(CacheEvent.created_at >= since)
        if until:
            cache_latency_query = cache_latency_query.filter(CacheEvent.created_at <= until)
        if tenant_id:
            cache_latency_query = cache_latency_query.filter(CacheEvent.tenant_id == tenant_id)

        cache_avg, cache_min, cache_max = cache_latency_query.first()

        # Provider latency
        provider_latency_query = self.session.query(
            func.avg(ProviderCall.latency_ms),
            func.min(ProviderCall.latency_ms),
            func.max(ProviderCall.latency_ms)
        ).filter(
            ProviderCall.latency_ms.isnot(None)
        )

        if since:
            provider_latency_query = provider_latency_query.filter(ProviderCall.created_at >= since)
        if until:
            provider_latency_query = provider_latency_query.filter(ProviderCall.created_at <= until)
        if tenant_id:
            provider_latency_query = provider_latency_query.filter(ProviderCall.tenant_id == tenant_id)

        provider_avg, provider_min, provider_max = provider_latency_query.first()

        # Calculate speedup
        speedup = 0.0
        if cache_avg and provider_avg and provider_avg > 0:
            speedup = provider_avg / cache_avg

        return {
            "cache_latency": {
                "average_ms": round(cache_avg, 2) if cache_avg else 0.0,
                "min_ms": round(cache_min, 2) if cache_min else 0.0,
                "max_ms": round(cache_max, 2) if cache_max else 0.0
            },
            "provider_latency": {
                "average_ms": round(provider_avg, 2) if provider_avg else 0.0,
                "min_ms": round(provider_min, 2) if provider_min else 0.0,
                "max_ms": round(provider_max, 2) if provider_max else 0.0
            },
            "speedup_factor": round(speedup, 2)
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

        if not scores:
            return {}

        # Create histogram
        min_score = max(0.0, min(scores))
        max_score = min(1.0, max(scores))
        bin_width = (max_score - min_score) / bins

        distribution = {}
        for i in range(bins):
            bin_min = min_score + (i * bin_width)
            bin_max = bin_min + bin_width
            count = sum(1 for s in scores if bin_min <= s < bin_max)

            # Format bin label
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

    def calculate_provider_usage(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate provider usage statistics

        Returns breakdown by provider and model
        """
        query = self.session.query(
            ProviderCall.provider,
            ProviderCall.model,
            func.count(ProviderCall.id),
            func.sum(ProviderCall.total_tokens),
            func.sum(ProviderCall.estimated_cost)
        )

        if since:
            query = query.filter(ProviderCall.created_at >= since)
        if until:
            query = query.filter(ProviderCall.created_at <= until)
        if tenant_id:
            query = query.filter(ProviderCall.tenant_id == tenant_id)

        query = query.group_by(ProviderCall.provider, ProviderCall.model)

        results = query.all()

        # Aggregate by provider
        provider_stats = {}
        for provider, model, count, tokens, cost in results:
            if provider not in provider_stats:
                provider_stats[provider] = {
                    "total_calls": 0,
                    "total_tokens": 0,
                    "total_cost_usd": 0.0,
                    "models": {}
                }

            provider_stats[provider]["total_calls"] += count
            provider_stats[provider]["total_tokens"] += tokens or 0
            provider_stats[provider]["total_cost_usd"] += cost or 0.0

            provider_stats[provider]["models"][model] = {
                "calls": count,
                "tokens": tokens or 0,
                "cost_usd": round(cost or 0.0, 2)
            }

        # Round totals
        for provider in provider_stats:
            provider_stats[provider]["total_cost_usd"] = round(
                provider_stats[provider]["total_cost_usd"], 2
            )

        return provider_stats

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
            metric: "hit_rate", "latency", "requests"
            since: Start time
            until: End time
            interval_minutes: Bucket size
            tenant_id: Optional tenant filter

        Returns:
            List of time buckets with metric values
        """
        time_series = []
        current = since

        while current < until:
            bucket_end = current + timedelta(minutes=interval_minutes)

            if metric == "hit_rate":
                value = self._calculate_hit_rate_for_period(
                    current, bucket_end, tenant_id
                )
            elif metric == "latency":
                value = self._calculate_avg_latency_for_period(
                    current, bucket_end, tenant_id
                )
            elif metric == "requests":
                value = self._calculate_requests_for_period(
                    current, bucket_end, tenant_id
                )
            else:
                value = 0

            time_series.append({
                "timestamp": current.isoformat(),
                "value": value
            })

            current = bucket_end

        return time_series

    def _calculate_cost_saved(
        self,
        since: Optional[datetime],
        until: Optional[datetime],
        tenant_id: Optional[str]
    ) -> float:
        """Calculate estimated cost saved from cache hits"""
        # Simple estimate: cache hits avoided provider calls
        # Estimate based on average provider call cost

        # Get average cost per provider call
        cost_query = self.session.query(
            func.avg(ProviderCall.estimated_cost)
        ).filter(
            ProviderCall.estimated_cost.isnot(None)
        )

        if since:
            cost_query = cost_query.filter(ProviderCall.created_at >= since)
        if until:
            cost_query = cost_query.filter(ProviderCall.created_at <= until)
        if tenant_id:
            cost_query = cost_query.filter(ProviderCall.tenant_id == tenant_id)

        avg_cost = cost_query.scalar() or 0.001  # Default to $0.001 if no data

        # Get cache hit count
        hit_query = self.session.query(
            func.count(CacheEvent.id)
        ).filter(
            CacheEvent.cache_status == CacheStatus.HIT
        )

        if since:
            hit_query = hit_query.filter(CacheEvent.created_at >= since)
        if until:
            hit_query = hit_query.filter(CacheEvent.created_at <= until)
        if tenant_id:
            hit_query = hit_query.filter(CacheEvent.tenant_id == tenant_id)

        cache_hits = hit_query.scalar() or 0

        return cache_hits * avg_cost

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

    def _calculate_avg_latency_for_period(
        self,
        start: datetime,
        end: datetime,
        tenant_id: Optional[str]
    ) -> float:
        """Calculate average latency for a specific time period"""
        query = self.session.query(
            func.avg(CacheEvent.latency_ms)
        ).filter(
            CacheEvent.created_at >= start,
            CacheEvent.created_at < end,
            CacheEvent.latency_ms.isnot(None)
        )

        if tenant_id:
            query = query.filter(CacheEvent.tenant_id == tenant_id)

        return query.scalar() or 0.0

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
