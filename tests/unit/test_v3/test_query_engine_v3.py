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
