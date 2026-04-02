"""Unit tests for platform permission engine and tool gateway."""

from __future__ import annotations

import pytest

from src.core.plugins.registry import RuntimePluginRegistry
from src.platform.policy.permission_engine import PermissionEngine
from src.platform.tooling.gateway import ToolGateway, ToolPermissionDenied


class _RecordingToolRegistry:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def invoke_raw(self, name: str, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append((name, payload))
        return {"ok": True, "tool": name, "payload": payload}


class _FakeGateway:
    async def invoke(
        self,
        tool_name: str,
        payload: dict[str, object],
        context: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return {
            "tool": tool_name,
            "payload": payload,
            "context": context or {},
            "via": "fake_gateway",
        }



def test_permission_engine_denies_sensitive_vision_tool_without_consent() -> None:
    engine = PermissionEngine()

    decision = engine.decide("vision_extract", payload={"image_base64": "abc"}, context={})

    assert decision.allow is False
    assert "consent" in decision.reason.lower()
    assert decision.decision_id



def test_permission_engine_allows_sensitive_tool_when_consent_present() -> None:
    engine = PermissionEngine()

    decision = engine.decide(
        "vision_extract",
        payload={"image_base64": "abc"},
        context={"consent": True},
    )

    assert decision.allow is True
    assert decision.decision_id


@pytest.mark.asyncio
async def test_tool_gateway_denies_before_executing_tool() -> None:
    registry = _RecordingToolRegistry()
    gateway = ToolGateway(tool_registry=registry, permission_engine=PermissionEngine())

    with pytest.raises(ToolPermissionDenied):
        await gateway.invoke("vision_extract", {"image_base64": "abc"}, context={})

    assert registry.calls == []


@pytest.mark.asyncio
async def test_runtime_plugin_registry_accepts_gateway_hook_and_delegates() -> None:
    plugin_registry = RuntimePluginRegistry()
    gateway = _FakeGateway()

    plugin_registry.attach_tool_gateway(gateway)

    assert plugin_registry.tool_gateway is gateway
    result = await plugin_registry.invoke_tool(
        "weather.fetch",
        {"city": "Shanghai"},
        context={"consent": True},
    )
    assert result["via"] == "fake_gateway"
