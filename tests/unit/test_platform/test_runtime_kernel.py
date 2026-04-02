"""RuntimeKernel integration tests."""

import os
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient
import pytest

os.environ.setdefault("QWEN_API_KEY", "test-key")

from src.core.runtime.types import CapabilityResult
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
