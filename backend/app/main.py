"""
Main FastAPI application entry point

Features:
- Redis lifecycle management
- PostgreSQL database initialization
- Historical event recording
- OpenAI-compatible API endpoints
"""
import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.redis import get_redis_manager, shutdown_redis
from app.database.session import get_db_manager, shutdown_db
from app.api.routes import api_router

logger = logging.getLogger(__name__)


def cleanup_expired_vectors() -> int:
    """Remove expired vectors and persist the index when it changes."""
    from app.vectorstore.search import get_search_service

    search_service = get_search_service()
    removed_count = search_service.remove_expired_vectors()
    if removed_count > 0:
        search_service.save_index()
        logger.info("Removed and persisted %s expired FAISS vectors", removed_count)
    return removed_count


async def periodic_vector_cleanup(interval_seconds: int) -> None:
    """Run expired-vector cleanup until the application shuts down."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await asyncio.to_thread(cleanup_expired_vectors)
        except Exception:
            logger.exception("Periodic expired-vector cleanup failed")


def get_llm_configuration_status() -> dict:
    """Describe configured providers and whether the default model can route."""
    configured_providers = []
    if settings.OPENAI_API_KEY:
        configured_providers.append("openai")
    if settings.ANTHROPIC_API_KEY:
        configured_providers.append("anthropic")
    if settings.OLLAMA_BASE_URL:
        configured_providers.append("ollama")

    model = settings.DEFAULT_MODEL.lower()
    if model.startswith("gpt-"):
        default_provider = "openai"
    elif model.startswith("claude-"):
        default_provider = "anthropic"
    elif model.startswith(("llama", "mistral", "mixtral", "phi", "codellama")):
        default_provider = "ollama"
    else:
        default_provider = None

    default_ready = default_provider in configured_providers if default_provider else False
    return {
        "status": "configured" if default_ready else "not_configured",
        "default_model": settings.DEFAULT_MODEL,
        "default_provider": default_provider,
        "configured_providers": configured_providers,
    }


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

        # Run Alembic migrations automatically
        try:
            from alembic.config import Config
            from alembic import command
            import os

            # Get alembic config path
            alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
            alembic_cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))

            # Run migrations
            command.upgrade(alembic_cfg, "head")
            logger.info("Database migrations completed successfully")
        except Exception as e:
            logger.warning(f"Failed to run migrations, trying create_tables: {e}")
            # Fallback to create_tables for dev
            try:
                db_manager.create_tables()
                logger.info("Database tables initialized")
            except Exception as e2:
                logger.warning(f"Failed to create tables (may already exist): {e2}")

    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        logger.warning("Running without PostgreSQL - historical recording disabled")

    # Initialize Redis connection
    try:
        redis_manager = await get_redis_manager()
        # Verify connection is working
        if await redis_manager.health_check():
            logger.info("Redis connection established and verified")
        else:
            logger.error("Redis health check failed after connection")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        logger.error(f"Redis URL being used: {settings.get_redis_url()[:20]}...")  # Log first 20 chars for debugging
        logger.warning("Running without Redis - cache will use fallback storage")

    # Clean up expired vectors from FAISS index on startup.
    try:
        cleanup_expired_vectors()
    except Exception as e:
        logger.warning(f"Failed to clean up expired vectors on startup: {e}")

    cleanup_task = asyncio.create_task(
        periodic_vector_cleanup(settings.VECTOR_CLEANUP_INTERVAL_SECONDS),
        name="expired-vector-cleanup",
    )

    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task

        # Shutdown
        logger.info("Shutting down DriftCache API...")

        # Save FAISS index to disk before shutdown
        try:
            from app.vectorstore.search import get_search_service
            search_service = get_search_service()
            search_service.save_index()
            logger.info("FAISS index saved to disk")
        except Exception as e:
            logger.error(f"Failed to save FAISS index on shutdown: {e}")

        await shutdown_redis()
        logger.info("Redis connection closed")
        shutdown_db()
        logger.info("PostgreSQL connection closed")


# Initialize FastAPI app
app = FastAPI(
    title="DriftCache API",
    description="Semantic caching and quality monitoring for LLM systems",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
# Allow all Vercel domains for demo/preview deployments
if settings.ALLOW_ALL_VERCEL:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https://.*\.vercel\.app",  # Allow all Vercel domains
        allow_origins=settings.cors_origins,  # Also allow explicit origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Production: only allow explicit origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
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

    llm_status = get_llm_configuration_status()

    # Overall status includes the provider required by the configured default model.
    all_healthy = (
        db_status == "connected"
        and redis_status == "connected"
        and llm_status["status"] == "configured"
    )
    overall_status = "healthy" if all_healthy else "degraded"

    return {
        "status": overall_status,
        "database": db_status,
        "redis": redis_status,
        "llm": llm_status,
    }
