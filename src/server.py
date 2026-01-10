"""LangServe server for TriNav.

This module provides the FastAPI/LangServe entry point for the TriNav API.
Exposes the triage workflow at POST /assistant/invoke.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langserve import add_routes
from langchain.schema.runnable import RunnableConfig
import uvicorn

from .config.settings import settings
from .chains.triage_chain import chain
from .utils.logging_config import get_logger, set_correlation_id
from .utils.metrics import (
    request_count,
    request_duration,
    external_service_health,
)
import time

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


@app.post("/assistant/invoke")
async def invoke_assistant(request: dict):
    """Custom invoke endpoint with metrics and correlation ID.

    Args:
        request: Dict with session_id, text, optional image_base64, gps_lat, gps_lng

    Returns:
        dict: Triage assessment response
    """
    start_time = time.time()
    session_id = request.get("session_id", "unknown")

    # Set correlation ID for tracing
    set_correlation_id(session_id)

    try:
        # Validate required fields
        if not request.get("session_id"):
            raise HTTPException(status_code=400, detail="session_id is required")

        if not request.get("text"):
            raise HTTPException(status_code=400, detail="text is required")

        # Invoke chain
        config = RunnableConfig(metadata={"session_id": session_id})
        result = await chain.ainvoke(request, config=config)

        # Record metrics
        duration = time.time() - start_time
        status = result.get("status", "error")
        request_count.labels(endpoint="/assistant/invoke", status=status).inc()
        request_duration.labels(endpoint="/assistant/invoke").observe(duration)

        if status == "final" and result.get("triage_level"):
            triage_level = result.get("triage_level")
            from .utils.metrics import triage_decisions
            triage_decisions.labels(
                triage_level=triage_level,
                source=result.get("triage_source", "unknown")
            ).inc()

        logger.info(
            f"Request completed: status={status}",
            extra={"session_id": session_id, "duration": duration}
        )

        return result

    except HTTPException:
        raise

    except ValueError as e:
        request_count.labels(endpoint="/assistant/invoke", status="validation_error").inc()
        logger.warning(f"Validation error: {e}", extra={"session_id": session_id})
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        request_count.labels(endpoint="/assistant/invoke", status="error").inc()
        logger.error(f"Unexpected error: {e}", extra={"session_id": session_id})
        raise HTTPException(status_code=500, detail="系统暂时繁忙，请稍后重试")


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
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_config=None,  # Use our custom logging
    )


if __name__ == "__main__":
    main()
