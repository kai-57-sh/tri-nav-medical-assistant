"""Evidence model for literature references."""
from typing import Optional
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """Medical literature reference for public education (NOT treatment guidance)."""

    # === Identification ===
    pmid: str = Field(..., description="PubMed ID")

    # === Metadata ===
    title: str = Field(..., min_length=1, max_length=500, description="Article title")
    year: str = Field(..., pattern=r"^\d{4}$", description="Publication year (last 10 years per FR-030)")
    source: str = Field(..., max_length=200, description="Journal name")
    type: str = Field(
        ...,
        pattern="^(Guideline|SystematicReview|Review|RCT|CaseReport|Other)$",
        description="Article type (per FR-030: preference for reviews/guidelines)"
    )

    # === Relevance ===
    note: Optional[str] = Field(None, max_length=500, description="Brief relevance explanation")

    class Config:
        json_schema_extra = {
            "example": {
                "pmid": "12345678",
                "title": "Acute urticaria: Evaluation and management",
                "year": "2023",
                "source": "Journal of Allergy and Clinical Immunology",
                "type": "Review",
                "note": "最新急性荨麻疹诊疗指南"
            }
        }

# Constraints:
# - Usage: For public education ONLY, NOT as individual treatment guidance (per entity description in spec)
# - Max items: 8 per response (FR-031)
# - Time filter: Last 10 years preference (FR-030)
# - Type preference: Guidelines > Systematic Reviews > Reviews > RCT > Case Reports (FR-030)
