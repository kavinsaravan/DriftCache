"""
Main FastAPI application entry point

Week 3 Updates:
- Redis lifecycle management
- PostgreSQL database initialization
- Historical event recording
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.redis import get_redis_manager, shutdown_redis
from app.database.session import get_db_manager, shutdown_db
from app.api.routes import api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager

    Handles startup and shutdown events
    """
    # Startup
    logger.info("Starting DriftCache API...")

    # Initialize PostgreSQL database
    try:
        db_manager = get_db_manager()
        logger.info("PostgreSQL connection established")

        # Create tables if they don't exist (for dev)
        # In production, use Alembic migrations
        try:
            db_manager.create_tables()
            logger.info("Database tables initialized")
        except Exception as e:
            logger.warning(f"Failed to create tables (may already exist): {e}")

    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        logger.warning("Running without PostgreSQL - historical recording disabled")

    # Initialize Redis connection
    try:
        redis_manager = await get_redis_manager()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        logger.warning("Running without Redis - cache will use fallback storage")

    yield

    # Shutdown
    logger.info("Shutting down DriftCache API...")
    await shutdown_redis()
    logger.info("Redis connection closed")
    shutdown_db()
    logger.info("PostgreSQL connection closed")


# Initialize FastAPI app
app = FastAPI(
    title="DriftCache API",
    description="Adaptive Semantic Caching & Autonomous Optimization Platform for LLM Systems",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "DriftCache",
        "version": "0.1.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    # Check PostgreSQL health
    db_status = "disconnected"
    try:
        db_manager = get_db_manager()
        is_healthy = db_manager.health_check()
        db_status = "connected" if is_healthy else "unhealthy"
    except Exception as e:
        logger.error(f"PostgreSQL health check failed: {e}")
        db_status = "error"

    # Check Redis health
    redis_status = "disconnected"
    try:
        redis_manager = await get_redis_manager()
        is_healthy = await redis_manager.health_check()
        redis_status = "connected" if is_healthy else "unhealthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        redis_status = "error"

    # Overall status
    all_healthy = db_status == "connected" and redis_status == "connected"
    overall_status = "healthy" if all_healthy else "degraded"

    return {
        "status": overall_status,
        "database": db_status,
        "redis": redis_status,
        "llm": "configured"  # TODO: Add actual LLM check
    }
