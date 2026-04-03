"""Navigation Result model for hospital recommendations and routes."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RoutePlan(BaseModel):
    """Navigation route to top-ranked hospital."""

    to_hospital_rank: int = Field(..., ge=1, le=3, description="Target hospital rank (always 1)")
    mode: Literal["driving", "transit", "walking"] = Field(
        ...,
        description="Transport method (per FR-036)"
    )
    eta_min: int = Field(..., ge=1, description="Estimated travel time in minutes (per FR-036)")
    summary: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Plain-language route description (per FR-036)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "to_hospital_rank": 1,
                "mode": "driving",
                "eta_min": 15,
                "summary": "大约15分钟车程"
            }
        }
    )


class Hospital(BaseModel):
    """Individual hospital recommendation."""

    rank: int = Field(..., ge=1, le=3, description="Priority order (1 = top recommendation)")
    name: str = Field(..., max_length=100, description="Hospital name")
    is_3a: bool = Field(..., description="Grade 3A (三甲) status (per FR-034)")
    address: str | None = Field(None, max_length=200, description="Hospital address")
    distance_m: int | None = Field(None, ge=0, description="Distance in meters")
    location: dict[str, float] = Field(..., description="GPS coordinates {lat, lng}")
    phone: str | None = Field(None, max_length=50, description="Hospital phone number")
    reason: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Ranking rationale (per FR-044)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rank": 1,
                "name": "北京协和医院",
                "is_3a": True,
                "address": "北京市东城区帅府园1号",
                "distance_m": 1200,
                "location": {"lat": 39.914, "lng": 116.417},
                "phone": "010-69156699",
                "reason": "三甲综合医院，距离较近，急诊/门诊齐全"
            }
        }
    )


class NavigationResult(BaseModel):
    """Complete navigation result with hospitals and route."""

    # === Search Parameters ===
    radius_km: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Search radius in kilometers (per FR-033)"
    )

    # === Hospital Recommendations ===
    hospitals: list[Hospital] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly 3 hospitals: Top1 + 2 alternatives (per FR-035)"
    )

    @field_validator('hospitals')
    @classmethod
    def exactly_three_hospitals(cls, v: list[Hospital]) -> list[Hospital]:
        """Enforce exactly 3 hospitals per FR-035."""
        if len(v) != 3:
            raise ValueError("Must have exactly 3 hospitals")
        return v

    @field_validator('hospitals')
    @classmethod
    def ranked_correctly(cls, v: list[Hospital]) -> list[Hospital]:
        """Validate ranking sequence 1, 2, 3."""
        ranks = [h.rank for h in v]
        if sorted(ranks) != [1, 2, 3]:
            raise ValueError("Hospitals must be ranked 1, 2, 3")
        return v

    # === Route Planning ===
    route_plan: RoutePlan | None = Field(
        default=None,
        description="Route to top-ranked hospital (per FR-036, optional)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "radius_km": 10,
                "hospitals": [
                    {
                        "rank": 1,
                        "name": "北京协和医院",
                        "is_3a": True,
                        "address": "北京市东城区帅府园1号",
                        "distance_m": 1200,
                        "location": {"lat": 39.914, "lng": 116.417},
                        "phone": "010-69156699",
                        "reason": "三甲综合医院，距离较近，急诊/门诊齐全"
                    },
                    {
                        "rank": 2,
                        "name": "中日友好医院",
                        "is_3a": True,
                        "address": "北京市朝阳区樱花园东街",
                        "distance_m": 3500,
                        "location": {"lat": 39.979, "lng": 116.447},
                        "phone": "010-84205566",
                        "reason": "三甲综合医院，口碑较好"
                    },
                    {
                        "rank": 3,
                        "name": "朝阳医院",
                        "is_3a": False,
                        "address": "北京市朝阳区工人体育场南路",
                        "distance_m": 900,
                        "location": {"lat": 39.921, "lng": 116.457},
                        "phone": "010-85231000",
                        "reason": "距离更近，可作为备选"
                    }
                ],
                "route_plan": {
                    "to_hospital_rank": 1,
                    "mode": "driving",
                    "eta_min": 15,
                    "summary": "大约15分钟车程"
                }
            }
        }
    )

# Validation Rules:
# - Exactly 3 hospitals: Top recommendation + 2 alternatives (FR-035)
# - Ranking priority: Grade 3A hospitals prioritized (FR-034)
# - Route to Rank 1 only: Navigation provided for top hospital (FR-036)
# - Radius: 10km default, configurable (FR-033, AS-009)
