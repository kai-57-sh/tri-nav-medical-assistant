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
    assert result.state_patch["consultation"]["summary"] == result.payload["summary"]
    assert isinstance(result.state_patch["consultation"]["symptom_schema"], dict)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("capability", "name", "signal_key", "expected_status", "state_section", "state_keys"),
    [
        (
            TriageCapability(),
            "triage",
            "triage_level",
            "ok",
            "triage",
            [
                "triage_level",
                "triage_reason",
                "recommended_departments",
                "possible_causes",
                "self_care_tips",
                "red_flags",
            ],
        ),
        (
            EvidenceCapability(),
            "evidence",
            "evidence_signal",
            "ok",
            "evidence",
            ["ncbi_query", "evidence_selected"],
        ),
        (
            NavigationCapability(),
            "navigation",
            "navigation_signal",
            "ok",
            "navigation",
            ["navigation_result", "weather_alert"],
        ),
        (ResponseCapability(), "response", "response_signal", "final", "", []),
    ],
)
async def test_v3_capability_stub_payloads_keep_medical_signals(
    capability: object,
    name: str,
    signal_key: str,
    expected_status: str,
    state_section: str,
    state_keys: list[str],
) -> None:
    context = _build_context()

    plan = await capability.plan(context)  # type: ignore[attr-defined]
    result = await capability.run(context, plan)  # type: ignore[attr-defined]

    assert result.name == name
    assert result.success is True
    assert result.payload["status"] == expected_status
    assert signal_key in result.payload
    if state_section:
        assert state_section in result.state_patch
        for key in state_keys:
            assert key in result.state_patch[state_section]
    else:
        assert result.state_patch == {}


@pytest.mark.asyncio
async def test_response_capability_signal_contract_for_run_and_fallback() -> None:
    capability = ResponseCapability()
    context = _build_context()

    run_result = await capability.run(context, await capability.plan(context))
    fallback_result = await capability.fallback(context, reason="response_unavailable")

    assert run_result.payload["status"] in {"final", "need_more_info"}
    assert run_result.payload["response_signal"] == "response_ready"
    assert "response" in run_result.payload
    assert fallback_result.payload["status"] == "error"
    assert fallback_result.payload["response_signal"] == "response_error"
    assert fallback_result.payload["response"] == ""


@pytest.mark.asyncio
async def test_triage_capability_fallback_uses_allowed_enum_value() -> None:
    capability = TriageCapability()
    fallback_result = await capability.fallback(_build_context(), reason="triage_unavailable")

    assert fallback_result.payload["triage_level"] == "SELF_CARE"
    assert fallback_result.payload["triage_signal"] == "triage_degraded"
