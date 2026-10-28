"""
OpenAI-compatible models endpoint
"""
import time
from fastapi import APIRouter

from app.models.schemas import ModelsListResponse, ModelInfo
from app.core.model_catalog import available_models

router = APIRouter()


@router.get("/models", response_model=ModelsListResponse)
async def list_models():
    """
    List available models (OpenAI-compatible)

    Returns deployment-selected models whose provider is configured.
    This does not validate upstream credentials or model access.
    """
    created_time = int(time.time())

    # Advertise models selected by the deployment, not a static provider catalogue.
    available_model_ids = available_models()

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
