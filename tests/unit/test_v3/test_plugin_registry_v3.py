"""Tests for v3 runtime plugin registry."""

import pytest

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult


class _PrefixPlugin:
    name = "prefix"

    async def before_execute(self, context: ExecutionContext) -> ExecutionContext:
        metadata = dict(context.metadata)
        metadata["plugin_prefix"] = True
        return context.model_copy(update={"metadata": metadata})

    async def after_execute(
        self,
        context: ExecutionContext,
        results: list[CapabilityResult],
    ) -> list[CapabilityResult]:
        _ = context
        return results + [
            CapabilityResult(
                name="plugin:prefix",
                success=True,
                payload={"status": "final", "note": "prefix_applied"},
                provenance={"source": "plugin_prefix"},
            )
        ]


class _BrokenPlugin:
    name = "broken"

    async def before_execute(self, context: ExecutionContext) -> ExecutionContext:
        raise RuntimeError("before boom")

    async def after_execute(
        self,
        context: ExecutionContext,
        results: list[CapabilityResult],
    ) -> list[CapabilityResult]:
        raise RuntimeError("after boom")


@pytest.mark.asyncio
async def test_plugin_registry_applies_before_and_after_hooks() -> None:
    from src.core.plugins.registry import RuntimePluginRegistry

    registry = RuntimePluginRegistry()
    registry.register(_PrefixPlugin())

    context = ExecutionContext(request_id="req-1", session_id="sess-1", text="咳嗽")
    prepared = await registry.apply_before_execute(context)
    assert prepared.metadata["plugin_prefix"] is True

    results = [
        CapabilityResult(
            name="triage",
            success=True,
            payload={"status": "final"},
        )
    ]
    finalized = await registry.apply_after_execute(prepared, results)
    assert len(finalized) == 2
    assert finalized[-1].name == "plugin:prefix"


@pytest.mark.asyncio
async def test_plugin_registry_records_before_errors_in_metadata() -> None:
    from src.core.plugins.registry import RuntimePluginRegistry

    registry = RuntimePluginRegistry()
    registry.register(_BrokenPlugin())
    context = ExecutionContext(request_id="req-2", session_id="sess-2", text="头痛")

    prepared = await registry.apply_before_execute(context)
    errors = prepared.metadata.get("_plugin_errors")
    assert isinstance(errors, list)
    assert len(errors) == 1
    assert "before boom" in str(errors[0])


def test_plugin_registry_rejects_duplicate_names() -> None:
    from src.core.plugins.registry import RuntimePluginRegistry

    registry = RuntimePluginRegistry()
    registry.register(_PrefixPlugin())
    with pytest.raises(ValueError):
        registry.register(_PrefixPlugin())
