"""Tests for assistant v3 SSE stream route."""

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

os.environ.setdefault("QWEN_API_KEY", "test-key")

from src.core.runtime.types import CapabilityResult
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
                "request_id": "req-test-v3",
                "session_id": "sess-test-v3",
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


def test_assistant_v3_stream_returns_ordered_sse_frames(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V3 stream should keep v2 SSE order and final payload shape."""

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

    async def fake_invoke(payload):  # type: ignore[no-untyped-def]
        _ = payload
        raise RuntimeError("stream boom")

    monkeypatch.setattr("src.interfaces.api.assistant_v2.invoke_assistant_v2", fake_invoke)

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
    assert final_payload["error_message"] == "assistant_v2_stream_failed"


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
        raise AssertionError("stream path should not execute invoke_assistant_v2 when runtime is disabled")

    monkeypatch.setattr("src.interfaces.api.assistant_v2.invoke_assistant_v2", fail_invoke)

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
