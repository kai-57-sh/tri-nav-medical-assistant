"""Runtime coordinator that composes plugins and query engine."""

from __future__ import annotations

from typing import Protocol

from src.core.plugins.registry import RuntimePluginRegistry
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult


class RuntimeEngineProtocol(Protocol):
    """Minimal runtime engine contract used by RuntimeCoordinator."""

    async def run(self, context: ExecutionContext) -> list[CapabilityResult]:
        """Execute runtime with one normalized context."""


class RuntimeCoordinator:
    """Compose plugin interception around runtime engine execution."""

    def __init__(
        self,
        *,
        engine: RuntimeEngineProtocol,
        plugins: RuntimePluginRegistry | None = None,
    ) -> None:
        self._engine = engine
        self._plugins = plugins or RuntimePluginRegistry()

    async def run(self, context: ExecutionContext) -> list[CapabilityResult]:
        """Run before hooks, engine, then after hooks in order."""

        prepared = await self._plugins.apply_before_execute(context)
        results = await self._engine.run(prepared)
        return await self._plugins.apply_after_execute(prepared, results)
