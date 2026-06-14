"""
Index Manager

Manages FAISS index versions and swapping
"""
from typing import Optional, Dict, Any
import logging
from datetime import datetime
from pathlib import Path

from app.models.index_version import IndexVersion
from app.database.session import get_db_session

logger = logging.getLogger(__name__)


class IndexManager:
    """
    Manages FAISS index lifecycle

    Responsibilities:
    - Track active index version
    - Swap indexes safely
    - Rollback to previous version
    - Maintain index metadata
    """

    def __init__(self, index_storage_path: str = "/var/lib/driftcache/indexes"):
        self.index_storage_path = Path(index_storage_path)

    def get_active_index_version(
        self,
        tenant_id: Optional[str] = None
    ) -> Optional[IndexVersion]:
        """
        Get currently active index version

        Args:
            tenant_id: Optional tenant isolation

        Returns:
            Active IndexVersion or None
        """
        with get_db_session() as session:
            version = session.query(IndexVersion).filter(
                IndexVersion.is_active == True,
                IndexVersion.tenant_id == tenant_id
            ).order_by(IndexVersion.created_at.desc()).first()

            return version

    def create_index_version(
        self,
        version_name: str,
        embedding_model: str,
        embedding_dimension: int,
        index_type: str,
        vector_count: int,
        reason: str,
        created_by: str,
        file_path: str,
        rebuild_job_id: Optional[int] = None,
        tenant_id: Optional[str] = None
    ) -> IndexVersion:
        """
        Create new index version record

        Args:
            version_name: Unique version identifier
            embedding_model: Model name
            embedding_dimension: Vector dimension
            index_type: FAISS index type
            vector_count: Number of vectors
            reason: Why this version was created
            created_by: Creator identifier
            file_path: Path to index file
            rebuild_job_id: Optional rebuild job reference
            tenant_id: Optional tenant isolation

        Returns:
            Created IndexVersion
        """
        with get_db_session() as session:
            now = datetime.utcnow()

            new_version = IndexVersion(
                version_name=version_name,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dimension,
                index_type=index_type,
                vector_count=vector_count,
                reason=reason,
                created_by=created_by,
                rebuild_job_id=rebuild_job_id,
                file_path=file_path,
                is_active=False,  # Not active yet
                active_from=now,
                active_until=None,
                tenant_id=tenant_id
            )

            session.add(new_version)
            session.commit()
            session.refresh(new_version)

            logger.info(f"Created index version: {version_name}")
            return new_version

    def activate_index_version(
        self,
        version_id: int,
        tenant_id: Optional[str] = None
    ) -> bool:
        """
        Activate an index version (swap operation)

        Args:
            version_id: ID of version to activate
            tenant_id: Optional tenant isolation

        Returns:
            Success status
        """
        with get_db_session() as session:
            # Deactivate current active version
            current_active = session.query(IndexVersion).filter(
                IndexVersion.is_active == True,
                IndexVersion.tenant_id == tenant_id
            ).all()

            now = datetime.utcnow()
            for version in current_active:
                version.is_active = False
                version.active_until = now
                logger.info(f"Deactivated index version: {version.version_name}")

            # Activate new version
            new_active = session.query(IndexVersion).filter(
                IndexVersion.id == version_id
            ).first()

            if not new_active:
                logger.error(f"Index version {version_id} not found")
                return False

            new_active.is_active = True
            new_active.active_from = now
            new_active.active_until = None

            session.commit()

            logger.info(f"Activated index version: {new_active.version_name}")
            return True

    def rollback_to_previous_version(
        self,
        tenant_id: Optional[str] = None
    ) -> Optional[IndexVersion]:
        """
        Rollback to previous index version

        Args:
            tenant_id: Optional tenant isolation

        Returns:
            Rollback version or None
        """
        with get_db_session() as session:
            # Get most recent non-active version
            previous_version = session.query(IndexVersion).filter(
                IndexVersion.is_active == False,
                IndexVersion.tenant_id == tenant_id
            ).order_by(IndexVersion.created_at.desc()).first()

            if not previous_version:
                logger.warning("No previous version to rollback to")
                return None

            # Activate previous version
            success = self.activate_index_version(
                previous_version.id,
                tenant_id=tenant_id
            )

            if success:
                logger.info(f"Rolled back to version: {previous_version.version_name}")
                return previous_version
            else:
                return None

    def get_index_file_path(
        self,
        version_name: str,
        tenant_id: Optional[str] = None
    ) -> Path:
        """
        Get file path for index version

        Args:
            version_name: Version identifier
            tenant_id: Optional tenant isolation

        Returns:
            Path to index file
        """
        if tenant_id:
            return self.index_storage_path / tenant_id / f"{version_name}.faiss"
        else:
            return self.index_storage_path / f"{version_name}.faiss"

    def get_index_history(
        self,
        limit: int = 10,
        tenant_id: Optional[str] = None
    ) -> list[Dict[str, Any]]:
        """
        Get index version history

        Args:
            limit: Number of versions to return
            tenant_id: Optional tenant filter

        Returns:
            List of index version summaries
        """
        with get_db_session() as session:
            query = session.query(IndexVersion)

            if tenant_id:
                query = query.filter(IndexVersion.tenant_id == tenant_id)

            versions = query.order_by(IndexVersion.created_at.desc()).limit(limit).all()

            return [v.to_dict() for v in versions]
