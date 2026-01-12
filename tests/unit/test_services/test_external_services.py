"""Unit tests for external API services."""
from datetime import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.amap_service import AmapService, get_amap_service
from src.services.ncbi_service import NCBIService, get_ncbi_service
from src.services.weather_service_openmeteo import OpenMeteoService, get_openmeteo_service


def _build_response(payload):
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    return response


def _mock_async_client(responses):
    mock_client = AsyncMock()
    if isinstance(responses, (list, tuple)):
        mock_client.get = AsyncMock(side_effect=list(responses))
    else:
        mock_client.get = AsyncMock(return_value=responses)
    mock_async_client = AsyncMock()
    mock_async_client.__aenter__.return_value = mock_client
    mock_async_client.__aexit__.return_value = None
    return mock_async_client, mock_client


@pytest.mark.asyncio
class TestAmapService:
    """Test Amap navigation service."""

    async def test_search_hospitals_three_a_priority(self, mock_amap_response):
        """Test hospital search prioritizes 3A hospitals."""
        mock_response = _build_response(mock_amap_response)
        mock_async_client, _ = _mock_async_client(mock_response)

        with patch('httpx.AsyncClient', return_value=mock_async_client):
            service = AmapService()
            service.api_key = "test-key"
            result = await service.search_hospitals(39.9042, 116.4074, radius_km=10)

            # Should return exactly 3 hospitals
            assert len(result) == 3
            # Should prioritize 3A hospitals
            assert result[0]["is_3a"] is True

    async def test_search_hospitals_no_results(self):
        """Test hospital search handles no results."""
        mock_response = _build_response({"status": "1", "info": "OK", "pois": []})
        mock_async_client, _ = _mock_async_client(mock_response)

        with patch('httpx.AsyncClient', return_value=mock_async_client):
            service = AmapService()
            service.api_key = "test-key"
            result = await service.search_hospitals(39.9042, 116.4074)

            # Should return empty list
            assert result == []

    async def test_get_route_success(self):
        """Test route planning success."""
        mock_response = _build_response({
            "status": "1",
            "info": "OK",
            "route": {
                "paths": [
                    {
                        "distance": "1500",
                        "duration": "300",
                        "steps": []
                    }
                ]
            }
        })
        mock_async_client, _ = _mock_async_client(mock_response)

        with patch('httpx.AsyncClient', return_value=mock_async_client):
            service = AmapService()
            service.api_key = "test-key"
            result = await service.get_route(39.9042, 116.4074, 39.9139, 116.4170)

            # Should return route plan
            assert result["distance_km"] == 1.5
            assert result["eta_min"] == 5
            assert "分钟" in result["summary"]

    async def test_get_route_failure(self):
        """Test route plan handles API failure gracefully."""
        with patch.object(AmapService, "_make_request", AsyncMock(return_value=None)):
            service = AmapService()
            result = await service.get_route(39.9042, 116.4074, 39.9139, 116.4170)

        # Should return None on error
        assert result is None


@pytest.mark.asyncio
class TestNCBIService:
    """Test NCBI literature service."""

    async def test_search_pubmed_success(self, mock_ncbi_response):
        """Test PubMed search success."""
        mock_response = _build_response(mock_ncbi_response)
        mock_async_client, _ = _mock_async_client(mock_response)

        with patch('httpx.AsyncClient', return_value=mock_async_client):
            service = NCBIService()
            result = await service.search_pubmed("arm rash", max_results=20)

            # Should return article IDs
            assert result == ["12345678", "87654321"]

    async def test_search_and_retrieve_success(self):
        """Test search and retrieve with ranking."""
        # Mock search response
        search_response = _build_response({
            "esearchresult": {
                "count": "3",
                "idlist": ["111", "222", "333"]
            }
        })

        # Mock summary responses
        summary_response = _build_response({
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
        })

        mock_async_client, _ = _mock_async_client([search_response, summary_response])

        with patch('httpx.AsyncClient', return_value=mock_async_client):
            service = NCBIService()
            result = await service.search_and_retrieve("dermatitis", max_results=8)

        # Should return ranked articles
        assert len(result) == 3
        # Guidelines should be prioritized
        assert result[0]["type"] == "Guideline"

    async def test_search_and_retrieve_filters_by_date(self, mock_ncbi_response):
        """Test PubMed search filters by last 10 years."""
        mock_response = _build_response(mock_ncbi_response)
        mock_async_client, mock_client = _mock_async_client(mock_response)

        with patch('httpx.AsyncClient', return_value=mock_async_client):
            service = NCBIService()
            await service.search_pubmed("arm rash")

            # Should include date filter in query
            call_args = mock_client.get.call_args
            query = call_args[1]["params"]["term"]
            min_year = datetime.now().year - 10
            assert f"{min_year}:3000[dpcr]" in query

    async def test_search_pubmed_failure(self):
        """Test PubMed search handles failure gracefully."""
        with patch.object(NCBIService, "_make_request", AsyncMock(return_value=None)):
            service = NCBIService()
            result = await service.search_pubmed("test query")

        # Should return empty list on error
        assert result == []


