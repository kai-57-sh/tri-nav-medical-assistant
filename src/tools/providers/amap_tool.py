"""Amap tool adapter for TriNav v2 runtime."""

from numbers import Real
from typing import Any

from src.services.amap_service import get_amap_service


def _validate_coordinate(payload: dict[str, Any], key: str, minimum: float, maximum: float) -> float:
    if key not in payload:
        raise ValueError(
            f"payload['{key}'] is required and must be a number in range [{minimum}, {maximum}]"
        )

    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(
            f"payload['{key}'] must be a number in range [{minimum}, {maximum}]"
        )

    value_f = float(value)
    if value_f < minimum or value_f > maximum:
        raise ValueError(
            f"payload['{key}'] out of range; expected [{minimum}, {maximum}], got {value_f}"
        )

    return value_f


def _validate_radius_km(payload: dict[str, Any]) -> float:
    radius_km = payload.get("radius_km", 10)
    if isinstance(radius_km, bool) or not isinstance(radius_km, Real):
        raise ValueError("payload['radius_km'] must be a positive number")

    radius_km_f = float(radius_km)
    if radius_km_f <= 0:
        raise ValueError(
            f"payload['radius_km'] must be > 0, got {radius_km_f}"
        )

    return radius_km_f


async def amap_search_tool(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Adapter from generic payload to Amap hospital search call."""

    lat = _validate_coordinate(payload, key="lat", minimum=-90.0, maximum=90.0)
    lng = _validate_coordinate(payload, key="lng", minimum=-180.0, maximum=180.0)
    radius_km = _validate_radius_km(payload)

    return await get_amap_service().search_hospitals(
        lat=lat,
        lng=lng,
        radius_km=radius_km,
    )
