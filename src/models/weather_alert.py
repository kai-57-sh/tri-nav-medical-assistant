"""Weather Alert model for weather-related travel tips."""
from pydantic import BaseModel, ConfigDict, Field


class WeatherAlert(BaseModel):
    """Weather-related travel tips."""

    condition: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Weather condition (e.g., 小雨/多云)"
    )
    temp_c: float = Field(
        ...,
        description="Temperature in Celsius"
    )
    humidity: int = Field(
        ...,
        ge=0,
        le=100,
        description="Relative humidity percentage"
    )
    wind_speed_kmh: float = Field(
        ...,
        ge=0,
        description="Wind speed in km/h"
    )
    tip: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Travel advice"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "condition": "小雨",
                "temp_c": 5,
                "humidity": 75,
                "wind_speed_kmh": 15,
                "tip": "下雨路滑，出行请注意安全，建议携带雨具"
            }
        }
    )

# Constraints:
# - Optional: Weather failure does not block navigation (FR-038, FR-046)
# - Relevance: Tips related to travel conditions (umbrella, clothing, road safety)
