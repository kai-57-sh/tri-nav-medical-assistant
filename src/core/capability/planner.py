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

        planned: list[Capability] = []
        seen: set[str] = set()
        for name in self._order:
            if name in seen or name not in capabilities_by_name:
                continue
            seen.add(name)
            planned.append(capabilities_by_name[name])
        return planned
