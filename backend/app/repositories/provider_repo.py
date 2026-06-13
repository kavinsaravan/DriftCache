"""
Provider Call Repository

Handles database operations for provider_calls table
"""
import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.provider_call import ProviderCall

logger = logging.getLogger(__name__)


class ProviderRepository:
    """Repository for provider call records"""

    def __init__(self, session: Session):
        """
        Initialize repository

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def create(
        self,
        request_id: str,
        provider: str,
        model: str,
        tenant_id: str,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        estimated_cost: Optional[float] = None,
        latency_ms: Optional[float] = None,
        user_id: Optional[str] = None
    ) -> ProviderCall:
        """
        Create a provider call record

        Args:
            request_id: Request ID
            provider: Provider name
            model: Model name
            tenant_id: Tenant namespace
            input_tokens: Input token count
            output_tokens: Output token count
            total_tokens: Total token count
            estimated_cost: Estimated cost in USD
            latency_ms: Provider latency
            user_id: Optional user ID

        Returns:
            Created ProviderCall object
        """
        call = ProviderCall(
            request_id=request_id,
            provider=provider,
            model=model,
            tenant_id=tenant_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            latency_ms=latency_ms,
            user_id=user_id
        )

        self.session.add(call)
        self.session.commit()
        self.session.refresh(call)

        logger.debug(f"Created provider call: {provider}/{model} for request {request_id}")
        return call

    def get_by_request(self, request_id: str) -> Optional[ProviderCall]:
        """
        Get provider call by request ID

        Args:
            request_id: Request ID

        Returns:
            ProviderCall object or None
        """
        return self.session.query(ProviderCall).filter(
            ProviderCall.request_id == request_id
        ).first()

    def get_recent(
        self,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[ProviderCall]:
        """
        Get recent provider calls

        Args:
            limit: Maximum results
            since: Optional minimum timestamp

        Returns:
            List of ProviderCall objects
        """
        query = self.session.query(ProviderCall)

        if since:
            query = query.filter(ProviderCall.created_at >= since)

        return query.order_by(ProviderCall.created_at.desc()).limit(limit).all()

    def get_by_provider(
        self,
        provider: str,
        limit: int = 100
    ) -> List[ProviderCall]:
        """
        Get calls by provider

        Args:
            provider: Provider name
            limit: Maximum results

        Returns:
            List of ProviderCall objects
        """
        return self.session.query(ProviderCall).filter(
            ProviderCall.provider == provider
        ).order_by(ProviderCall.created_at.desc()).limit(limit).all()
