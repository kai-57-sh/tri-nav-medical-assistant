"""Tests for assistant v3 invoke route."""

import os
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient
import pytest

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
        "runtime_events",
        "provenance",
        "trace",
    }
    assert data["status"] == "final"
    assert data["session_id"] == "sess-test-v3"
    assert data["trace_id"] == "trace-test-v3"
    assert data["response"] == "mocked response"
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
    assert data["trace"]["path"] == "v3_task_coordinator"
    assert "已记录症状" in data["response"]
