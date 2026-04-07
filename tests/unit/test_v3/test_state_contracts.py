from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult


def test_execution_context_starts_with_empty_turn_state() -> None:
    context = ExecutionContext(
        request_id="req-state-1",
        session_id="sess-state-1",
        text="持续头痛两天",
    )

    assert context.turn_state.consultation.summary is None
    assert context.turn_state.triage.triage_level is None
    assert context.turn_state.evidence.evidence_selected == []
    assert context.turn_state.navigation.navigation_result is None


def test_capability_result_accepts_state_patch() -> None:
    result = CapabilityResult(
        name="consultation",
        success=True,
        payload={"status": "ok"},
        state_patch={"consultation": {"summary": "部位：头部；症状：头痛"}},
    )

    assert result.state_patch["consultation"]["summary"] == "部位：头部；症状：头痛"
