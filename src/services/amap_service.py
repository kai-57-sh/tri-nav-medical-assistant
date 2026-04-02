"""Amap service for hospital navigation and route planning."""
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config.settings import get_settings
from ..utils.logging_config import get_logger
from ..utils.metrics import set_external_service_health

logger = get_logger(__name__)

settings = get_settings()


class AmapService:
    """Amap API integration for hospital search and route planning.

    Implements graceful degradation per FR-038, FR-046.
    """

    def __init__(self):
        """Initialize Amap service."""
        self.api_key = settings.amap_api_key
        self.base_url = "https://restapi.amap.com/v3"
        self._healthy = True
        self._timeout = settings.amap_timeout

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=3)
    )
    async def _make_request(
        self,
        endpoint: str,
        params: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Make HTTP request to Amap API with retry.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            Response JSON or None on failure
        """
        if not self.api_key:
            logger.warning("Amap API key not configured")
            return None

        url = f"{self.base_url}/{endpoint}"
        params["key"] = self.api_key

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = response.json()

                # Check Amap response status
                if result.get("status") == "1" and result.get("info") == "OK":
                    self._healthy = True
                    set_external_service_health("amap", True)
                    return result
                else:
                    error_code = result.get("infocode", "unknown")
                    logger.error(f"Amap API error: {error_code} - {result.get('info', 'Unknown error')}")
                    return None

        except httpx.TimeoutException:
            self._healthy = False
            set_external_service_health("amap", False)
            logger.warning(f"Amap API timeout: {endpoint}")
            return None

        except httpx.HTTPError as e:
            self._healthy = False
            set_external_service_health("amap", False)
            logger.error(f"Amap API HTTP error: {e}")
            return None

        except Exception as e:
            self._healthy = False
            set_external_service_health("amap", False)
            logger.error(f"Amap API unexpected error: {e}")
            return None

    async def search_hospitals(
        self,
        lat: float,
        lng: float,
        radius_km: int = 10
    ) -> list[dict[str, Any]]:
        """Search hospitals near given location.

        Returns exactly 3 hospitals: Top1 + 2 alternatives per FR-035.
        Prioritizes 3A hospitals per FR-034.

        Args:
            lat: Latitude
            lng: Longitude
            radius_km: Search radius in kilometers

        Returns:
            List of 3 hospital dicts or empty list on failure
        """
        params = {
            "location": f"{lng},{lat}",  # Amap uses lng,lat order
            "keywords": "医院",
            "radius": radius_km * 1000,  # Convert to meters
            "types": "医疗保健服务",
            "extensions": "all",
            "page_size": 20  # Get more results to find 3A hospitals
        }

        result = await self._make_request("place/around", params)

        if not result:
            logger.warning("Amap place/around request returned no data")
            return []

        if "pois" not in result:
            logger.warning(
                "Amap place/around response missing POIs",
                extra={
                    "status": result.get("status"),
                    "info": result.get("info"),
                    "infocode": result.get("infocode")
                }
            )
            return []

        pois = result["pois"]
        if not pois:
            logger.info(
                "Amap returned zero POIs for hospital search",
                extra={
                    "count": result.get("count"),
                    "status": result.get("status"),
                    "info": result.get("info"),
                    "infocode": result.get("infocode"),
                    "suggestion": result.get("suggestion")
                }
            )
            return []

        # Process and rank hospitals
        hospitals = []
        for poi in pois:
            hospital = self._parse_hospital(poi, lat, lng)
            if hospital:
                hospitals.append(hospital)

        # Sort by 3A status and distance
        hospitals.sort(key=lambda h: (
            -1 if h["is_3a"] else 0,  # 3A hospitals first
            h.get("distance_m", float("inf"))
        ))

        # Return exactly 3 hospitals per FR-035
        top_hospitals = hospitals[:3]

        # Add ranking info
        for rank, hospital in enumerate(top_hospitals, start=1):
            hospital["rank"] = rank
            hospital["reason"] = self._generate_ranking_reason(hospital)

        logger.info(
            f"Found {len(top_hospitals)} hospitals",
            extra={"lat": lat, "lng": lng}
        )

        return top_hospitals

    def _parse_hospital(
        self,
        poi: dict[str, Any],
        user_lat: float,
        user_lng: float
    ) -> dict[str, Any] | None:
        """Parse hospital POI data.

        Args:
            poi: Amap POI data
            user_lat: User's latitude
            user_lng: User's longitude

        Returns:
            Hospital dict or None
        """
        try:
            name = poi.get("name", "")
            if not name:
                return None

            # Parse location
            location = poi.get("location", "")
            if "," not in location:
                return None

            lng_str, lat_str = location.split(",")
            hospital_lng = float(lng_str)
            hospital_lat = float(lat_str)

            # Calculate distance (simplified)
            from math import sqrt
            distance_m = int(sqrt(
                (hospital_lng - user_lng) ** 2 +
                (hospital_lat - user_lat) ** 2
            ) * 111000)  # Rough conversion to meters

            # Determine if 3A hospital
            is_3a = self._is_3a_hospital(name)

            return {
                "name": name,
                "is_3a": is_3a,
                "address": poi.get("address", ""),
                "distance_m": distance_m,
                "location": {"lat": hospital_lat, "lng": hospital_lng},
                "phone": poi.get("tel", "")
            }

        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse hospital POI: {e}")
            return None

    def _is_3a_hospital(self, name: str) -> bool:
        """Check if hospital is Grade 3A (三甲).

        Args:
            name: Hospital name

        Returns:
            True if 3A hospital
        """
        # Common 3A hospital keywords
        _3a_keywords = [
            "协和医院", "301医院", "同仁医院", "人民医院",
            "大学附属医院", "第一医院", "第二医院", "第三医院",
            "中医院", "儿童医院", "妇产医院", "肿瘤医院",
            "积水潭", "天坛", "安贞", "阜外"
        ]

        for keyword in _3a_keywords:
            if keyword in name:
                return True

        return False

    def _generate_ranking_reason(self, hospital: dict[str, Any]) -> str:
        """Generate ranking rationale for hospital.

        Args:
            hospital: Hospital dict

        Returns:
            Ranking reason string
        """
        reasons = []

        if hospital["is_3a"]:
            reasons.append("三甲综合医院")

        distance_km = hospital.get("distance_m", 0) / 1000
        if distance_km < 2:
            reasons.append("距离较近")
        elif distance_km < 5:
            reasons.append("距离适中")

        # Check departments
        name = hospital.get("name", "")
        if any(keyword in name for keyword in ["综合", "总医院"]):
            reasons.append("急诊/门诊齐全")

        return "，".join(reasons) if reasons else "可提供医疗服务"

    async def get_route(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float
    ) -> dict[str, Any] | None:
        """Get route plan from origin to destination.

        Args:
            origin_lat: Origin latitude
            origin_lng: Origin longitude
            dest_lat: Destination latitude
            dest_lng: Destination longitude

        Returns:
            Route plan dict or None on failure
        """
        params = {
            "origin": f"{origin_lng},{origin_lat}",
            "destination": f"{dest_lng},{dest_lat}",
            "strategy": 11,  # Priority to speed
            "extensions": "all"
        }

        result = await self._make_request("driving/policy", params)

        if not result or "route" not in result:
            logger.warning("No route found or API failure")
            return None

        try:
            route = result["route"]
            paths = route.get("paths", [])

            if not paths:
                return None

            # Get first (best) path
            best_path = paths[0]
            distance_m = int(best_path.get("distance", 0))
            duration_sec = int(best_path.get("duration", 0))
            duration_min = duration_sec // 60

            # Generate route summary
            if duration_min < 60:
                summary = f"大约{duration_min}分钟车程"
            else:
                hours = duration_min // 60
                mins = duration_min % 60
                summary = f"大约{hours}小时{mins}分钟车程"

            return {
                "to_hospital_rank": 1,
                "mode": "driving",
                "eta_min": duration_min,
                "distance_km": round(distance_m / 1000, 1),
                "summary": summary
            }

        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse route data: {e}")
            return None

    @property
    def is_healthy(self) -> bool:
        """Check if Amap service is healthy."""
        return self._healthy and self.api_key is not None


# Global Amap service instance
_amap_service: AmapService | None = None


def get_amap_service() -> AmapService:
    """Get or create global Amap service instance.

    Returns:
        AmapService instance
    """
    global _amap_service

    if _amap_service is None:
        _amap_service = AmapService()

    return _amap_service
