"""Session State model for Redis storage."""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


class SessionState(BaseModel):
    """Session state stored in Redis (60-minute TTL)."""

    # === Identity ===
    session_id: str = Field(..., description="UUID for conversation session")

    # === Conversation Tracking ===
    turn_count: int = Field(
        default=1,
        ge=1,
        le=2,
        description="Current clarification round (max 2 per CT-009)"
    )
    last_updated_at: datetime = Field(
        default_factory=datetime.now,
        description="Last access time for TTL refresh"
    )

    # === Clinical Data (Structured ONLY) ===
    symptom_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="Extracted symptom information (body part, duration, severity, etc.)"
    )
    clarify_questions: List[str] = Field(
        default_factory=list,
        description="Questions asked in previous turns"
    )
    triage_level: Optional[str] = Field(
        None,
        pattern="^(EMERGENCY|URGENT|ROUTINE|SELF_CARE)$",
        description="Current triage assessment"
    )
    case_domain: Optional[str] = Field(
        None,
        pattern="^(dermatology|trauma|respiratory|gastro|neuro|urology|other)$",
        description="Medical specialty"
    )

    # === Cache References (to avoid re-fetching) ===
    evidence_cache_key: Optional[str] = Field(
        None,
        description="Reference to cached NCBI evidence"
    )
    navigation_cache_key: Optional[str] = Field(
        None,
        description="Reference to cached hospital search results"
    )

    @field_validator('turn_count')
    @classmethod
    def max_two_rounds(cls, v: int) -> int:
        """Enforce max 2 clarification rounds per CT-009."""
        if v > 2:
            raise ValueError("turn_count cannot exceed 2")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "turn_count": 1,
                "last_updated_at": "2025-01-09T10:30:00Z",
                "symptom_schema": {
                    "body_part": "手臂",
                    "symptoms": ["红疹", "痒"],
                    "duration": "2天",
                    "severity": "轻微"
                },
                "clarify_questions": [],
                "triage_level": "ROUTINE",
                "case_domain": "dermatology"
            }
        }

# What's NOT stored (privacy constraints):
# - raw_text: Violates CT-008 (no full text storage)
# - raw_image_base64: Violates CT-007 (no raw images in Redis)
# - precise_gps_long_term: Privacy concern (use cache_key instead)
