"""Triage Classifier node (Node 7)."""
from typing import Any

from src.chains.nodes.base import safe_node
from src.services.llm_service import get_llm_service
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@safe_node("TriageClassifier")
async def triage_classifier(state: dict[str, Any]) -> dict[str, Any]:
    """Classify triage level using LLM with conservative bias.

    Prompt engineering: Conservative bias, avoid under-triaging.
    Temperature: 0.3 for balanced creativity.

    Args:
        state: Current workflow state

    Returns:
        Updated state with LLM triage assessment
    """
    symptom_schema = state.get("symptom_schema")

    if not symptom_schema:
        raise ValueError("缺少症状信息，无法进行分诊评估")

    llm_service = get_llm_service()

    # Classify triage level
    triage_decision = await llm_service.classify_triage(symptom_schema)

    logger.info(
        f"LLM triage: {triage_decision.get('triage_level')} - {triage_decision.get('triage_reason')}",
        extra={
            "session_id": state.get("session_id"),
            "triage_level": triage_decision.get("triage_level")
        }
    )

    return {
        "llm_triage_level": triage_decision.get("triage_level"),
        "llm_triage_reason": triage_decision.get("triage_reason"),
        "llm_recommended_departments": triage_decision.get("recommended_departments", []),
        "llm_possible_causes": triage_decision.get("possible_causes", []),
        "llm_self_care_tips": triage_decision.get("self_care_tips", []),
        "llm_red_flags": triage_decision.get("red_flags", [])
    }
