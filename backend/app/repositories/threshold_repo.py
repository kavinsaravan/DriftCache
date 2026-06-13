"""
Threshold Version Repository

Handles database operations for threshold_versions table
"""
import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.threshold_version import ThresholdVersion

logger = logging.getLogger(__name__)


class ThresholdRepository:
    """Repository for threshold version records"""

    def __init__(self, session: Session):
        """
        Initialize repository

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def create(
        self,
        threshold_value: float,
        reason: Optional[str] = None,
        created_by: Optional[str] = None,
        active_from: Optional[datetime] = None
    ) -> ThresholdVersion:
        """
        Create a new threshold version

        Automatically deactivates previous version

        Args:
            threshold_value: New threshold value
            reason: Reason for change
            created_by: Who/what created this version
            active_from: When this becomes active (defaults to now)

        Returns:
            Created ThresholdVersion object
        """
        now = datetime.utcnow()
        active_from = active_from or now

        # Deactivate previous active version
        self.deactivate_current(active_until=active_from)

        # Create new version
        version = ThresholdVersion(
            threshold_value=threshold_value,
            reason=reason,
            created_by=created_by,
            active_from=active_from,
            active_until=None  # Currently active
        )

        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)

        logger.info(
            f"Created threshold version: {threshold_value} "
            f"(created_by={created_by}, reason={reason})"
        )
        return version

    def get_current(self) -> Optional[ThresholdVersion]:
        """
        Get currently active threshold version

        Returns:
            Active ThresholdVersion or None
        """
        now = datetime.utcnow()

        return self.session.query(ThresholdVersion).filter(
            and_(
                ThresholdVersion.active_from <= now,
                ThresholdVersion.active_until.is_(None)
            )
        ).first()

    def get_at_time(self, timestamp: datetime) -> Optional[ThresholdVersion]:
        """
        Get threshold version active at a specific time

        Args:
            timestamp: Point in time

        Returns:
            ThresholdVersion active at that time or None
        """
        return self.session.query(ThresholdVersion).filter(
            and_(
                ThresholdVersion.active_from <= timestamp,
                (ThresholdVersion.active_until.is_(None)) |
                (ThresholdVersion.active_until > timestamp)
            )
        ).first()

    def deactivate_current(self, active_until: Optional[datetime] = None) -> None:
        """
        Deactivate currently active threshold version

        Args:
            active_until: When to end activity (defaults to now)
        """
        active_until = active_until or datetime.utcnow()

        current = self.get_current()
        if current:
            current.active_until = active_until
            self.session.commit()
            logger.debug(f"Deactivated threshold version {current.id}")

    def get_history(self, limit: int = 100) -> List[ThresholdVersion]:
        """
        Get threshold version history

        Args:
            limit: Maximum results

        Returns:
            List of ThresholdVersion objects
        """
        return self.session.query(ThresholdVersion).order_by(
            ThresholdVersion.active_from.desc()
        ).limit(limit).all()

    def get_by_id(self, version_id: int) -> Optional[ThresholdVersion]:
        """
        Get threshold version by ID

        Args:
            version_id: Version ID

        Returns:
            ThresholdVersion object or None
        """
        return self.session.query(ThresholdVersion).filter(
            ThresholdVersion.id == version_id
        ).first()
