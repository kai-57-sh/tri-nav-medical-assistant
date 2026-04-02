"""Session Saver node (Node 10)."""
from typing import Any

from src.chains.nodes.base import safe_node
from src.services.redis_service import get_redis_service
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@safe_node("SessionSaver")
async def session_save(state: dict[str, Any]) -> dict[str, Any]:
    """Save session state to Redis.

    Only stores structured data (no raw images/text) per CT-007, CT-008.
    TTL: 60 minutes per CT-006.

    Args:
        state: Current workflow state

    Returns:
        State unchanged (side effect: Redis save)
    """
    session_id = state.get("session_id")

    if not session_id:
        logger.warning("No session ID, skipping save")
        return {}

    redis_service = await get_redis_service()

    if redis_service.is_healthy:
        # Save minimal state to Redis
        await redis_service.save_session(session_id, state)

        logger.debug(
            f"Session saved: {session_id}",
            extra={"session_id": session_id}
        )
    else:
        logger.warning(f"Redis unhealthy, session not saved: {session_id}")

    # No state updates (side effect only)
    return {}