@pytest.mark.asyncio
class TestWeatherService:
    """Test weather service."""

    async def test_get_weather_success(self, mock_weather_response):
        """Test weather retrieval success."""
        mock_response = _build_response(mock_weather_response)
        mock_async_client, _ = _mock_async_client(mock_response)

        with patch('httpx.AsyncClient', return_value=mock_async_client):
            service = OpenMeteoService()
            result = await service.get_weather(39.9042, 116.4074)

        # Should return weather alert with tips
        assert result is not None
        assert "summary" in result
        assert "tips" in result
        assert len(result["tips"]) > 0

    async def test_get_weather_rain(self):
        """Test weather generates tips for rain."""
        mock_response = _build_response({
            "current": {
                "temperature_2m": 15,
                "apparent_temperature": 15,
                "relative_humidity_2m": 80,
                "weather_code": 61,
                "wind_speed_10m": 5,
                "wind_direction_10m": 180
            }
        })
        mock_async_client, _ = _mock_async_client(mock_response)

        with patch('httpx.AsyncClient', return_value=mock_async_client):
            service = OpenMeteoService()
            result = await service.get_weather(39.9042, 116.4074)

        # Should include umbrella tip
        assert any("伞" in tip for tip in result["tips"])

    async def test_get_weather_cold(self):
        """Test weather generates tips for cold weather."""
        mock_response = _build_response({
            "current": {
                "temperature_2m": 2,
                "apparent_temperature": 1,
                "relative_humidity_2m": 50,
                "weather_code": 0,
                "wind_speed_10m": 3,
                "wind_direction_10m": 90
            }
        })
        mock_async_client, _ = _mock_async_client(mock_response)

        with patch('httpx.AsyncClient', return_value=mock_async_client):
            service = OpenMeteoService()
            result = await service.get_weather(39.9042, 116.4074)

        # Should include warm clothing tip
        assert any("暖" in tip or "衣" in tip for tip in result["tips"])

    async def test_get_weather_failure(self):
        """Test weather retrieval handles failure gracefully (non-critical)."""
        with patch.object(OpenMeteoService, "_make_request", AsyncMock(return_value=None)):
            service = OpenMeteoService()
            result = await service.get_weather(39.9042, 116.4074)

        # Should return None on error (non-critical path)
        assert result is None


@pytest.mark.asyncio
async def test_get_amap_service_singleton():
    """Test Amap service singleton."""
    with patch('src.services.amap_service.AmapService') as mock_service_class:
        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance

        with patch('src.services.amap_service._amap_service', None):
            service1 = get_amap_service()
            service2 = get_amap_service()

        assert service1 is service2


@pytest.mark.asyncio
async def test_get_ncbi_service_singleton():
    """Test NCBI service singleton."""
    with patch('src.services.ncbi_service.NCBIService') as mock_service_class:
        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance

        with patch('src.services.ncbi_service._ncbi_service', None):
            service1 = get_ncbi_service()
            service2 = get_ncbi_service()

        assert service1 is service2


@pytest.mark.asyncio
async def test_get_weather_service_singleton():
    """Test Open-Meteo service singleton."""
    with patch('src.services.weather_service_openmeteo.OpenMeteoService') as mock_service_class:
        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance

        with patch('src.services.weather_service_openmeteo._openmeteo_service', None):
            service1 = get_openmeteo_service()
            service2 = get_openmeteo_service()

        assert service1 is service2
