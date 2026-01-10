"""Clinical Extractor node (Node 5)."""
from typing import Dict, Any
from src.chains.nodes.base import safe_node
from src.services.llm_service import get_llm_service
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@safe_node("ClinicalExtractor")
async def clinical_extractor(state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract structured symptom schema from user input.

    Combines text and visual findings (if available) into unified schema.

    Args:
        state: Current workflow state

    Returns:
        Updated state with symptom_schema extracted
    """
    text = state.get("text")
    visual_findings = state.get("visual_findings")

    # Need text or visual findings
    if not text and not visual_findings:
        raise ValueError("需要提供症状描述或图片")

    llm_service = get_llm_service()

    # Extract symptoms from text + visual findings
    symptom_schema = await llm_service.extract_symptoms(
        text=text or "",
        visual_findings=visual_findings
    )

    logger.info(
        f"Symptom extracted: {symptom_schema.get('body_part')} - {symptom_schema.get('symptoms')}",
        extra={"session_id": state.get("session_id")}
    )

    return {
        "symptom_schema": symptom_schema
    }
