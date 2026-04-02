"""Tests for assistant v2 server routes."""

import os

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
    result: CapabilityResult,
) -> None:
    async def fake_run(self, context):  # type: ignore[no-untyped-def]
        _ = self
        _ = context
        return [result]

    def fake_dump(self):  # type: ignore[no-untyped-def]
        _ = self
        return [
            {
                "event_type": "runtime_finished",
                "request_id": "req-test-v2",
                "session_id": "sess-test-v2",
                "data": {"capabilities_executed": 1, "success": result.success},
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
        "response",
        "runtime_events",
        "provenance",
        "trace",
    }
    assert data["status"] == "final"
    assert data["session_id"] == "sess-test-v2"
    assert data["response"] == "mocked response"
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
