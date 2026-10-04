"""
Main API router

Endpoints use different auth based on their function:
- Most endpoints require main API_KEY (full access)
- Metrics endpoints accept either API_KEY or METRICS_API_KEY (read-only)
"""
from fastapi import APIRouter, Depends
from app.api.endpoints import chat, models, evaluation, metrics, drift, benchmark, vectorstore, training
from app.core.auth import verify_api_key, verify_metrics_key

# Main router without global dependencies to avoid stacking
api_router = APIRouter()

# OpenAI-compatible endpoints (require main API key)
api_router.include_router(
    models.router,
    tags=["models"],
    dependencies=[Depends(verify_api_key)]
)
api_router.include_router(
    chat.router,
    tags=["chat"],
    dependencies=[Depends(verify_api_key)]
)

# Evaluation endpoints (require main API key)
api_router.include_router(
    evaluation.router,
    tags=["evaluation"],
    dependencies=[Depends(verify_api_key)]
)

# Metrics endpoints (accept either main key or read-only metrics key)
api_router.include_router(
    metrics.router,
    tags=["metrics"],
    dependencies=[Depends(verify_metrics_key)]
)

# Drift detection endpoints (require main API key)
api_router.include_router(
    drift.router,
    prefix="/drift",
    tags=["drift"],
    dependencies=[Depends(verify_api_key)]
)

# Benchmark endpoints (require main API key)
api_router.include_router(
    benchmark.router,
    prefix="/benchmark",
    tags=["benchmark"],
    dependencies=[Depends(verify_api_key)]
)

# Vectorstore / FAISS index endpoints (require main API key)
api_router.include_router(
    vectorstore.router,
    prefix="/vectorstore",
    tags=["vectorstore"],
    dependencies=[Depends(verify_api_key)]
)

# Training and fine-tuning endpoints (require main API key)
api_router.include_router(
    training.router,
    prefix="/training",
    tags=["training"],
    dependencies=[Depends(verify_api_key)]
)

# API status endpoint (no auth required)
@api_router.get("/status")
async def api_status():
    """API status endpoint"""
    return {"status": "operational", "version": "v1"}
