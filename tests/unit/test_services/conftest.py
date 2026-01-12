"""Service-specific test configuration."""
import pytest
import redis.asyncio as redis
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_redis_pool():
    """Mock Redis connection pool."""
    mock = MagicMock()
    mock.get_connection = AsyncMock()
    return mock


@pytest.fixture
def sample_session_state():
    """Sample session state for testing."""
    return {
        "session_id": "test-123",
        "turn_count": 1,
        "symptom_schema": {
            "body_part": "手臂",
            "symptoms": ["红疹"],
            "duration": "2天"
        }
    }


@pytest.fixture
def sample_cache_result():
    """Sample cached external API result."""
    return {
        "hospitals": [
            {"rank": 1, "name": "Test Hospital", "is_3a": True}
        ],
        "route_plan": None
    }


@pytest.fixture
def mock_ai_response():
    """Sample LLM API response."""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"triage_level": "ROUTINE"}'
                }
            }
        ],
        "usage": {
            "total_tokens": 100
        }
    }


@pytest.fixture
def mock_amap_response():
    """Sample Amap API response."""
    return {
        "status": "1",
        "info": "OK",
        "pois": [
            {
                "id": "B000A7BD6C",
                "name": "北京协和医院",
                "distance": "1500",
                "location": "116.4170,39.9139",
                "typecode": "090100"
            },
            {
                "id": "B000A7BD6D",
                "name": "北京人民医院",
                "distance": "2500",
                "location": "116.4074,39.9042",
                "typecode": "090100"
            },
            {
                "id": "B000A7BD6E",
                "name": "东城区社区医院",
                "distance": "800",
                "location": "116.4100,39.9100",
                "typecode": "090100"
            }
        ]
    }


@pytest.fixture
def mock_ncbi_response():
    """Sample NCBI API response."""
    return {
        "esearchresult": {
            "count": "2",
            "idlist": ["12345678", "87654321"]
        }
    }


@pytest.fixture
def mock_weather_response():
    """Sample weather API response."""
    return {
        "current": {
            "temperature_2m": 15.0,
            "apparent_temperature": 15.0,
            "relative_humidity_2m": 65,
            "weather_code": 3,
            "wind_speed_10m": 3.5,
            "wind_direction_10m": 180
        }
    }
