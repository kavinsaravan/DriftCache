"""
Index Health Monitoring

Calculates FAISS index health metrics to detect when rebuild is needed
"""
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class IndexHealthMonitor:
    """
    Monitors FAISS index health

    Tracks:
    - Vector count vs active cache count
    - Search latency trends
    - Stale vector ratio
    - Index age
    """

    def __init__(self, db_session=None):
        self.db_session = db_session

    def calculate_health_metrics(
        self,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive index health metrics

        Args:
            tenant_id: Optional tenant isolation

        Returns:
            Health metrics dictionary
        """
        logger.info("Calculating index health metrics")

        # For Week 7, return mock metrics
        # In production, this would query actual FAISS index and database

        metrics = {
            "vector_count": 15234,
            "active_cache_count": 12450,
            "stale_vector_count": 2784,
            "stale_vector_ratio": 0.183,  # 18.3% stale
            "index_age_hours": 72.5,
            "avg_search_latency_ms": 8.3,
            "p95_search_latency_ms": 12.7,
            "p99_search_latency_ms": 18.2,
            "health_status": self._determine_health_status(
                stale_ratio=0.183,
                avg_latency=8.3,
                age_hours=72.5
            ),
            "tenant_id": tenant_id,
            "measured_at": datetime.utcnow().isoformat(),
        }

        logger.info(
            f"Index health: {metrics['health_status']}, "
            f"stale_ratio={metrics['stale_vector_ratio']:.1%}, "
            f"latency={metrics['avg_search_latency_ms']:.1f}ms"
        )

        return metrics

    def _determine_health_status(
        self,
        stale_ratio: float,
        avg_latency: float,
        age_hours: float
    ) -> str:
        """
        Determine overall index health status

        Args:
            stale_ratio: Ratio of stale vectors
            avg_latency: Average search latency in ms
            age_hours: Index age in hours

        Returns:
            Health status: healthy, degraded, critical
        """
        # Critical conditions
        if stale_ratio > 0.30:  # >30% stale
            return "critical"
        if avg_latency > 50:  # >50ms average latency
            return "critical"

        # Degraded conditions
        if stale_ratio > 0.15:  # >15% stale
            return "degraded"
        if avg_latency > 20:  # >20ms average latency
            return "degraded"
        if age_hours > 168:  # >7 days old
            return "degraded"

        # Healthy
        return "healthy"

    def needs_rebuild(
        self,
        health_metrics: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Determine if index needs rebuild

        Args:
            health_metrics: Pre-calculated health metrics (optional)
            tenant_id: Optional tenant isolation

        Returns:
            (needs_rebuild, reason)
        """
        if health_metrics is None:
            health_metrics = self.calculate_health_metrics(tenant_id=tenant_id)

        stale_ratio = health_metrics.get("stale_vector_ratio", 0)
        avg_latency = health_metrics.get("avg_search_latency_ms", 0)
        age_hours = health_metrics.get("index_age_hours", 0)
        health_status = health_metrics.get("health_status", "unknown")

        # Decision rules

        # Critical: High stale ratio
        if stale_ratio > 0.25:
            return True, f"High stale vector ratio ({stale_ratio:.1%})"

        # Critical: High latency
        if avg_latency > 40:
            return True, f"High search latency ({avg_latency:.1f}ms)"

        # Warning: Index very old with moderate staleness
        if age_hours > 168 and stale_ratio > 0.15:
            return True, f"Old index ({age_hours:.0f}h) with moderate staleness ({stale_ratio:.1%})"

        # Critical health status
        if health_status == "critical":
            return True, f"Index health critical: stale={stale_ratio:.1%}, latency={avg_latency:.1f}ms"

        # No rebuild needed
        return False, f"Index healthy: stale={stale_ratio:.1%}, latency={avg_latency:.1f}ms, age={age_hours:.0f}h"

    def get_stale_vector_ratio(
        self,
        tenant_id: Optional[str] = None
    ) -> float:
        """
        Calculate ratio of stale vectors

        Stale vectors are those that point to expired or deleted cache entries

        Args:
            tenant_id: Optional tenant isolation

        Returns:
            Stale vector ratio (0-1)
        """
        # Mock implementation for Week 7
        # In production, this would:
        # 1. Count total vectors in FAISS
        # 2. Count active cache entries in database
        # 3. Calculate stale ratio

        if self.db_session:
            # TODO: Query actual database for active cache count
            # from app.models.cache_entry import CacheEntry
            # active_count = self.db_session.query(CacheEntry).filter(
            #     CacheEntry.is_active == True,
            #     CacheEntry.tenant_id == tenant_id
            # ).count()
            pass

        # Mock data
        total_vectors = 15234
        active_cache = 12450
        stale_vectors = total_vectors - active_cache
        stale_ratio = stale_vectors / total_vectors if total_vectors > 0 else 0

        return stale_ratio

    def get_search_latency_metrics(
        self,
        tenant_id: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Get search latency statistics

        Args:
            tenant_id: Optional tenant isolation

        Returns:
            Latency metrics (avg, p95, p99)
        """
        # Mock implementation for Week 7
        # In production, this would query metrics table for recent FAISS searches

        return {
            "avg_latency_ms": 8.3,
            "p50_latency_ms": 6.2,
            "p95_latency_ms": 12.7,
            "p99_latency_ms": 18.2,
            "sample_count": 5420,
        }

    def get_index_age(
        self,
        tenant_id: Optional[str] = None
    ) -> float:
        """
        Get index age in hours

        Args:
            tenant_id: Optional tenant isolation

        Returns:
            Index age in hours
        """
        # Mock implementation for Week 7
        # In production, this would query index_versions table

        if self.db_session:
            # TODO: Query index_versions for active index
            # from app.models.index_version import IndexVersion
            # active_index = self.db_session.query(IndexVersion).filter(
            #     IndexVersion.is_active == True,
            #     IndexVersion.tenant_id == tenant_id
            # ).first()
            # if active_index:
            #     age = datetime.utcnow() - active_index.created_at
            #     return age.total_seconds() / 3600
            pass

        # Mock: 3 days old
        return 72.5

    def generate_health_report(
        self,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive health report

        Args:
            tenant_id: Optional tenant isolation

        Returns:
            Health report with metrics and recommendations
        """
        health_metrics = self.calculate_health_metrics(tenant_id=tenant_id)
        needs_rebuild, rebuild_reason = self.needs_rebuild(health_metrics=health_metrics)

        recommendations = []

        # Generate recommendations
        if health_metrics["stale_vector_ratio"] > 0.20:
            recommendations.append({
                "priority": "high",
                "action": "schedule_rebuild",
                "reason": f"Stale vector ratio {health_metrics['stale_vector_ratio']:.1%} exceeds 20%"
            })
        elif health_metrics["stale_vector_ratio"] > 0.10:
            recommendations.append({
                "priority": "medium",
                "action": "monitor_staleness",
                "reason": f"Stale vector ratio {health_metrics['stale_vector_ratio']:.1%} approaching threshold"
            })

        if health_metrics["avg_search_latency_ms"] > 30:
            recommendations.append({
                "priority": "high",
                "action": "optimize_index",
                "reason": f"Search latency {health_metrics['avg_search_latency_ms']:.1f}ms is elevated"
            })

        if health_metrics["index_age_hours"] > 168:  # 7 days
            recommendations.append({
                "priority": "low",
                "action": "consider_refresh",
                "reason": f"Index is {health_metrics['index_age_hours']:.0f} hours old"
            })

        return {
            "health_metrics": health_metrics,
            "needs_rebuild": needs_rebuild,
            "rebuild_reason": rebuild_reason,
            "recommendations": recommendations,
            "summary": self._generate_summary(health_metrics, needs_rebuild, rebuild_reason)
        }

    def _generate_summary(
        self,
        health_metrics: Dict[str, Any],
        needs_rebuild: bool,
        rebuild_reason: str
    ) -> str:
        """Generate human-readable summary"""
        status = health_metrics["health_status"]
        stale_ratio = health_metrics["stale_vector_ratio"]
        latency = health_metrics["avg_search_latency_ms"]

        summary = f"Index health: {status.upper()}\n"
        summary += f"Stale vectors: {stale_ratio:.1%}\n"
        summary += f"Average latency: {latency:.1f}ms\n"

        if needs_rebuild:
