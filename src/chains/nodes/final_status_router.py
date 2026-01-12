"""Final Status Router node (Node 18)."""
from typing import Dict, Any
from src.chains.nodes.base import safe_node
from src.utils.constants import DISCLAIMER_TEXT
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@safe_node("FinalStatusRouter")
async def final_status_router(state: Dict[str, Any]) -> Dict[str, Any]:
    """Route to final output based on status.

    Prepares final response dict for API return.

    Args:
        state: Current workflow state

    Returns:
        Final output dict ready for API response
    """
    status = state.get("status", "error")
    session_id = state.get("session_id")
    final_response = state.get("final_response", "") or ""
    error_message = state.get("error_message")

    if status == "need_more_info":
        # Clarification needed
        clarify_questions = state.get("clarify_questions", [])

        logger.info(
            f"Returning need_more_info response",
            extra={"session_id": session_id}
        )

        return {
            "status": "need_more_info",
            "session_id": session_id,
            "clarify_questions": clarify_questions,
            "response": final_response,
            "disclaimer": DISCLAIMER_TEXT
        }

    elif status == "final":
        # Final triage assessment
        triage_level = state.get("triage_level")
        departments = state.get("recommended_departments", [])
        causes = state.get("possible_causes", [])
        tips = state.get("self_care_tips", [])
        red_flags = state.get("red_flags", [])

        logger.info(
            f"Returning final triage response: {triage_level}",
            extra={"session_id": session_id, "triage_level": triage_level}
        )

        return {
            "status": "final",
            "session_id": session_id,
            "response": final_response,
            "disclaimer": DISCLAIMER_TEXT,
            "triage_level": triage_level,
            "recommended_departments": departments,
            "possible_causes": causes,
            "self_care_tips": tips,
            "red_flags": red_flags,
            "navigation": state.get("navigation_result"),  # Optional
            "evidence": state.get("evidence_selected")  # Optional
        }

    else:  # status == "error"
        # Error response
        logger.warning(
            f"Returning error response: {error_message}",
            extra={"session_id": session_id}
        )

        return {
            "status": "error",
            "session_id": session_id,
            "error_message": error_message or "系统错误，请稍后重试"
        }
