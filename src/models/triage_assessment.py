"""Triage Assessment model for medical triage decisions."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TriageAssessment(BaseModel):
    """Medical triage decision and recommendations."""

    # === Urgency Assessment ===
    triage_level: Literal["EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"] = Field(
        ...,
        description="Urgency classification (per FR-018)"
    )
    triage_reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Explanation of triage decision (per FR-043)"
    )
    triage_source: Literal["rule_engine", "llm", "merged"] = Field(
        ...,
        description="Source of triage decision (for audit trail per FR-066)"
    )

    # === Recommendations ===
    recommended_departments: list[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Suggested medical departments (per FR-019)"
    )

    # === Possible Causes (Qualified) ===
    possible_causes: list[str] = Field(
        ...,
        min_length=0,
        max_length=3,
        description="Suspected causes with '疑似' or '可能' qualifiers (per FR-020)"
    )

    @field_validator('possible_causes')
    @classmethod
    def must_use_qualified_language(cls, v: list[str]) -> list[str]:
        """Enforce '疑似' or '可能' qualifiers per FR-020, CT-001."""
        for cause in v:
            if not any(q in cause for q in ["疑似", "可能", "相关"]):
                raise ValueError(f"Cause must use qualified language: {cause}")
        return v

    # === Self-Care Guidance ===
    self_care_tips: list[str] = Field(
        ...,
        min_length=0,
        max_length=10,
        description="Non-prescriptive care guidance (per FR-021)"
    )

    @field_validator('self_care_tips')
    @classmethod
    def no_prescriptive_language(cls, v: list[str]) -> list[str]:
        """Prohibit drug dosages or treatment protocols per FR-021, CT-002."""
        prohibited_patterns = ["mg", "每次", "剂量", "片", "服用", "用药"]
        for tip in v:
            if any(p in tip for p in prohibited_patterns):
                raise ValueError(f"Self-care tip cannot contain prescriptive language: {tip}")
        return v

    # === Red Flags (Warning Signs) ===
    red_flags: list[str] = Field(
        ...,
        min_length=0,
        max_length=10,
        description="Warning signs requiring immediate emergency care (per FR-022)"
    )

    # === Internal State ===
    red_flags_hit: list[str] = Field(
        default_factory=list,
        description="IDs of triggered red flag rules (for audit per FR-066)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "triage_level": "ROUTINE",
                "triage_reason": "症状轻微，无危险信号",
                "triage_source": "llm",
                "recommended_departments": ["皮肤科"],
                "possible_causes": [
                    "过敏相关皮疹（疑似）",
                    "接触性皮炎（疑似）"
                ],
                "self_care_tips": [
                    "避免抓挠患处",
                    "记录皮疹变化",
                    "避免接触可能过敏源"
                ],
                "red_flags": [
                    "如果出现呼吸困难/脸唇肿胀/全身迅速扩散，请立刻急诊"
                ],
                "red_flags_hit": []
            }
        }
