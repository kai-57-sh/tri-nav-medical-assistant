"""Tests for assistant v3 invoke route."""

import json
import os
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

os.environ.setdefault("QWEN_API_KEY", "test-key")

from src.core.runtime.types import CapabilityResult
from src.interfaces.api.assistant_v2 import (
    AssistantV2InvokePayload,
    get_runtime_session_state,
)
from src.interfaces.api.assistant_v3 import invoke_assistant_v3
from src.interfaces.api.runtime_v3 import invoke_runtime_v3
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

    async def fake_primary(_: AssistantV2InvokePayload) -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content={
                "status": "final",
                "session_id": "sess-test-v3",
                "trace_id": "trace-test-v3",
                "response": "mocked response",
                "safety": {"risk_level": "low", "matched_rules": []},
                "runtime_events": [],
                "provenance": {"source": "legacy_graph"},
                "trace": {"request_id": "req-test-v3"},
            },
        )

    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_primary_v3", fake_primary)

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

    async def fake_primary(_: AssistantV2InvokePayload) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "session_id": "sess-test-v3",
                "trace_id": "11111111-1111-1111-1111-111111111111",
                "response": "mocked response",
                "safety": {"risk_level": "low", "matched_rules": []},
                "runtime_events": [],
                "provenance": {"source": "legacy_graph"},
                "trace": {"request_id": "req-test-v3"},
                "error_message": "assistant_v3_task_runtime_failed",
            },
        )

    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_primary_v3", fake_primary)

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


@pytest.mark.asyncio
async def test_assistant_v3_invoke_delegates_to_runtime_v3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V3 invoke should inject runtime_mode and delegate to runtime_v3."""

    observed_payload: AssistantV2InvokePayload | None = None
    calls = 0
    delegated_response = JSONResponse({"status": "final"})

    async def fake_invoke(payload: AssistantV2InvokePayload) -> JSONResponse:
        nonlocal calls
        nonlocal observed_payload
        calls += 1
        observed_payload = payload
        return delegated_response

    monkeypatch.setattr("src.interfaces.api.assistant_v3.invoke_runtime_v3", fake_invoke)

    original_payload = AssistantV2InvokePayload(
        request_id="req-adapter-v3-invoke",
        session_id="sess-adapter-v3-invoke",
        trace_id="trace-adapter-v3-invoke",
        text="头晕",
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


@pytest.mark.asyncio
async def test_runtime_v3_uses_legacy_fallback_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime v3 should preserve the v3 envelope when legacy fallback is used."""

    payload = AssistantV2InvokePayload(
        request_id="req-v3-fallback-1",
        session_id="sess-v3-fallback-1",
        trace_id="trace-v3-fallback-1",
        text="头痛发热",
    )
    legacy_payload = {
        "status": "final",
        "session_id": "sess-v3-fallback-1",
        "response": "legacy fallback response",
    }

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.get_settings",
        lambda: SimpleNamespace(v3_legacy_fallback_enabled=True),
    )

    async def fake_primary(_: AssistantV2InvokePayload) -> JSONResponse:
        raise RuntimeError("primary v3 failed")

    async def fake_legacy(_: AssistantV2InvokePayload) -> dict[str, str]:
        return legacy_payload

    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_primary_v3", fake_primary)
    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_legacy_fallback", fake_legacy)

    response = await invoke_runtime_v3(payload)

    assert response.status_code == 200
    assert isinstance(response, JSONResponse)
    data = json.loads(response.body)
    assert data["status"] == "final"
    assert data["session_id"] == "sess-v3-fallback-1"
    assert data["trace_id"] == "trace-v3-fallback-1"
    assert data["response"] == "legacy fallback response"
    assert data["safety"] == {"risk_level": "low", "matched_rules": []}
    assert isinstance(data["runtime_events"], list)
    assert data["provenance"]["source"] == "legacy_graph"
    assert data["provenance"]["fallback"] == "v3_legacy"
    assert data["trace"]["path"] == "legacy_fallback"
    assert data["trace"]["request_id"] == "req-v3-fallback-1"
    assert data["trace"]["primary_error_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_runtime_v3_falls_back_when_primary_returns_structured_error_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Structured primary error responses should still trigger fallback when enabled."""

    payload = AssistantV2InvokePayload(
        request_id="req-v3-fallback-from-response-1",
        session_id="sess-v3-fallback-from-response-1",
        trace_id="trace-v3-fallback-from-response-1",
        text="头痛发热",
    )
    legacy_payload = {
        "status": "final",
        "session_id": "sess-v3-fallback-from-response-1",
        "response": "legacy fallback response",
    }

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.get_settings",
        lambda: SimpleNamespace(v3_legacy_fallback_enabled=True),
    )

    async def fake_primary(_: AssistantV2InvokePayload) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "session_id": "sess-v3-fallback-from-response-1",
                "trace_id": "trace-v3-fallback-from-response-1",
                "response": "",
                "safety": {"risk_level": "low", "matched_rules": []},
                "runtime_events": [],
                "provenance": {"source": "assistant_v3"},
                "trace": {"error_type": "PrimaryReturnedError"},
                "error_message": "primary returned structured error",
            },
        )

    async def fake_legacy(_: AssistantV2InvokePayload) -> dict[str, str]:
        return legacy_payload

    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_primary_v3", fake_primary)
    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_legacy_fallback", fake_legacy)

    response = await invoke_runtime_v3(payload)

    assert response.status_code == 200
    data = json.loads(response.body)
    assert data["status"] == "final"
    assert data["session_id"] == "sess-v3-fallback-from-response-1"
    assert data["response"] == "legacy fallback response"
    assert data["trace"]["path"] == "legacy_fallback"


