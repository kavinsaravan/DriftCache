"""
Metrics Service

Coordinates metric retrieval for the API

This is what the dashboard calls to get metrics
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.metrics.calculator import MetricsCalculator
from app.database.session import get_db_manager

logger = logging.getLogger(__name__)


class MetricsService:
    """
    Metrics service for API consumption

    Frontend should call this, not database directly
    """

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize metrics service

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

    def get_summary(
        self,
        period: str = "24h",
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get summary metrics for dashboard

        Args:
            period: Time period ("1h", "24h", "7d", "30d")
            tenant_id: Optional tenant filter

        Returns:
            Summary metrics dictionary
        """
        since = self._parse_period(period)
        calculator = MetricsCalculator(self.session)

        return calculator.calculate_summary(
            since=since,
            tenant_id=tenant_id
        )

    def get_latency_stats(
        self,
        period: str = "24h",
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get latency statistics

        Args:
            period: Time period
            tenant_id: Optional tenant filter

        Returns:
            Latency breakdown
        """
        since = self._parse_period(period)
        calculator = MetricsCalculator(self.session)

        return calculator.calculate_latency_breakdown(
            since=since,
            tenant_id=tenant_id
        )

    def get_similarity_distribution(
        self,
        period: str = "24h",
        tenant_id: Optional[str] = None,
        bins: int = 10
    ) -> Dict[str, int]:
        """
        Get similarity score distribution

        Args:
            period: Time period
            tenant_id: Optional tenant filter
            bins: Number of histogram bins

        Returns:
            Distribution dict
        """
        since = self._parse_period(period)
        calculator = MetricsCalculator(self.session)

        return calculator.calculate_similarity_distribution(
            since=since,
            tenant_id=tenant_id,
            bins=bins
        )

    def get_top_cached_prompts(
        self,
        limit: int = 10,
        period: str = "24h",
        tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get top cached prompts

        Args:
            limit: Maximum results
            period: Time period
            tenant_id: Optional tenant filter

        Returns:
            List of top prompts
        """
        since = self._parse_period(period)
        calculator = MetricsCalculator(self.session)

        return calculator.calculate_top_cached_prompts(
            limit=limit,
            since=since,
            tenant_id=tenant_id
        )

    def get_provider_usage(
        self,
        period: str = "24h",
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get provider usage statistics

        Args:
            period: Time period
            tenant_id: Optional tenant filter

        Returns:
            Provider usage breakdown
        """
        since = self._parse_period(period)
        calculator = MetricsCalculator(self.session)

        return calculator.calculate_provider_usage(
            since=since,
            tenant_id=tenant_id
        )

    def get_time_series(
        self,
        metric: str,
        period: str = "24h",
        interval: str = "1h",
        tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get time series data for a metric

        Args:
            metric: "hit_rate", "latency", "requests"
            period: Time period
            interval: Bucket size ("5m", "1h", "1d")
            tenant_id: Optional tenant filter

        Returns:
            Time series data points
        """
        since = self._parse_period(period)
        until = datetime.utcnow()
        interval_minutes = self._parse_interval(interval)

        calculator = MetricsCalculator(self.session)

        return calculator.calculate_time_series(
            metric=metric,
            since=since,
            until=until,
            interval_minutes=interval_minutes,
            tenant_id=tenant_id
        )

    def get_dashboard_data(
        self,
        period: str = "24h",
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get complete dashboard data in one call

        This reduces API calls for the frontend

        Args:
            period: Time period
            tenant_id: Optional tenant filter

        Returns:
            Complete dashboard data
        """
        calculator = MetricsCalculator(self.session)
        since = self._parse_period(period)

        return {
            "period": period,
            "generated_at": datetime.utcnow().isoformat(),

            # Summary metrics
            "summary": calculator.calculate_summary(
                since=since,
                tenant_id=tenant_id
            ),

            # Latency comparison
            "latency": calculator.calculate_latency_breakdown(
                since=since,
                tenant_id=tenant_id
            ),

            # Similarity distribution
            "similarity_distribution": calculator.calculate_similarity_distribution(
                since=since,
                tenant_id=tenant_id,
                bins=10
            ),

            # Top prompts
            "top_cached_prompts": calculator.calculate_top_cached_prompts(
                limit=5,
                since=since,
                tenant_id=tenant_id
            ),

            # Provider usage
            "provider_usage": calculator.calculate_provider_usage(
                since=since,
                tenant_id=tenant_id
            )
        }

    def _parse_period(self, period: str) -> datetime:
        """
        Parse period string to datetime

        Args:
            period: "1h", "24h", "7d", "30d"

        Returns:
            Start datetime
        """
        now = datetime.utcnow()

        if period == "1h":
            return now - timedelta(hours=1)
        elif period == "24h":
            return now - timedelta(hours=24)
        elif period == "7d":
            return now - timedelta(days=7)
        elif period == "30d":
            return now - timedelta(days=30)
        else:
            # Default to 24 hours
            return now - timedelta(hours=24)

    def _parse_interval(self, interval: str) -> int:
        """
        Parse interval string to minutes

        Args:
            interval: "5m", "1h", "1d"

        Returns:
            Interval in minutes
        """
        if interval == "5m":
            return 5
        elif interval == "15m":
            return 15
        elif interval == "1h":
            return 60
        elif interval == "6h":
            return 360
        elif interval == "1d":
            return 1440
        else:
            # Default to 1 hour
            return 60


def get_metrics_service(session: Optional[Session] = None) -> MetricsService:
    """
    Get metrics service instance

    Args:
        session: Optional SQLAlchemy session

    Returns:
        MetricsService instance
    """
    return MetricsService(session=session)
