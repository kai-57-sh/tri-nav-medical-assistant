"""Tests for v3 real medical capabilities (non-stub pipeline)."""

import os

import pytest

os.environ.setdefault("QWEN_API_KEY", "test-key")

from src.capabilities import (
    ConsultationCapability,
    EvidenceCapability,
    NavigationCapability,
    ResponseCapability,
    TriageCapability,
)
from src.core.runtime.execution_context import ExecutionContext

SAFE_BUSY_MESSAGE = "服务繁忙，请尽快线下就医"


def _build_context(*, text: str = "持续头痛并伴有轻微发热") -> ExecutionContext:
    return ExecutionContext(
        request_id="req-v3-real-1",
        session_id="sess-v3-real-1",
        text=text,
        metadata={"age": 32},
    )


@pytest.mark.asyncio
async def test_triage_emergency_like_text_not_constant_routine() -> None:
    capability = TriageCapability()
    context = _build_context(text="胸痛并呼吸困难，伴有明显出汗")

    result = await capability.run(context, await capability.plan(context))

    assert result.success is True
    assert result.payload["status"] == "ok"
    assert result.payload["triage_level"] in {"EMERGENCY", "URGENT"}
    assert result.payload["triage_level"] != "ROUTINE"


@pytest.mark.asyncio
async def test_consultation_and_triage_emit_state_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_clinical_extractor(state):
        return {
            **state,
            "symptom_schema": {
                "body_part": "头部",
                "symptoms": ["头痛"],
                "duration": "2天",
                "severity": "轻微",
                "accompanying_symptoms": [],
                "onset": None,
            },
        }

    async def fake_red_flag_detector(state):
        return {
            **state,
            "rule_triage_level": None,
            "red_flags_hit": [],
            "recommended_departments": [],
            "triage_reason": "",
        }

    async def fake_triage_classifier(state):
        return {
            **state,
            "llm_triage_level": "ROUTINE",
            "llm_triage_reason": "症状相对稳定，建议常规就诊",
            "llm_recommended_departments": ["内科"],
            "llm_possible_causes": ["上呼吸道感染（疑似）"],
            "llm_self_care_tips": ["补水休息"],
            "llm_red_flags": [],
        }

    async def fake_triage_merger(state):
        return {
            **state,
            "triage_level": "ROUTINE",
            "triage_source": "llm",
            "recommended_departments": ["内科"],
            "possible_causes": ["上呼吸道感染（疑似）"],
            "self_care_tips": ["补水休息"],
            "red_flags": [],
            "triage_reason": "症状相对稳定，建议常规就诊",
        }

    monkeypatch.setattr(
        "src.capabilities.consultation.capability.clinical_extractor",
        fake_clinical_extractor,
    )
    monkeypatch.setattr("src.capabilities.triage.capability.red_flag_detector", fake_red_flag_detector)
    monkeypatch.setattr("src.capabilities.triage.capability.triage_classifier", fake_triage_classifier)
    monkeypatch.setattr("src.capabilities.triage.capability.triage_merger", fake_triage_merger)

    context = _build_context()

    consultation = ConsultationCapability()
    consultation_result = await consultation.run(context, await consultation.plan(context))
    assert consultation_result.state_patch["consultation"]["summary"] != ""
    assert consultation_result.state_patch["consultation"]["symptom_schema"] != {}

    triage = TriageCapability()
    triage_result = await triage.run(context, await triage.plan(context))
    assert triage_result.state_patch["triage"]["triage_level"] in {
        "EMERGENCY",
        "URGENT",
        "ROUTINE",
        "SELF_CARE",
    }
    assert triage_result.state_patch["triage"]["triage_reason"] != ""
    assert triage_result.state_patch["triage"]["recommended_departments"] != []


