"""
OpenAI-compatible models endpoint
"""
import time
from fastapi import APIRouter

from app.models.schemas import ModelsListResponse, ModelInfo

router = APIRouter()


@router.get("/models", response_model=ModelsListResponse)
async def list_models():
    """
    List available models (OpenAI-compatible)

    Returns models that DriftCache supports, mapped to Claude models
    """
    created_time = int(time.time())

    models = [
        ModelInfo(
            id="gpt-4",
            object="model",
            created=created_time,
            owned_by="driftcache"
        ),
        ModelInfo(
            id="gpt-4-turbo",
            object="model",
            created=created_time,
            owned_by="driftcache"
        ),
        ModelInfo(
            id="gpt-3.5-turbo",
            object="model",
            created=created_time,
            owned_by="driftcache"
        ),
        ModelInfo(
            id="claude-3-5-sonnet",
            object="model",
            created=created_time,
            owned_by="driftcache"
        ),
        ModelInfo(
            id="claude-3-opus",
            object="model",
            created=created_time,
            owned_by="driftcache"
        ),
        ModelInfo(
            id="claude-3-sonnet",
            object="model",
            created=created_time,
            owned_by="driftcache"
        ),
        ModelInfo(
            id="claude-3-haiku",
            object="model",
            created=created_time,
            owned_by="driftcache"
        ),
    ]

    return ModelsListResponse(
        object="list",
        data=models
    )
