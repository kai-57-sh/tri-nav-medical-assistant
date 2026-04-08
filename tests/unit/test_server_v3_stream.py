"""Tests for assistant v3 SSE stream route."""

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.testclient import TestClient

os.environ.setdefault("QWEN_API_KEY", "test-key")

from src.interfaces.api.assistant_v2 import AssistantV2InvokePayload
from src.interfaces.api.assistant_v3 import stream_assistant_v3
from src.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def enable_v3_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit v3 stream tests assume the runtime gate is enabled unless overridden."""

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.get_settings",
        lambda: SimpleNamespace(v3_runtime_enabled=True, v3_legacy_fallback_enabled=False),
    )


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


def test_assistant_v3_stream_returns_ordered_sse_frames(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V3 stream should emit status/final/[DONE] SSE frames with correct payload shape."""

    async def fake_invoke_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
        _ = payload
        return JSONResponse(
            status_code=200,
            content={
                "status": "final",
                "session_id": "sess-test-v3",
                "trace_id": "trace-test-v3",
                "response": "mocked response",
                "safety": {"risk_level": "low", "matched_rules": []},
                "runtime_events": [
                    {
                        "event_type": "runtime_finished",
                        "request_id": "req-test-v3",
                        "session_id": "sess-test-v3",
                        "data": {"capabilities_executed": 1, "success": True},
                    }
                ],
                "provenance": {"source": "v3_primary"},
                "trace": {"request_id": "req-test-v3"},
            },
        )

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.invoke_runtime_v3",
        fake_invoke_v3,
    )

    response = client.post(
        "/assistant/v3/stream",
        json={
            "request_id": "req-test-v3",
            "session_id": "sess-test-v3",
            "trace_id": "trace-test-v3",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert response.text.count("data: [DONE]") == 1

    frames = _parse_sse_frames(response.text)
    assert len(frames) == 3
    assert frames[0]["event"] == "status"
    assert frames[1]["event"] == "final"
    assert "event" not in frames[2]
    assert frames[2]["data"] == "[DONE]"

    status_payload = json.loads(frames[0]["data"])
    assert status_payload["status"] == "start"
    assert status_payload["request_id"] == "req-test-v3"
    assert status_payload["session_id"] == "sess-test-v3"
    assert status_payload["trace_id"] == "trace-test-v3"

    final_payload = json.loads(frames[1]["data"])
    assert set(final_payload.keys()) >= {
        "status",
        "session_id",
        "trace_id",
        "response",
        "safety",
        "runtime_events",
        "provenance",
        "trace",
    }
    assert final_payload["status"] == "final"
    assert final_payload["session_id"] == "sess-test-v3"
    assert final_payload["trace_id"] == "trace-test-v3"
    assert final_payload["response"] == "mocked response"
    assert final_payload["safety"]["risk_level"] == "low"
    assert final_payload["safety"]["matched_rules"] == []


def test_assistant_v3_stream_error_final_still_uses_http_200(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V3 stream should keep 200 transport status with final error payload."""

    async def fake_invoke_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
        _ = payload
        raise RuntimeError("stream boom")

    monkeypatch.setattr("src.interfaces.api.runtime_v3.invoke_runtime_v3", fake_invoke_v3)

    response = client.post(
        "/assistant/v3/stream",
        json={
            "request_id": "req-test-v3",
            "session_id": "sess-test-v3",
            "trace_id": "trace-test-v3",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    frames = _parse_sse_frames(response.text)
    assert len(frames) == 3
    assert frames[0]["event"] == "status"
    assert frames[1]["event"] == "final"
    assert frames[2]["data"] == "[DONE]"
    assert response.text.count("data: [DONE]") == 1

    final_payload = json.loads(frames[1]["data"])
    assert final_payload["status"] == "error"
    assert final_payload["error_message"] == "assistant_v3_stream_failed"


def test_assistant_v3_stream_returns_final_error_when_runtime_flag_disabled(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit v3 stream should not execute the runtime when the v3 flag is disabled."""

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {"v3_runtime_enabled": False, "v3_legacy_fallback_enabled": True},
        )(),
    )

    async def fail_invoke(payload):
        _ = payload
        raise AssertionError("stream path should not execute invoke_runtime_v3 when runtime is disabled")

    monkeypatch.setattr("src.interfaces.api.runtime_v3.invoke_runtime_v3", fail_invoke)

    response = client.post(
        "/assistant/v3/stream",
        json={
            "request_id": "req-test-v3-disabled-stream",
            "session_id": "sess-test-v3-disabled-stream",
            "trace_id": "trace-test-v3-disabled-stream",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    frames = _parse_sse_frames(response.text)
    assert len(frames) == 3
    final_payload = json.loads(frames[1]["data"])
    assert final_payload["status"] == "error"
    assert final_payload["error_message"] == "assistant_v3_runtime_disabled"
    assert final_payload["trace"]["error_stage"] == "runtime_gate"
    assert frames[2]["data"] == "[DONE]"


def test_assistant_v3_stream_contract_doc_mentions_http_200_error_parity() -> None:
    """V3 stream contract doc should state HTTP 200 transport on final error payload."""

    root = Path(__file__).resolve().parents[2]
    doc_text = (root / "docs" / "frontend_contract" / "events_v3.md").read_text(encoding="utf-8")
    assert "HTTP status remains 200" in doc_text
    assert '"safety":{' in doc_text


@pytest.mark.asyncio
async def test_assistant_v3_stream_sets_runtime_mode_and_calls_runtime_v3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V3 stream should only inject runtime_mode and delegate to runtime_v3."""

    observed_payload: AssistantV2InvokePayload | None = None
    calls = 0

    async def _events() -> Any:
        yield b"event: status\ndata: {}\n\n"
        yield b"data: [DONE]\n\n"

    delegated_response = StreamingResponse(_events(), media_type="text/event-stream")

    async def fake_stream(payload: AssistantV2InvokePayload) -> StreamingResponse:
        nonlocal calls
        nonlocal observed_payload
        calls += 1
        observed_payload = payload
        return delegated_response

    monkeypatch.setattr("src.interfaces.api.assistant_v3.stream_runtime_v3", fake_stream)

    original_payload = AssistantV2InvokePayload(
        request_id="req-adapter-v3-stream",
        session_id="sess-adapter-v3-stream",
        trace_id="trace-adapter-v3-stream",
        text="头晕",
        metadata={"runtime_mode": "legacy", "foo": "bar"},
    )

    response = await stream_assistant_v3(original_payload)

    assert calls == 1
    assert observed_payload is not None
    assert observed_payload is not original_payload
    assert observed_payload.metadata["runtime_mode"] == "v3"
    assert observed_payload.metadata["foo"] == "bar"
    assert original_payload.metadata["runtime_mode"] == "legacy"
    assert original_payload.metadata["foo"] == "bar"
    assert response is delegated_response


# ---------------------------------------------------------------------------
# Unified stream semantics: stream_runtime_v3 delegates to invoke_runtime_v3
# and converts the JSONResponse to SSE, sharing the same
# primary / fallback / disabled logic instead of calling stream_assistant_v2.
# ---------------------------------------------------------------------------


def test_stream_primary_structured_error_converted_to_sse_final_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When invoke_runtime_v3 returns a structured error, stream should emit it as a final error SSE."""

    error_body = JSONResponse(
        status_code=503,
        content={
            "status": "error",
            "session_id": "sess-stream-err",
            "trace_id": "trace-stream-err",
            "error_message": "assistant_v3_task_runtime_failed",
            "trace": {
                "request_id": "req-stream-err",
                "error_stage": "task_orchestration",
                "error_type": "RuntimeError",
                "error_message": "coordinator crashed",
            },
        },
    )

    async def fake_invoke_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
        _ = payload
        return error_body

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.invoke_runtime_v3",
        fake_invoke_v3,
    )

    response = client.post(
        "/assistant/v3/stream",
        json={
            "request_id": "req-stream-err",
            "session_id": "sess-stream-err",
            "trace_id": "trace-stream-err",
            "text": "头痛",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    frames = _parse_sse_frames(response.text)
    assert len(frames) == 3
    assert frames[0]["event"] == "status"
    assert frames[1]["event"] == "final"
    assert frames[2]["data"] == "[DONE]"

    final_payload = json.loads(frames[1]["data"])
    assert final_payload["status"] == "error"
    assert final_payload["error_message"] == "assistant_v3_task_runtime_failed"


def test_stream_legacy_fallback_success_converted_to_sse_final(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When invoke_runtime_v3 returns legacy fallback result, stream should emit it as a final success SSE."""

    fallback_body = JSONResponse(
        status_code=200,
        content={
            "status": "final",
            "session_id": "sess-stream-fallback",
            "trace_id": "trace-stream-fallback",
            "response": "legacy fallback response",
            "safety": {"risk_level": "low", "matched_rules": []},
            "runtime_events": [
                {"event_type": "runtime_fallback_triggered", "session_id": "sess-stream-fallback"},
            ],
            "provenance": {"source": "legacy_graph", "fallback": "v3_legacy"},
            "trace": {
                "request_id": "req-stream-fallback",
                "path": "legacy_fallback",
                "primary_error_type": "RuntimeError",
            },
        },
    )

    async def fake_invoke_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
        _ = payload
        return fallback_body

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.invoke_runtime_v3",
        fake_invoke_v3,
    )

    response = client.post(
        "/assistant/v3/stream",
        json={
            "request_id": "req-stream-fallback",
            "session_id": "sess-stream-fallback",
            "trace_id": "trace-stream-fallback",
            "text": "头痛",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    frames = _parse_sse_frames(response.text)
    assert len(frames) == 3
    assert frames[0]["event"] == "status"
    assert frames[1]["event"] == "final"
    assert frames[2]["data"] == "[DONE]"

    final_payload = json.loads(frames[1]["data"])
    assert final_payload["status"] == "final"
    assert final_payload["response"] == "legacy fallback response"
    assert final_payload["provenance"]["source"] == "legacy_graph"


def test_stream_does_not_call_stream_assistant_v2_when_runtime_enabled(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stream success path should use invoke_runtime_v3, NOT stream_assistant_v2."""

    invoke_calls = 0

    async def fake_invoke_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
        nonlocal invoke_calls
        invoke_calls += 1
        _ = payload
        return JSONResponse(
            status_code=200,
            content={
                "status": "final",
                "session_id": "sess-no-v2",
                "trace_id": "trace-no-v2",
                "response": "direct v3",
                "safety": {"risk_level": "low", "matched_rules": []},
                "runtime_events": [],
                "provenance": {"source": "v3_primary"},
                "trace": {"request_id": "req-no-v2"},
            },
        )

    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.invoke_runtime_v3",
        fake_invoke_v3,
    )

    response = client.post(
        "/assistant/v3/stream",
        json={
            "request_id": "req-no-v2",
            "session_id": "sess-no-v2",
            "trace_id": "trace-no-v2",
            "text": "头痛",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert invoke_calls == 1
    frames = _parse_sse_frames(response.text)
    final_payload = json.loads(frames[1]["data"])
    assert final_payload["response"] == "direct v3"
