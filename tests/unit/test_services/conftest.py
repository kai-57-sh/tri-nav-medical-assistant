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
        "pois": [
            {
                "id": "B000A7BD6C",
                "name": "北京协和医院",
                "distance": "1500",
                "location": "116.4170,39.9139",
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
        "main": {
            "temp": 15.0,
            "humidity": 65
        },
        "weather": [
            {
                "description": "阴"
            }
        ],
        "wind": {
            "speed": 3.5
        }
    }
