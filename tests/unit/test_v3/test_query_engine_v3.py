import pytest

from src.core.capability.planner import StaticPlanner
from src.core.runtime.budget_manager import BudgetManager
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.query_engine import QueryEngine
from src.core.runtime.stop_reason import StopReason
from src.core.runtime.types import CapabilityResult, JSONValue


class StubCapability:
    def __init__(
        self,
        *,
        name: str,
        calls: list[str],
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.version = "v1"
        self._calls = calls
        self._enabled = enabled

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
        self._calls.append(f"fallback:{self.name}")
        return CapabilityResult(name=self.name, success=False, payload={}, errors=["fallback"])


class ExplodingPlanner:
    def plan(
        self,
        context: ExecutionContext,
        capabilities_by_name: dict[str, StubCapability],
    ) -> list[StubCapability]:
        _ = context
        _ = capabilities_by_name
        raise RuntimeError("planner boom")


class AsyncEventStore:
    def __init__(self) -> None:
        self.events: list[dict[str, JSONValue]] = []

    async def append(self, session_id: str, event: dict[str, JSONValue]) -> None:
        self.events.append({"session_id": session_id, **event})


@pytest.mark.asyncio
async def test_query_engine_uses_planner_for_default_execution_path() -> None:
    calls: list[str] = []
    capabilities = [
        StubCapability(name="triage", calls=calls),
        StubCapability(name="routing", calls=calls),
        StubCapability(name="navigation", calls=calls),
    ]
    planner = StaticPlanner(order=["navigation", "triage"])
    ctx = ExecutionContext(request_id="req-v3-1", session_id="sess-v3-1", text="fever")
    engine = QueryEngine(capabilities, planner=planner)

    results = await engine.run(ctx)

    assert [result.name for result in results] == ["navigation", "triage"]
    assert calls == [
        "plan:navigation",
        "run:navigation",
        "plan:triage",
        "run:triage",
    ]


@pytest.mark.asyncio
async def test_query_engine_emits_runtime_stopped_when_budget_is_already_exceeded() -> None:
    calls: list[str] = []
    timeline = iter([0.0, 1.0])  # seconds
    budget = BudgetManager(max_tool_calls=10, max_elapsed_ms=500, now_fn=lambda: next(timeline))
    capability = StubCapability(name="triage", calls=calls)
    ctx = ExecutionContext(request_id="req-v3-2", session_id="sess-v3-2", text="cough")
    engine = QueryEngine([capability], budget=budget)

    results = await engine.run(ctx)
    events = engine.event_bus.dump()

    assert results == []
    assert calls == []
    assert [event["event_type"] for event in events] == [
        "runtime_started",
        "runtime_stopped",
        "runtime_finished",
    ]
    assert events[1]["data"]["reason"] == StopReason.TIME_BUDGET_EXCEEDED.value
    assert events[2]["data"]["success"] is False
    assert events[2]["data"]["capabilities_executed"] == 0


@pytest.mark.asyncio
async def test_query_engine_emits_failure_lifecycle_when_planner_raises() -> None:
    capability = StubCapability(name="triage", calls=[])
    planner = ExplodingPlanner()
    ctx = ExecutionContext(request_id="req-v3-3", session_id="sess-v3-3", text="fever")
    engine = QueryEngine([capability], planner=planner)

    with pytest.raises(RuntimeError, match="planner boom"):
        await engine.run(ctx)

    events = engine.event_bus.dump()
    assert [event["event_type"] for event in events] == [
        "runtime_started",
        "runtime_failed",
        "runtime_finished",
    ]
    assert events[1]["data"]["error_type"] == "RuntimeError"
    assert events[1]["data"]["error_message"] == "planner boom"
    assert events[1]["data"]["error_stage"] == "planner"
    assert events[2]["data"]["success"] is False
    assert events[2]["data"]["capabilities_executed"] == 0


@pytest.mark.asyncio
async def test_query_engine_awaits_async_event_store_append() -> None:
    calls: list[str] = []
    capability = StubCapability(name="triage", calls=calls)
    store = AsyncEventStore()
    ctx = ExecutionContext(request_id="req-v3-4", session_id="sess-v3-4", text="fever")
    engine = QueryEngine([capability], event_store=store)

    await engine.run(ctx)

    assert [event["event_type"] for event in store.events] == [
        "runtime_started",
        "capability_completed",
        "runtime_finished",
    ]
    assert all(event["session_id"] == "sess-v3-4" for event in store.events)
