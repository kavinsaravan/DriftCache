"""
Cache Decision Engine

The "brain" that decides whether to reuse a cached response or call the LLM.

Decision factors:
1. Similarity score (primary)
2. Model compatibility
3. System prompt compatibility
4. TTL (expiration)
5. Tenant namespace
"""
import logging
from typing import Optional
from datetime import datetime

from app.models.cache_schemas import (
    CacheDecision,
    CacheDecisionResult,
    CachedResponse,
    CacheConfig,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheDecisionEngine:
    """
    Evaluates whether a cached response can be reused

    This is the core logic that balances cost savings vs correctness
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialize decision engine

        Args:
            config: Cache configuration (defaults to settings)
        """
        self.config = config or CacheConfig(
            similarity_threshold=settings.SIMILARITY_THRESHOLD,
            ttl_seconds=settings.CACHE_TTL_SECONDS
        )

        logger.info(
            f"CacheDecisionEngine initialized: "
            f"threshold={self.config.similarity_threshold}, "
            f"ttl={self.config.ttl_seconds}s"
        )

    def evaluate(
        self,
        cached_response: Optional[CachedResponse],
        similarity: Optional[float],
        requested_model: str,
        requested_system_prompt: Optional[str] = None,
        tenant_id: str = "default"
    ) -> CacheDecisionResult:
        """
        Evaluate whether to use a cached response

        Args:
            cached_response: The cached response candidate
            similarity: Similarity score [0, 1]
            requested_model: Model requested by user
            requested_system_prompt: System prompt from request
            tenant_id: Tenant namespace

        Returns:
            CacheDecisionResult with decision and reasoning
        """
        start_time = datetime.utcnow()

        # No cached response found
        if cached_response is None:
            return CacheDecisionResult(
                decision=CacheDecision.MISS,
                similarity=similarity,
                reason="No similar cached response found",
                similarity_threshold_met=False,
                model_compatible=False,
                not_expired=False,
                system_prompt_compatible=False
            )

        # Check 1: Similarity threshold
        similarity_ok = self._check_similarity(similarity)

        # Check 2: Expiration
        expired_ok = self._check_expiration(cached_response)

        # Check 3: Model compatibility
        model_ok = self._check_model_compatibility(
            cached_response.model_name,
            requested_model
        )

        # Check 4: System prompt compatibility
        system_ok = self._check_system_prompt_compatibility(
            cached_response.system_prompt,
            requested_system_prompt
        )

        # Check 5: Tenant match
        tenant_ok = self._check_tenant(cached_response.tenant_id, tenant_id)

        # Make decision
        decision, reason = self._make_decision(
            similarity_ok=similarity_ok,
            expired_ok=expired_ok,
            model_ok=model_ok,
            system_ok=system_ok,
            tenant_ok=tenant_ok,
            similarity=similarity,
            cached_response=cached_response
        )

        # Calculate evaluation time
        eval_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        result = CacheDecisionResult(
            decision=decision,
            cached_response=cached_response if decision == CacheDecision.HIT else None,
            similarity=similarity,
            reason=reason,
            similarity_threshold_met=similarity_ok,
            model_compatible=model_ok,
            not_expired=expired_ok,
            system_prompt_compatible=system_ok,
            evaluation_time_ms=eval_time
        )

        logger.info(
            f"Cache decision: {decision.value} "
            f"(similarity={similarity:.3f if similarity else 0}, "
            f"threshold={self.config.similarity_threshold})"
        )

        return result

    def _check_similarity(self, similarity: Optional[float]) -> bool:
        """Check if similarity meets threshold"""
        if similarity is None:
            return False
        return similarity >= self.config.similarity_threshold

    def _check_expiration(self, cached_response: CachedResponse) -> bool:
        """Check if cached response has not expired"""
        return not cached_response.is_expired()

    def _check_model_compatibility(
        self,
        cached_model: str,
        requested_model: str
    ) -> bool:
        """
        Check if models are compatible

        Args:
            cached_model: Model that generated cached response
            requested_model: Model requested by user

        Returns:
            True if compatible, False otherwise
        """
        # If config requires same model, do exact match
        if self.config.require_same_model:
            return cached_model == requested_model

        # Otherwise, allow reuse (Week 2 MVP behavior)
        # Later: Add smarter compatibility logic
        #   - gpt-4 can reuse gpt-4-turbo responses
        #   - But not gpt-3.5 -> gpt-4
        return True

    def _check_system_prompt_compatibility(
        self,
        cached_system: Optional[str],
        requested_system: Optional[str]
    ) -> bool:
        """
        Check if system prompts are compatible

        CRITICAL: Different system prompts should NOT share cache!

        Example:
        - "You are a legal assistant"
        - "You are a funny comedian"
        -> Should NOT reuse cache

        Args:
            cached_system: System prompt from cached response
            requested_system: System prompt from request

        Returns:
            True if compatible, False otherwise
        """
        # If we don't include system prompt in cache key, allow all
        if not self.config.include_system_prompt:
            return True

        # Both None -> compatible
        if cached_system is None and requested_system is None:
            return True

        # One None, one not -> incompatible
        if (cached_system is None) != (requested_system is None):
            return False

        # Both exist -> must match exactly
        return cached_system == requested_system

    def _check_tenant(self, cached_tenant: str, requested_tenant: str) -> bool:
        """Check if tenants match"""
        return cached_tenant == requested_tenant

    def _make_decision(
        self,
        similarity_ok: bool,
        expired_ok: bool,
        model_ok: bool,
        system_ok: bool,
        tenant_ok: bool,
        similarity: Optional[float],
        cached_response: CachedResponse
    ) -> tuple[CacheDecision, str]:
        """
        Make final cache decision based on all factors

        Args:
            similarity_ok: Similarity threshold met
            expired_ok: Not expired
            model_ok: Model compatible
            system_ok: System prompt compatible
            tenant_ok: Tenant matches
            similarity: Similarity score
            cached_response: Cached response

        Returns:
            (decision, reason) tuple
        """
        # Check tenant first (security)
        if not tenant_ok:
            return (
                CacheDecision.MISS,
                "Tenant mismatch"
            )

        # Check expiration
        if not expired_ok:
            return (
                CacheDecision.EXPIRED,
                f"Cache entry expired at {cached_response.expires_at}"
            )

        # Check system prompt
        if not system_ok:
            return (
                CacheDecision.SYSTEM_MISMATCH,
                "System prompt incompatible"
            )

        # Check model
        if not model_ok:
            return (
                CacheDecision.MODEL_MISMATCH,
                f"Model mismatch: cached={cached_response.model_name}"
            )

        # Check similarity (primary criterion)
        if not similarity_ok:
            return (
                CacheDecision.THRESHOLD_NOT_MET,
                f"Similarity {similarity:.3f if similarity else 0} "
                f"< threshold {self.config.similarity_threshold}"
            )

        # ALL checks passed -> CACHE HIT!
        return (
            CacheDecision.HIT,
            f"Cache hit with similarity {similarity:.3f if similarity else 0}"
        )

    def update_config(self, **updates) -> None:
        """
        Update configuration

        Args:
            **updates: Fields to update
        """
        for key, value in updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"Updated config: {key}={value}")

    def get_config(self) -> CacheConfig:
        """Get current configuration"""
        return self.config


# Global instance
_decision_engine: Optional[CacheDecisionEngine] = None


def get_decision_engine() -> CacheDecisionEngine:
    """
    Get global decision engine instance

    Returns:
        CacheDecisionEngine singleton
    """
    global _decision_engine

    if _decision_engine is None:
        _decision_engine = CacheDecisionEngine()

    return _decision_engine
