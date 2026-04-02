"""Unit tests for session_loader node."""
from unittest.mock import AsyncMock, patch

import pytest

from src.chains.nodes.session_loader import session_load


@pytest.mark.asyncio
async def test_session_loader_new_session(minimal_state, mock_redis_service):
    """Test session loader creates new session when none exists."""
    state = minimal_state.copy()

    with patch("src.chains.nodes.session_loader.get_redis_service", return_value=mock_redis_service):
        result = await session_load(state)

    # Should initialize new session
    assert result["turn_count"] == 1
    assert result.get("symptom_schema") is None
    mock_redis_service.load_session.assert_called_once()


@pytest.mark.asyncio
async def test_session_loader_existing_session(minimal_state, mock_redis_service):
    """Test session loader restores existing session."""
    state = minimal_state.copy()
    state["session_id"] = "existing-session-456"

    # Mock existing session data
    mock_redis_service.load_session.return_value = {
        "turn_count": 1,
        "symptom_schema": {
            "body_part": "胸部",
            "symptoms": ["疼痛"],
            "duration": "1天"
        }
    }

    with patch("src.chains.nodes.session_loader.get_redis_service", return_value=mock_redis_service):
        result = await session_load(state)

    # Should restore session with incremented turn count
    assert result["turn_count"] == 2
    assert result["symptom_schema"]["body_part"] == "胸部"
    mock_redis_service.load_session.assert_called_once_with("existing-session-456")


@pytest.mark.asyncio
async def test_session_loader_redis_unhealthy(minimal_state):
    """Test session loader handles Redis failure gracefully."""
    state = minimal_state.copy()

    # Mock unhealthy Redis
    mock_redis = AsyncMock()
    mock_redis.is_healthy = False
    mock_redis.load_session = AsyncMock(return_value=None)

    with patch("src.chains.nodes.session_loader.get_redis_service", return_value=mock_redis):
        result = await session_load(state)

    # Should initialize new session when Redis is unhealthy
    assert result["turn_count"] == 1
    assert result.get("symptom_schema") is None


@pytest.mark.asyncio
async def test_session_loader_redis_exception(minimal_state):
    """Test session loader handles Redis exception gracefully."""
    state = minimal_state.copy()

    # Mock Redis that raises exception
    mock_redis = AsyncMock()
    mock_redis.is_healthy = True
    mock_redis.load_session = AsyncMock(side_effect=Exception("Redis connection failed"))

    with patch("src.chains.nodes.session_loader.get_redis_service", return_value=mock_redis):
        result = await session_load(state)

    # Should initialize new session when Redis fails
    assert result["turn_count"] == 1
