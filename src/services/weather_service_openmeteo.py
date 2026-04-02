"""Weather service using Open-Meteo API (No authentication required).

Open-Meteo is a free open-source weather API that requires no API key.
Official documentation: https://open-meteo.com/
GitHub: https://github.com/open-meteo/open-meteo
"""
from typing import Any, cast

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..utils.logging_config import get_logger
from ..utils.metrics import set_external_service_health

logger = get_logger(__name__)


class OpenMeteoService:
    """Open-Meteo API integration for weather alerts.

    Implements graceful degradation per FR-037, FR-038.
    Non-critical path - failure does not block navigation.

    Authentication: None required (free open-source API)
    """

    # Open-Meteo API endpoint (no authentication needed)
    API_BASE_URL = "https://api.open-meteo.com/v1"

    # Weather code to Chinese description mapping
    # Based on WMO weather interpretation codes
    WEATHER_CODES = {
        0: "晴朗",
        1: "大部晴朗",
        2: "多云",
        3: "阴天",
        45: "雾",
        48: "雾凇",
        51: "毛毛雨",
        53: "毛毛雨",
        55: "毛毛雨",
        61: "小雨",
        63: "中雨",
        65: "大雨",
        71: "小雪",
        73: "中雪",
        75: "大雪",
        77: "雪粒",
        80: "阵雨",
        81: "阵雨",
        82: "暴雨",
        85: "阵雪",
        86: "阵雪",
        95: "雷雨",
        96: "雷雨伴冰雹",
        99: "雷雨伴冰雹"
    }

    def __init__(self, timeout: float = 10.0) -> None:
        """Initialize Open-Meteo weather service.

        Args:
            timeout: Request timeout in seconds
        """
        self._healthy = True
        self._timeout = timeout
        logger.info("Open-Meteo weather service initialized (no API key required)")

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=3)
    )
    async def _make_request(
        self,
        lat: float,
        lng: float
    ) -> dict[str, Any] | None:
        """Make HTTP request to Open-Meteo API with retry.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Response JSON or None on failure
        """
        try:
            # Build URL for Open-Meteo API
            # Endpoint: /forecast
            # Parameters: current weather data
            url = f"{self.API_BASE_URL}/forecast"
            params: dict[str, str | float] = {
                "latitude": lat,
                "longitude": lng,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m",
                "wind_speed_unit": "ms"
            }

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = cast(dict[str, Any], response.json())

                self._healthy = True
                set_external_service_health("weather", True)
                return result

        except httpx.TimeoutException:
            self._healthy = False
            set_external_service_health("weather", False)
            logger.warning("Open-Meteo API timeout")
            return None

        except httpx.HTTPStatusError as e:
            self._healthy = False
            set_external_service_health("weather", False)
            logger.error(f"Open-Meteo API HTTP error: {e.response.status_code}")
            return None

        except Exception as e:
            self._healthy = False
            set_external_service_health("weather", False)
            logger.error(f"Open-Meteo API unexpected error: {e}")
            return None

    async def get_weather(
        self,
        lat: float,
        lng: float
    ) -> dict[str, Any] | None:
        """Get weather information for location.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Weather alert dict with structured fields, or None on failure
        """
        result = await self._make_request(lat, lng)

        if not result:
            return None

        try:
            # Parse Open-Meteo API response
            weather_data = self._parse_weather_response(result)

            if weather_data:
                logger.info(
                    "Weather retrieved",
                    extra={"lat": lat, "lng": lng, "weather": weather_data.get("condition")}
                )

            return weather_data

        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Failed to parse weather data: {e}")
            return None

    def _parse_weather_response(self, result: dict[str, Any]) -> dict[str, Any] | None:
        """Parse Open-Meteo API response into standard format.

        Args:
            result: Raw Open-Meteo API response

        Returns:
            Weather alert dict or None

        Open-Meteo API response format:
        {
            "latitude": 39.9042,
            "longitude": 116.4074,
            "current": {
                "time": "2025-01-10T12:00",
                "interval": 900,
                "temperature_2m": 24.5,
                "relative_humidity_2m": 65,
                "apparent_temperature": 26.2,
                "weather_code": 1,
                "wind_speed_10m": 3.5,
                "wind_direction_10m": 180
            }
        }
        """
        try:
            # Extract current weather from Open-Meteo format
            current = result.get("current", {})
            if not current:
                logger.warning("No 'current' data in Open-Meteo response")
                return None

            # Extract weather information
            temp = current.get("temperature_2m", 0)
            weather_code = current.get("weather_code", 0)
            humidity = int(current.get("relative_humidity_2m", 0))
            wind_speed = current.get("wind_speed_10m", 0)

            # Convert weather code to Chinese description
            text = self.WEATHER_CODES.get(weather_code, "未知")

            # Convert wind speed from m/s to Beaufort scale (0-12)
            wind_scale = self._get_beaufort_scale(wind_speed)

            # Generate travel tips based on conditions
            tips = self._generate_travel_tips(
                text=text,
                temp=int(temp),
                humidity=humidity,
                wind_scale=wind_scale
            )
            tip = "；".join(tips) if tips else "适宜出行"

            return {
                "condition": text,
                "temp_c": round(float(temp), 1),
                "humidity": humidity,
                "wind_speed_kmh": round(float(wind_speed) * 3.6, 1),
                "tip": tip
            }

        except Exception as e:
            logger.warning(f"Failed to parse Open-Meteo response: {e}")
            return None

    def _get_wind_direction(self, degrees: float) -> str:
        """Convert wind direction in degrees to cardinal direction.

        Args:
            degrees: Wind direction in degrees (0-360)

        Returns:
            Cardinal direction string (e.g., "东风", "东南风")
        """
        if degrees >= 337.5 or degrees < 22.5:
            return "北风"
        elif 22.5 <= degrees < 67.5:
            return "东北风"
        elif 67.5 <= degrees < 112.5:
            return "东风"
        elif 112.5 <= degrees < 157.5:
            return "东南风"
        elif 157.5 <= degrees < 202.5:
            return "南风"
        elif 202.5 <= degrees < 247.5:
            return "西南风"
        elif 247.5 <= degrees < 292.5:
            return "西风"
        elif 292.5 <= degrees < 337.5:
            return "西北风"
        else:
            return ""

    def _get_beaufort_scale(self, wind_speed_ms: float) -> int:
        """Convert wind speed from m/s to Beaufort scale (0-12).

        Args:
            wind_speed_ms: Wind speed in meters per second

        Returns:
            Beaufort scale (0-12)
        """
        if wind_speed_ms < 0.3:
            return 0
        elif wind_speed_ms < 1.6:
            return 1
        elif wind_speed_ms < 3.4:
            return 2
        elif wind_speed_ms < 5.5:
            return 3
        elif wind_speed_ms < 8.0:
            return 4
        elif wind_speed_ms < 10.8:
            return 5
        elif wind_speed_ms < 13.9:
            return 6
        elif wind_speed_ms < 17.2:
            return 7
        elif wind_speed_ms < 20.8:
            return 8
        elif wind_speed_ms < 24.5:
            return 9
        elif wind_speed_ms < 28.5:
            return 10
        elif wind_speed_ms < 32.7:
            return 11
        else:
            return 12

    def _generate_travel_tips(
        self,
        text: str,
        temp: int,
        humidity: int,
        wind_scale: int
    ) -> list[str]:
        """Generate travel tips based on weather conditions.

        Args:
            text: Weather condition text (e.g., "多云", "小雨")
            temp: Temperature in Celsius
            humidity: Humidity percentage
            wind_scale: Wind scale (0-12)

        Returns:
            List of travel tip strings (max 5 per spec)
        """
        tips = []

        # Rain-related tips
        if any(keyword in text for keyword in ["雨", "雷", "毛毛雨", "阵雨", "暴雨"]):
            tips.append("带伞出行")

        # Snow-related tips
        if any(keyword in text for keyword in ["雪", "雪粒"]):
            tips.append("注意保暖")
            tips.append("路面可能结冰")

        # Temperature tips
        if temp >= 30:
            tips.append("注意防暑")
        elif temp <= 5:
            tips.append("注意保暖")
        elif temp <= 10:
            tips.append("穿外套保暖")

        # Wind tips
        if wind_scale >= 5:
            tips.append("注意防风")

        # Humidity tips
        if humidity >= 80:
            tips.append("湿度较大")

        # Fog/mist tips
        if any(keyword in text for keyword in ["雾", "雾凇"]):
            tips.append("能见度低，小心驾驶")

        # Default tips if no specific conditions
        if not tips:
            tips.append("适宜出行")

        # Max 5 tips per spec
        return tips[:5]

    @property
    def is_healthy(self) -> bool:
        """Check if Weather service is healthy."""
        return self._healthy


# Global Open-Meteo service instance
_openmeteo_service: OpenMeteoService | None = None


def get_openmeteo_service() -> OpenMeteoService:
    """Get or create global Open-Meteo service instance.

    Returns:
        OpenMeteoService instance
    """
    global _openmeteo_service

    if _openmeteo_service is None:
        _openmeteo_service = OpenMeteoService()

    return _openmeteo_service
