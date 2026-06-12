"""
Main API router
"""
from fastapi import APIRouter
from app.api.endpoints import chat, models

api_router = APIRouter()

# OpenAI-compatible endpoints
api_router.include_router(models.router, tags=["models"])
api_router.include_router(chat.router, tags=["chat"])

# API status endpoint
@api_router.get("/status")
async def api_status():
    """API status endpoint"""
    return {"status": "operational", "version": "v1"}
