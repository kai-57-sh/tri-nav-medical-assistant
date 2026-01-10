"""Weather service for weather-related travel tips.

Uses Qweather API (和风天气) with API KEY authentication.
Official documentation: https://dev.qweather.com/docs/configuration/authentication/
"""
import httpx
from typing import Dict, Any, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential
from ..config.settings import get_settings
from ..utils.logging_config import get_logger
from ..utils.metrics import set_external_service_health

logger = get_logger(__name__)

settings = get_settings()


class WeatherService:
    """Qweather API integration for weather alerts.

    Implements graceful degradation per FR-037, FR-038.
    Non-critical path - failure does not block navigation.

    Authentication: API KEY with X-Qw-Api-Key header
    """

    def __init__(self):
        """Initialize Weather service."""
        # Base API URL (should be like https://devapi.qweather.com/v7)
        self.api_url = settings.weather_api_url.rstrip('/')
        self.api_key = settings.weather_api_key
        self._healthy = True
        self._timeout = settings.weather_timeout

        if self.api_key:
            logger.info("Weather service initialized with API KEY authentication")
        else:
            logger.warning("Weather API not configured - no API key found")

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=3)
    )
    async def _make_request(
        self,
        location: str
    ) -> Optional[Dict[str, Any]]:
        """Make HTTP request to Qweather API with retry.

        Args:
            location: Qweather location ID (e.g., "101010100" for Beijing)
                     or coordinates "lng,lat" (e.g., "116.41,39.92")

        Returns:
            Response JSON or None on failure
        """
        if not self.api_url:
            logger.warning("Weather API URL not configured")
            return None

        if not self.api_key:
            logger.warning("Weather API key not configured")
            return None

        try:
            # Build URL for Qweather API
            # Endpoint: /weather/now
            url = f"{self.api_url}/weather/now"
            params = {"location": location}

            # Use X-Qw-Api-Key header for authentication (official method)
            headers = {
                "X-Qw-Api-Key": self.api_key,
                "Accept-Encoding": "gzip"
            }

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                result = response.json()

                # Check Qweather API response code
                if result.get("code") == "200":
                    self._healthy = True
                    set_external_service_health("weather", True)
                    return result
                else:
                    # Qweather API returned an error
                    error_code = result.get("code")
                    logger.error(f"Qweather API error code: {error_code}")

                    # Handle specific error codes
                    if error_code == "401":
                        logger.error("Authentication failed - check API key")
                    elif error_code == "403":
                        logger.error("Invalid Host - domain whitelist or API type issue")
                        logger.error("Solution: Check console.qweather.com - ensure API type is 'Web API'")

                    self._healthy = False
                    set_external_service_health("weather", False)
                    return None

        except httpx.TimeoutException:
            self._healthy = False
            set_external_service_health("weather", False)
            logger.warning("Weather API timeout")
            return None

        except httpx.HTTPStatusError as e:
            self._healthy = False
            set_external_service_health("weather", False)
            logger.error(f"Weather API HTTP error: {e.response.status_code}")
            if e.response.status_code == 403:
                logger.error("403 Forbidden - likely domain whitelist or API type issue")
                logger.error("Solution: Check console.qweather.com - ensure API type is 'Web API'")
            return None

        except Exception as e:
            self._healthy = False
            set_external_service_health("weather", False)
            logger.error(f"Weather API unexpected error: {e}")
            return None

    async def get_weather(
        self,
        lat: float,
        lng: float
    ) -> Optional[Dict[str, Any]]:
        """Get weather information for location.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Weather alert dict with summary and tips, or None on failure
        """
        # Convert coordinates to Qweather location format: "lng,lat"
        location = f"{lng},{lat}"

        result = await self._make_request(location)

        if not result:
            return None

        try:
            # Parse Qweather API response
            weather_data = self._parse_weather_response(result)

            if weather_data:
                logger.info(
                    f"Weather retrieved",
                    extra={"lat": lat, "lng": lng, "weather": weather_data.get("summary")}
                )

            return weather_data

        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Failed to parse weather data: {e}")
            return None

    def _parse_weather_response(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse Qweather API response into standard format.

        Args:
            result: Raw Qweather API response

        Returns:
            Weather alert dict or None

        Qweather API response format:
        {
            "code": "200",
            "updateTime": "2020-06-30T22:00+08:00",
            "now": {
                "obsTime": "2020-06-30T21:40+08:00",
                "temp": "24",
                "feelsLike": "26",
                "text": "多云",
                "windDir": "东南风",
                "windScale": "1",
                "humidity": "72"
            }
        }
        """
        try:
            # Extract current weather from Qweather format
            now = result.get("now", {})
            if not now:
                logger.warning("No 'now' data in Qweather response")
                return None

            # Extract weather information
            temp = now.get("temp", "0")
            feels_like = now.get("feelsLike", temp)
            text = now.get("text", "未知")
            humidity = int(now.get("humidity", 0))
            wind_dir = now.get("windDir", "")
            wind_scale = now.get("windScale", "0")

            # Generate summary
            summary_parts = [text, f"{temp}°C"]

            # Add feels like if different from temp
            if feels_like != temp:
                summary_parts.append(f"(体感{feels_like}°C)")

            # Add wind info
            if wind_dir:
                summary_parts.append(f"{wind_dir}")
                if wind_scale and wind_scale != "0":
                    summary_parts.append(f"{wind_scale}级")

            # Add humidity if notable
            if humidity >= 80:
                summary_parts.append(f"湿度{humidity}%")

            summary = "，".join(summary_parts)

            # Generate travel tips based on conditions
            tips = self._generate_travel_tips(
                text=text,
                temp=int(temp),
                humidity=humidity,
                wind_scale=int(wind_scale) if wind_scale.isdigit() else 0
            )

            return {
                "summary": summary,
                "tips": tips
            }

        except Exception as e:
            logger.warning(f"Failed to parse Qweather response: {e}")
            return None

    def _generate_travel_tips(
        self,
        text: str,
        temp: int,
        humidity: int,
        wind_scale: int
    ) -> List[str]:
        """Generate travel tips based on Qweather conditions.

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
        if any(keyword in text for keyword in ["雨", "雷", "阵雨", "暴雨", "小雨", "中雨", "大雨"]):
            tips.append("带伞出行")

        # Snow-related tips
        if any(keyword in text for keyword in ["雪", "雨夹雪"]):
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
        if any(keyword in text for keyword in ["雾", "霾", "沙尘"]):
            tips.append("能见度低，小心驾驶")

        # Default tips if no specific conditions
        if not tips:
            tips.append("适宜出行")

        # Max 5 tips per spec
        return tips[:5]

    @property
    def is_healthy(self) -> bool:
        """Check if Weather service is healthy."""
        return self._healthy and self.api_url is not None


# Global Weather service instance
_weather_service: Optional[WeatherService] = None


def get_weather_service() -> WeatherService:
    """Get or create global Weather service instance.

    Returns:
        WeatherService instance
    """
    global _weather_service

    if _weather_service is None:
        _weather_service = WeatherService()

    return _weather_service
