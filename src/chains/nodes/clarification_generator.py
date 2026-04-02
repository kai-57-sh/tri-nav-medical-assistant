"""Clarification Generator node (Node 9)."""
from typing import Any

from src.chains.nodes.base import safe_node
from src.config.settings import get_settings
from src.services.llm_service import get_llm_service
from src.utils.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()


@safe_node("ClarificationGenerator")
async def clarification_generator(state: dict[str, Any]) -> dict[str, Any]:
    """Generate clarification questions if information is insufficient.

    - Max 2 rounds per CT-009
    - Max 3 questions per turn per spec
    - Force final triage if turn_count >= 2

    Args:
        state: Current workflow state

    Returns:
        Updated state with clarify_questions and need_clarify flag
    """
    symptom_schema = state.get("symptom_schema")
    triage_level = state.get("triage_level")
    turn_count = state.get("turn_count", 1)

    # Emergency: skip clarification, provide immediate response
    if triage_level == "EMERGENCY":
        logger.info("Emergency detected, skipping clarification")
        return {
            "need_clarify": False,
            "clarify_questions": []
        }

    # Check if max rounds reached
    if turn_count >= settings.max_clarification_rounds:
        logger.info(f"Max clarification rounds reached ({turn_count}), forcing final triage")
        return {
            "need_clarify": False,
            "clarify_questions": []
        }

    # Check if symptom information is sufficient
    if not symptom_schema:
        # No symptoms extracted, need clarification
        return {
            "need_clarify": True,
            "clarify_questions": ["请详细描述您的症状，包括部位、持续时间等"]
        }

    # Use LLM to determine if clarification needed
    llm_service = get_llm_service()
    questions = await llm_service.generate_clarification_questions(
        symptom_schema,
        turn_count
    )

    # Determine if clarification is needed
    need_clarify = len(questions) > 0

    if need_clarify:
        logger.info(
            f"Clarification needed: {len(questions)} questions",
            extra={
                "session_id": state.get("session_id"),
                "questions": questions
            }
        )

    return {
        "need_clarify": need_clarify,
        "clarify_questions": questions[:settings.max_clarification_questions]
    }
