import pytest
from pydantic import ValidationError

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.medical_state import MedicalTurnState
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
    assert context.turn_state.response.response is None


def test_execution_context_turn_state_dump_contains_all_branches() -> None:
    context = ExecutionContext(
        request_id="req-state-2",
        session_id="sess-state-2",
        text="发烧伴随咳嗽",
    )

    turn_state_dump = context.turn_state.model_dump(mode="json")

    assert set(turn_state_dump.keys()) == {
        "consultation",
        "triage",
        "evidence",
        "navigation",
        "response",
    }
    assert turn_state_dump["consultation"] == {"symptom_schema": {}, "summary": None}
    assert turn_state_dump["triage"] == {
        "triage_level": None,
        "triage_reason": None,
        "recommended_departments": [],
        "possible_causes": [],
        "self_care_tips": [],
        "red_flags": [],
    }
    assert turn_state_dump["evidence"] == {"ncbi_query": None, "evidence_selected": []}
    assert turn_state_dump["navigation"] == {"navigation_result": None, "weather_alert": None}
    assert turn_state_dump["response"] == {"status": None, "response": None}


def test_medical_turn_state_rejects_non_json_values() -> None:
    with pytest.raises(ValidationError):
        MedicalTurnState(
            consultation={"symptom_schema": {"raw": object()}},
        )

    with pytest.raises(ValidationError):
        MedicalTurnState(
            evidence={"evidence_selected": [{"record": {"bad": {1, 2}}}]},
        )

    with pytest.raises(ValidationError):
        MedicalTurnState(
            navigation={"navigation_result": {"provider_payload": object()}},
        )

    with pytest.raises(ValidationError):
        MedicalTurnState(
            navigation={"weather_alert": {"raw": object()}},
        )


def test_medical_turn_state_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        MedicalTurnState(
            consultation={"summary": "部位：头部；症状：头痛", "unknown_field": "unexpected"},
        )

    with pytest.raises(ValidationError):
        MedicalTurnState(
            unknown_top_level={"foo": "bar"},
        )


def test_capability_result_accepts_state_patch_for_known_sections() -> None:
    state_patch = {
        "consultation": {"summary": "部位：头部；症状：头痛"},
        "triage": {"triage_level": "ROUTINE", "triage_reason": "症状轻微且稳定"},
        "evidence": {"ncbi_query": "headache tension type"},
        "navigation": {"navigation_result": {"hospital_name": "市人民医院"}},
        "response": {"status": "ready"},
    }

    result = CapabilityResult(
        name="consultation",
        success=True,
        payload={"status": "ok"},
        state_patch=state_patch,
    )

    assert result.state_patch == state_patch


def test_capability_result_rejects_unknown_state_patch_section() -> None:
    with pytest.raises(ValidationError):
        CapabilityResult(
            name="consultation",
            success=True,
            payload={"status": "ok"},
            state_patch={"unknown_section": {"foo": "bar"}},
        )


def test_capability_result_rejects_unknown_field_inside_patch_section() -> None:
    with pytest.raises(ValidationError):
        CapabilityResult(
            name="consultation",
            success=True,
            payload={"status": "ok"},
            state_patch={
                "consultation": {
                    "summary": "部位：头部；症状：头痛",
                    "unknown_field": "unexpected",
                }
            },
        )
