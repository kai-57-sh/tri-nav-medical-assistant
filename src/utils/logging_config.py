"""Structured logging configuration with correlation IDs."""
import logging
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from pythonjsonlogger import jsonlogger

# Context variable for correlation ID
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class JSONFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with correlation ID."""

    def add_fields(self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]):
        super().add_fields(log_record, record, message_dict)
        # Add correlation ID if available
        correlation_id = correlation_id_var.get()
        if correlation_id:
            log_record["correlation_id"] = correlation_id


def setup_logging(log_level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """Setup structured logging with JSON formatting.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for JSON logs

    Returns:
        Configured logger instance
    """
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers = []

    # Create console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level.upper()))
    formatter = JSONFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s %(correlation_id)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z"
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current context.

    Args:
        correlation_id: Unique correlation identifier
    """
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> str:
    """Get the current correlation ID.

    Returns:
        Current correlation ID or empty string
    """
    return correlation_id_var.get()
