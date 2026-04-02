from collections.abc import Mapping, Sequence
from typing import Protocol

from src.core.capability.protocol import Capability
from src.core.runtime.execution_context import ExecutionContext


class PlannerProtocol(Protocol):
    def plan(
        self,
        context: ExecutionContext,
        capabilities_by_name: Mapping[str, Capability],
    ) -> list[Capability]:
        raise NotImplementedError


class StaticPlanner:
    def __init__(self, order: Sequence[str]) -> None:
        self._order = list(order)

    def plan(
        self,
        context: ExecutionContext,
        capabilities_by_name: Mapping[str, Capability],
    ) -> list[Capability]:
        _ = context
        return [capabilities_by_name[name] for name in self._order if name in capabilities_by_name]