@pytest.mark.asyncio
async def test_runtime_v3_legacy_fallback_applies_safe_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy fallback should return rewritten safe text, not the raw unsafe text."""

    payload = AssistantV2InvokePayload(
        request_id="req-v3-fallback-safe-1",
        session_id="sess-v3-fallback-safe-1",
        trace_id="trace-v3-fallback-safe-1",
        text="胸痛发热",
    )
    legacy_payload = {
        "status": "final",
        "session_id": "sess-v3-fallback-safe-1",
        "response": "你已经确诊肺炎，先别去医院。",
    }

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.get_settings",
        lambda: SimpleNamespace(v3_legacy_fallback_enabled=True),
    )

    async def fake_primary(_: AssistantV2InvokePayload) -> JSONResponse:
        raise RuntimeError("primary v3 failed")

    async def fake_legacy(_: AssistantV2InvokePayload) -> dict[str, str]:
        return legacy_payload

    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_primary_v3", fake_primary)
    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_legacy_fallback", fake_legacy)

    response = await invoke_runtime_v3(payload)

    assert response.status_code == 200
    data = json.loads(response.body)
    assert "确诊" not in data["response"]
    assert "别去医院" not in data["response"]
    assert "疑似" in data["response"]
    assert "建议尽快就医" in data["response"]
    assert data["safety"]["risk_level"] == "high"
    assert "rewrite.confirmed_diagnosis" in data["safety"]["matched_rules"]


@pytest.mark.asyncio
async def test_runtime_v3_successful_legacy_fallback_preserves_structured_clinical_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful legacy fallback should expose key structured clinical fields when present."""

    payload = AssistantV2InvokePayload(
        request_id="req-v3-fallback-structured-1",
        session_id="sess-v3-fallback-structured-1",
        trace_id="trace-v3-fallback-structured-1",
        text="持续咳嗽两周",
    )
    legacy_payload = {
        "status": "final",
        "session_id": "sess-v3-fallback-structured-1",
        "response": "legacy fallback response",
        "triage_level": "ROUTINE",
        "recommended_departments": ["全科", "内科"],
        "possible_causes": ["上呼吸道感染（疑似）"],
        "red_flags": ["若呼吸困难请立即急诊"],
        "disclaimer": "本建议仅供参考，不替代专业医疗诊断。",
    }

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.get_settings",
        lambda: SimpleNamespace(v3_legacy_fallback_enabled=True),
    )

    async def fake_primary(_: AssistantV2InvokePayload) -> JSONResponse:
        raise RuntimeError("primary v3 failed")

    async def fake_legacy(_: AssistantV2InvokePayload) -> dict[str, object]:
        return legacy_payload

    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_primary_v3", fake_primary)
    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_legacy_fallback", fake_legacy)

    response = await invoke_runtime_v3(payload)

    assert response.status_code == 200
    data = json.loads(response.body)
    assert data["triage_level"] == "ROUTINE"
    assert data["recommended_departments"] == ["全科", "内科"]
    assert data["possible_causes"] == ["上呼吸道感染（疑似）"]
    assert data["red_flags"] == ["若呼吸困难请立即急诊"]
    assert data["disclaimer"] == "本建议仅供参考，不替代专业医疗诊断。"


