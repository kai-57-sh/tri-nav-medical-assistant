"""Unit tests for TriNav v2 tool registry and provider adapters."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.tools.providers.amap_tool import amap_search_tool
from src.tools.providers.ncbi_tool import ncbi_search_tool
from src.tools.registry.tool_registry import (
    ToolInvocationError,
    ToolNotFoundError,
    ToolRegistry,
    ToolTimeoutError,
)
from src.tools.registry.tool_spec import ToolSpec


@pytest.mark.asyncio
async def test_register_and_invoke_async_tool() -> None:
    registry = ToolRegistry()

    async def ping_tool(payload: dict[str, object]) -> dict[str, object]:
        return {"pong": payload.get("ping")}

    registry.register(ToolSpec(name="ping", handler=ping_tool, timeout_s=1.0))

    result = await registry.invoke("ping", {"ping": "ok"})

    assert result == {"pong": "ok"}


def test_register_duplicate_name_raises_value_error() -> None:
    registry = ToolRegistry()

    async def first(payload: dict[str, object]) -> dict[str, object]:
        _ = payload
        return {"ok": True}

    async def second(payload: dict[str, object]) -> dict[str, object]:
        _ = payload
        return {"ok": True}

    registry.register(ToolSpec(name="dup", handler=first, timeout_s=1.0))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(ToolSpec(name="dup", handler=second, timeout_s=1.0))


@pytest.mark.asyncio
async def test_invoke_unknown_tool_raises_not_found_error() -> None:
    registry = ToolRegistry()

    with pytest.raises(ToolNotFoundError, match="missing"):
        await registry.invoke("missing", {})


@pytest.mark.asyncio
async def test_invoke_timeout_raises_custom_timeout_error() -> None:
    registry = ToolRegistry()

    async def slow_tool(payload: dict[str, object]) -> dict[str, object]:
        _ = payload
        await asyncio.sleep(0.05)
        return {"done": True}

    registry.register(ToolSpec(name="slow", handler=slow_tool, timeout_s=0.01))

    with pytest.raises(ToolTimeoutError, match="slow") as exc_info:
        await registry.invoke("slow", {})

    assert exc_info.value.tool_name == "slow"
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_invoke_handler_failure_raises_custom_invocation_error() -> None:
    registry = ToolRegistry()

    async def bad_tool(payload: dict[str, object]) -> dict[str, object]:
        _ = payload
        raise RuntimeError("boom")

    registry.register(ToolSpec(name="bad", handler=bad_tool, timeout_s=1.0))

    with pytest.raises(ToolInvocationError, match="bad") as exc_info:
        await registry.invoke("bad", {})

    assert exc_info.value.tool_name == "bad"
    assert isinstance(exc_info.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_invoke_cancelled_error_is_not_wrapped() -> None:
    registry = ToolRegistry()

    async def cancelled_tool(payload: dict[str, object]) -> dict[str, object]:
        _ = payload
        raise asyncio.CancelledError()

    registry.register(ToolSpec(name="cancelled", handler=cancelled_tool, timeout_s=1.0))

    with pytest.raises(asyncio.CancelledError):
        await registry.invoke("cancelled", {})


@pytest.mark.asyncio
async def test_ncbi_adapter_valid_payload_calls_service() -> None:
    mock_service = Mock()
    mock_service.search_and_retrieve = AsyncMock(return_value=[{"pmid": "1"}])

    with patch("src.tools.providers.ncbi_tool.get_ncbi_service", return_value=mock_service):
        result = await ncbi_search_tool({"query": "dermatitis", "max_results": 5})

    assert result == [{"pmid": "1"}]
    mock_service.search_and_retrieve.assert_awaited_once_with(
        query="dermatitis",
        max_results=5,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload, message",
    [
        ({}, "query"),
        ({"query": ""}, "query"),
        ({"query": "   "}, "query"),
        ({"query": 123}, "query"),
        ({"query": "ok", "max_results": 0}, "max_results"),
        ({"query": "ok", "max_results": -1}, "max_results"),
        ({"query": "ok", "max_results": 51}, "max_results"),
        ({"query": "ok", "max_results": "3"}, "max_results"),
        ({"query": "ok", "max_results": True}, "max_results"),
    ],
)
async def test_ncbi_adapter_invalid_payload_raises_value_error(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        await ncbi_search_tool(payload)


@pytest.mark.asyncio
async def test_amap_adapter_valid_payload_calls_service() -> None:
    mock_service = Mock()
    mock_service.search_hospitals = AsyncMock(return_value=[{"name": "h1"}])

    with patch("src.tools.providers.amap_tool.get_amap_service", return_value=mock_service):
        result = await amap_search_tool({"lat": 39.9, "lng": 116.4, "radius_km": 8.0})

    assert result == [{"name": "h1"}]
    mock_service.search_hospitals.assert_awaited_once_with(
        lat=39.9,
        lng=116.4,
        radius_km=8.0,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload, message",
    [
        ({}, "lat"),
        ({"lat": "39.9", "lng": 116.4}, "lat"),
        ({"lat": True, "lng": 116.4}, "lat"),
        ({"lat": -91, "lng": 116.4}, "lat"),
        ({"lat": 39.9}, "lng"),
        ({"lat": 39.9, "lng": "116.4"}, "lng"),
        ({"lat": 39.9, "lng": 181}, "lng"),
        ({"lat": 39.9, "lng": 116.4, "radius_km": "8"}, "radius_km"),
        ({"lat": 39.9, "lng": 116.4, "radius_km": 0}, "radius_km"),
        ({"lat": 39.9, "lng": 116.4, "radius_km": -1}, "radius_km"),
        ({"lat": 39.9, "lng": 116.4, "radius_km": False}, "radius_km"),
    ],
)
async def test_amap_adapter_invalid_payload_raises_value_error(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        await amap_search_tool(payload)
