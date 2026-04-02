"""Weather Fetcher node (Node 16).

Fetches weather alerts for travel tips using Open-Meteo service.
Non-critical path with graceful degradation per FR-037.
"""
from typing import Any

from src.chains.nodes.base import safe_node
from src.services.redis_service import get_redis_service
from src.services.weather_service_openmeteo import get_openmeteo_service
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@safe_node("WeatherFetcher")
async def weather_fetcher(state: dict[str, Any]) -> dict[str, Any]:
    """Fetch weather alerts for travel tips.

    Provides context-aware travel tips based on weather conditions:
    - Rain: Bring umbrella
    - Cold: Wear warm clothing
    - Snow: Allow extra travel time
    - Fog: Drive carefully, low visibility

    Only runs if GPS coordinates are available.
    Non-critical path: failure doesn't block workflow per FR-037.

    Args:
        state: Current workflow state

    Returns:
        Updated state with weather_alert dict
    """
    gps_lat = state.get("gps_lat")
    gps_lng = state.get("gps_lng")
    session_id = state.get("session_id")

    # Skip if no GPS coordinates
    if gps_lat is None or gps_lng is None:
        logger.info(
            "No GPS coordinates provided, skipping weather check",
            extra={"session_id": session_id}
        )
        return {"weather_alert": None}

    try:
        # Check Redis cache first
        redis_service = await get_redis_service()
        cache_key = f"weather:{gps_lat:.2f},{gps_lng:.2f}"

        if redis_service.is_healthy:
            cached_result = await redis_service.load_cached_result(cache_key)
            if cached_result:
                logger.info(
                    "Returning cached weather data",
                    extra={"session_id": session_id, "cache_key": cache_key}
                )
                return {"weather_alert": cached_result}

        # Get weather service
        weather_service = get_openmeteo_service()

        # Fetch weather data
        logger.info(
            f"Fetching weather for {gps_lat}, {gps_lng}",
            extra={"session_id": session_id}
        )

        weather_alert = await weather_service.get_weather(
            lat=gps_lat,
            lng=gps_lng
        )

        if not weather_alert:
            logger.info(
                "No weather data available",
                extra={"session_id": session_id}
            )
            return {"weather_alert": None}

        # Cache results (30min TTL - weather changes slowly)
        if redis_service.is_healthy:
            await redis_service.cache_external_result(
                cache_key=cache_key,
                result=weather_alert,
                ttl=1800
            )

        logger.info(
            f"Weather alert retrieved: {weather_alert.get('condition')}",
            extra={"session_id": session_id}
        )

        return {"weather_alert": weather_alert}

    except Exception as e:
        # Graceful degradation per FR-037: non-critical path
        logger.warning(
            f"Weather fetch failed: {e}, continuing without weather info",
            extra={"session_id": session_id}
        )
        return {"weather_alert": None}
