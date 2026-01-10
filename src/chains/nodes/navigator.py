"""Navigator node (Node 15).

Hospital search and route planning using Amap service.
Returns 3 hospitals with route planning per FR-034, FR-035, FR-036.
"""
from typing import Dict, Any, Optional
from src.chains.nodes.base import safe_node
from src.services.amap_service import get_amap_service
from src.services.redis_service import get_redis_service
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@safe_node("Navigator")
async def navigator(state: Dict[str, Any]) -> Dict[str, Any]:
    """Search hospitals and plan routes using Amap service.

    Performs:
    1. Hospital search with 3A prioritization (FR-034)
    2. Returns exactly 3 hospitals (FR-035)
    3. Route planning with ETA calculation (FR-036)

    Only runs for EMERGENCY, URGENT, and ROUTINE triage levels.
    Skipped for SELF_CARE cases (no hospital needed).

    Args:
        state: Current workflow state

    Returns:
        Updated state with navigation_result dict
    """
    triage_level = state.get("triage_level")
    gps_lat = state.get("gps_lat")
    gps_lng = state.get("gps_lng")
    session_id = state.get("session_id")
    case_domain = state.get("case_domain")
    departments = state.get("recommended_departments", [])

    # Skip navigation for SELF_CARE or missing GPS
    if triage_level == "SELF_CARE":
        logger.info(
            "Skipping navigation for SELF_CARE triage",
            extra={"session_id": session_id}
        )
        return {"navigation_result": None}

    if not gps_lat or not gps_lng:
        logger.warning(
            "No GPS coordinates provided, skipping navigation",
            extra={"session_id": session_id}
        )
        return {"navigation_result": None}

    try:
        # Check Redis cache first
        redis_service = await get_redis_service()
        cache_key = f"amap:{gps_lat:.2f},{gps_lng:.2f}:{case_domain or 'general'}"

        if redis_service.is_healthy:
            cached_result = await redis_service.load_cached_result(cache_key)
            if cached_result:
                logger.info(
                    "Returning cached navigation results",
                    extra={"session_id": session_id, "cache_key": cache_key}
                )
                return {"navigation_result": cached_result}

        # Get Amap service
        amap_service = get_amap_service()

        # Search hospitals near user location
        logger.info(
            f"Searching hospitals near {gps_lat}, {gps_lng}",
            extra={"session_id": session_id}
        )

        hospitals = await amap_service.search_hospitals(
            lat=gps_lat,
            lng=gps_lng,
            radius_km=10  # 10km radius
        )

        if not hospitals:
            logger.warning(
                "No hospitals found, using fallback guidance",
                extra={"session_id": session_id}
            )
            return {"navigation_result": None}

        # Get route to top hospital
        top_hospital = hospitals[0]
        dest_lat = top_hospital.get("location", {}).get("lat")
        dest_lng = top_hospital.get("location", {}).get("lng")

        route_plan = None
        if dest_lat and dest_lng:
            route_plan = await amap_service.get_route(
                origin_lat=gps_lat,
                origin_lng=gps_lng,
                dest_lat=dest_lat,
                dest_lng=dest_lng
            )

        # Build navigation result
        navigation_result = {
            "hospitals": hospitals,
            "route_plan": route_plan
        }

        # Cache results (30min TTL per FR-056)
        if redis_service.is_healthy:
            await redis_service.cache_external_result(
                cache_key=cache_key,
                result=navigation_result,
                ttl=1800
            )

        logger.info(
            f"Navigation complete: {len(hospitals)} hospitals, route available: {route_plan is not None}",
            extra={"session_id": session_id}
        )

        return {"navigation_result": navigation_result}

    except Exception as e:
        # Graceful degradation per FR-038
        logger.warning(
            f"Navigation failed: {e}, providing general guidance",
            extra={"session_id": session_id}
        )
        return {"navigation_result": None}
