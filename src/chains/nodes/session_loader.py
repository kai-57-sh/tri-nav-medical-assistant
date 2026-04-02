"""Session Loader node (Node 2)."""
from typing import Any

from src.chains.nodes.base import safe_node
from src.services.redis_service import get_redis_service
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@safe_node("SessionLoader")
async def session_load(state: dict[str, Any]) -> dict[str, Any]:
    """Load session state from Redis or initialize new session.

    Args:
        state: Current workflow state

    Returns:
        Updated state with session data loaded from Redis
    """
    session_id = state.get("session_id")
    if not isinstance(session_id, str):
        session_id = ""

    # Try to load existing session
    redis_service = await get_redis_service()

    if redis_service.is_healthy:
        session_data = await redis_service.load_session(session_id)

        if session_data:
            # Restore session state
            logger.info(f"Session loaded: {session_id}", extra={"session_id": session_id})

            return {
                **state,
                "turn_count": session_data.get("turn_count", 1) + 1,  # Increment turn
                "symptom_schema": session_data.get("symptom_schema"),
                "clarify_questions": session_data.get("clarify_questions", []),
                "triage_level": session_data.get("triage_level"),
                "case_domain": session_data.get("case_domain"),
                "evidence_cache_key": session_data.get("evidence_cache_key"),
                "navigation_cache_key": session_data.get("navigation_cache_key")
            }

    # Initialize new session if not found or Redis unhealthy
    logger.info(f"New session initialized: {session_id}", extra={"session_id": session_id})

    return {
        **state,
        "turn_count": 1,
        "symptom_schema": None,
        "clarify_questions": [],
        "triage_level": None,
        "case_domain": None,
        "evidence_cache_key": None,
        "navigation_cache_key": None
    }
