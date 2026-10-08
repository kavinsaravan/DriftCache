"""
Main API router

Endpoints use different auth based on their function:
- Chat and model discovery accept project keys or the main API_KEY
- Administrative endpoints require the main API_KEY
- Metrics endpoints accept either API_KEY or METRICS_API_KEY (read-only)
"""
from fastapi import APIRouter, Depends
from app.api.endpoints import chat, models, evaluation, metrics, drift, benchmark, vectorstore, training, projects
from app.core.auth import verify_admin_key, verify_api_key, verify_metrics_key

# Main router without global dependencies to avoid stacking
api_router = APIRouter()

# OpenAI-compatible endpoints accept project-scoped keys.
api_router.include_router(
    models.router,
    tags=["models"],
    dependencies=[Depends(verify_api_key)]
)
api_router.include_router(
    chat.router,
    tags=["chat"],
)

# Project and key administration has its own bootstrap-key dependency.
api_router.include_router(projects.router)

# Operational endpoints remain restricted to the bootstrap/admin key. Their
# tenant query parameters are not yet derived from a project auth context.
api_router.include_router(
    evaluation.router,
    tags=["evaluation"],
    dependencies=[Depends(verify_admin_key)]
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
    dependencies=[Depends(verify_admin_key)]
)

# Benchmark endpoints (require main API key)
api_router.include_router(
    benchmark.router,
    prefix="/benchmark",
    tags=["benchmark"],
    dependencies=[Depends(verify_admin_key)]
)

# Vectorstore / FAISS index endpoints (require main API key)
api_router.include_router(
    vectorstore.router,
    prefix="/vectorstore",
    tags=["vectorstore"],
    dependencies=[Depends(verify_admin_key)]
)

# Training and fine-tuning endpoints (require main API key)
api_router.include_router(
    training.router,
    prefix="/training",
    tags=["training"],
    dependencies=[Depends(verify_admin_key)]
)

# API status endpoint (no auth required)
@api_router.get("/status")
async def api_status():
    """API status endpoint"""
    return {"status": "operational", "version": "v1"}
