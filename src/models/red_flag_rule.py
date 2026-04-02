"""Red Flag Rule model for emergency symptom detection."""
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class RuleCondition(BaseModel):
    """Single rule condition for symptom matching."""

    field: str = Field(
        ...,
        description="Symptom schema field to check (e.g., 'accompanying_symptoms')"
    )
    op: Literal["contains_any", "equals", "contains_all"] = Field(
        ...,
        description="Comparison operator"
    )
    value: Any = Field(..., description="Expected value(s)")


class RedFlagRule(BaseModel):
    """Emergency symptom detection rule (versioned for audit trail per FR-054)."""

    # === Identification ===
    id: str = Field(
        ...,
        pattern=r"^RF_[A-Z_]+$",
        description="Unique rule identifier (e.g., 'RF_BREATHING_DIFFICULTY')"
    )
    priority: Literal["high", "medium", "low"] = Field(
        ...,
        description="Rule importance for sorting"
    )
    version: str = Field(..., description="Rule version for traceability (per FR-054)")

    # === Rule Logic ===
    conditions: list[RuleCondition] = Field(
        ...,
        min_items=1,
        description="Rule conditions (AND logic between conditions)"
    )

    # === Output ===
    triage_level: Literal["EMERGENCY"] = Field(
        ...,
        description="Triage level when rule triggers (always EMERGENCY)"
    )
    user_message: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Explanation to user"
    )
    department: list[str] = Field(
        ...,
        min_items=1,
        description="Recommended departments (typically ['急诊'])"
    )

    @field_validator('id')
    @classmethod
    def must_start_with_rf(cls, v: str) -> str:
        """Ensure rule ID follows naming convention."""
        if not v.startswith("RF_"):
            raise ValueError("Rule ID must start with 'RF_'")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "id": "RF_BREATHING_DIFFICULTY",
                "priority": "high",
                "version": "1.0.0",
                "conditions": [
                    {
                        "field": "accompanying_symptoms",
                        "op": "contains_any",
                        "value": ["呼吸困难", "喘不过气", "窒息感"]
                    }
                ],
                "triage_level": "EMERGENCY",
                "user_message": "检测到呼吸困难症状，建议立即急诊/呼叫急救",
                "department": ["急诊"]
            }
        }

# Version Control:
# - File: config/red_flag_rules.yaml (committed to Git)
# - Version field: Incremented on each change (semantic versioning)
# - Audit trail: All changes tracked via Git (per FR-054, FR-066)
# - Medical sign-off: Required before deployment (per SC-008)
