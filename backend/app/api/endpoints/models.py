"""
OpenAI-compatible models endpoint
"""
import time
from fastapi import APIRouter

from app.models.schemas import ModelsListResponse, ModelInfo
from app.providers.router import provider_router

router = APIRouter()


@router.get("/models", response_model=ModelsListResponse)
async def list_models():
    """
    List available models (OpenAI-compatible)

    Returns all models supported across all configured providers
    """
    created_time = int(time.time())

    # Get all available models from the provider router
    available_model_ids = provider_router.get_available_models()

    models = [
        ModelInfo(
            id=model_id,
            object="model",
            created=created_time,
            owned_by="driftcache"
        )
        for model_id in sorted(available_model_ids)
    ]

    return ModelsListResponse(
        object="list",
        data=models
    )