@pytest.mark.asyncio
async def test_runtime_v3_returns_structured_error_when_fallback_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime v3 should return structured v3 error response when fallback is disabled."""

    payload = AssistantV2InvokePayload(
        request_id="req-v3-fallback-disabled-1",
        session_id="sess-v3-fallback-disabled-1",
        trace_id="trace-v3-fallback-disabled-1",
        text="头痛发热",
    )

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.get_settings",
        lambda: SimpleNamespace(v3_legacy_fallback_enabled=False),
    )

    async def fake_primary(_: AssistantV2InvokePayload) -> JSONResponse:
        raise RuntimeError("primary v3 failed")

    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_primary_v3", fake_primary)

    response = await invoke_runtime_v3(payload)

    assert response.status_code == 503
    data = json.loads(response.body)
    assert data["status"] == "error"
    assert data["session_id"] == "sess-v3-fallback-disabled-1"
    assert data["trace_id"] == "trace-v3-fallback-disabled-1"
    assert data["response"] == ""
    assert data["safety"] == {"risk_level": "low", "matched_rules": []}
    assert isinstance(data["runtime_events"], list)
    assert data["provenance"]["source"] == "assistant_v2"
    assert data["trace"]["error_stage"] == "task_orchestration"
    assert data["error_message"] == "assistant_v3_task_runtime_failed"


@pytest.mark.asyncio
async def test_runtime_v3_returns_structured_error_when_primary_and_fallback_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both primary and legacy fallback failures should return structured v3 error."""

    payload = AssistantV2InvokePayload(
        request_id="req-v3-fallback-double-fail-1",
        session_id="sess-v3-fallback-double-fail-1",
        trace_id="trace-v3-fallback-double-fail-1",
        text="头痛发热",
    )

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.get_settings",
        lambda: SimpleNamespace(v3_legacy_fallback_enabled=True),
    )

    async def fake_primary(_: AssistantV2InvokePayload) -> JSONResponse:
        raise RuntimeError("primary v3 failed")

    async def fake_legacy(_: AssistantV2InvokePayload) -> dict[str, str]:
        raise ValueError("legacy fallback failed")

    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_primary_v3", fake_primary)
    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_legacy_fallback", fake_legacy)

    response = await invoke_runtime_v3(payload)

    assert response.status_code == 503
    data = json.loads(response.body)
    assert data["status"] == "error"
    assert data["session_id"] == "sess-v3-fallback-double-fail-1"
    assert data["trace_id"] == "trace-v3-fallback-double-fail-1"
    assert data["response"] == ""
    assert data["safety"] == {"risk_level": "low", "matched_rules": []}
    assert isinstance(data["runtime_events"], list)
    assert data["trace"]["error_stage"] == "task_orchestration"
    assert data["trace"]["error_type"] == "ValueError"
    assert data["error_message"] == "assistant_v3_task_runtime_failed"