@pytest.mark.asyncio
async def test_capabilities_are_no_longer_marked_as_v3_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_clinical_extractor(state):
        return {
            **state,
            "symptom_schema": {
                "body_part": "头部",
                "symptoms": ["头痛"],
                "duration": "2天",
                "severity": "轻微",
                "accompanying_symptoms": [],
            },
        }

    async def fake_red_flag_detector(state):
        return {
            **state,
            "rule_triage_level": None,
            "red_flags_hit": [],
            "recommended_departments": [],
            "triage_reason": "",
        }

    async def fake_triage_classifier(state):
        return {
            **state,
            "llm_triage_level": "ROUTINE",
            "llm_triage_reason": "症状相对稳定，建议常规就诊",
            "llm_recommended_departments": ["内科"],
            "llm_possible_causes": ["上呼吸道感染（疑似）"],
            "llm_self_care_tips": ["补水休息"],
            "llm_red_flags": [],
        }

    async def fake_triage_merger(state):
        return {
            **state,
            "triage_level": "ROUTINE",
            "triage_source": "llm",
            "recommended_departments": ["内科"],
            "possible_causes": ["上呼吸道感染（疑似）"],
            "self_care_tips": ["补水休息"],
            "red_flags": [],
            "triage_reason": "症状相对稳定，建议常规就诊",
        }

    async def fake_ncbi_query_builder(state):
        return {**state, "ncbi_query": '"head" AND "headache" AND 2016:3000[dpcr]'}

    async def fake_ncbi_retriever_tool(state):
        return {
            **state,
            "evidence_selected": [
                {"pmid": "1", "title": "Mock Article", "year": "2024", "type": "Review"}
            ],
        }

    async def fake_navigator(state):
        return {
            **state,
            "navigation_result": {
                "radius_km": 10,
                "hospitals": [{"rank": 1, "name": "示例医院", "reason": "距离较近"}],
                "route_plan": None,
            },
        }

    async def fake_weather_fetcher(state):
        return {
            **state,
            "weather_alert": {
                "condition": "晴",
                "temp_c": 26,
                "humidity": 40,
                "wind_speed_kmh": 8,
                "tip": "注意补水",
            },
        }

    async def fake_reasoning_verifier(state):
        return {
            **state,
            "final_response": "建议常规门诊就诊，并观察症状变化。",
            "status": "final",
        }

    monkeypatch.setattr(
        "src.capabilities.consultation.capability.clinical_extractor",
        fake_clinical_extractor,
    )
    monkeypatch.setattr("src.capabilities.triage.capability.red_flag_detector", fake_red_flag_detector)
    monkeypatch.setattr("src.capabilities.triage.capability.triage_classifier", fake_triage_classifier)
    monkeypatch.setattr("src.capabilities.triage.capability.triage_merger", fake_triage_merger)
    monkeypatch.setattr("src.capabilities.evidence.capability.ncbi_query_builder", fake_ncbi_query_builder)
    monkeypatch.setattr("src.capabilities.evidence.capability.ncbi_retriever_tool", fake_ncbi_retriever_tool)
    monkeypatch.setattr("src.capabilities.navigation.capability.navigator", fake_navigator)
    monkeypatch.setattr("src.capabilities.navigation.capability.weather_fetcher", fake_weather_fetcher)
    monkeypatch.setattr("src.capabilities.response.capability.reasoning_verifier", fake_reasoning_verifier)

    context = _build_context()
    capabilities = [
        ConsultationCapability(),
        TriageCapability(),
        EvidenceCapability(),
        NavigationCapability(),
        ResponseCapability(),
    ]

    for capability in capabilities:
        result = await capability.run(context, await capability.plan(context))
        assert result.success is True
        assert result.provenance.get("source") != "v3_stub"


@pytest.mark.asyncio
async def test_evidence_external_tools_enabled_by_default_and_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_queries: list[str] = []

    async def fake_ncbi_query_builder(state):
        return {**state, "ncbi_query": '"head" AND "headache" AND 2016:3000[dpcr]'}

    async def fake_ncbi_retriever_tool(state):
        query = state.get("ncbi_query", "")
        captured_queries.append(str(query))
        if query:
            return {
                **state,
                "evidence_selected": [{"pmid": "1", "title": "Mock", "year": "2024"}],
            }
        return {**state, "evidence_selected": []}

    monkeypatch.setattr("src.capabilities.evidence.capability.ncbi_query_builder", fake_ncbi_query_builder)
    monkeypatch.setattr("src.capabilities.evidence.capability.ncbi_retriever_tool", fake_ncbi_retriever_tool)

    capability = EvidenceCapability()

    enabled_context = _build_context()
    enabled_result = await capability.run(enabled_context, await capability.plan(enabled_context))
    assert enabled_result.payload["evidence_signal"] == "evidence_ready"

    disabled_context = ExecutionContext(
        request_id="req-v3-real-2",
        session_id="sess-v3-real-2",
        text="持续头痛并伴有轻微发热",
        metadata={"enable_external_tools": False},
    )
    disabled_result = await capability.run(disabled_context, await capability.plan(disabled_context))
    assert disabled_result.payload["evidence_signal"] == "evidence_pending"

    assert captured_queries[0] != ""
    assert captured_queries[1] == ""


@pytest.mark.asyncio
async def test_navigation_and_response_consume_metadata_triage_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_navigation_triage: dict[str, str] = {}

    async def fake_navigator(state):
        captured_navigation_triage["value"] = str(state.get("triage_level"))
        return {**state, "navigation_result": None}

    async def fake_weather_fetcher(state):
        return {**state, "weather_alert": None}

    async def fake_reasoning_verifier(state):
        return {
            **state,
            "status": "final",
            "final_response": f"triage={state.get('triage_level')}",
        }

    monkeypatch.setattr("src.capabilities.navigation.capability.navigator", fake_navigator)
    monkeypatch.setattr("src.capabilities.navigation.capability.weather_fetcher", fake_weather_fetcher)
    monkeypatch.setattr("src.capabilities.response.capability.reasoning_verifier", fake_reasoning_verifier)

    context = ExecutionContext(
        request_id="req-v3-real-3",
        session_id="sess-v3-real-3",
        text="症状轻微，正在好转",
        metadata={"triage_level": "SELF_CARE"},
    )

    navigation = NavigationCapability()
    navigation_result = await navigation.run(context, await navigation.plan(context))
    assert captured_navigation_triage["value"] == "SELF_CARE"
    assert navigation_result.payload["navigation_signal"] in {"routing_prepared", "routing_unavailable"}

    response = ResponseCapability()
    response_result = await response.run(context, await response.plan(context))
    assert "triage=SELF_CARE" in str(response_result.payload["response"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("capability", "expected_status"),
    [
        (ConsultationCapability(), "degraded"),
        (TriageCapability(), "degraded"),
        (EvidenceCapability(), "degraded"),
        (NavigationCapability(), "degraded"),
        (ResponseCapability(), "error"),
    ],
)
async def test_capability_fallbacks_expose_safe_busy_message(
    capability: object,
    expected_status: str,
) -> None:
    context = _build_context()

    result = await capability.fallback(context, reason="simulated_failure")  # type: ignore[attr-defined]

    assert result.success is False
    assert result.payload["status"] == expected_status
    assert SAFE_BUSY_MESSAGE in str(result.payload.get("message", ""))
