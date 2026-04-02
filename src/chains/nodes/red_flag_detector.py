"""Red Flag Detector node (Node 6)."""
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.chains.nodes.base import safe_node
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def _load_red_flag_rules() -> list[dict[str, Any]]:
    """Load red flag rules from config file.

    Returns:
        List of red flag rule dicts
    """
    config_path = Path(__file__).parent.parent.parent / "config" / "red_flag_rules.yaml"

    try:
        with open(config_path, encoding='utf-8') as f:
            rules = yaml.safe_load(f)
        if not isinstance(rules, list):
            return []
        return [rule for rule in rules if isinstance(rule, dict)]
    except Exception as e:
        logger.error(f"Failed to load red flag rules: {e}")
        return []


def _matches_rule(symptom_schema: dict[str, Any], rule: dict[str, Any]) -> bool:
    """Check if symptom schema matches a red flag rule.

    Args:
        symptom_schema: Structured symptom data
        rule: Red flag rule dict

    Returns:
        True if rule conditions match
    """
    conditions = rule.get("conditions", [])

    for condition in conditions:
        field = condition.get("field")
        op = condition.get("op")
        value = condition.get("value")

        # Get field value from symptom schema
        field_value = symptom_schema.get(field)

        # Handle missing fields
        if field_value is None:
            return False

        # Apply operation
        if op == "equals":
            if field_value != value:
                return False

        elif op == "contains_any":
            if isinstance(field_value, list):
                if not any(v in field_value for v in value):
                    return False
            else:
                if not any(v in str(field_value) for v in value):
                    return False

        elif op == "contains_all":
            if isinstance(field_value, list):
                if not all(v in field_value for v in value):
                    return False
            else:
                if not all(v in str(field_value) for v in value):
                    return False

    # All conditions passed
    return True


@safe_node("RedFlagDetector")
async def red_flag_detector(state: dict[str, Any]) -> dict[str, Any]:
    """Detect emergency symptoms using rule-based red flag detection.

    Evaluated BEFORE LLM triage per constitution Principle I.
    Rules override LLM when in conflict (more conservative).

    Args:
        state: Current workflow state

    Returns:
        Updated state with red flag detection results
    """
    symptom_schema = state.get("symptom_schema")

    if not symptom_schema:
        logger.debug("No symptom schema, skipping red flag detection")
        return {}

    # Load red flag rules
    rules = _load_red_flag_rules()

    if not rules:
        logger.warning("No red flag rules loaded")
        return {}

    # Check each rule
    flags_hit = []

    for rule in rules:
        if _matches_rule(symptom_schema, rule):
            flags_hit.append(rule)
            logger.warning(
                f"Red flag triggered: {rule['id']}",
                extra={
                    "session_id": state.get("session_id"),
                    "rule_id": rule["id"],
                    "priority": rule["priority"]
                }
            )

    if flags_hit:
        # Use highest priority rule (sorted by priority: high > medium > low)
        priority_order = {"high": 0, "medium": 1, "low": 2}
        flags_hit.sort(key=lambda r: priority_order.get(r["priority"], 3))
        top_rule = flags_hit[0]

        logger.info(
            f"Emergency detected by rule: {top_rule['id']}",
            extra={"session_id": state.get("session_id")}
        )

        return {
            "rule_triage_level": "EMERGENCY",
            "red_flags_hit": [r["id"] for r in flags_hit],
            "recommended_departments": top_rule.get("department", ["急诊"]),
            "triage_reason": top_rule.get("user_message", "检测到危险信号")
        }

    # No red flags triggered
    return {
        "rule_triage_level": None,
        "red_flags_hit": []
    }