@pytest.mark.asyncio
async def test_runtime_v3_legacy_fallback_logical_error_maps_to_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy fallback logical error should preserve envelope and map to 503."""

    payload = AssistantV2InvokePayload(
        request_id="req-v3-fallback-error-1",
        session_id="sess-v3-fallback-error-1",
        trace_id="trace-v3-fallback-error-1",
        text="头痛发热",
    )
    legacy_payload = {
        "status": "not_allowed",
        "session_id": "sess-v3-fallback-error-1",
        "response": "legacy fallback response",
        "error_message": "legacy path rejected request",
    }

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.get_settings",
        lambda: SimpleNamespace(v3_legacy_fallback_enabled=True),
    )

    async def fake_primary(_: AssistantV2InvokePayload) -> JSONResponse:
        raise RuntimeError("primary v3 failed")

    async def fake_legacy(_: AssistantV2InvokePayload) -> dict[str, str]:
        return legacy_payload

    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_primary_v3", fake_primary)
    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_legacy_fallback", fake_legacy)

    response = await invoke_runtime_v3(payload)

    assert response.status_code == 503
    data = json.loads(response.body)
    assert data["status"] == "error"
    assert data["session_id"] == "sess-v3-fallback-error-1"
    assert data["trace_id"] == "trace-v3-fallback-error-1"
    assert data["response"] == "legacy fallback response"
    assert data["error_message"] == "legacy path rejected request"
    assert data["provenance"]["fallback"] == "v3_legacy"
    assert data["trace"]["path"] == "legacy_fallback"


@pytest.mark.asyncio
async def test_runtime_v3_successful_legacy_fallback_persists_runtime_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful legacy fallback should persist snapshot and events to shared stores."""

    payload = AssistantV2InvokePayload(
        request_id="req-v3-fallback-persist-1",
        session_id="sess-v3-fallback-persist-1",
        trace_id="trace-v3-fallback-persist-1",
        text="持续低热三天",
    )
    legacy_payload = {
        "status": "final",
        "session_id": "sess-v3-fallback-persist-1",
        "response": "legacy fallback persisted response",
    }

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.get_settings",
        lambda: SimpleNamespace(v3_legacy_fallback_enabled=True),
    )

    async def fake_primary(_: AssistantV2InvokePayload) -> JSONResponse:
        raise RuntimeError("primary v3 failed")

    async def fake_legacy(_: AssistantV2InvokePayload) -> dict[str, str]:
        return legacy_payload

    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_primary_v3", fake_primary)
    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_legacy_fallback", fake_legacy)

    response = await invoke_runtime_v3(payload)

    assert response.status_code == 200
    state = await get_runtime_session_state("sess-v3-fallback-persist-1")
    snapshot = state["snapshot"]
    assert snapshot is not None
    assert snapshot["status"] == "final"
    assert snapshot["trace_id"] == "trace-v3-fallback-persist-1"
    assert snapshot["response"] == "legacy fallback persisted response"
    assert snapshot["trace"]["path"] == "legacy_fallback"
    assert isinstance(state["runtime_events"], list)
    assert state["runtime_events"][0]["event_type"] == "runtime_fallback_triggered"
    assert state["runtime_events"][-1]["event_type"] == "runtime_finished"


