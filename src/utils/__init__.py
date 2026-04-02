"""Utility functions for TriNav application."""
from .logging_config import get_correlation_id, get_logger, set_correlation_id, setup_logging
from .metrics import (
    get_content_type,
    get_metrics,
    record_error,
    record_request,
    record_triage_decision,
    set_external_service_health,
    update_active_sessions,
    update_queue_depth,
)
from .safety_filters import (
    check_prohibited_content,
    contains_delay_care,
    contains_diagnosis,
    contains_prescription,
    sanitize_response,
)
from .telemetry import get_tracer, setup_telemetry

__all__ = [
    "setup_logging",
    "get_logger",
    "set_correlation_id",
    "get_correlation_id",
    "setup_telemetry",
    "get_tracer",
    "record_request",
    "record_error",
    "set_external_service_health",
    "record_triage_decision",
    "update_active_sessions",
    "update_queue_depth",
    "get_metrics",
    "get_content_type",
    "contains_diagnosis",
    "contains_prescription",
    "contains_delay_care",
    "check_prohibited_content",
    "sanitize_response",
]
