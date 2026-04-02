"""Unit tests for TriNav v2 capability registry."""

import pytest

from src.core.capability.protocol import Capability
from src.core.capability.registry import CapabilityRegistry
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult, JSONValue


class StubCapability:
    """Minimal capability implementation for registry tests."""

    def __init__(self, *, name: str, version: str = "v1") -> None:
        self.name = name
        self.version = version

    async def plan(self, context: ExecutionContext) -> dict[str, JSONValue]:
        return {"request_id": context.request_id}

    async def run(
        self,
        context: ExecutionContext,
        plan: dict[str, JSONValue] | None = None,
    ) -> CapabilityResult:
        _ = context
        _ = plan
        return CapabilityResult(name=self.name, success=True, payload={})

    async def fallback(
        self,
        context: ExecutionContext,
        reason: str,
        error: Exception | None = None,
    ) -> CapabilityResult:
        _ = context
        _ = error
        return CapabilityResult(name=self.name, success=False, payload={}, errors=[reason])


def test_register_and_get_capability() -> None:
    registry = CapabilityRegistry()
    capability: Capability = StubCapability(name="triage")

    registry.register(capability)

    assert registry.get("triage") is capability
    assert registry.list_names() == ["triage"]


def test_register_duplicate_name_raises_value_error() -> None:
    registry = CapabilityRegistry()
    first: Capability = StubCapability(name="navigator", version="v1")
    duplicate: Capability = StubCapability(name="navigator", version="v2")

    registry.register(first)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(duplicate)
