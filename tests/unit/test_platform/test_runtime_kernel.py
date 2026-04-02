"""RuntimeKernel integration tests."""

import os
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("QWEN_API_KEY", "test-key")

from src.core.runtime.types import CapabilityResult
from src.platform.runtime.kernel import RuntimeKernelInvokeError, RuntimeKernelInvokeResult
from src.platform.runtime.turn_loop import RuntimeTurnLoop
from src.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_assistant_v2_invoke_delegates_to_runtime_kernel(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """assistant_v2 invoke should delegate execution through RuntimeKernel."""

    calls = {"builder": 0, "invoke": 0}
    runtime_events = [
        {
            "event_type": "runtime_finished",
            "request_id": "req-test-kernel",
            "session_id": "sess-test-kernel",
            "data": {"capabilities_executed": 1, "success": True},
        }
    ]

    class FakeKernel:
        async def invoke(  # type: ignore[no-untyped-def]
            self,
            *,
            payload,
            request_id: str,
            session_id: str,
            trace_id: str,
        ) -> Any:
            calls["invoke"] += 1
            assert payload.text == "头痛两天"
            assert request_id == "req-test-kernel"
            assert session_id == "sess-test-kernel"
            assert trace_id == "trace-test-kernel"
            return SimpleNamespace(
                results=[
                    CapabilityResult(
                        name="legacy_triage",
                        success=True,
                        payload={
                            "status": "final",
                            "session_id": session_id,
                            "response": "kernel response",
                        },
                        provenance={"source": "runtime_kernel"},
                        errors=[],
                    )
                ],
                runtime_events=runtime_events,
            )

    def fake_build_runtime_kernel() -> FakeKernel:
        calls["builder"] += 1
        return FakeKernel()

    monkeypatch.setattr(
        "src.interfaces.api.assistant_v2.build_runtime_kernel",
        fake_build_runtime_kernel,
        raising=False,
    )

    response = client.post(
        "/assistant/v2/invoke",
        json={
            "request_id": "req-test-kernel",
            "session_id": "sess-test-kernel",
            "trace_id": "trace-test-kernel",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    data = response.json()
    assert calls == {"builder": 1, "invoke": 1}
    assert data["status"] == "final"
    assert data["response"] == "kernel response"
    assert data["runtime_events"] == runtime_events


def test_assistant_v2_invoke_returns_bootstrap_error_when_kernel_build_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kernel builder failures should return bootstrap-stage unavailable response."""

    def fake_build_runtime_kernel() -> Any:
        raise RuntimeError("kernel build boom")

    monkeypatch.setattr(
        "src.interfaces.api.assistant_v2.build_runtime_kernel",
        fake_build_runtime_kernel,
    )

    response = client.post(
        "/assistant/v2/invoke",
        json={
            "request_id": "req-bootstrap-error",
            "session_id": "sess-bootstrap-error",
            "trace_id": "trace-bootstrap-error",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert data["error_message"] == "assistant_v2_runtime_unavailable"
    assert data["trace"]["error_stage"] == "bootstrap"
    assert data["trace"]["error_type"] == "RuntimeError"


def test_assistant_v2_invoke_returns_kernel_runtime_events_on_invoke_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RuntimeKernelInvokeError should propagate attached runtime events."""

    runtime_events = [
        {
            "event_type": "runtime_started",
            "request_id": "req-kernel-error",
            "session_id": "sess-kernel-error",
            "data": {"path": "legacy"},
        }
    ]

    class FakeKernel:
        async def invoke(  # type: ignore[no-untyped-def]
            self,
            *,
            payload,
            request_id: str,
            session_id: str,
            trace_id: str,
        ) -> Any:
            _ = payload
            _ = request_id
            _ = session_id
            _ = trace_id
            raise RuntimeKernelInvokeError(
                message="assistant_v2_runtime_failed",
                runtime_events=runtime_events,
                error=RuntimeError("invoke boom"),
            )

    monkeypatch.setattr(
        "src.interfaces.api.assistant_v2.build_runtime_kernel",
        lambda: FakeKernel(),
    )

    response = client.post(
        "/assistant/v2/invoke",
        json={
            "request_id": "req-kernel-error",
            "session_id": "sess-kernel-error",
            "trace_id": "trace-kernel-error",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 503
    data = response.json()
    assert data["error_message"] == "assistant_v2_runtime_failed"
    assert data["trace"]["error_stage"] == "invoke"
    assert data["runtime_events"] == runtime_events


def test_assistant_v2_invoke_preserves_runtime_events_on_generic_exception(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generic invoke exceptions should preserve runtime_events when attached."""

    runtime_events = [
        {
            "event_type": "runtime_started",
            "request_id": "req-generic-error",
            "session_id": "sess-generic-error",
            "data": {"path": "legacy"},
        }
    ]

    class GenericKernelError(RuntimeError):
        def __init__(self) -> None:
            super().__init__("generic invoke boom")
            self.runtime_events = runtime_events

    class FakeKernel:
        async def invoke(  # type: ignore[no-untyped-def]
            self,
            *,
            payload,
            request_id: str,
            session_id: str,
            trace_id: str,
        ) -> Any:
            _ = payload
            _ = request_id
            _ = session_id
            _ = trace_id
            raise GenericKernelError()

    monkeypatch.setattr(
        "src.interfaces.api.assistant_v2.build_runtime_kernel",
        lambda: FakeKernel(),
    )

    response = client.post(
        "/assistant/v2/invoke",
        json={
            "request_id": "req-generic-error",
            "session_id": "sess-generic-error",
            "trace_id": "trace-generic-error",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 503
    data = response.json()
    assert data["error_message"] == "assistant_v2_runtime_failed"
    assert data["trace"]["error_stage"] == "invoke"
    assert data["runtime_events"] == runtime_events


@pytest.mark.asyncio
async def test_runtime_turn_loop_delegates_to_kernel_invoke() -> None:
    """Turn loop scaffold should delegate a turn directly to RuntimeKernel.invoke."""

    calls = {"invoke": 0}
    expected = RuntimeKernelInvokeResult(results=[], runtime_events=[])

    class FakeKernel:
        async def invoke(  # type: ignore[no-untyped-def]
            self,
            *,
            payload,
            request_id: str,
            session_id: str,
            trace_id: str,
        ) -> RuntimeKernelInvokeResult:
            calls["invoke"] += 1
            assert payload.text == "头痛两天"
            assert request_id == "req-turn-loop"
            assert session_id == "sess-turn-loop"
            assert trace_id == "trace-turn-loop"
            return expected

    payload = SimpleNamespace(
        text="头痛两天",
        image_base64=None,
        gps_lat=None,
        gps_lng=None,
        metadata={},
    )
    turn_loop = RuntimeTurnLoop(kernel=FakeKernel())
    result = await turn_loop.run_turn(
        payload=payload,
        request_id="req-turn-loop",
        session_id="sess-turn-loop",
        trace_id="trace-turn-loop",
    )

    assert calls == {"invoke": 1}
    assert result == expected
