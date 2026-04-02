"""Unit tests for v3 capability stubs."""

import pytest

from src.capabilities import (
    ConsultationCapability,
    EvidenceCapability,
    NavigationCapability,
    ResponseCapability,
    TriageCapability,
)
from src.core.runtime.execution_context import ExecutionContext


def _build_context() -> ExecutionContext:
    return ExecutionContext(
        request_id="req-v3-1",
        session_id="sess-v3-1",
        text="持续头痛并伴有轻微发热",
        metadata={"age": 32},
    )


@pytest.mark.asyncio
async def test_consultation_capability_returns_status_payload() -> None:
    capability = ConsultationCapability()

    result = await capability.run(_build_context(), await capability.plan(_build_context()))

    assert result.name == "consultation"
    assert result.success is True
    assert result.payload["status"] == "ok"
    assert "summary" in result.payload


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("capability", "name", "signal_key"),
    [
        (TriageCapability(), "triage", "triage_level"),
        (EvidenceCapability(), "evidence", "evidence_signal"),
        (NavigationCapability(), "navigation", "navigation_signal"),
        (ResponseCapability(), "response", "response_text"),
    ],
)
async def test_v3_capability_stub_payloads_keep_medical_signals(
    capability: object, name: str, signal_key: str
) -> None:
    context = _build_context()

    plan = await capability.plan(context)  # type: ignore[attr-defined]
    result = await capability.run(context, plan)  # type: ignore[attr-defined]

    assert result.name == name
    assert result.success is True
    assert result.payload["status"] == "ok"
    assert signal_key in result.payload

