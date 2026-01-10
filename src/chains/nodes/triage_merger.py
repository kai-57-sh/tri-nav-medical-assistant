"""Triage Merger node (Node 8)."""
from typing import Dict, Any, List
from src.chains.nodes.base import safe_node
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@safe_node("TriageMerger")
async def triage_merger(state: Dict[str, Any]) -> Dict[str, Any]:
    """Merge rule-based and LLM triage decisions.

    RULE WINS per constitution Principle I (more conservative).
    If rule says EMERGENCY, always EMERGENCY.
    If uncertain, escalate to higher urgency.

    Args:
        state: Current workflow state

    Returns:
        Updated state with final triage level and source
    """
    rule_triage = state.get("rule_triage_level")
    llm_triage = state.get("llm_triage_level")

    # Get rule-based data
    red_flags_hit = state.get("red_flags_hit", [])
    rule_departments = state.get("recommended_departments", [])
    rule_reason = state.get("triage_reason", "")

    # Get LLM-based data
    llm_departments = state.get("llm_recommended_departments", [])
    llm_reason = state.get("llm_triage_reason", "")
    llm_causes = state.get("llm_possible_causes", [])
    llm_tips = state.get("llm_self_care_tips", [])
    llm_red_flags = state.get("llm_red_flags", [])

    # Merge logic: RULE WINS (more conservative)
    if rule_triage == "EMERGENCY":
        # Rule engine takes precedence
        final_triage = "EMERGENCY"
        triage_source = "rule_engine"
        final_departments = rule_departments or ["急诊"]
        final_reason = rule_reason

        logger.info(
            f"Triage merged: Rule engine EMERGENCY override LLM {llm_triage}",
            extra={
                "session_id": state.get("session_id"),
                "rule_triage": rule_triage,
                "llm_triage": llm_triage,
                "final_triage": final_triage
            }
        )

    elif llm_triage:
        # Use LLM triage (no rule override)
        final_triage = llm_triage
        triage_source = "llm"
        final_departments = llm_departments
        final_reason = llm_reason

        logger.info(
            f"Triage merged: LLM {llm_triage}",
            extra={
                "session_id": state.get("session_id"),
                "final_triage": final_triage
            }
        )

    else:
        # Neither rule nor LLM provided triage (shouldn't happen)
        logger.warning("No triage decision available, defaulting to URGENT")
        final_triage = "URGENT"
        triage_source = "default"
        final_departments = ["急诊"]
        final_reason = "系统无法评估，建议急诊确认"

    # Merge other data
    final_causes = llm_causes or []
    final_tips = llm_tips or []
    final_red_flags = llm_red_flags or []

    # Add rule-based red flags if any
    if red_flags_hit:
        final_red_flags.extend([f"触发预警规则: {', '.join(red_flags_hit)}"])

    return {
        "triage_level": final_triage,
        "triage_source": triage_source,
        "recommended_departments": final_departments,
        "possible_causes": final_causes,
        "self_care_tips": final_tips,
        "red_flags": final_red_flags,
        "triage_reason": final_reason
    }
