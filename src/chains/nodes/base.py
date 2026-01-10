"""Base node decorator with error handling and logging."""
import uuid
from typing import Callable, Dict, Any
from functools import wraps
from src.utils.logging_config import get_logger, set_correlation_id
from src.utils.metrics import record_error

logger = get_logger(__name__)


def safe_node(node_name: str, raise_on_error: bool = False):
    """Decorator for LangGraph nodes with error handling and logging.

    Args:
        node_name: Name of the node for logging/metrics
        raise_on_error: If True, raise exceptions; if False, degrade gracefully

    Returns:
        Decorator function
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
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
                result = await func(state)

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

        return wrapper
    return decorator
