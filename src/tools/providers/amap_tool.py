"""Amap tool adapter for TriNav v2 runtime."""

from typing import Any, cast

from src.services.amap_service import get_amap_service


async def amap_search_tool(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Adapter from generic payload to Amap hospital search call."""

    lat = cast(float, payload["lat"])
    lng = cast(float, payload["lng"])
    radius_km = cast(int, payload.get("radius_km", 10))

    return await get_amap_service().search_hospitals(
        lat=lat,
        lng=lng,
        radius_km=radius_km,
    )
