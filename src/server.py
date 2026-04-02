"""LangServe server for TriNav.

This module provides the FastAPI/LangServe entry point for the TriNav API.
Exposes the triage workflow at POST /assistant/invoke.
"""
from contextlib import asynccontextmanager
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langserve import add_routes

from .config.settings import get_settings
from .chains.triage_chain import chain
from .utils.logging_config import get_logger, setup_logging
from .utils.metrics import external_service_health

# Get settings
settings = get_settings()
log_file = os.getenv("TRINAV_LOG_FILE", "logs/trinav.log").strip() or None
setup_logging(settings.log_level, log_file=log_file)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    logger.info("TriNav LangServe server starting up")

    # Initialize services on startup
    from .services.redis_service import get_redis_service
    from .services.llm_service import get_llm_service

    # Warm up Redis connection
    try:
        redis = await get_redis_service()
        if redis.is_healthy:
            external_service_health.labels(service_name="redis").set(1)
            logger.info("Redis connection healthy")
        else:
            external_service_health.labels(service_name="redis").set(0)
            logger.warning("Redis connection failed, graceful degradation enabled")
    except Exception as e:
        external_service_health.labels(service_name="redis").set(0)
        logger.error(f"Redis initialization error: {e}")

    # Warm up LLM service
    try:
        llm = get_llm_service()
        external_service_health.labels(service_name="llm").set(1)
        logger.info("LLM service initialized")
    except Exception as e:
        external_service_health.labels(service_name="llm").set(0)
        logger.error(f"LLM initialization error: {e}")

    yield

    logger.info("TriNav LangServe server shutting down")


# Create FastAPI app
app = FastAPI(
    title="TriNav Medical Triage Assistant",
    description="AI-powered medical triage and hospital navigation system",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add LangServe routes
add_routes(
    app,
    chain,
    path="/assistant",
    input_type=dict,
    output_type=dict,
)

try:
    from .interfaces.api.assistant_v2 import router as assistant_v2_router
    from .interfaces.api.assistant_v3 import router as assistant_v3_router
    from .interfaces.api.shadow_compare import router as shadow_compare_router
    from .interfaces.api.shadow_compare_v3 import router as shadow_compare_v3_router

    app.include_router(assistant_v2_router)
    app.include_router(assistant_v3_router)
    app.include_router(shadow_compare_router)
    app.include_router(shadow_compare_v3_router)
except Exception as exc:  # pragma: no cover - defensive import guard
    logger.exception("api router registration failed")
    raise


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    from .services.redis_service import get_redis_service

    redis = await get_redis_service()
    redis_healthy = redis.is_healthy if redis else False

    return {
        "status": "healthy" if redis_healthy else "degraded",
        "redis": "healthy" if redis_healthy else "unhealthy",
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "TriNav Medical Triage Assistant",
        "version": "1.0.0",
        "endpoints": {
            "invoke": "POST /assistant/invoke",
            "health": "GET /health",
            "docs": "GET /docs",
        },
        "documentation": "https://github.com/your-org/TriNav",
    }


def main():
    """Run the LangServe server."""
    uvicorn.run(
        "src.server:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,  # No reload in production
        log_config=None,  # Use our custom logging
    )


if __name__ == "__main__":
    main()
