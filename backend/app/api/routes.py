"""
Main API router

All endpoints require API key authentication
"""
from fastapi import APIRouter, Depends
from app.api.endpoints import chat, models, evaluation, metrics, drift, agents, supervisor, benchmark, vectorstore, training
from app.core.auth import verify_api_key, verify_metrics_key

# Protect all endpoints with API key authentication
api_router = APIRouter(dependencies=[Depends(verify_api_key)])

# OpenAI-compatible endpoints
api_router.include_router(models.router, tags=["models"])
api_router.include_router(chat.router, tags=["chat"])

# Evaluation endpoints
api_router.include_router(evaluation.router, tags=["evaluation"])

# Metrics endpoints (use separate metrics key for dashboard access)
metrics_router = APIRouter(dependencies=[Depends(verify_metrics_key)])
metrics_router.include_router(metrics.router, tags=["metrics"])
api_router.include_router(metrics_router)

# Drift detection endpoints
api_router.include_router(drift.router, prefix="/drift", tags=["drift"])

# Autonomous agent endpoints
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])

# Supervisor orchestration endpoints
api_router.include_router(supervisor.router, prefix="/supervisor", tags=["supervisor"])

# Benchmark endpoints
api_router.include_router(benchmark.router, prefix="/benchmark", tags=["benchmark"])

# Vectorstore / FAISS index endpoints
api_router.include_router(vectorstore.router, prefix="/vectorstore", tags=["vectorstore"])

# Training and fine-tuning endpoints
api_router.include_router(training.router, prefix="/training", tags=["training"])

# API status endpoint
@api_router.get("/status")
async def api_status():
    """API status endpoint"""
    return {"status": "operational", "version": "v1"}
