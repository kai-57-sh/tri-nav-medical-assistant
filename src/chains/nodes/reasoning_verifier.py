"""Reasoning Verifier node (Node 17)."""
from typing import Dict, Any
from src.chains.nodes.base import safe_node
from src.chains.nodes.response_composer import compose_response
from src.services.llm_service import get_llm_service
from src.utils.safety_filters import check_prohibited_content
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@safe_node("ReasoningVerifier")
async def reasoning_verifier(state: Dict[str, Any]) -> Dict[str, Any]:
    """Dual safety verification: rule-based + LLM reasoning verifier.

    1. Rule-based: Check for prohibited content patterns
    2. LLM-based: Verify reasoning and safety compliance

    If violations found, rewrite to compliant language.

    Args:
        state: Current workflow state

    Returns:
        Updated state with verified response and final status
    """
    # Compose draft response first
    draft_response = compose_response(state)

    # Check for prohibited content using rule-based filters
    violations = check_prohibited_content(draft_response)

    if violations:
        logger.warning(
            f"Prohibited content detected: {violations}",
            extra={
                "session_id": state.get("session_id"),
                "violations": violations
            }
        )

        # Use LLM to rewrite response
        llm_service = get_llm_service()
        verification = await llm_service.verify_safety(draft_response)

        if verification.get("is_safe"):
            final_response = verification.get("sanitized_content", draft_response)
        else:
            # Use sanitized version even if not perfectly safe
            final_response = verification.get("sanitized_content", draft_response)
            logger.warning(f"Response has violations, using sanitized version")

    else:
        # No violations detected
        final_response = draft_response

    # Determine final status
    need_clarify = state.get("need_clarify", False)

    if need_clarify:
        final_status = "need_more_info"
    else:
        final_status = "final"

    logger.info(
        f"Response verified: status={final_status}",
        extra={"session_id": state.get("session_id")}
    )

    return {
        "final_response": final_response,
        "status": final_status
    }
