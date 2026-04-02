from dataclasses import dataclass

from src.core.capability.planner import StaticPlanner
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult, JSONValue


@dataclass
class StubCap:
    name: str
    version: str = "v1"

    async def plan(self, context: ExecutionContext) -> dict[str, JSONValue]:
        _ = context
        return {}

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
        _ = reason
        _ = error
        return CapabilityResult(name=self.name, success=False, payload={}, errors=["fallback"])


def test_static_planner_uses_declared_order() -> None:
    planner = StaticPlanner(order=["consultation", "triage"])
    caps = {"triage": StubCap("triage"), "consultation": StubCap("consultation")}
    context = ExecutionContext(request_id="r1", session_id="s1", text="rash")
    planned = planner.plan(context, caps)
    assert [cap.name for cap in planned] == ["consultation", "triage"]


def test_static_planner_ignores_unknown_capability_names() -> None:
    planner = StaticPlanner(order=["consultation", "unknown", "triage"])
    caps = {"triage": StubCap("triage"), "consultation": StubCap("consultation")}
    context = ExecutionContext(request_id="r1", session_id="s1", text="rash")
    planned = planner.plan(context, caps)
    assert [cap.name for cap in planned] == ["consultation", "triage"]


def test_static_planner_dedupes_duplicate_capability_names() -> None:
    planner = StaticPlanner(order=["triage", "triage", "consultation", "triage"])
    caps = {"triage": StubCap("triage"), "consultation": StubCap("consultation")}
    context = ExecutionContext(request_id="r1", session_id="s1", text="rash")
    planned = planner.plan(context, caps)
    assert [cap.name for cap in planned] == ["triage", "consultation"]
