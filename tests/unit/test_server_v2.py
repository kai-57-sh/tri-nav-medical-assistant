"""Tests for assistant v2 server routes."""

import os
from uuid import UUID

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

os.environ.setdefault("QWEN_API_KEY", "test-key")

from src.core.runtime.types import CapabilityResult
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
                "request_id": "req-test-v2",
                "session_id": "sess-test-v2",
                "data": {"capabilities_executed": 1, "success": success},
            }
        ]

    monkeypatch.setattr("src.core.runtime.query_engine.QueryEngine.run", fake_run)
    monkeypatch.setattr("src.core.runtime.event_bus.EventBus.dump", fake_dump)


def test_assistant_v2_invoke_success_contract_shape(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Route should return stable success contract fields."""

    _mock_runtime_run(
        monkeypatch,
        result=CapabilityResult(
            name="legacy_triage",
            success=True,
            payload={
                "status": "final",
                "session_id": "sess-test-v2",
                "response": "mocked response",
            },
            provenance={"source": "legacy_graph"},
            errors=[],
        ),
    )
    response = client.post(
        "/assistant/v2/invoke",
        json={
            "request_id": "req-test-v2",
            "session_id": "sess-test-v2",
            "trace_id": "trace-test-v2",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code in (200, 503)
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
    assert data["session_id"] == "sess-test-v2"
    assert data["trace_id"] == "trace-test-v2"
    assert data["response"].startswith("mocked response")
    assert data["safety"]["risk_level"] == "low"
    assert data["safety"]["matched_rules"] == []
    assert isinstance(data["runtime_events"], list)
    assert isinstance(data["provenance"], dict)
    assert isinstance(data["trace"], dict)


def test_assistant_v2_unknown_status_normalized_to_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown runtime status should normalize to error and return 503."""

    _mock_runtime_run(
        monkeypatch,
        result=CapabilityResult(
            name="legacy_triage",
            success=True,
            payload={
                "status": "unrecognized_status",
                "session_id": "sess-test-v2",
                "response": "mocked response",
            },
            provenance={"source": "legacy_graph"},
            errors=[],
        ),
    )
    response = client.post(
        "/assistant/v2/invoke",
        json={
            "request_id": "req-test-v2",
            "session_id": "sess-test-v2",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code in (200, 503)
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert "error_message" in data


def test_assistant_v2_failure_precedence_overrides_payload_status(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When capability reports failure, response status must be error."""

    _mock_runtime_run(
        monkeypatch,
        result=CapabilityResult(
            name="legacy_triage",
            success=False,
            payload={
                "status": "final",
                "session_id": "sess-test-v2",
                "response": "mocked response",
            },
            provenance={"source": "legacy_graph"},
            errors=["downstream failed"],
        ),
    )
    response = client.post(
        "/assistant/v2/invoke",
        json={
            "request_id": "req-test-v2",
            "session_id": "sess-test-v2",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"


def test_assistant_v2_error_with_text_response_still_enforces_medical_safety(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Error payloads with response text should still pass through medical safety engine."""

    _mock_runtime_run(
        monkeypatch,
        result=CapabilityResult(
            name="legacy_triage",
            success=False,
            payload={
                "status": "final",
                "session_id": "sess-test-v2",
                "response": "你已经确诊肺炎，先观察几天。",
            },
            provenance={"source": "legacy_graph"},
            errors=["downstream failed"],
        ),
    )
    response = client.post(
        "/assistant/v2/invoke",
        json={
            "request_id": "req-test-v2",
            "session_id": "sess-test-v2",
            "text": "胸痛并伴呼吸困难",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert "确诊" not in data["response"]
    assert "建议尽快就医" in data["response"]
    assert data["safety"]["risk_level"] == "high"
    assert "rewrite.confirmed_diagnosis" in data["safety"]["matched_rules"]


def test_assistant_v2_runtime_exception_returns_invoke_trace(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unhandled runtime errors should return structured invoke-stage trace."""

    _mock_runtime_run(
        monkeypatch,
        run_error=RuntimeError("runtime boom"),
    )
    response = client.post(
        "/assistant/v2/invoke",
        json={
            "request_id": "req-test-v2",
            "session_id": "sess-test-v2",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert data["trace"]["error_stage"] == "invoke"
    assert data["error_message"] == "assistant_v2_runtime_failed"


def test_assistant_v2_generates_trace_id_when_missing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Route should generate a UUID trace_id when payload does not include one."""

    _mock_runtime_run(
        monkeypatch,
        result=CapabilityResult(
            name="legacy_triage",
            success=True,
            payload={
                "status": "final",
                "session_id": "sess-test-v2",
                "response": "mocked response",
            },
            provenance={"source": "legacy_graph"},
            errors=[],
        ),
    )
    response = client.post(
        "/assistant/v2/invoke",
        json={
            "request_id": "req-test-v2",
            "session_id": "sess-test-v2",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get("trace_id"), str)
    UUID(data["trace_id"])


def test_assistant_v2_no_results_returns_503(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty runtime results should return structured 503 response."""

    _mock_runtime_run(
        monkeypatch,
        results=[],
    )
    response = client.post(
        "/assistant/v2/invoke",
        json={
            "request_id": "req-test-v2",
            "session_id": "sess-test-v2",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert data["error_message"] == "assistant_v2_runtime_failed_no_results"


def test_public_assistant_invoke_delegates_to_compat_v3_surface(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Public invoke should be served by compat->v3, not legacy runtime registration."""

    observed_runtime_mode: str | None = None
    compat_calls = 0

    async def fake_invoke_runtime_v3(payload):  # type: ignore[no-untyped-def]
        nonlocal compat_calls
        nonlocal observed_runtime_mode
        compat_calls += 1
        observed_runtime_mode = payload.metadata.get("runtime_mode")
        return JSONResponse(
            status_code=200,
            content={
                "status": "final",
                "session_id": "sess-public-cutover",
                "trace_id": "trace-public-cutover",
                "response": "compat v3 route",
            },
        )

    async def fail_legacy_runtime(self, context):  # type: ignore[no-untyped-def]
        raise AssertionError("legacy QueryEngine.run should not back /assistant/invoke")

    monkeypatch.setattr("src.interfaces.api.assistant_compat.invoke_runtime_v3", fake_invoke_runtime_v3)
    monkeypatch.setattr("src.core.runtime.query_engine.QueryEngine.run", fail_legacy_runtime)

    response = client.post(
        "/assistant/invoke",
        json={
            "input": {
                "request_id": "req-public-cutover",
                "session_id": "sess-public-cutover",
                "trace_id": "trace-public-cutover",
                "text": "头痛两天",
            }
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert compat_calls == 1
    assert observed_runtime_mode == "v3"
    assert response.json() == {
        "output": {
            "status": "final",
            "session_id": "sess-public-cutover",
            "trace_id": "trace-public-cutover",
            "response": "compat v3 route",
        },
        "metadata": {"runtime_mode": "v3"},
    }
