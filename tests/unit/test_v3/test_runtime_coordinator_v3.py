"""Tests for v3 runtime coordinator orchestration."""

import pytest

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult


class _FakeEngine:
    def __init__(self) -> None:
        self.last_context: ExecutionContext | None = None

    async def run(self, context: ExecutionContext) -> list[CapabilityResult]:
        self.last_context = context
        return [
            CapabilityResult(
                name="triage",
                success=True,
                payload={"status": "final", "response": "ok"},
                provenance={"source": "engine"},
            )
        ]


class _TagPlugin:
    name = "tag"

    async def before_execute(self, context: ExecutionContext) -> ExecutionContext:
        metadata = dict(context.metadata)
        metadata["tagged"] = "yes"
        return context.model_copy(update={"metadata": metadata})

    async def after_execute(
        self,
        context: ExecutionContext,
        results: list[CapabilityResult],
    ) -> list[CapabilityResult]:
        _ = context
        return results + [
            CapabilityResult(
                name="plugin:tag",
                success=True,
                payload={"status": "final", "response": "tagged"},
                provenance={"source": "tag_plugin"},
            )
        ]


@pytest.mark.asyncio
async def test_runtime_coordinator_runs_plugins_around_engine() -> None:
    from src.core.coordinator.runtime_coordinator import RuntimeCoordinator
    from src.core.plugins.registry import RuntimePluginRegistry

    engine = _FakeEngine()
    registry = RuntimePluginRegistry()
    registry.register(_TagPlugin())
    coordinator = RuntimeCoordinator(engine=engine, plugins=registry)

    context = ExecutionContext(request_id="req-1", session_id="sess-1", text="胸闷")
    results = await coordinator.run(context)

    assert engine.last_context is not None
    assert engine.last_context.metadata["tagged"] == "yes"
    assert len(results) == 2
    assert results[0].name == "triage"
    assert results[1].name == "plugin:tag"
