"""
Metrics Collector

Captures request-level metrics during the request flow

This is the "sensory system" that measures what's happening in real-time
"""
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """
    Request-level metrics

    Tracks latency breakdown and cache performance for a single request
    """
    # Request identification
    request_id: str
    tenant_id: str = "default"
    user_id: Optional[str] = None

    # Timestamps
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    # Latency breakdown (milliseconds)
    total_latency_ms: Optional[float] = None
    embedding_latency_ms: Optional[float] = None
    faiss_search_latency_ms: Optional[float] = None
    redis_lookup_latency_ms: Optional[float] = None
    provider_latency_ms: Optional[float] = None
    cache_decision_latency_ms: Optional[float] = None

    # Cache status
    cache_status: Optional[str] = None  # HIT, MISS, EXPIRED, etc.
    similarity_score: Optional[float] = None
    threshold_used: Optional[float] = None

    # Token usage
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    # Cost estimates
    estimated_provider_cost: Optional[float] = None
    estimated_cost_saved: Optional[float] = None

    # Model info
    model: Optional[str] = None
    embedding_model: Optional[str] = None
    provider: Optional[str] = None

    # Cache info
    matched_cache_id: Optional[str] = None
    retrieval_source: Optional[str] = None  # "redis" or "legacy"

    def start_phase(self, phase_name: str) -> float:
        """
        Start timing a phase

        Args:
            phase_name: Name of the phase (for logging)

        Returns:
            Start time for this phase
        """
        return time.time()

    def record_phase(
        self,
        phase_name: str,
        start_time: float,
        latency_attr: str
    ) -> None:
        """
        Record a phase latency

        Args:
            phase_name: Name of the phase
            start_time: When the phase started
            latency_attr: Attribute name to store latency
        """
        latency_ms = (time.time() - start_time) * 1000
        setattr(self, latency_attr, latency_ms)
        logger.debug(f"{phase_name}: {latency_ms:.2f}ms")

    def finish(self) -> None:
        """Complete the request and calculate total latency"""
        self.end_time = time.time()
        self.total_latency_ms = (self.end_time - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for logging/storage

        Returns:
            Dictionary representation
        """
        return {
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,

            # Latency
            "total_latency_ms": self.total_latency_ms,
            "embedding_latency_ms": self.embedding_latency_ms,
            "faiss_search_latency_ms": self.faiss_search_latency_ms,
            "redis_lookup_latency_ms": self.redis_lookup_latency_ms,
            "provider_latency_ms": self.provider_latency_ms,
            "cache_decision_latency_ms": self.cache_decision_latency_ms,

            # Cache
            "cache_status": self.cache_status,
            "similarity_score": self.similarity_score,
            "threshold_used": self.threshold_used,
            "matched_cache_id": self.matched_cache_id,
            "retrieval_source": self.retrieval_source,

            # Tokens
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,

            # Cost
            "estimated_provider_cost": self.estimated_provider_cost,
            "estimated_cost_saved": self.estimated_cost_saved,

            # Models
            "model": self.model,
            "embedding_model": self.embedding_model,
            "provider": self.provider,
        }

    def log_summary(self) -> None:
        """Log a summary of this request's metrics"""
        logger.info(
            f"Request {self.request_id[:8]}... | "
            f"Status: {self.cache_status} | "
            f"Latency: {self.total_latency_ms:.1f}ms | "
            f"Similarity: {self.similarity_score:.3f if self.similarity_score else 'N/A'} | "
            f"Cost saved: ${self.estimated_cost_saved:.4f if self.estimated_cost_saved else 0}"
        )


class MetricsCollector:
    """
    Metrics collection service

    Coordinates metric capture across the request lifecycle
    """

    def __init__(self):
        """Initialize metrics collector"""
        self.active_requests: Dict[str, RequestMetrics] = {}
        logger.info("MetricsCollector initialized")

    def start_request(
        self,
        request_id: str,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> RequestMetrics:
        """
        Start tracking a new request

        Args:
            request_id: Unique request ID
            tenant_id: Tenant namespace
            user_id: Optional user ID
            model: Model name

        Returns:
            RequestMetrics instance
        """
        metrics = RequestMetrics(
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            model=model
        )

        self.active_requests[request_id] = metrics
        logger.debug(f"Started tracking request {request_id[:8]}...")

        return metrics

    def get_request(self, request_id: str) -> Optional[RequestMetrics]:
        """
        Get metrics for an active request

        Args:
            request_id: Request ID

        Returns:
            RequestMetrics or None
        """
        return self.active_requests.get(request_id)

    def finish_request(self, request_id: str) -> Optional[RequestMetrics]:
        """
        Finish tracking a request

        Args:
            request_id: Request ID

        Returns:
            Final RequestMetrics or None
        """
        metrics = self.active_requests.pop(request_id, None)

        if metrics:
            metrics.finish()
            metrics.log_summary()

        return metrics

    def estimate_cost(
        self,
        model: str,
        input_tokens: Optional[int],
        output_tokens: Optional[int]
    ) -> float:
        """
        Estimate cost for a provider call

        Simplified pricing model for MVP

        Args:
            model: Model name
            input_tokens: Input token count
            output_tokens: Output token count

        Returns:
            Estimated cost in USD
        """
        if not input_tokens and not output_tokens:
            return 0.0

        # Simplified pricing (per 1M tokens)
        # In production, use actual provider pricing tables
        pricing = {
            # OpenAI
            "gpt-4o": {"input": 5.00, "output": 15.00},
            "gpt-4o-mini": {"input": 0.150, "output": 0.600},
            "gpt-4-turbo": {"input": 10.00, "output": 30.00},
            "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},

            # Anthropic
            "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
            "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
            "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},

            # Default
            "default": {"input": 1.00, "output": 3.00}
        }

        # Get model pricing or use default
        model_pricing = pricing.get(model, pricing["default"])

        # Calculate cost
        input_cost = ((input_tokens or 0) / 1_000_000) * model_pricing["input"]
        output_cost = ((output_tokens or 0) / 1_000_000) * model_pricing["output"]

        return input_cost + output_cost

    def estimate_cost_saved(
        self,
        model: str,
        cached_response_length: int
    ) -> float:
        """
        Estimate cost saved by cache hit

        Args:
            model: Model name
            cached_response_length: Length of cached response in characters

        Returns:
            Estimated cost saved in USD
        """
        # Rough estimate: 1 token ≈ 4 characters
        estimated_output_tokens = cached_response_length // 4

        # For cache hit, we avoid output tokens
        # (input tokens still needed for prompt embedding, but much smaller)
        return self.estimate_cost(
            model=model,
            input_tokens=0,
            output_tokens=estimated_output_tokens
        )


# Global instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """
    Get global metrics collector instance

    Returns:
        MetricsCollector singleton
    """
    global _metrics_collector

    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()

    return _metrics_collector
