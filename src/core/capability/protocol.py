"""Capability protocol for TriNav v2 runtime."""

from typing import Protocol, runtime_checkable

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult, JSONValue


@runtime_checkable
class Capability(Protocol):
    """Contract implemented by all runtime capabilities."""

    name: str
    version: str

    async def plan(self, context: ExecutionContext) -> dict[str, JSONValue]:
        """Build an execution plan for the provided context."""

    async def run(
        self,
        context: ExecutionContext,
        plan: dict[str, JSONValue] | None = None,
    ) -> CapabilityResult:
        """Execute the capability using context and optional plan."""

    async def fallback(
        self,
        context: ExecutionContext,
        reason: str,
        error: Exception | None = None,
    ) -> CapabilityResult:
        """Provide a degraded result when run cannot complete successfully."""
