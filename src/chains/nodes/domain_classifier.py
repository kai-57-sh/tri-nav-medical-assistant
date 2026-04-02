"""Domain Classifier node (Node 14).

Classifies the medical specialty domain for the case.
Used for routing to appropriate departments and improving NCBI queries.
"""
from typing import Any

from src.chains.nodes.base import safe_node
from src.services.llm_service import get_llm_service
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@safe_node("DomainClassifier")
async def domain_classifier(state: dict[str, Any]) -> dict[str, Any]:
    """Classify medical specialty domain from symptom schema.

    Uses LLM to determine which medical specialty is most relevant:
    - Internal Medicine (adult general)
    - Pediatrics (children)
    - Emergency Medicine (urgent cases)
    - Dermatology (skin conditions)
    - Orthopedics (bones/joints)
    - Cardiology (heart)
    - Neurology (nervous system)
    - etc.

    This classification helps:
    1. Recommend specific departments
    2. Improve NCBI query relevance
    3. Provide context-appropriate guidance

    Args:
        state: Current workflow state

    Returns:
        Updated state with case_domain string
    """
    symptom_schema = state.get("symptom_schema", {})
    session_id = state.get("session_id")

    if not symptom_schema:
        logger.info(
            "No symptom schema available for domain classification",
            extra={"session_id": session_id}
        )
        return {"case_domain": None}

    try:
        # Get LLM service
        llm_service = get_llm_service()

        # Classify domain
        logger.info(
            "Classifying medical domain",
            extra={"session_id": session_id}
        )

        domain = await llm_service.classify_domain(symptom_schema)

        logger.info(
            f"Domain classified: {domain}",
            extra={"session_id": session_id, "domain": domain}
        )

        return {"case_domain": domain}

    except Exception as e:
        # Graceful degradation: continue without domain classification
        logger.warning(
            f"Domain classification failed: {e}, continuing without domain",
            extra={"session_id": session_id}
        )
        return {"case_domain": None}
