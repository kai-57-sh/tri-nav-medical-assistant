"""Unit tests for TriNav v2 tool registry."""

import asyncio

import pytest

from src.tools.registry.tool_registry import ToolRegistry
from src.tools.registry.tool_spec import ToolSpec


@pytest.mark.asyncio
async def test_register_and_invoke_async_tool() -> None:
    registry = ToolRegistry()

    async def ping_tool(payload: dict[str, object]) -> dict[str, object]:
        return {"pong": payload.get("ping")}

    registry.register(ToolSpec(name="ping", handler=ping_tool, timeout_s=1.0))

    result = await registry.invoke("ping", {"ping": "ok"})

    assert result == {"pong": "ok"}


@pytest.mark.asyncio
async def test_invoke_timeout_raises_timeout_error() -> None:
    registry = ToolRegistry()

    async def slow_tool(payload: dict[str, object]) -> dict[str, object]:
        _ = payload
        await asyncio.sleep(0.05)
        return {"done": True}

    registry.register(ToolSpec(name="slow", handler=slow_tool, timeout_s=0.01))

    with pytest.raises(asyncio.TimeoutError):
        await registry.invoke("slow", {})


@pytest.mark.asyncio
async def test_invoke_uses_asyncio_wait_for(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = ToolRegistry()

    async def ping_tool(payload: dict[str, object]) -> dict[str, object]:
        return {"pong": payload.get("ping")}

    registry.register(ToolSpec(name="ping", handler=ping_tool, timeout_s=2.5))

    captured_timeout: float | None = None
    wait_for_called = False
    real_wait_for = asyncio.wait_for

    def tracking_wait_for(awaitable: object, timeout: float | None) -> object:
        nonlocal captured_timeout, wait_for_called
        wait_for_called = True
        captured_timeout = timeout
        return real_wait_for(awaitable, timeout)

    monkeypatch.setattr("src.tools.registry.tool_registry.asyncio.wait_for", tracking_wait_for)

    result = await registry.invoke("ping", {"ping": "ok"})

    assert result == {"pong": "ok"}
    assert wait_for_called is True
    assert captured_timeout == 2.5
