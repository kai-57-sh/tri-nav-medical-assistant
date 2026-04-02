"""Tests for built-in runtime plugins."""

import pytest

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult


@pytest.mark.asyncio
async def test_trace_context_plugin_marks_context_metadata() -> None:
    from src.core.plugins.builtin import TraceContextPlugin

    plugin = TraceContextPlugin()
    context = ExecutionContext(
        request_id="req-1",
        session_id="sess-1",
        text="发热两天",
        metadata={"trace_id": "trace-1"},
    )

    updated = await plugin.before_execute(context)
    assert updated.metadata["trace_id"] == "trace-1"
    assert updated.metadata["trace_plugin_enabled"] is True


@pytest.mark.asyncio
async def test_medical_disclaimer_plugin_appends_once_for_final_payload() -> None:
    from src.core.plugins.builtin import MedicalDisclaimerPlugin

    plugin = MedicalDisclaimerPlugin()
    context = ExecutionContext(request_id="req-2", session_id="sess-2", text="头痛")
    results = [
        CapabilityResult(
            name="response",
            success=True,
            payload={"status": "final", "response": "建议补液休息"},
            provenance={"source": "response_capability"},
        )
    ]

    updated = await plugin.after_execute(context, results)
    response = str(updated[0].payload["response"])
    assert "不替代专业医疗诊断" in response

    updated_again = await plugin.after_execute(context, updated)
    response_again = str(updated_again[0].payload["response"])
    assert response_again.count("不替代专业医疗诊断") == 1


def test_create_builtin_plugins_respects_switches() -> None:
    from src.core.plugins.builtin import create_builtin_plugins

    plugins = create_builtin_plugins(trace_enabled=True, medical_footer_enabled=False)
    assert [plugin.name for plugin in plugins] == ["trace_context"]
