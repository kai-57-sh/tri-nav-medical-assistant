"""Plugin protocol for runtime request/response interception."""

from typing import Protocol, runtime_checkable

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult


@runtime_checkable
class RuntimePlugin(Protocol):
    """Contract for runtime plugins around query-engine execution."""

    name: str

    async def before_execute(self, context: ExecutionContext) -> ExecutionContext:
        """Mutate or enrich execution context before runtime execution."""

    async def after_execute(
        self,
        context: ExecutionContext,
        results: list[CapabilityResult],
    ) -> list[CapabilityResult]:
        """Mutate or enrich capability results after runtime execution."""
