"""
Index Management Tools

LangChain tools for FAISS index operations and rebuilding
"""
from typing import Optional, Dict, Any
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class IndexStatusInput(BaseModel):
    """Input schema for index status tool"""
    tenant_id: Optional[str] = Field(None, description="Optional tenant ID")


class IndexStatusTool(BaseTool):
    """
    Tool for getting FAISS index status

    Returns health and performance metrics for vector index
    """
    name: str = "get_index_status"
    description: str = """
    Gets FAISS index health and performance status.

    Returns:
    - index_size: Number of vectors in index
    - last_rebuild: When index was last rebuilt
    - avg_search_time_ms: Average vector search latency
    - index_version: Current index version identifier
    - health_status: Index health (healthy/degraded/critical)

    Use this to detect if index is degrading and needs rebuild.

    Signs of degradation:
    - Increasing search latency
    - High drift score with low recall
    - Age > 30 days with high query volume
    """
    args_schema: type[BaseModel] = IndexStatusInput

    def _run(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get index status"""
        try:
            logger.info(f"Getting index status for tenant_id={tenant_id}")

            # Get real FAISS index data
            from app.vectorstore.search import get_search_service
            from app.core.config import settings
            import os
            from pathlib import Path

            search_service = get_search_service()
            faiss_index = search_service.faiss_index

            # Get index size from FAISS
            index_size = 0
            if faiss_index and faiss_index.index is not None:
                index_size = faiss_index.index.ntotal

            # Get embedding model and dimension from settings
            embedding_model = settings.EMBEDDING_MODEL
            dimension = settings.EMBEDDING_DIMENSION

            # Get last rebuild time from index file modification time
            last_rebuild = None
            days_since_rebuild = None
            index_path = faiss_index.index_path if faiss_index else None

            if index_path and os.path.exists(index_path):
                mtime = os.path.getmtime(index_path)
                last_rebuild_dt = datetime.fromtimestamp(mtime)
                last_rebuild = last_rebuild_dt.isoformat() + "Z"
                days_since_rebuild = (datetime.utcnow() - last_rebuild_dt).days
            else:
                last_rebuild = None
                days_since_rebuild = None

            # Determine health status
            health_status = "healthy"
            if index_size == 0:
                health_status = "empty"
            elif days_since_rebuild and days_since_rebuild > 30:
                health_status = "degraded"

            # Create version identifier
            index_version = f"v1_{last_rebuild_dt.strftime('%Y%m%d')}" if last_rebuild_dt else "unknown"

            return {
                "index_size": index_size,
                "last_rebuild": last_rebuild,
                "avg_search_time_ms": 12.3,  # TODO: Track real search times
                "index_version": index_version,
                "embedding_model": embedding_model,
                "dimension": dimension,
                "health_status": health_status,
                "days_since_rebuild": days_since_rebuild,
                "tenant_id": tenant_id,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Failed to get index status: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }


class TriggerRebuildInput(BaseModel):
    """Input schema for trigger rebuild tool"""
    reason: str = Field(..., description="Reason for rebuild")
    priority: str = Field("normal", description="Priority: low, normal, high, urgent")
    dry_run: bool = Field(True, description="If True, only simulate rebuild")
    tenant_id: Optional[str] = Field(None, description="Optional tenant ID")


class TriggerIndexRebuildTool(BaseTool):
    """
    Tool for triggering FAISS index rebuild

    Self-healing vector infrastructure
    """
    name: str = "trigger_index_rebuild"
    description: str = """
    Triggers or schedules FAISS index rebuild.

    Use cases:
    - High drift score (>0.75) with semantic distribution change
    - Search latency degradation
    - Index staleness (>30 days old with high volume)
    - After major prompt pattern shift

    Process:
    1. Creates rebuild job in queue
    2. Rebuilds index with recent embeddings
    3. Validates new index performance
    4. Swaps to new index
    5. Archives old index

    Priority levels:
    - low: Scheduled during off-peak (next maintenance window)
    - normal: Scheduled within 24 hours
    - high: Scheduled within 6 hours
    - urgent: Immediate rebuild (use with caution)

    By default runs in dry-run mode .
    Will implement actual rebuild pipeline.
    """
    args_schema: type[BaseModel] = TriggerRebuildInput

    def _run(
        self,
        reason: str,
        priority: str = "normal",
        dry_run: bool = True,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Trigger index rebuild"""
        try:
            logger.info(
                f"Index rebuild trigger: reason={reason}, "
                f"priority={priority}, dry_run={dry_run}, tenant_id={tenant_id}"
            )

            # Validate priority
            valid_priorities = ["low", "normal", "high", "urgent"]
            if priority not in valid_priorities:
                return {
                    "error": f"Priority must be one of: {valid_priorities}",
                    "status": "failed"
                }

            if dry_run:
                #  Simulation mode
                job_id = f"rebuild_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

                # Estimate rebuild time based on index size
                estimated_duration_minutes = 45  # Mock value

                # Calculate schedule based on priority
                schedule_map = {
                    "low": "next_maintenance_window",
                    "normal": "within_24_hours",
                    "high": "within_6_hours",
                    "urgent": "immediate"
                }

                return {
                    "status": "simulated",
                    "job_id": job_id,
                    "job_type": "INDEX_REBUILD",
                    "priority": priority,
                    "scheduled": schedule_map[priority],
                    "reason": reason,
                    "action": "would_create_rebuild_job",
                    "message": f"DRY RUN: Would create {priority} priority rebuild job",
                    "estimated_impact": {
                        "duration_minutes": estimated_duration_minutes,
                        "downtime_required": False,
                        "performance_impact": "minimal_during_rebuild",
                        "expected_improvements": [
                            "Reduced search latency",
                            "Better recall on recent queries",
                            "Updated embeddings distribution"
                        ]
                    },
                    "details": {
                        "would_create_job": True,
                        "would_backup_current_index": True,
                        "would_rebuild_with_recent_data": True,
                        "would_validate_new_index": True,
                        "would_swap_indexes": True,
                        "reason": reason,
                        "tenant_id": tenant_id
                    }
                }

        except Exception as e:
            logger.error(f"Index rebuild trigger failed: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }


def get_index_tools():
    """Get all index-related tools"""
    return [
        IndexStatusTool(),
        TriggerIndexRebuildTool(),
    ]
