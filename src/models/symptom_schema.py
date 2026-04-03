"""Symptom Schema model for clinical extraction."""

from pydantic import BaseModel, ConfigDict, Field


class VisualFindings(BaseModel):
    """Image-based observations (optional, only if image provided)."""

    type: str = Field(
        ...,
        pattern="^(rash|wound|unknown)$",
        description="Type of visual symptom"
    )
    summary: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Plain-language visual description"
    )
    features: list[str] = Field(
        default_factory=list,
        description="Observable characteristics (e.g., ['红斑', '丘疹'])"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Extraction confidence score"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "rash",
                "summary": "手臂红斑伴丘疹",
                "features": ["红斑", "丘疹", "肿胀"],
                "confidence": 0.85
            }
        }
    )


class SymptomSchema(BaseModel):
    """Structured symptom information for clinical decision-making."""

    # === Core Symptoms ===
    body_part: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Affected area (e.g., '手臂', '胸口')"
    )
    symptoms: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Reported symptoms (e.g., ['红疹', '痒'])"
    )

    # === Context ===
    duration: str | None = Field(
        None,
        max_length=50,
        description="How long symptoms persisted (e.g., '2天', '1周')"
    )
    severity: str | None = Field(
        None,
        pattern="^(轻微|中度|严重)$",
        description="User-reported intensity"
    )
    accompanying_symptoms: list[str] = Field(
        default_factory=list,
        description="Other symptoms (e.g., ['发热', '头痛'])"
    )
    onset: str | None = Field(
        None,
        pattern="^(突然|逐渐)$",
        description="How symptoms started"
    )

    # === Visual Findings (Optional) ===
    visual_findings: VisualFindings | None = Field(
        None,
        description="Image-based observations if image uploaded"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "body_part": "手臂",
                "symptoms": ["红疹", "痒"],
                "duration": "2天",
                "severity": "轻微",
                "accompanying_symptoms": [],
                "onset": "逐渐",
                "visual_findings": {
                    "type": "rash",
                    "summary": "手臂红斑伴丘疹",
                    "features": ["红斑", "丘疹", "肿胀"],
                    "confidence": 0.85
                }
            }
        }
    )
