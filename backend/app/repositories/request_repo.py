"""
Request Repository

Handles database operations for requests table
"""
import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.request import Request

logger = logging.getLogger(__name__)


class RequestRepository:
    """Repository for request records"""

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
        tenant_id: str,
        model: str,
        messages_json: dict,
        prompt_text: str,
        prompt_hash: str,
        system_prompt: Optional[str] = None,
        user_id: Optional[str] = None,
        stream: bool = False
    ) -> Request:
        """
        Create a new request record

        Args:
            request_id: Unique request ID
            tenant_id: Tenant namespace
            model: Model name
            messages_json: Full message array
            prompt_text: Extracted user prompt
            prompt_hash: SHA256 hash of prompt
            system_prompt: Optional system prompt
            user_id: Optional user ID
            stream: Whether streaming is enabled

        Returns:
            Created Request object
        """
        request = Request(
            request_id=request_id,
            tenant_id=tenant_id,
            model=model,
            messages_json=messages_json,
            prompt_text=prompt_text,
            prompt_hash=prompt_hash,
            system_prompt=system_prompt,
            user_id=user_id,
            stream=stream
        )

        self.session.add(request)
        self.session.commit()
        self.session.refresh(request)

        logger.debug(f"Created request: {request_id}")
        return request

    def get_by_id(self, request_id: str) -> Optional[Request]:
        """
        Get request by ID

        Args:
            request_id: Request ID

        Returns:
            Request object or None
        """
        return self.session.query(Request).filter(
            Request.request_id == request_id
        ).first()

    def get_by_tenant(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Request]:
        """
        Get requests by tenant

        Args:
            tenant_id: Tenant ID
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of Request objects
        """
        return self.session.query(Request).filter(
            Request.tenant_id == tenant_id
        ).order_by(Request.created_at.desc()).limit(limit).offset(offset).all()

    def count_by_tenant(self, tenant_id: str) -> int:
        """
        Count requests by tenant

        Args:
            tenant_id: Tenant ID

        Returns:
            Request count
        """
        return self.session.query(Request).filter(
            Request.tenant_id == tenant_id
        ).count()

    def get_recent(
        self,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[Request]:
        """
        Get recent requests

        Args:
            limit: Maximum results
            since: Optional minimum timestamp

        Returns:
            List of Request objects
        """
        query = self.session.query(Request)

        if since:
            query = query.filter(Request.created_at >= since)

        return query.order_by(Request.created_at.desc()).limit(limit).all()
