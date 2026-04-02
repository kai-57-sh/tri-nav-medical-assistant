"""Vision Extract node (Node 4).

Extracts visual features from medical images using Qwen-VL model.
Only processes images that passed quality gate.
"""
from typing import Dict, Any
from src.chains.nodes.base import safe_node
from src.services.llm_service import get_llm_service
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@safe_node("VisionExtract")
async def vision_extract(state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract visual findings from image using Qwen-VL model.

    Only runs if image passed quality gate (image_as_valid=True).
    Extracts structured visual findings like:
    - Body part visible
    - Visual symptoms (rash, swelling, redness, etc.)
    - Severity indicators
    - Distribution patterns

    Args:
        state: Current workflow state

    Returns:
        Updated state with visual_findings dict
    """
    image_as_valid = state.get("image_as_valid", False)
    image_base64 = state.get("image_base64")
    session_id = state.get("session_id")
    text = state.get("text", "")

    # Skip if image didn't pass quality gate
    if not image_as_valid or not image_base64:
        logger.info(
            "Skipping vision extraction (image invalid or not provided)",
            extra={"session_id": session_id}
        )
        return {"visual_findings": None}

    try:
        # Get LLM service
        llm_service = get_llm_service()

        # Extract visual findings
        logger.info("Extracting visual features from image", extra={"session_id": session_id})

        visual_findings = await llm_service.extract_visual_features(
            image_base64=image_base64,
            text=text  # Provide text context for better extraction
        )

        logger.info(
            f"Visual extraction complete: {visual_findings.get('body_part', 'unknown')}",
            extra={"session_id": session_id}
        )

        return {"visual_findings": visual_findings}

    except Exception as e:
        # Graceful degradation: continue with text-only workflow
        logger.warning(
            f"Vision extraction failed: {e}, continuing with text-only workflow",
            extra={"session_id": session_id}
        )
        return {"visual_findings": None}
