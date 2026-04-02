"""Unit tests for legacy triage capability adapter."""

from unittest.mock import AsyncMock

import pytest

from src.capabilities.legacy_triage.capability import LegacyTriageCapability
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import JSONValue


@pytest.mark.asyncio
async def test_legacy_capability_run_invokes_legacy_chain_and_returns_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_payload: dict[str, JSONValue] = {
        "status": "ok",
        "session_id": "sess-1",
        "response": "legacy response",
        "triage_level": "ROUTINE",
    }
    mock_invoke_chain = AsyncMock(return_value=expected_payload)
    monkeypatch.setattr(
        "src.capabilities.legacy_triage.capability.invoke_chain",
        mock_invoke_chain,
    )

    capability = LegacyTriageCapability()
    context = ExecutionContext(
        request_id="req-1",
        session_id="sess-1",
        text="头痛两天",
        image_base64="abc123",
        gps_lat=31.2304,
        gps_lng=121.4737,
    )

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
    mock_invoke_chain.assert_awaited_once_with(
        session_id="sess-1",
        text="头痛两天",
        image_base64="abc123",
        gps_lat=31.2304,
        gps_lng=121.4737,
    )
