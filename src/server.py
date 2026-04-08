"""Server entry point for TriNav.

This module provides the FastAPI entry point for the TriNav API.
Exposes the assistant compatibility surface at POST /assistant/invoke.
"""
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config.settings import get_settings
from .utils.logging_config import get_logger, setup_logging
from .utils.metrics import external_service_health, get_content_type, get_metrics

# Get settings
settings = get_settings()
log_file = os.getenv("TRINAV_LOG_FILE", "logs/trinav.log").strip() or None
setup_logging(settings.log_level, log_file=log_file)
logger = get_logger(__name__)


class DependencyHealth(BaseModel):
    """Readiness state for a single operational dependency."""

    healthy: bool


class ReadinessDependencies(BaseModel):
    """Readiness state grouped by dependency name."""

    redis: DependencyHealth
    llm: DependencyHealth


class ReadinessResponse(BaseModel):
    """Structured readiness response published in OpenAPI."""

    status: str
    dependencies: ReadinessDependencies


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup/shutdown."""
    logger.info("TriNav LangServe server starting up")

    # Initialize services on startup
    from .services.llm_service import get_llm_service
    from .services.redis_service import get_redis_service

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
        get_llm_service()
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


try:
    from .interfaces.api.assistant_compat import router as assistant_compat_router
    from .interfaces.api.assistant_v2 import router as assistant_v2_router
    from .interfaces.api.assistant_v3 import router as assistant_v3_router
    from .interfaces.api.runtime_admin_v3 import router as runtime_admin_v3_router
    from .interfaces.api.shadow_compare import router as shadow_compare_router
    from .interfaces.api.shadow_compare_v3 import router as shadow_compare_v3_router

    app.include_router(assistant_compat_router)
    app.include_router(assistant_v2_router)
    app.include_router(assistant_v3_router)
    app.include_router(runtime_admin_v3_router)
    app.include_router(shadow_compare_router)
    app.include_router(shadow_compare_v3_router)
except Exception:  # pragma: no cover - defensive import guard
    logger.exception("api router registration failed")
    raise


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for monitoring."""
    from .services.redis_service import get_redis_service

    redis = await get_redis_service()
    redis_healthy = redis.is_healthy if redis else False

    return {
        "status": "healthy" if redis_healthy else "degraded",
        "redis": "healthy" if redis_healthy else "unhealthy",
    }


async def _get_dependency_readiness() -> dict[str, dict[str, bool]]:
    """Collect readiness state for operational dependencies."""
    from .services.llm_service import get_llm_service
    from .services.redis_service import get_redis_service

    dependencies = {
        "redis": {"healthy": False},
        "llm": {"healthy": False},
    }

    try:
        redis = await get_redis_service()
        dependencies["redis"]["healthy"] = bool(redis and redis.is_healthy)
    except Exception:
        logger.warning("Redis readiness check failed", exc_info=True)

    try:
        llm = get_llm_service()
        dependencies["llm"]["healthy"] = bool(llm and llm.is_healthy)
    except Exception:
        logger.warning("LLM readiness check failed", exc_info=True)

    return dependencies


@app.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse, "description": "Dependencies degraded"}},
)
async def readiness_check(response: Response) -> ReadinessResponse:
    """Readiness endpoint for orchestration probes."""
    dependencies = await _get_dependency_readiness()
    ready = all(dependency["healthy"] for dependency in dependencies.values())
    response.status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if ready else "degraded",
        dependencies=ReadinessDependencies(
            redis=DependencyHealth(**dependencies["redis"]),
            llm=DependencyHealth(**dependencies["llm"]),
        ),
    )


@app.get("/metrics")
async def metrics() -> Response:
    """Expose Prometheus metrics for scraping."""
    return Response(
        content=get_metrics(),
        headers={"Content-Type": get_content_type()},
    )


@app.get("/")
async def root() -> dict[str, str | dict[str, str]]:
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


def main() -> None:
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
