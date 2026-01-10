"""Weather Alert model for weather-related travel tips."""
from typing import List
from pydantic import BaseModel, Field


class WeatherAlert(BaseModel):
    """Weather-related travel tips."""

    summary: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Weather condition description"
    )
    tips: List[str] = Field(
        ...,
        min_items=0,
        max_items=5,
        description="Relevant advice (e.g., ['带伞', '注意保暖'])"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "summary": "小雨，气温5°C",
                "tips": ["带伞出行", "注意保暖", "路面湿滑小心"]
            }
        }

# Constraints:
# - Optional: Weather failure does not block navigation (FR-038, FR-046)
# - Relevance: Tips related to travel conditions (umbrella, clothing, road safety)
