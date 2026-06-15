"""
Main API router
"""
from fastapi import APIRouter
from app.api.endpoints import chat, models, evaluation, metrics, drift, agents, supervisor, benchmark, vectorstore

api_router = APIRouter()

# OpenAI-compatible endpoints
api_router.include_router(models.router, tags=["models"])
api_router.include_router(chat.router, tags=["chat"])

# Evaluation endpoints
api_router.include_router(evaluation.router, tags=["evaluation"])

# Metrics endpoints
api_router.include_router(metrics.router, tags=["metrics"])

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

# API status endpoint
@api_router.get("/status")
async def api_status():
    """API status endpoint"""
    return {"status": "operational", "version": "v1"}
