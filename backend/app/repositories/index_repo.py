"""
Index Version Repository

Handles database operations for index_versions table
"""
import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.index_version import IndexVersion

logger = logging.getLogger(__name__)


class IndexRepository:
    """Repository for index version records"""

    def __init__(self, session: Session):
        """
        Initialize repository

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def create(
        self,
        version_name: str,
        embedding_model: str,
        embedding_dimension: int,
        index_type: str,
        vector_count: int = 0,
        reason: Optional[str] = None,
        created_by: Optional[str] = None,
        active_from: Optional[datetime] = None
    ) -> IndexVersion:
        """
        Create a new index version

        Automatically deactivates previous version

        Args:
            version_name: Unique version identifier
            embedding_model: Embedding model name
            embedding_dimension: Vector dimension
            index_type: FAISS index type
            vector_count: Number of vectors
            reason: Reason for new version
            created_by: Who/what created this version
            active_from: When this becomes active (defaults to now)

        Returns:
            Created IndexVersion object
        """
        now = datetime.utcnow()
        active_from = active_from or now

        # Deactivate previous active version
        self.deactivate_current(active_until=active_from)

        # Create new version
        version = IndexVersion(
            version_name=version_name,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            index_type=index_type,
            vector_count=vector_count,
            reason=reason,
            created_by=created_by,
            active_from=active_from,
            active_until=None  # Currently active
        )

        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)

        logger.info(
            f"Created index version: {version_name} "
            f"(model={embedding_model}, vectors={vector_count})"
        )
        return version

    def get_current(self) -> Optional[IndexVersion]:
        """
        Get currently active index version

        Returns:
            Active IndexVersion or None
        """
        now = datetime.utcnow()

        return self.session.query(IndexVersion).filter(
            and_(
                IndexVersion.active_from <= now,
                IndexVersion.active_until.is_(None)
            )
        ).first()

    def get_at_time(self, timestamp: datetime) -> Optional[IndexVersion]:
        """
        Get index version active at a specific time

        Args:
            timestamp: Point in time

        Returns:
            IndexVersion active at that time or None
        """
        return self.session.query(IndexVersion).filter(
            and_(
                IndexVersion.active_from <= timestamp,
                (IndexVersion.active_until.is_(None)) |
                (IndexVersion.active_until > timestamp)
            )
        ).first()

    def deactivate_current(self, active_until: Optional[datetime] = None) -> None:
        """
        Deactivate currently active index version

        Args:
            active_until: When to end activity (defaults to now)
        """
        active_until = active_until or datetime.utcnow()

        current = self.get_current()
        if current:
            current.active_until = active_until
            self.session.commit()
            logger.debug(f"Deactivated index version {current.id}")

    def get_history(self, limit: int = 100) -> List[IndexVersion]:
        """
        Get index version history

        Args:
            limit: Maximum results

        Returns:
            List of IndexVersion objects
        """
        return self.session.query(IndexVersion).order_by(
            IndexVersion.active_from.desc()
        ).limit(limit).all()

    def get_by_id(self, version_id: int) -> Optional[IndexVersion]:
        """
        Get index version by ID

        Args:
            version_id: Version ID

        Returns:
            IndexVersion object or None
        """
        return self.session.query(IndexVersion).filter(
            IndexVersion.id == version_id
        ).first()

    def get_by_name(self, version_name: str) -> Optional[IndexVersion]:
        """
        Get index version by name

        Args:
            version_name: Version name

        Returns:
            IndexVersion object or None
        """
        return self.session.query(IndexVersion).filter(
            IndexVersion.version_name == version_name
        ).first()

    def update_vector_count(self, version_id: int, vector_count: int) -> None:
        """
        Update vector count for an index version

        Args:
            version_id: Version ID
            vector_count: New vector count
        """
        version = self.get_by_id(version_id)
        if version:
            version.vector_count = vector_count
            self.session.commit()
            logger.debug(f"Updated vector count for version {version_id}: {vector_count}")
