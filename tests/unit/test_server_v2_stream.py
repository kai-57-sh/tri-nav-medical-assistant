"""Tests for assistant v2 SSE stream route."""

import json
import os
from pathlib import Path

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

os.environ.setdefault("QWEN_API_KEY", "test-key")

from src.core.runtime.types import CapabilityResult
from src.server import app

from tests.conftest import parse_sse_frames


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


def test_assistant_v2_stream_returns_ordered_sse_frames(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stream endpoint should emit status, final, and done frames in order."""

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
        "/assistant/v2/stream",
        json={
            "request_id": "req-test-v2",
            "session_id": "sess-test-v2",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert response.text.count("\n\n") == 3

    frames = parse_sse_frames(response.text)
    assert len(frames) == 3

    assert frames[0]["event"] == "status"
    status_payload = json.loads(frames[0]["data"])
    assert status_payload["status"] == "start"
    assert status_payload["request_id"] == "req-test-v2"
    assert status_payload["session_id"] == "sess-test-v2"

    assert frames[1]["event"] == "final"
    final_payload = json.loads(frames[1]["data"])
    assert set(final_payload.keys()) >= {
        "status",
        "session_id",
        "response",
        "safety",
        "runtime_events",
        "provenance",
        "trace",
    }
    assert final_payload["status"] == "final"
    assert final_payload["session_id"] == "sess-test-v2"
    assert final_payload["response"].startswith("mocked response")
    assert final_payload["safety"]["risk_level"] == "low"
    assert final_payload["safety"]["matched_rules"] == []

    assert "event" not in frames[2]
    assert frames[2]["data"] == "[DONE]"


def test_assistant_v2_stream_runtime_exception_still_emits_final_and_done(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stream should emit final error payload and done marker when invoke raises."""

    async def fake_invoke(payload):  # type: ignore[no-untyped-def]
        _ = payload
        raise RuntimeError("stream boom")

    monkeypatch.setattr("src.interfaces.api.assistant_v2.invoke_assistant_v2", fake_invoke)

    response = client.post(
        "/assistant/v2/stream",
        json={
            "request_id": "req-test-v2",
            "session_id": "sess-test-v2",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert response.text.count("\n\n") == 3

    frames = parse_sse_frames(response.text)
    assert len(frames) == 3
    assert frames[0]["event"] == "status"
    assert frames[1]["event"] == "final"
    assert frames[2]["data"] == "[DONE]"

    final_payload = json.loads(frames[1]["data"])
    assert set(final_payload.keys()) >= {
        "status",
        "session_id",
        "response",
        "safety",
        "runtime_events",
        "provenance",
        "trace",
        "error_message",
    }
    assert final_payload["status"] == "error"
    assert final_payload["session_id"] == "sess-test-v2"
    assert final_payload["error_message"] == "assistant_v2_stream_failed"
    assert final_payload["safety"]["risk_level"] == "low"
    assert final_payload["safety"]["matched_rules"] == []


def test_assistant_v2_stream_invalid_payload_falls_back_to_error_with_safety(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stream decode fallback should preserve safety contract fields."""

    async def fake_invoke(payload):  # type: ignore[no-untyped-def]
        _ = payload
        return JSONResponse(status_code=200, content=["invalid-payload"])

    monkeypatch.setattr("src.interfaces.api.assistant_v2.invoke_assistant_v2", fake_invoke)

    response = client.post(
        "/assistant/v2/stream",
        json={
            "request_id": "req-test-v2",
            "session_id": "sess-test-v2",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    frames = parse_sse_frames(response.text)
    assert len(frames) == 3
    assert frames[0]["event"] == "status"
    assert frames[1]["event"] == "final"
    assert frames[2]["data"] == "[DONE]"

    final_payload = json.loads(frames[1]["data"])
    assert final_payload["status"] == "error"
    assert final_payload["error_message"] == "assistant_v2_stream_invalid_payload"
    assert final_payload["safety"]["risk_level"] == "low"
    assert final_payload["safety"]["matched_rules"] == []


def test_assistant_v2_stream_contract_doc_mentions_safety_field() -> None:
    """V2 stream contract doc should explicitly include safety in final payload."""

    root = Path(__file__).resolve().parents[2]
    doc_text = (root / "docs" / "frontend_contract" / "events.md").read_text(encoding="utf-8")
    assert '"safety":{' in doc_text
