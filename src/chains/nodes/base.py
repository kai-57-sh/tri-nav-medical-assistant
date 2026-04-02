"""Base node decorator with error handling and logging."""
import uuid
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar, cast

from src.utils.logging_config import get_logger, set_correlation_id
from src.utils.metrics import record_error

logger = get_logger(__name__)
F = TypeVar("F", bound=Callable[..., Any])


def safe_node(node_name: str, raise_on_error: bool = False) -> Callable[[F], F]:
    """Decorator for LangGraph nodes with error handling and logging.

    Args:
        node_name: Name of the node for logging/metrics
        raise_on_error: If True, raise exceptions; if False, degrade gracefully

    Returns:
        Decorator function
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(state: dict[str, Any]) -> dict[str, Any]:
            # Set correlation ID if not present
            session_id = state.get("session_id")
            if not session_id:
                session_id = str(uuid.uuid4())
                state["session_id"] = session_id

            set_correlation_id(session_id)

            try:
                logger.info(f"Entering node: {node_name}", extra={
                    "node": node_name,
                    "session_id": session_id
                })

                # Execute node function
                typed_func = cast(Callable[[dict[str, Any]], Awaitable[dict[str, Any]]], func)
                result = await typed_func(state)

                # Merge result with state
                updated_state = {**state, **result}

                logger.info(f"Exiting node: {node_name}", extra={
                    "node": node_name,
                    "session_id": session_id
                })

                return updated_state

            except ValueError as e:
                # Validation errors - log but don't crash
                logger.error(f"Validation error in {node_name}: {e}", extra={
                    "node": node_name,
                    "session_id": session_id
                })
                record_error("validation_error", node_name)

                if raise_on_error:
                    raise

                # Return error state
                return {
                    **state,
                    "status": "error",
                    "error_message": f"输入验证失败: {str(e)}"
                }

            except Exception as e:
                # Unexpected errors
                logger.error(f"Error in {node_name}: {e}", exc_info=True, extra={
                    "node": node_name,
                    "session_id": session_id
                })
                record_error("node_error", node_name)

                if raise_on_error:
                    raise

                # Graceful degradation per constitution Principle V
                # If triage already determined, still return final
                if state.get("triage_level") == "EMERGENCY":
                    return {
                        **state,
                        "status": "final",
                        "error_message": None  # Don't show error for emergency
                    }

                return {
                    **state,
                    "status": "error",
                    "error_message": "系统暂时繁忙，请稍后重试"
                }

        return cast(F, wrapper)
    return decorator
