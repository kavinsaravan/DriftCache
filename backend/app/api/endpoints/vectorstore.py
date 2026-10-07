"""Endpoints for inspecting and maintaining the live FAISS index."""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from app.services.index_maintenance import IndexMaintenanceService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats")
@router.get("/health", include_in_schema=False)
async def get_index_stats(
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
) -> Dict[str, Any]:
    """Return counts and health derived from the current FAISS and metadata state."""
    try:
        return IndexMaintenanceService().get_stats(tenant_id=tenant_id)
    except Exception as exc:
        logger.exception("Failed to inspect the index")
        raise HTTPException(
            status_code=500, detail="Failed to inspect the index"
        ) from exc


@router.post("/rebuild")
async def rebuild_index(
    tenant_id: Optional[str] = Query(None, description="Initiating tenant"),
    dry_run: bool = Query(
        True, description="Preview the rebuild without changing data"
    ),
) -> Dict[str, Any]:
    """Re-embed active metadata and replace the persisted FAISS index."""
    try:
        service = IndexMaintenanceService()
        return await run_in_threadpool(
            service.rebuild,
            dry_run=dry_run,
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.exception("Failed to rebuild the index")
        raise HTTPException(
            status_code=500, detail="Failed to rebuild the index"
        ) from exc


@router.get("/status", include_in_schema=False)
async def get_index_status(
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
) -> Dict[str, Any]:
    """Compatibility alias for clients that used the old status endpoint."""
    return await get_index_stats(tenant_id)
