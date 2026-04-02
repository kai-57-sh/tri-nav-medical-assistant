"""Tests for assistant v2 SSE stream route."""

import json
import os
from typing import Any

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


def _parse_sse_frames(body: str) -> list[dict[str, Any]]:
    assert body.endswith("\n\n")
    raw_frames = [frame for frame in body.split("\n\n") if frame]
    parsed: list[dict[str, Any]] = []
    for frame in raw_frames:
        lines = frame.split("\n")
        entry: dict[str, Any] = {"raw": frame, "lines": lines}
        for line in lines:
            if line.startswith("event: "):
                entry["event"] = line.removeprefix("event: ")
            if line.startswith("data: "):
                entry["data"] = line.removeprefix("data: ")
        parsed.append(entry)
    return parsed


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

    frames = _parse_sse_frames(response.text)
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
        "runtime_events",
        "provenance",
        "trace",
    }
    assert final_payload["status"] == "final"
    assert final_payload["session_id"] == "sess-test-v2"
    assert final_payload["response"] == "mocked response"

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

    frames = _parse_sse_frames(response.text)
    assert len(frames) == 3
    assert frames[0]["event"] == "status"
    assert frames[1]["event"] == "final"
    assert frames[2]["data"] == "[DONE]"

    final_payload = json.loads(frames[1]["data"])
    assert set(final_payload.keys()) >= {
        "status",
        "session_id",
        "response",
        "runtime_events",
        "provenance",
        "trace",
        "error_message",
    }
    assert final_payload["status"] == "error"
    assert final_payload["session_id"] == "sess-test-v2"
    assert final_payload["error_message"] == "assistant_v2_stream_failed"
