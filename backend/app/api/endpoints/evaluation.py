"""
Evaluation API Endpoints

Provides point-in-time evaluation and cache decision replay
"""
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database.session import get_db
from app.evaluation.point_in_time import get_point_in_time_evaluator
from app.evaluation.replay import get_cache_replayer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


# Request/Response Models

class ThresholdReplayRequest(BaseModel):
    """Request for threshold replay"""
    cache_event_id: int = Field(..., description="Cache event ID to replay")
    new_threshold: float = Field(..., ge=0.0, le=1.0, description="New threshold to test")


class BatchReplayRequest(BaseModel):
    """Request for batch replay"""
    start_time: datetime = Field(..., description="Start of time range")
    end_time: datetime = Field(..., description="End of time range")
    new_threshold: float = Field(..., ge=0.0, le=1.0, description="New threshold to test")
    tenant_id: Optional[str] = Field(None, description="Optional tenant filter")


class ThresholdComparisonRequest(BaseModel):
    """Request for threshold comparison"""
    start_time: datetime = Field(..., description="Start of time range")
    end_time: datetime = Field(..., description="End of time range")
    thresholds: List[float] = Field(..., description="List of thresholds to compare")
    tenant_id: Optional[str] = Field(None, description="Optional tenant filter")


# Endpoints

@router.get("/cache-decision/{cache_event_id}")
async def evaluate_cache_decision(
    cache_event_id: int,
    db: Session = Depends(get_db)
):
    """
    Evaluate a cache decision at the point in time it was made

    This retrieves all context from the time of decision:
    - Threshold used
    - Embedding model
    - Similarity score
    - Matched cache entry
    - Request details

    This is critical for:
    - Understanding why a decision was made
    - Preventing data leakage in evaluation
    - Historical performance analysis
    """
    try:
        with get_point_in_time_evaluator(session=db) as evaluator:
            report = evaluator.evaluate_cache_decision(cache_event_id)
            return report

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to evaluate cache decision: {e}")
        raise HTTPException(status_code=500, detail="Evaluation failed")


@router.get("/cache-decisions/batch")
async def evaluate_batch(
    cache_event_ids: str = Query(..., description="Comma-separated cache event IDs"),
    db: Session = Depends(get_db)
):
    """
    Evaluate multiple cache decisions

    Query parameter:
    - cache_event_ids: "123,456,789"
    """
    try:
        event_ids = [int(id.strip()) for id in cache_event_ids.split(",")]

        with get_point_in_time_evaluator(session=db) as evaluator:
            reports = evaluator.evaluate_batch(event_ids)
            return {
                "total": len(reports),
                "evaluations": reports
            }

    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid cache_event_ids format")
    except Exception as e:
        logger.error(f"Failed to evaluate batch: {e}")
        raise HTTPException(status_code=500, detail="Batch evaluation failed")


@router.get("/cache-decisions/time-range")
async def evaluate_time_range(
    start_time: datetime = Query(..., description="Start of time range"),
    end_time: datetime = Query(..., description="End of time range"),
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """
    Evaluate all cache decisions in a time range

    This is useful for:
    - Analyzing performance over a specific period
    - Investigating incidents
    - Generating evaluation datasets
    """
    try:
        with get_point_in_time_evaluator(session=db) as evaluator:
            reports = evaluator.evaluate_time_range(
                start_time=start_time,
                end_time=end_time,
                tenant_id=tenant_id,
                limit=limit
            )

            return {
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                },
                "total": len(reports),
                "evaluations": reports
            }

    except Exception as e:
        logger.error(f"Failed to evaluate time range: {e}")
        raise HTTPException(status_code=500, detail="Time range evaluation failed")


@router.post("/replay/threshold")
async def replay_threshold(
    request: ThresholdReplayRequest,
    db: Session = Depends(get_db)
):
    """
    Replay a cache decision with a different threshold

    This answers: "What if we had used threshold X instead of Y?"

    Use case:
    - Testing threshold changes before deploying
    - Understanding impact of threshold adjustments
    - A/B testing thresholds
    """
    try:
        with get_cache_replayer(session=db) as replayer:
            result = replayer.replay_with_threshold(
                cache_event_id=request.cache_event_id,
                new_threshold=request.new_threshold
            )
            return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to replay threshold: {e}")
        raise HTTPException(status_code=500, detail="Replay failed")


@router.post("/replay/batch")
async def replay_batch(
    request: BatchReplayRequest,
    db: Session = Depends(get_db)
):
    """
    Replay a batch of cache decisions with a different threshold

    This answers: "If we change threshold from X to Y, what happens?"

    Returns:
    - Hit rate change
    - Number of HITs that become MISSes
    - Number of MISSes that become HITs
    - Overall impact summary

    This is critical for threshold optimization.
    """
    try:
        with get_cache_replayer(session=db) as replayer:
            result = replayer.replay_batch_with_threshold(
                start_time=request.start_time,
                end_time=request.end_time,
                new_threshold=request.new_threshold,
                tenant_id=request.tenant_id
            )
            return result

    except Exception as e:
        logger.error(f"Failed to replay batch: {e}")
        raise HTTPException(status_code=500, detail="Batch replay failed")


@router.post("/replay/compare-thresholds")
async def compare_thresholds(
    request: ThresholdComparisonRequest,
    db: Session = Depends(get_db)
):
    """
    Compare multiple thresholds on the same historical data

    This answers: "Which threshold performs best on historical data?"

    Use case:
    - Finding optimal threshold value
    - Understanding threshold sensitivity
    - Supporting agent-driven threshold optimization

    Returns the optimal threshold based on hit rate.
    """
    try:
        with get_cache_replayer(session=db) as replayer:
            result = replayer.compare_thresholds(
                start_time=request.start_time,
                end_time=request.end_time,
                thresholds=request.thresholds,
                tenant_id=request.tenant_id
            )
            return result

    except Exception as e:
        logger.error(f"Failed to compare thresholds: {e}")
        raise HTTPException(status_code=500, detail="Threshold comparison failed")


@router.get("/health")
async def evaluation_health():
    """Evaluation service health check"""
    return {
        "status": "healthy",
        "service": "evaluation",
        "features": [
            "point_in_time_evaluation",
            "cache_decision_replay",
            "threshold_comparison",
            "batch_evaluation"
        ]
    }
