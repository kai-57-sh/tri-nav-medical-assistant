"""Unit tests for TriNav v2 query engine runtime orchestration."""

import pytest

from src.core.capability.protocol import Capability
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.query_engine import QueryEngine
from src.core.runtime.types import CapabilityResult, JSONValue


class StubCapability:
    """Simple capability test double with configurable enable flag."""

    def __init__(self, *, name: str, enabled: bool, calls: list[str]) -> None:
        self.name = name
        self.version = "v1"
        self._enabled = enabled
        self._calls = calls

    async def plan(self, context: ExecutionContext) -> dict[str, JSONValue]:
        _ = context
        self._calls.append(f"plan:{self.name}")
        return {"enabled": self._enabled}

    async def run(
        self,
        context: ExecutionContext,
        plan: dict[str, JSONValue] | None = None,
    ) -> CapabilityResult:
        _ = context
        _ = plan
        self._calls.append(f"run:{self.name}")
        return CapabilityResult(name=self.name, success=True, payload={})

    async def fallback(
        self,
        context: ExecutionContext,
        reason: str,
        error: Exception | None = None,
    ) -> CapabilityResult:
        _ = context
        _ = reason
        _ = error
        return CapabilityResult(name=self.name, success=False, payload={})


@pytest.mark.asyncio
async def test_query_engine_runs_enabled_capabilities_in_order_and_emits_events() -> None:
    calls: list[str] = []
    capabilities: list[Capability] = [
        StubCapability(name="triage", enabled=True, calls=calls),
        StubCapability(name="routing", enabled=False, calls=calls),
        StubCapability(name="navigation", enabled=True, calls=calls),
    ]
    ctx = ExecutionContext(request_id="req-1", session_id="sess-1", text="发烧")
    engine = QueryEngine(capabilities)

    results = await engine.run(ctx)
    events = engine.event_bus.dump()

    assert [result.name for result in results] == ["triage", "navigation"]
    assert calls == [
        "plan:triage",
        "run:triage",
        "plan:routing",
        "plan:navigation",
        "run:navigation",
    ]
    assert [event["event_type"] for event in events] == [
        "runtime_started",
        "capability_completed",
        "capability_completed",
        "runtime_finished",
    ]
    assert [event["request_id"] for event in events] == ["req-1", "req-1", "req-1", "req-1"]
    assert [event["session_id"] for event in events] == ["sess-1", "sess-1", "sess-1", "sess-1"]
    assert [
        event["data"]["capability"]
        for event in events
        if event["event_type"] == "capability_completed"
    ] == ["triage", "navigation"]
