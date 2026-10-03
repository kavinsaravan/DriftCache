"""
Cache Management Tools

LangChain tools for cache inspection, invalidation, and quality assessment
"""
from typing import Optional, Dict, Any
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import logging

from app.evaluation.reports import get_report_generator
from app.database.session import get_db_manager

logger = logging.getLogger(__name__)


class CacheQualityInput(BaseModel):
    """Input schema for cache quality tool"""
    dataset_name: str = Field("default", description="Test dataset to use (default or minimal)")
    threshold: float = Field(0.90, ge=0.0, le=1.0, description="Threshold to evaluate")
    tenant_id: Optional[str] = Field(None, description="Optional tenant ID")


class CacheQualityTool(BaseTool):
    """
    Tool for retrieving cache quality metrics

    Evaluates whether semantic cache decisions are reliable
    """
    name: str = "get_cache_quality"
    description: str = """
    Gets cache quality evaluation metrics.

    Returns:
    - precision: Valid cache hits / total cache hits (trustworthiness)
    - recall: Correct cache hits / all reusable prompts (savings)
    - f1_score: Balanced metric combining precision and recall
    - false_hit_rate: Bad cache hits / total hits (danger metric)
    - false_miss_rate: Missed opportunities / all reusable (efficiency)

    Use this to determine if cache decisions are reliable or if
    threshold adjustments are needed.

    High false_hit_rate (>0.10) is dangerous - serving wrong answers.
    High false_miss_rate (>0.40) means missing cost savings.
    """
    args_schema: type[BaseModel] = CacheQualityInput

    def _run(
        self,
        dataset_name: str = "default",
        threshold: float = 0.90,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get cache quality metrics"""
        try:
            logger.info(
                f"Getting cache quality: dataset={dataset_name}, "
                f"threshold={threshold}, tenant_id={tenant_id}"
            )

            with get_db_manager().session_scope() as session:
                with get_report_generator(session=session) as generator:
                    # Try to get latest evaluation first
                    latest = generator.get_latest_evaluation(tenant_id=tenant_id)

                    # If no recent evaluation or different threshold, run new one
                    if latest is None or abs(latest.threshold_used - threshold) > 0.01:
                        result = generator.run_evaluation(
                            dataset_name=dataset_name,
                            threshold=threshold,
                            tenant_id=tenant_id,
                            save_to_db=True
                        )
                    else:
                        result = latest

                    return {
                        "precision": round(result.precision, 4),
                        "recall": round(result.recall, 4),
                        "f1_score": round(result.f1_score, 4),
                        "false_hit_rate": round(result.false_hit_rate, 4),
                        "false_miss_rate": round(result.false_miss_rate, 4),
                        "threshold": result.threshold_used,
                        "recommendation": {
                            "action": result.recommended_action,
                            "confidence": round(result.recommendation_confidence, 4) if result.recommendation_confidence else None,
                            "details": result.recommendation_details,
                        },
                        "evaluation_run_id": result.evaluation_run_id,
                        "status": "success"
                    }

        except Exception as e:
            logger.error(f"Cache quality evaluation failed: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }


class CacheInvalidationInput(BaseModel):
    """Input schema for cache invalidation tool"""
    cache_id: str = Field(..., description="Cache entry ID to invalidate")
    reason: str = Field(..., description="Reason for invalidation")
    dry_run: bool = Field(True, description="If True, only simulate invalidation")


class CacheInvalidationTool(BaseTool):
    """
    Tool for invalidating stale or risky cache entries

    Runs in dry-run mode by default for safety
    """
    name: str = "invalidate_cache_entry"
    description: str = """
    Invalidates a cache entry that is stale or risky.

    Use cases:
    - Cache hit has low semantic similarity
    - Response is outdated
    - False cache hit detected

    By default runs in dry-run mode .
    Will enable actual invalidation.

    Returns success status and simulation details.
    """
    args_schema: type[BaseModel] = CacheInvalidationInput

    def _run(
        self,
        cache_id: str,
        reason: str,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Invalidate cache entry"""
        try:
            logger.info(
                f"Cache invalidation: cache_id={cache_id}, "
                f"reason={reason}, dry_run={dry_run}"
            )

            if dry_run:
                # Simulation mode
                return {
                    "status": "simulated",
                    "cache_id": cache_id,
                    "reason": reason,
                    "action": "would_invalidate",
                    "message": f"DRY RUN: Would invalidate cache entry {cache_id}",
                    "details": {
                        "would_remove_from_redis": True,
                        "would_remove_from_metadata": True,
                        "would_remove_from_faiss": True,
                        "reason": reason
                    }
                }

            # Actually invalidate
            import asyncio
            from app.cache.redis_store import get_redis_store
            from app.vectorstore.storage import get_metadata_store
            from app.vectorstore.faiss_index import get_faiss_index
            import numpy as np

            removed_from_redis = False
            removed_from_metadata = False
            removed_from_faiss = False

            # Remove from Redis
            try:
                # Handle async in sync context
                try:
                    # Try to get existing event loop
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Already in async context - can't use run_until_complete
                        logger.warning("Cannot invalidate from Redis in async context (tool called from async)")
                        removed_from_redis = False
                    else:
                        # No running loop, safe to use
                        redis_store = loop.run_until_complete(get_redis_store())
                        # Use correct Redis key pattern: cache:response:{id}
                        result = loop.run_until_complete(redis_store.redis.delete(f"cache:response:{cache_id}"))
                        removed_from_redis = (result > 0)
                        logger.info(f"Removed {cache_id} from Redis (deleted {result} keys)")
                except RuntimeError:
                    # No event loop exists, create one
                    redis_store = asyncio.run(get_redis_store())
                    result = asyncio.run(redis_store.redis.delete(f"cache:response:{cache_id}"))
                    removed_from_redis = (result > 0)
                    logger.info(f"Removed {cache_id} from Redis (deleted {result} keys)")
            except Exception as e:
                logger.error(f"Failed to remove from Redis: {e}")

            # Remove from metadata store and FAISS
            try:
                metadata_store = get_metadata_store()
                faiss_index = get_faiss_index()

                # Find vector_id by searching metadata
                vector_id_to_remove = None
                for vid, meta in metadata_store.metadata.items():
                    if meta.cache_key_hash == cache_id:
                        vector_id_to_remove = vid
                        break

                if vector_id_to_remove is not None:
                    # Remove from FAISS (now supported with IndexIDMap2)
                    try:
                        faiss_index.remove_vectors(np.array([vector_id_to_remove], dtype=np.int64))
                        removed_from_faiss = True
                        logger.info(f"Removed vector_id={vector_id_to_remove} from FAISS")
                    except Exception as e:
                        logger.error(f"Failed to remove from FAISS: {e}")

                    # Remove from metadata
                    metadata_store.delete(vector_id_to_remove)
                    metadata_store.save()
                    removed_from_metadata = True
                    logger.info(f"Removed vector_id={vector_id_to_remove} from metadata")
                else:
                    logger.warning(f"Could not find metadata for cache_id={cache_id}")
            except Exception as e:
                logger.error(f"Failed to remove from metadata/FAISS: {e}")

            return {
                "status": "completed",
                "cache_id": cache_id,
                "reason": reason,
                "action": "invalidated",
                "message": f"Invalidated cache entry {cache_id}",
                "details": {
                    "removed_from_redis": removed_from_redis,
                    "removed_from_metadata": removed_from_metadata,
                    "removed_from_faiss": removed_from_faiss,
                    "reason": reason
                }
            }

        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }


def get_cache_tools():
    """Get all cache-related tools"""
    return [
        CacheQualityTool(),
        CacheInvalidationTool(),
    ]
