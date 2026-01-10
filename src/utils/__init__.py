"""Utility functions for TriNav application."""
from .logging_config import (
    setup_logging,
    get_logger,
    set_correlation_id,
    get_correlation_id
)
from .telemetry import setup_telemetry, get_tracer
from .metrics import (
    record_request,
    record_error,
    set_external_service_health,
    record_triage_decision,
    update_active_sessions,
    update_queue_depth,
    get_metrics,
    get_content_type
)
from .safety_filters import (
    contains_diagnosis,
    contains_prescription,
    contains_delay_care,
    check_prohibited_content,
    sanitize_response
)

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
