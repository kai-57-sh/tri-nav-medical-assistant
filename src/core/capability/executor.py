"""Capability execution helpers for TriNav v2 runtime."""

from typing import Protocol

from src.core.capability.protocol import Capability
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult


class ExecutorProtocol(Protocol):
    """Executor contract used by the runtime query engine."""

    async def execute(self, context: ExecutionContext) -> list[CapabilityResult]:
        """Execute runtime capabilities for a single request context."""


class SequentialExecutor:
    """Execute capabilities sequentially in the provided order."""

    def __init__(self, capabilities: list[Capability]) -> None:
        self._capabilities = list(capabilities)

    async def execute(self, context: ExecutionContext) -> list[CapabilityResult]:
        """Run enabled capabilities in order and collect results."""

        results: list[CapabilityResult] = []
        for capability in self._capabilities:
            try:
                plan = await capability.plan(context)
                enabled = plan.get("enabled", True)
                if not isinstance(enabled, bool):
                    raise TypeError("Plan field 'enabled' must be bool.")
            except Exception as exc:
                results.append(
                    await capability.fallback(
                        context,
                        reason=f"plan_failed: {exc}",
                        error=exc,
                    )
                )
                continue

            if enabled is False:
                continue

            try:
                results.append(await capability.run(context, plan))
            except Exception as exc:
                results.append(
                    await capability.fallback(
                        context,
                        reason=f"run_failed: {exc}",
                        error=exc,
                    )
                )
        return results
