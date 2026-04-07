"""Tests for assistant v3 invoke route."""

import os
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

os.environ.setdefault("QWEN_API_KEY", "test-key")

from src.core.runtime.types import CapabilityResult
from src.interfaces.api.assistant_v2 import AssistantV2InvokePayload
from src.interfaces.api.assistant_v3 import invoke_assistant_v3
from src.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _mock_runtime_run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: CapabilityResult | None = None,
    results: list[CapabilityResult] | None = None,
    run_error: Exception | None = None,
) -> None:
    async def fake_run(self, context):  # type: ignore[no-untyped-def]
        _ = self
        _ = context
        if run_error is not None:
            raise run_error
        if results is not None:
            return results
        assert result is not None
        return [result]

    def fake_dump(self):  # type: ignore[no-untyped-def]
        _ = self
        success = None if result is None else result.success
        return [
            {
                "event_type": "runtime_finished",
                "request_id": "req-test-v3",
                "session_id": "sess-test-v3",
                "data": {"capabilities_executed": 1, "success": success},
            }
        ]

    monkeypatch.setattr("src.core.runtime.query_engine.QueryEngine.run", fake_run)
    monkeypatch.setattr("src.core.runtime.event_bus.EventBus.dump", fake_dump)


def test_assistant_v3_invoke_success_contract_shape(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V3 invoke should expose v2-parity schema and success semantics."""

    _mock_runtime_run(
        monkeypatch,
        result=CapabilityResult(
            name="legacy_triage",
            success=True,
            payload={
                "status": "final",
                "session_id": "sess-test-v3",
                "response": "mocked response",
            },
            provenance={"source": "legacy_graph"},
            errors=[],
        ),
    )

    response = client.post(
        "/assistant/v3/invoke",
        json={
            "request_id": "req-test-v3",
            "session_id": "sess-test-v3",
            "trace_id": "trace-test-v3",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) >= {
        "status",
        "session_id",
        "trace_id",
        "response",
        "safety",
        "runtime_events",
        "provenance",
        "trace",
    }
    assert data["status"] == "final"
    assert data["session_id"] == "sess-test-v3"
    assert data["trace_id"] == "trace-test-v3"
    assert data["response"] == "mocked response"
    assert data["safety"]["risk_level"] == "low"
    assert data["safety"]["matched_rules"] == []
    assert isinstance(data["runtime_events"], list)
    assert isinstance(data["provenance"], dict)
    assert isinstance(data["trace"], dict)


def test_assistant_v3_invoke_error_status_maps_to_503(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V3 invoke should keep v2 parity: normalized error status returns 503."""

    _mock_runtime_run(
        monkeypatch,
        result=CapabilityResult(
            name="legacy_triage",
            success=True,
            payload={
                "status": "not_allowed",
                "session_id": "sess-test-v3",
                "response": "mocked response",
            },
            provenance={"source": "legacy_graph"},
            errors=[],
        ),
    )

    response = client.post(
        "/assistant/v3/invoke",
        json={
            "request_id": "req-test-v3",
            "session_id": "sess-test-v3",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert "error_message" in data
    assert isinstance(data["trace_id"], str)
    UUID(data["trace_id"])


def test_assistant_v3_invoke_uses_task_coordinator_when_enabled(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When v3 task coordinator switch is on, v3 invoke should use coordinator path."""

    monkeypatch.setattr(
        "src.interfaces.api.assistant_v2.get_settings",
        lambda: SimpleNamespace(
            v3_task_coordinator_enabled=True,
            v3_builtin_plugins_enabled=False,
            v3_plugin_trace_enabled=True,
            v3_plugin_medical_footer_enabled=True,
        ),
    )

    response = client.post(
        "/assistant/v3/invoke",
        json={
            "request_id": "req-v3-task-1",
            "session_id": "sess-v3-task-1",
            "trace_id": "trace-v3-task-1",
            "text": "持续咳嗽两周",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "final"
    assert data["session_id"] == "sess-v3-task-1"
    assert data["trace_id"] == "trace-v3-task-1"
    assert data["triage_level"] == "ROUTINE"
    assert data["recommended_departments"] == ["全科", "内科"]
    assert len(data["possible_causes"]) >= 1
    assert isinstance(data["red_flags"], list)
    assert data["disclaimer"] == "本建议仅供参考，不替代专业医疗诊断。"
    assert data["trace"]["path"] == "v3_task_coordinator"
    assert "已记录症状" in data["response"]


def test_assistant_v3_task_coordinator_applies_medical_guard(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V3 task coordinator output should be post-processed by medical guard."""

    monkeypatch.setattr(
        "src.interfaces.api.assistant_v2.get_settings",
        lambda: SimpleNamespace(
            v3_task_coordinator_enabled=True,
            v3_builtin_plugins_enabled=False,
            v3_plugin_trace_enabled=True,
            v3_plugin_medical_footer_enabled=True,
        ),
    )

    async def fake_response_run(self, context, plan=None):  # type: ignore[no-untyped-def]
        _ = (self, context, plan)
        return CapabilityResult(
            name="response",
            success=True,
            payload={
                "status": "final",
                "response": "你已经确诊肺炎，先别去医院。",
            },
            provenance={"source": "test"},
            errors=[],
        )

    monkeypatch.setattr(
        "src.capabilities.response.capability.ResponseCapability.run",
        fake_response_run,
    )

    response = client.post(
        "/assistant/v3/invoke",
        json={
            "request_id": "req-v3-guard-1",
            "session_id": "sess-v3-guard-1",
            "trace_id": "trace-v3-guard-1",
            "text": "胸痛并伴呼吸困难",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "final"
    assert "确诊" not in data["response"]
    assert "别去医院" not in data["response"]
    assert "疑似" in data["response"]
    assert "建议尽快就医" in data["response"]
    assert data["safety"]["risk_level"] == "high"
    assert "rewrite.confirmed_diagnosis" in data["safety"]["matched_rules"]


def test_assistant_v3_task_coordinator_propagates_triage_metadata_to_followup_tasks(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Coordinator should pass triage outputs to follow-up capabilities via context metadata."""

    monkeypatch.setattr(
        "src.interfaces.api.assistant_v2.get_settings",
        lambda: SimpleNamespace(
            v3_task_coordinator_enabled=True,
            v3_builtin_plugins_enabled=False,
            v3_plugin_trace_enabled=True,
            v3_plugin_medical_footer_enabled=True,
        ),
    )

    captured: dict[str, str] = {}

    async def fake_consultation_run(self, context, plan=None):  # type: ignore[no-untyped-def]
        _ = (self, context, plan)
        return CapabilityResult(
            name="consultation",
            success=True,
            payload={"status": "ok", "summary": "mock summary"},
            provenance={"source": "test"},
            errors=[],
        )

    async def fake_triage_run(self, context, plan=None):  # type: ignore[no-untyped-def]
        _ = (self, context, plan)
        return CapabilityResult(
            name="triage",
            success=True,
            payload={
                "status": "ok",
                "triage_level": "SELF_CARE",
                "triage_reason": "症状偏轻，建议居家观察",
                "recommended_departments": ["全科"],
                "red_flags": ["若症状加重请及时就医"],
            },
            provenance={"source": "test"},
            errors=[],
        )

    async def fake_evidence_run(self, context, plan=None):  # type: ignore[no-untyped-def]
        _ = (self, context, plan)
        return CapabilityResult(
            name="evidence",
            success=True,
            payload={"status": "ok", "evidence_signal": "evidence_pending", "evidence_selected": []},
            provenance={"source": "test"},
            errors=[],
        )

    async def fake_navigation_run(self, context, plan=None):  # type: ignore[no-untyped-def]
        _ = (self, plan)
        captured["navigation_triage_level"] = str(context.metadata.get("triage_level"))
        return CapabilityResult(
            name="navigation",
            success=True,
            payload={"status": "ok", "navigation_signal": "routing_unavailable"},
            provenance={"source": "test"},
            errors=[],
        )

    async def fake_response_run(self, context, plan=None):  # type: ignore[no-untyped-def]
        _ = (self, plan)
        captured["response_triage_level"] = str(context.metadata.get("triage_level"))
        return CapabilityResult(
            name="response",
            success=True,
            payload={
                "status": "final",
                "response": f"triage={context.metadata.get('triage_level')}",
            },
            provenance={"source": "test"},
            errors=[],
        )

    monkeypatch.setattr(
        "src.capabilities.consultation.capability.ConsultationCapability.run",
        fake_consultation_run,
    )
    monkeypatch.setattr(
        "src.capabilities.triage.capability.TriageCapability.run",
        fake_triage_run,
    )
    monkeypatch.setattr(
        "src.capabilities.evidence.capability.EvidenceCapability.run",
        fake_evidence_run,
    )
    monkeypatch.setattr(
        "src.capabilities.navigation.capability.NavigationCapability.run",
        fake_navigation_run,
    )
    monkeypatch.setattr(
        "src.capabilities.response.capability.ResponseCapability.run",
        fake_response_run,
    )

    response = client.post(
        "/assistant/v3/invoke",
        json={
            "request_id": "req-v3-prop-1",
            "session_id": "sess-v3-prop-1",
            "trace_id": "trace-v3-prop-1",
            "text": "症状轻微，已好转",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert captured["navigation_triage_level"] == "SELF_CARE"
    assert captured["response_triage_level"] == "SELF_CARE"
    data = response.json()
    assert data["triage_level"] == "SELF_CARE"
    assert "triage=SELF_CARE" in data["response"]


def test_assistant_v3_task_coordinator_response_fields_prefer_turn_state(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V3 response body fields should be sourced from canonical turn_state when available."""

    monkeypatch.setattr(
        "src.interfaces.api.assistant_v2.get_settings",
        lambda: SimpleNamespace(
            v3_task_coordinator_enabled=True,
            v3_builtin_plugins_enabled=False,
            v3_plugin_trace_enabled=True,
            v3_plugin_medical_footer_enabled=True,
        ),
    )

    async def fake_consultation_run(self, context, plan=None):  # type: ignore[no-untyped-def]
        _ = (self, context, plan)
        return CapabilityResult(
            name="consultation",
            success=True,
            payload={"status": "ok", "summary": "mock summary"},
            provenance={"source": "test"},
            errors=[],
        )

    async def fake_triage_run(self, context, plan=None):  # type: ignore[no-untyped-def]
        _ = (self, context, plan)
        return CapabilityResult(
            name="triage",
            success=True,
            payload={
                "status": "ok",
                "triage_level": "ROUTINE",
                "triage_reason": "payload says routine",
                "recommended_departments": ["全科"],
                "possible_causes": ["普通不适"],
                "red_flags": ["payload red flag"],
            },
            provenance={"source": "test"},
            errors=[],
            state_patch={
                "triage": {
                    "triage_level": "EMERGENCY",
                    "triage_reason": "state says emergency",
                    "recommended_departments": ["急诊"],
                    "possible_causes": ["蛛网膜下腔出血（疑似）"],
                    "red_flags": ["突发剧烈头痛伴意识改变"],
                }
            },
        )

    async def fake_evidence_run(self, context, plan=None):  # type: ignore[no-untyped-def]
        _ = (self, context, plan)
        return CapabilityResult(
            name="evidence",
            success=True,
            payload={"status": "ok", "evidence_signal": "evidence_pending", "evidence_selected": []},
            provenance={"source": "test"},
            errors=[],
        )

    async def fake_navigation_run(self, context, plan=None):  # type: ignore[no-untyped-def]
        _ = (self, context, plan)
        return CapabilityResult(
            name="navigation",
            success=True,
            payload={"status": "ok", "navigation_signal": "routing_unavailable"},
            provenance={"source": "test"},
            errors=[],
        )

    async def fake_response_run(self, context, plan=None):  # type: ignore[no-untyped-def]
        _ = (self, context, plan)
        return CapabilityResult(
            name="response",
            success=True,
            payload={"status": "final", "response": "state-aware response"},
            provenance={"source": "test"},
            errors=[],
        )

    monkeypatch.setattr(
        "src.capabilities.consultation.capability.ConsultationCapability.run",
        fake_consultation_run,
    )
    monkeypatch.setattr(
        "src.capabilities.triage.capability.TriageCapability.run",
        fake_triage_run,
    )
    monkeypatch.setattr(
        "src.capabilities.evidence.capability.EvidenceCapability.run",
        fake_evidence_run,
    )
    monkeypatch.setattr(
        "src.capabilities.navigation.capability.NavigationCapability.run",
        fake_navigation_run,
    )
    monkeypatch.setattr(
        "src.capabilities.response.capability.ResponseCapability.run",
        fake_response_run,
    )

    response = client.post(
        "/assistant/v3/invoke",
        json={
            "request_id": "req-v3-turn-state-1",
            "session_id": "sess-v3-turn-state-1",
            "trace_id": "trace-v3-turn-state-1",
            "text": "轻微头痛",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["triage_level"] == "EMERGENCY"
    assert data["recommended_departments"] == ["急诊"]
    assert data["possible_causes"] == ["蛛网膜下腔出血（疑似）"]
    assert data["red_flags"] == ["突发剧烈头痛伴意识改变"]


@pytest.mark.asyncio
async def test_assistant_v3_sets_runtime_mode_and_calls_v2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V3 invoke should only inject runtime_mode and delegate to v2 invoke."""

    observed_payload: AssistantV2InvokePayload | None = None
    calls = 0
    delegated_response = JSONResponse({"status": "final", "response": "delegated"})

    async def fake_invoke(payload: AssistantV2InvokePayload) -> JSONResponse:
        nonlocal calls
        nonlocal observed_payload
        calls += 1
        observed_payload = payload
        return delegated_response

    monkeypatch.setattr("src.interfaces.api.assistant_v3.invoke_assistant_v2", fake_invoke)

    original_payload = AssistantV2InvokePayload(
        request_id="req-adapter-v3",
        session_id="sess-adapter-v3",
        trace_id="trace-adapter-v3",
        text="咳嗽",
        metadata={"runtime_mode": "legacy", "foo": "bar"},
    )

    response = await invoke_assistant_v3(original_payload)

    assert calls == 1
    assert observed_payload is not None
    assert observed_payload is not original_payload
    assert observed_payload.metadata["runtime_mode"] == "v3"
    assert observed_payload.metadata["foo"] == "bar"
    assert original_payload.metadata["runtime_mode"] == "legacy"
    assert original_payload.metadata["foo"] == "bar"
    assert response is delegated_response