@pytest.mark.asyncio
async def test_runtime_v3_legacy_fallback_blank_session_id_uses_resolved_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blank legacy session ids should fall back to the resolved request session id."""

    payload = AssistantV2InvokePayload(
        request_id="req-v3-fallback-blank-session-1",
        session_id="sess-v3-fallback-blank-session-1",
        trace_id="trace-v3-fallback-blank-session-1",
        text="持续低热三天",
    )
    legacy_payload = {
        "status": "final",
        "session_id": "   ",
        "response": "legacy fallback response",
    }

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.get_settings",
        lambda: SimpleNamespace(v3_legacy_fallback_enabled=True),
    )

    async def fake_primary(_: AssistantV2InvokePayload) -> JSONResponse:
        raise RuntimeError("primary v3 failed")

    async def fake_legacy(_: AssistantV2InvokePayload) -> dict[str, str]:
        return legacy_payload

    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_primary_v3", fake_primary)
    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_legacy_fallback", fake_legacy)

    response = await invoke_runtime_v3(payload)

    assert response.status_code == 200
    data = json.loads(response.body)
    assert data["session_id"] == "sess-v3-fallback-blank-session-1"
    state = await get_runtime_session_state("sess-v3-fallback-blank-session-1")
    snapshot = state["snapshot"]
    assert snapshot is not None
    assert snapshot["session_id"] == "sess-v3-fallback-blank-session-1"
    assert state["runtime_events"][0]["session_id"] == "sess-v3-fallback-blank-session-1"
    assert state["runtime_events"][-1]["session_id"] == "sess-v3-fallback-blank-session-1"


@pytest.mark.asyncio
async def test_runtime_v3_legacy_fallback_non_uuid_public_session_uses_stable_internal_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy fallback should map non-UUID public session ids to a stable internal UUID only."""

    payload = AssistantV2InvokePayload(
        request_id="req-v3-fallback-non-uuid-1",
        session_id="sess-public-non-uuid-1",
        trace_id="trace-v3-fallback-non-uuid-1",
        text="持续低热三天",
    )
    seen_legacy_session_ids: list[str] = []

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.get_settings",
        lambda: SimpleNamespace(v3_legacy_fallback_enabled=True),
    )

    async def fake_primary(_: AssistantV2InvokePayload) -> JSONResponse:
        raise RuntimeError("primary v3 failed")

    async def fake_invoke_chain(
        session_id: str,
        text: str,
        image_base64: str | None = None,
        gps_lat: float | None = None,
        gps_lng: float | None = None,
        config: object | None = None,
    ) -> dict[str, object]:
        _ = (text, image_base64, gps_lat, gps_lng, config)
        seen_legacy_session_ids.append(session_id)
        UUID(session_id)
        return {
            "status": "final",
            "session_id": session_id,
            "response": "legacy fallback response",
        }

    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_primary_v3", fake_primary)
    monkeypatch.setattr("src.chains.triage_chain.invoke_chain", fake_invoke_chain)

    first_response = await invoke_runtime_v3(payload)
    second_response = await invoke_runtime_v3(payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert len(seen_legacy_session_ids) == 2
    assert seen_legacy_session_ids[0] == seen_legacy_session_ids[1]
    assert seen_legacy_session_ids[0] != "sess-public-non-uuid-1"

    first_data = json.loads(first_response.body)
    second_data = json.loads(second_response.body)
    assert first_data["session_id"] == "sess-public-non-uuid-1"
    assert second_data["session_id"] == "sess-public-non-uuid-1"

    state = await get_runtime_session_state("sess-public-non-uuid-1")
    snapshot = state["snapshot"]
    assert snapshot is not None
    assert snapshot["session_id"] == "sess-public-non-uuid-1"
    assert snapshot["trace_id"] == "trace-v3-fallback-non-uuid-1"
    assert state["runtime_events"][0]["session_id"] == "sess-public-non-uuid-1"
    assert state["runtime_events"][-1]["session_id"] == "sess-public-non-uuid-1"


@pytest.mark.asyncio
async def test_runtime_v3_legacy_session_ids_do_not_alias_uuid_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canonical UUID text must not alias with alternate raw spellings of the same UUID."""

    canonical_session_id = "12345678-1234-5678-9abc-def012345678"
    uppercase_session_id = canonical_session_id.upper()
    seen_legacy_session_ids: list[str] = []

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.get_settings",
        lambda: SimpleNamespace(v3_legacy_fallback_enabled=True),
    )

    async def fake_primary(_: AssistantV2InvokePayload) -> JSONResponse:
        raise RuntimeError("primary v3 failed")

    async def fake_invoke_chain(
        session_id: str,
        text: str,
        image_base64: str | None = None,
        gps_lat: float | None = None,
        gps_lng: float | None = None,
        config: object | None = None,
    ) -> dict[str, object]:
        _ = (text, image_base64, gps_lat, gps_lng, config)
        seen_legacy_session_ids.append(session_id)
        UUID(session_id)
        return {
            "status": "final",
            "session_id": session_id,
            "response": "legacy fallback response",
        }

    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_primary_v3", fake_primary)
    monkeypatch.setattr("src.chains.triage_chain.invoke_chain", fake_invoke_chain)

    canonical_response = await invoke_runtime_v3(
        AssistantV2InvokePayload(
            request_id="req-v3-fallback-canonical-1",
            session_id=canonical_session_id,
            trace_id="trace-v3-fallback-canonical-1",
            text="持续低热三天",
        )
    )
    uppercase_response = await invoke_runtime_v3(
        AssistantV2InvokePayload(
            request_id="req-v3-fallback-uppercase-1",
            session_id=uppercase_session_id,
            trace_id="trace-v3-fallback-uppercase-1",
            text="持续低热三天",
        )
    )

    assert canonical_response.status_code == 200
    assert uppercase_response.status_code == 200
    assert len(seen_legacy_session_ids) == 2
    assert seen_legacy_session_ids[0] == canonical_session_id
    assert seen_legacy_session_ids[1] != uppercase_session_id
    assert seen_legacy_session_ids[1] != seen_legacy_session_ids[0]

    canonical_data = json.loads(canonical_response.body)
    uppercase_data = json.loads(uppercase_response.body)
    assert canonical_data["session_id"] == canonical_session_id
    assert uppercase_data["session_id"] == uppercase_session_id


@pytest.mark.asyncio
async def test_runtime_v3_returns_structured_error_when_settings_resolution_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings resolution failures should return a structured v3 503 envelope."""

    payload = AssistantV2InvokePayload(
        request_id="req-v3-settings-error-1",
        session_id="sess-v3-settings-error-1",
        trace_id="trace-v3-settings-error-1",
        text="头痛发热",
    )

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.get_settings",
        lambda: (_ for _ in ()).throw(RuntimeError("settings unavailable")),
    )

    response = await invoke_runtime_v3(payload)

    assert response.status_code == 503
    data = json.loads(response.body)
    assert data["status"] == "error"
    assert data["session_id"] == "sess-v3-settings-error-1"
    assert data["trace_id"] == "trace-v3-settings-error-1"
    assert data["response"] == ""
    assert data["safety"] == {"risk_level": "low", "matched_rules": []}
    assert isinstance(data["runtime_events"], list)
    assert data["provenance"]["source"] == "assistant_v2"
    assert data["trace"]["error_stage"] == "settings"
    assert data["error_message"] == "assistant_v3_task_runtime_failed"


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


def test_assistant_v3_task_coordinator_uses_payload_triage_when_canonical_state_is_empty(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When canonical triage state is empty, compatibility fallback should use triage payload."""

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
                "triage_level": "URGENT",
                "triage_reason": "payload says urgent",
                "recommended_departments": ["急诊", "内科"],
                "red_flags": ["若出现胸痛请立即急诊"],
            },
            provenance={"source": "test"},
            errors=[],
            state_patch={"triage": {}},
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
            payload={"status": "final", "response": "compatibility fallback response"},
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
            "request_id": "req-v3-compat-fallback-1",
            "session_id": "sess-v3-compat-fallback-1",
            "trace_id": "trace-v3-compat-fallback-1",
            "text": "持续高热并加重",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["triage_level"] == "URGENT"
    assert data["recommended_departments"] == ["急诊科", "内科"]
    assert data["red_flags"] == ["症状存在加重风险，建议尽快线下就医。"]
