"""Weather tool adapter for TriNav runtime."""

from numbers import Real
from typing import Any


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


def _get_openmeteo_service() -> Any:
    from src.services.weather_service_openmeteo import get_openmeteo_service

    return get_openmeteo_service()


async def weather_fetch_tool(payload: dict[str, Any]) -> dict[str, Any]:
    """Adapter from generic payload to Open-Meteo weather service call."""

    lat = _validate_coordinate(payload, key="lat", minimum=-90.0, maximum=90.0)
    lng = _validate_coordinate(payload, key="lng", minimum=-180.0, maximum=180.0)

    weather_data = await _get_openmeteo_service().get_weather(lat=lat, lng=lng)
    return {"weather": weather_data}
