"""Capability execution helpers for TriNav v2 runtime."""

from src.core.capability.protocol import Capability
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult


class SequentialExecutor:
    """Execute capabilities sequentially in the provided order."""

    def __init__(self, capabilities: list[Capability]) -> None:
        self._capabilities = list(capabilities)

    async def execute(self, context: ExecutionContext) -> list[CapabilityResult]:
        """Run enabled capabilities in order and collect results."""

        results: list[CapabilityResult] = []
        for capability in self._capabilities:
            plan = await capability.plan(context)
            if plan.get("enabled") is False:
                continue
            results.append(await capability.run(context, plan))
        return results
