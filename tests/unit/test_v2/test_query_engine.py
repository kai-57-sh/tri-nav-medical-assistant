"""Unit tests for TriNav v2 query engine runtime orchestration."""

import pytest

from src.core.capability.protocol import Capability
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.query_engine import QueryEngine
from src.core.runtime.types import CapabilityResult, JSONValue


class StubCapability:
    """Simple capability test double with configurable enable flag."""

    def __init__(
        self,
        *,
        name: str,
        enabled: JSONValue = True,
        calls: list[str],
        plan_error: Exception | None = None,
        run_error: Exception | None = None,
    ) -> None:
        self.name = name
        self.version = "v1"
        self._enabled = enabled
        self._calls = calls
        self._plan_error = plan_error
        self._run_error = run_error

    async def plan(self, context: ExecutionContext) -> dict[str, JSONValue]:
        _ = context
        self._calls.append(f"plan:{self.name}")
        if self._plan_error is not None:
            raise self._plan_error
        return {"enabled": self._enabled}

    async def run(
        self,
        context: ExecutionContext,
        plan: dict[str, JSONValue] | None = None,
    ) -> CapabilityResult:
        _ = context
        _ = plan
        self._calls.append(f"run:{self.name}")
        if self._run_error is not None:
            raise self._run_error
        return CapabilityResult(name=self.name, success=True, payload={})

    async def fallback(
        self,
        context: ExecutionContext,
        reason: str,
        error: Exception | None = None,
    ) -> CapabilityResult:
        _ = context
        self._calls.append(f"fallback:{self.name}")
        return CapabilityResult(
            name=self.name,
            success=False,
            payload={"fallback": True},
            errors=[reason],
            provenance={"error_type": None if error is None else type(error).__name__},
        )


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


@pytest.mark.asyncio
async def test_query_engine_uses_fallback_for_plan_and_run_failures_and_continues() -> None:
    calls: list[str] = []
    capabilities: list[Capability] = [
        StubCapability(name="triage", calls=calls, plan_error=ValueError("bad-plan")),
        StubCapability(name="routing", calls=calls, run_error=RuntimeError("bad-run")),
        StubCapability(name="navigation", calls=calls),
    ]
    ctx = ExecutionContext(request_id="req-2", session_id="sess-2", text="咳嗽")
    engine = QueryEngine(capabilities)

    results = await engine.run(ctx)
    events = engine.event_bus.dump()

    assert [result.name for result in results] == ["triage", "routing", "navigation"]
    assert [result.success for result in results] == [False, False, True]
    assert "plan" in results[0].errors[0]
    assert "run" in results[1].errors[0]
    assert calls == [
        "plan:triage",
        "fallback:triage",
        "plan:routing",
        "run:routing",
        "fallback:routing",
        "plan:navigation",
        "run:navigation",
    ]
    assert [event["event_type"] for event in events] == [
        "runtime_started",
        "capability_completed",
        "capability_completed",
        "capability_completed",
        "runtime_finished",
    ]


@pytest.mark.asyncio
async def test_query_engine_handles_malformed_enabled_via_fallback() -> None:
    calls: list[str] = []
    capabilities: list[Capability] = [
        StubCapability(name="triage", calls=calls, enabled="yes"),
        StubCapability(name="navigation", calls=calls),
    ]
    ctx = ExecutionContext(request_id="req-3", session_id="sess-3", text="胸闷")
    engine = QueryEngine(capabilities)

    results = await engine.run(ctx)
    events = engine.event_bus.dump()

    assert [result.name for result in results] == ["triage", "navigation"]
    assert results[0].success is False
    assert "enabled" in results[0].errors[0]
    assert calls == [
        "plan:triage",
        "fallback:triage",
        "plan:navigation",
        "run:navigation",
    ]
    assert [event["event_type"] for event in events] == [
        "runtime_started",
        "capability_completed",
        "capability_completed",
        "runtime_finished",
    ]


class ExplodingExecutor:
    async def execute(self, context: ExecutionContext) -> list[CapabilityResult]:
        _ = context
        raise RuntimeError("executor boom")


@pytest.mark.asyncio
async def test_query_engine_emits_runtime_failed_and_runtime_finished_when_executor_raises() -> None:
    ctx = ExecutionContext(request_id="req-4", session_id="sess-4", text="头痛")
    engine = QueryEngine(capabilities=[], executor=ExplodingExecutor())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="executor boom"):
        await engine.run(ctx)

    events = engine.event_bus.dump()
    assert [event["event_type"] for event in events] == [
        "runtime_started",
        "runtime_failed",
        "runtime_finished",
    ]
    failure_event = events[1]
    assert failure_event["data"]["error_type"] == "RuntimeError"
    assert "error_message" in failure_event["data"]
    assert "error_stage" in failure_event["data"]
