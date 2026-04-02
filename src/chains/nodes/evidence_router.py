"""Evidence Router node (Node 11).

Decides whether to retrieve NCBI evidence based on triage level.
Skips evidence retrieval for EMERGENCY cases to speed up response time.
"""
from typing import Any

from src.chains.nodes.base import safe_node
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@safe_node("EvidenceRouter")
async def evidence_router(state: dict[str, Any]) -> dict[str, Any]:
    """Decide whether to retrieve NCBI evidence.

    Per FR-032: Skip evidence retrieval for EMERGENCY triage to minimize latency.
    Evidence is most valuable for ROUTINE/SELF_CARE cases where users need
    educational information.

    Args:
        state: Current workflow state

    Returns:
        Updated state with should_retrieve_evidence flag
    """
    triage_level = state.get("triage_level")
    session_id = state.get("session_id")

    # Skip evidence for emergency cases
    if triage_level == "EMERGENCY":
        logger.info(
            "Skipping NCBI evidence retrieval for EMERGENCY triage",
            extra={"session_id": session_id, "triage_level": triage_level}
        )
        return {"should_retrieve_evidence": False}

    # Skip evidence when no causes identified (reduces low-value retrievals)
    causes = state.get("possible_causes", [])
    if not causes:
        logger.info(
            "Skipping NCBI evidence retrieval (no causes identified)",
            extra={"session_id": session_id, "triage_level": triage_level}
        )
        return {"should_retrieve_evidence": False}

    # Retrieve evidence for ROUTINE and URGENT cases
    logger.info(
        f"NCBI evidence retrieval approved for {triage_level}",
        extra={"session_id": session_id, "triage_level": triage_level}
    )

    return {"should_retrieve_evidence": True}
