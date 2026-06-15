"""
Vectorstore / FAISS Index Management Endpoints

Provides API endpoints for:
- Index health monitoring
- Index rebuild triggers
- Version management
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import logging

from app.vectorstore.index_health import IndexHealthMonitor
from app.agents.index_rebuild_agent import IndexRebuildAgent

logger = logging.getLogger(__name__)

router = APIRouter()


# Response models
class IndexHealthResponse(BaseModel):
    """Index health metrics response"""
    vector_count: int
    active_cache_count: int
    stale_vector_count: int
    stale_vector_ratio: float
    index_age_hours: float
    avg_search_latency_ms: float
    p95_search_latency_ms: float
    p99_search_latency_ms: float
    health_status: str
    measured_at: str
    tenant_id: Optional[str] = None


class IndexRebuildResponse(BaseModel):
    """Index rebuild result response"""
    status: str
    rebuild_id: str
    old_index_version: Optional[str] = None
    new_index_version: Optional[str] = None
    old_vector_count: int
    new_vector_count: int
    vectors_added: int
    vectors_removed: int
    rebuild_duration_ms: float
    validation_passed: bool
    rebuild_job_id: Optional[int] = None


@router.get("/health", response_model=IndexHealthResponse)
async def get_index_health(
    tenant_id: Optional[str] = Query(None, description="Optional tenant ID for isolation")
):
    """
    Get FAISS index health metrics

    Returns:
    - vector_count: Total vectors in index
    - active_cache_count: Active cache entries
    - stale_vector_ratio: Ratio of stale vectors (0-1)
    - index_status: healthy, degraded, or critical
    - latency metrics

    Index health is critical for cache performance
    """
    try:
        logger.info(f"Getting index health metrics for tenant_id={tenant_id}")

        monitor = IndexHealthMonitor()
        health_metrics = monitor.calculate_health_metrics(tenant_id=tenant_id)

        # Calculate stale vector count from ratio
        vector_count = health_metrics["vector_count"]
        stale_ratio = health_metrics["stale_vector_ratio"]
        active_cache_count = health_metrics["active_cache_count"]
        stale_vector_count = vector_count - active_cache_count

        response = IndexHealthResponse(
            vector_count=vector_count,
            active_cache_count=active_cache_count,
            stale_vector_count=stale_vector_count,
            stale_vector_ratio=stale_ratio,
            index_age_hours=health_metrics["index_age_hours"],
            avg_search_latency_ms=health_metrics["avg_search_latency_ms"],
            p95_search_latency_ms=health_metrics["p95_search_latency_ms"],
            p99_search_latency_ms=health_metrics["p99_search_latency_ms"],
            health_status=health_metrics["health_status"],
            measured_at=health_metrics["measured_at"],
            tenant_id=tenant_id
        )

        logger.info(
            f"Index health: {response.health_status}, "
            f"stale_ratio={response.stale_vector_ratio:.1%}"
        )

        return response

    except Exception as e:
        logger.error(f"Failed to get index health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get index health: {str(e)}")


@router.post("/rebuild", response_model=IndexRebuildResponse)
async def rebuild_index(
    tenant_id: Optional[str] = Query(None, description="Optional tenant ID for isolation"),
    dry_run: bool = Query(True, description="Run in simulation mode (default: true)")
):
    """
    Trigger FAISS index rebuild

    Rebuilds the vector index from active cache entries:
    1. Loads active cache entries
    2. Regenerates FAISS index
    3. Validates search quality
    4. Swaps index atomically
    5. Records rebuild job

    By default runs in dry_run mode (simulation only)
    """
    try:
        logger.info(f"Triggering index rebuild: tenant_id={tenant_id}, dry_run={dry_run}")

        # Create rebuild agent
        agent = IndexRebuildAgent(dry_run=dry_run)

        # Evaluate and execute rebuild
        result = agent.evaluate_and_rebuild(
            trigger_source="manual",
            tenant_id=tenant_id
        )

        # Extract rebuild result
        rebuild_result = result.get("rebuild_result", {})

        # If no rebuild was performed
        if "rebuild_result" not in result:
            # Health check passed, no rebuild needed
            health_metrics = result.get("health_metrics", {})
            return IndexRebuildResponse(
                status="skipped",
                rebuild_id="N/A",
                old_index_version=None,
                new_index_version=None,
                old_vector_count=health_metrics.get("vector_count", 0),
                new_vector_count=health_metrics.get("active_cache_count", 0),
                vectors_added=0,
                vectors_removed=0,
                rebuild_duration_ms=0.0,
                validation_passed=True,
                rebuild_job_id=None
        )

        response = IndexRebuildResponse(
            status="simulated" if dry_run else rebuild_result.get("status", "completed"),
            rebuild_id=rebuild_result.get("rebuild_id", "unknown"),
            old_index_version=rebuild_result.get("old_index_version"),
            new_index_version=rebuild_result.get("new_index_version"),
            old_vector_count=rebuild_result.get("old_vector_count", 0),
            new_vector_count=rebuild_result.get("new_vector_count", 0),
            vectors_added=rebuild_result.get("vectors_added", 0),
            vectors_removed=rebuild_result.get("vectors_removed", 0),
            rebuild_duration_ms=rebuild_result.get("rebuild_duration_ms", 0.0),
            validation_passed=rebuild_result.get("validation", {}).get("passed", False),
            rebuild_job_id=rebuild_result.get("rebuild_job_id")
        )

        logger.info(
            f"Index rebuild {'simulated' if dry_run else 'completed'}: "
            f"{response.old_vector_count} -> {response.new_vector_count} vectors"
        )

        return response

    except Exception as e:
        logger.error(f"Failed to rebuild index: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to rebuild index: {str(e)}")


@router.get("/status")
async def get_index_status(
    tenant_id: Optional[str] = Query(None, description="Optional tenant ID")
):
    """
    Get quick index status summary

    Returns simplified status for monitoring dashboards
    """
    try:
        monitor = IndexHealthMonitor()
        health_metrics = monitor.calculate_health_metrics(tenant_id=tenant_id)
        needs_rebuild, rebuild_reason = monitor.needs_rebuild(
            health_metrics=health_metrics,
            tenant_id=tenant_id
        )

        return {
            "status": health_metrics["health_status"],
            "vector_count": health_metrics["vector_count"],
            "stale_ratio": health_metrics["stale_vector_ratio"],
            "needs_rebuild": needs_rebuild,
            "rebuild_reason": rebuild_reason,
            "measured_at": health_metrics["measured_at"]
        }

    except Exception as e:
        logger.error(f"Failed to get index status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get index status: {str(e)}")
