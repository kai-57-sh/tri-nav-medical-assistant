"""Prometheus metrics collection for TriNav application."""
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from .logging_config import get_logger

logger = get_logger(__name__)


# Create custom registry
registry = CollectorRegistry()

# Request metrics
request_count = Counter(
    "trinav_requests_total",
    "Total number of requests",
    ["endpoint", "status"],
    registry=registry
)

request_duration = Histogram(
    "trinav_request_duration_seconds",
    "Request duration in seconds",
    ["endpoint"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 30.0),
    registry=registry
)

# Error metrics
error_count = Counter(
    "trinav_errors_total",
    "Total number of errors",
    ["error_type", "node"],
    registry=registry
)

# External service health
external_service_health = Gauge(
    "trinav_external_service_health",
    "External service health status (1=healthy, 0=unhealthy)",
    ["service_name"],
    registry=registry
)

# Triage metrics
triage_decisions = Counter(
    "trinav_triage_decisions_total",
    "Total number of triage decisions",
    ["triage_level", "source"],
    registry=registry
)

# Session metrics
active_sessions = Gauge(
    "trinav_active_sessions",
    "Number of active sessions",
    registry=registry
)

# Queue metrics
queue_depth = Gauge(
    "trinav_queue_depth",
    "Current request queue depth",
    registry=registry
)


def record_request(endpoint: str, status: str, duration: float) -> None:
    """Record a request metric.

    Args:
        endpoint: API endpoint
        status: Response status
        duration: Request duration in seconds
    """
    request_count.labels(endpoint=endpoint, status=status).inc()
    request_duration.labels(endpoint=endpoint).observe(duration)


def record_error(error_type: str, node: str) -> None:
    """Record an error metric.

    Args:
        error_type: Type of error
        node: Node where error occurred
    """
    error_count.labels(error_type=error_type, node=node).inc()


def set_external_service_health(service_name: str, healthy: bool) -> None:
    """Set external service health status.

    Args:
        service_name: Name of external service (redis, amap, weather, ncbi, qwen)
        healthy: Whether service is healthy
    """
    external_service_health.labels(service_name=service_name).set(1 if healthy else 0)


def record_triage_decision(triage_level: str, source: str) -> None:
    """Record a triage decision metric.

    Args:
        triage_level: Triage level (EMERGENCY, URGENT, ROUTINE, SELF_CARE)
        source: Decision source (rule_engine, llm, merged)
    """
    triage_decisions.labels(triage_level=triage_level, source=source).inc()


def update_active_sessions(count: int) -> None:
    """Update active sessions gauge.

    Args:
        count: Number of active sessions
    """
    active_sessions.set(count)


def update_queue_depth(depth: int) -> None:
    """Update queue depth gauge.

    Args:
        depth: Current queue depth
    """
    queue_depth.set(depth)


def get_metrics() -> bytes:
    """Get Prometheus metrics in text format.

    Returns:
        Metrics in Prometheus text format
    """
    return generate_latest(registry)


def get_content_type() -> str:
    """Get the content type for metrics endpoint.

    Returns:
        Content type string
    """
    return CONTENT_TYPE_LATEST
