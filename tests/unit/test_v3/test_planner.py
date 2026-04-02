from dataclasses import dataclass

from src.core.capability.planner import StaticPlanner
from src.core.runtime.execution_context import ExecutionContext


@dataclass
class StubCap:
    name: str
    version: str = "v1"


def test_static_planner_uses_declared_order() -> None:
    planner = StaticPlanner(order=["consultation", "triage"])
    caps = {"triage": StubCap("triage"), "consultation": StubCap("consultation")}
    context = ExecutionContext(request_id="r1", session_id="s1", text="rash")
    planned = planner.plan(context, caps)
    assert [cap.name for cap in planned] == ["consultation", "triage"]
