"""Unit tests for external API services."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.amap_service import AmapService, get_amap_service
from src.services.ncbi_service import NCBIService, get_ncbi_service
from src.services.weather_service import WeatherService, get_weather_service


@pytest.mark.asyncio
class TestAmapService:
    """Test Amap navigation service."""

    async def test_search_hospitals_three_a_priority(self, mock_amap_response):
        """Test hospital search prioritizes 3A hospitals."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_amap_response
            mock_get.return_value = mock_response

            service = AmapService()
            result = await service.search_hospitals(39.9042, 116.4074, radius_km=10)

            # Should return exactly 3 hospitals
            assert len(result) == 3
            # Should prioritize 3A hospitals
            assert result[0]["is_3a"] is True

    async def test_search_hospitals_no_results(self):
        """Test hospital search handles no results."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": "1", "pois": []}
            mock_get.return_value = mock_response

            service = AmapService()
            result = await service.search_hospitals(39.9042, 116.4074)

            # Should return empty list
            assert result == []

    async def test_get_route_success(self):
        """Test route planning success."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "route": {
                    "paths": [
                        {
                            "distance": "1500",
                            "duration": "300",
                            "steps": []
                        }
                    ]
                }
            }
            mock_get.return_value = mock_response

            service = AmapService()
            result = await service.get_route(39.9042, 116.4074, 39.9139, 116.4170)

            # Should return route plan
            assert result["distance"] == 1500
            assert result["duration"] == 300

    async def test_get_route_failure(self):
        """Test route plan handles API failure gracefully."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = Exception("API timeout")

            service = AmapService()
            result = await service.get_route(39.9042, 116.4074, 39.9139, 116.4170)

            # Should return None on error
            assert result is None


@pytest.mark.asyncio
class TestNCBIService:
    """Test NCBI literature service."""

    async def test_search_pubmed_success(self, mock_ncbi_response):
        """Test PubMed search success."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_ncbi_response
            mock_get.return_value = mock_response

            service = NCBIService()
            result = await service.search_pubmed("arm rash", max_results=20)

            # Should return article IDs
            assert result == ["12345678", "87654321"]

    async def test_search_and_retrieve_success(self):
        """Test search and retrieve with ranking."""
        with patch('httpx.AsyncClient.get') as mock_get:
            # Mock search response
            search_response = MagicMock()
            search_response.json.return_value = {
                "esearchresult": {
                    "count": "3",
                    "idlist": ["111", "222", "333"]
                }
            }

            # Mock summary responses
            summary_response = MagicMock()
            summary_response.json.return_value = {
                "result": {
                    "111": {
                        "title": "Guidelines for dermatitis",
                        "pubdate": "2023",
                        "source": "Dermatology Journal"
                    },
                    "222": {
                        "title": "Review of allergic reactions",
                        "pubdate": "2022",
                        "source": "Allergy Journal"
                    },
                    "333": {
                        "title": "Case report: Rare rash",
                        "pubdate": "2021",
                        "source": "Clinical Cases"
                    }
                }
            }

            mock_get.return_value = [search_response, summary_response]

            service = NCBIService()
            result = await service.search_and_retrieve("dermatitis", max_results=8)

            # Should return ranked articles
            assert len(result) == 3
            # Guidelines should be prioritized
            assert result[0]["type"] == "Guideline"

    async def test_search_and_retrieve_filters_by_date(self, mock_ncbi_response):
        """Test PubMed search filters by last 10 years."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_ncbi_response
            mock_get.return_value = mock_response

            service = NCBIService()
            await service.search_pubmed("arm rash")

            # Should include date filter in query
            call_args = mock_get.call_args
            query = call_args[1]["params"]["term"]
            assert "2015:3000[dpcr]" in query or "202" in query  # 10-year filter

    async def test_search_pubmed_failure(self):
        """Test PubMed search handles failure gracefully."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = Exception("NCBI API error")

            service = NCBIService()
            result = await service.search_pubmed("test query")

            # Should return empty list on error
            assert result == []


@pytest.mark.asyncio
class TestWeatherService:
    """Test weather service."""

    async def test_get_weather_success(self, mock_weather_response):
        """Test weather retrieval success."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_weather_response
            mock_get.return_value = mock_response

            service = WeatherService()
            result = await service.get_weather(39.9042, 116.4074)

            # Should return weather alert with tips
            assert result is not None
            assert "summary" in result
            assert "tips" in result
            assert len(result["tips"]) > 0

    async def test_get_weather_rain(self):
        """Test weather generates tips for rain."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "main": {"temp": 15, "humidity": 80},
                "weather": [{"description": "雨"}],
                "wind": {"speed": 5}
            }
            mock_get.return_value = mock_response

            service = WeatherService()
            result = await service.get_weather(39.9042, 116.4074)

            # Should include umbrella tip
            assert any("伞" in tip or "rain" in tip.lower() for tip in result["tips"])

    async def test_get_weather_cold(self):
        """Test weather generates tips for cold weather."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "main": {"temp": 2, "humidity": 50},
                "weather": [{"description": "晴"}],
                "wind": {"speed": 3}
            }
            mock_get.return_value = mock_response

            service = WeatherService()
            result = await service.get_weather(39.9042, 116.4074)

            # Should include warm clothing tip
            assert any("暖" in tip or "warm" in tip.lower() or "衣" in tip for tip in result["tips"])

    async def test_get_weather_failure(self):
        """Test weather retrieval handles failure gracefully (non-critical)."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = Exception("Weather API error")

            service = WeatherService()
            result = await service.get_weather(39.9042, 116.4074)

            # Should return None on error (non-critical path)
            assert result is None


@pytest.mark.asyncio
async def test_get_amap_service_singleton():
    """Test Amap service singleton."""
    with patch('src.services.amap_service.AmapService') as mock_service_class:
        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance

        service1 = await get_amap_service()
        service2 = await get_amap_service()

        assert service1 is service2


@pytest.mark.asyncio
async def test_get_ncbi_service_singleton():
    """Test NCBI service singleton."""
    with patch('src.services.ncbi_service.NCBIService') as mock_service_class:
        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance

        service1 = get_ncbi_service()
        service2 = get_ncbi_service()

        assert service1 is service2


@pytest.mark.asyncio
async def test_get_weather_service_singleton():
    """Test Weather service singleton."""
    with patch('src.services.weather_service.WeatherService') as mock_service_class:
        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance

        service1 = await get_weather_service()
        service2 = await get_weather_service()

        assert service1 is service2
