"""Unit tests for TriNav v3 tool registry envelope and provider adapters."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.tools.providers.vision_tool import vision_extract_tool
from src.tools.providers.weather_tool import weather_fetch_tool
from src.tools.registry.tool_registry import ToolRegistry
from src.tools.registry.tool_spec import ToolSpec


@pytest.mark.asyncio
async def test_tool_registry_invoke_returns_envelope() -> None:
    registry = ToolRegistry()

    async def ping_tool(payload: dict[str, object]) -> dict[str, object]:
        return {"pong": payload.get("ping")}

    registry.register(ToolSpec(name="ping", handler=ping_tool, timeout_s=1.0))

    result = await registry.invoke("ping", {"ping": "ok"})

    assert result == {
        "tool": "ping",
        "ok": True,
        "result": {"pong": "ok"},
    }


@pytest.mark.asyncio
async def test_weather_provider_valid_payload_calls_openmeteo_service() -> None:
    mock_service = Mock()
    mock_service.get_weather = AsyncMock(return_value={"condition": "晴", "temp_c": 26.0})

    with patch("src.tools.providers.weather_tool._get_openmeteo_service", return_value=mock_service):
        result = await weather_fetch_tool({"lat": 31.23, "lng": 121.47})

    assert result == {
        "weather": {"condition": "晴", "temp_c": 26.0},
    }
    mock_service.get_weather.assert_awaited_once_with(lat=31.23, lng=121.47)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload, message",
    [
        ({}, "lat"),
        ({"lat": "31.2", "lng": 121.4}, "lat"),
        ({"lat": -91, "lng": 121.4}, "lat"),
        ({"lat": 31.2}, "lng"),
        ({"lat": 31.2, "lng": "121.4"}, "lng"),
        ({"lat": 31.2, "lng": 181}, "lng"),
    ],
)
async def test_weather_provider_invalid_payload_raises_value_error(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        await weather_fetch_tool(payload)


@pytest.mark.asyncio
async def test_vision_provider_valid_payload_calls_llm_service() -> None:
    mock_service = Mock()
    mock_service.extract_visual_features = AsyncMock(return_value={"type": "rash", "confidence": 0.9})

    with patch("src.tools.providers.vision_tool._get_llm_service", return_value=mock_service):
        result = await vision_extract_tool({"image_base64": "abc123", "text": "皮疹"})

    assert result == {"visual": {"type": "rash", "confidence": 0.9}}
    mock_service.extract_visual_features.assert_awaited_once_with(
        image_base64="abc123",
        text="皮疹",
    )


@pytest.mark.asyncio
async def test_vision_provider_accepts_optional_text() -> None:
    mock_service = Mock()
    mock_service.extract_visual_features = AsyncMock(return_value={"type": "unknown"})

    with patch("src.tools.providers.vision_tool._get_llm_service", return_value=mock_service):
        result = await vision_extract_tool({"image_base64": "xyz789"})

    assert result == {"visual": {"type": "unknown"}}
    mock_service.extract_visual_features.assert_awaited_once_with(
        image_base64="xyz789",
        text=None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload, message",
    [
        ({}, "image_base64"),
        ({"image_base64": ""}, "image_base64"),
        ({"image_base64": "   "}, "image_base64"),
        ({"image_base64": 123}, "image_base64"),
        ({"image_base64": "ok", "text": 1}, "text"),
    ],
)
async def test_vision_provider_invalid_payload_raises_value_error(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        await vision_extract_tool(payload)
