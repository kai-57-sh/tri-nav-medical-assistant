"""Unit tests for legacy triage capability adapter."""

from unittest.mock import AsyncMock

import pytest

from src.capabilities.legacy_triage.capability import LegacyTriageCapability
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import JSONValue


def _build_context() -> ExecutionContext:
    return ExecutionContext(
        request_id="req-1",
        session_id="sess-1",
        text="头痛两天",
        image_base64="abc123",
        gps_lat=31.2304,
        gps_lng=121.4737,
    )


@pytest.mark.asyncio
async def test_legacy_capability_run_invokes_legacy_chain_and_returns_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    expected_payload: dict[str, JSONValue] = {
        "status": "ok",
        "session_id": "sess-1",
        "response": "legacy response",
        "triage_level": "ROUTINE",
    }
    mock_invoke_chain = AsyncMock(return_value=expected_payload)
    capability = LegacyTriageCapability(invoker=mock_invoke_chain)
    context = _build_context()

    plan = await capability.plan(context)
    result = await capability.run(context, plan)

    assert plan["enabled"] is True
    assert result.success is True
    assert result.name == "legacy_triage"
    assert result.payload == expected_payload
    assert result.provenance == {
        "source": "legacy_graph",
        "graph": "src.chains.triage_chain.invoke_chain",
        "capability_version": "v1",
    }
    assert result.errors == []
    mock_invoke_chain.assert_awaited_once_with(
        session_id="sess-1",
        text="头痛两天",
        image_base64="abc123",
        gps_lat=31.2304,
        gps_lng=121.4737,
    )


@pytest.mark.asyncio
async def test_legacy_capability_run_maps_error_status_and_error_message() -> None:
    expected_payload: dict[str, JSONValue] = {
        "status": "error",
        "session_id": "sess-1",
        "error_message": "legacy execution failed",
    }
    capability = LegacyTriageCapability(invoker=AsyncMock(return_value=expected_payload))

    result = await capability.run(_build_context())

    assert result.success is False
    assert result.payload == expected_payload
    assert result.errors == ["legacy execution failed"]
    assert result.provenance == {
        "source": "legacy_graph",
        "graph": "src.chains.triage_chain.invoke_chain",
        "capability_version": "v1",
    }


@pytest.mark.asyncio
async def test_legacy_capability_run_propagates_invoker_exception() -> None:
    capability = LegacyTriageCapability(invoker=AsyncMock(side_effect=RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        await capability.run(_build_context())


@pytest.mark.asyncio
async def test_legacy_capability_fallback_shape_and_provenance() -> None:
    capability = LegacyTriageCapability()

    result = await capability.fallback(
        _build_context(),
        reason="run_failed: boom",
        error=RuntimeError("boom"),
    )

    assert result.name == "legacy_triage"
    assert result.success is False
    assert result.payload == {}
    assert result.errors == ["run_failed: boom"]
    assert result.provenance == {
        "source": "legacy_graph",
        "graph": "src.chains.triage_chain.invoke_chain",
        "capability_version": "v1",
        "error_type": "RuntimeError",
    }
