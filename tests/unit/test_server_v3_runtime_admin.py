"""Tests for v3 runtime admin endpoints."""

import os
from types import SimpleNamespace
from typing import Any

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest

os.environ.setdefault("QWEN_API_KEY", "test-key")

from src.core.runtime.types import CapabilityResult
from src.platform.state.replay_service import SessionNotResumableError, SessionReplayNotFoundError
from src.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _mock_runtime_run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: CapabilityResult,
    runtime_events: list[dict[str, Any]] | None = None,
) -> None:
    async def fake_run(self, context):  # type: ignore[no-untyped-def]
        _ = self
        _ = context
        return [result]

    def fake_dump(self):  # type: ignore[no-untyped-def]
        _ = self
        if runtime_events is not None:
            return runtime_events
        return [
            {
                "event_type": "runtime_finished",
                "request_id": "req-test-v3-admin",
                "session_id": "sess-test-v3-admin",
                "data": {"capabilities_executed": 1, "success": result.success},
            }
        ]

    monkeypatch.setattr("src.core.runtime.query_engine.QueryEngine.run", fake_run)
    monkeypatch.setattr("src.core.runtime.event_bus.EventBus.dump", fake_dump)


def test_runtime_doctor_v3_returns_flags_and_dependency_health(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Doctor endpoint should expose runtime flags and redis health."""

    monkeypatch.setattr(
        "src.interfaces.api.runtime_admin_v3.get_settings",
        lambda: SimpleNamespace(v3_runtime_enabled=True, v3_shadow_compare_enabled=False),
    )

    async def fake_get_redis_service() -> Any:
        return SimpleNamespace(is_healthy=True)

    monkeypatch.setattr(
        "src.services.redis_service.get_redis_service",
        fake_get_redis_service,
    )
    monkeypatch.setattr(
        "src.interfaces.api.runtime_admin_v3.get_runtime_store_summary",
        lambda: {
            "sessions_with_events": 3,
            "total_runtime_events": 15,
            "sessions_with_snapshots": 2,
        },
    )

    response = client.get("/assistant/v3/runtime/doctor")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["runtime"]["v3_runtime_enabled"] is True
    assert body["runtime"]["v3_shadow_compare_enabled"] is False
    assert body["dependencies"]["redis"]["healthy"] is True
    assert body["observability"] == {
        "sessions_with_events": 3,
        "total_runtime_events": 15,
        "sessions_with_snapshots": 2,
    }


def test_runtime_replay_v3_returns_404_when_session_missing(client: TestClient) -> None:
    """Replay endpoint should return 404 for unknown session ids."""

    response = client.get("/assistant/v3/runtime/sessions/sess-missing/replay")

    assert response.status_code == 404
    assert response.json() == {"detail": "session_not_found"}


def test_runtime_plugins_v3_lists_registered_plugins(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plugin list endpoint should return coordinator plugin names."""

    monkeypatch.setattr(
        "src.interfaces.api.runtime_admin_v3.list_runtime_plugins",
        lambda: ["trace_metadata", "medical_footer"],
    )

    response = client.get("/assistant/v3/runtime/plugins")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "plugins": ["trace_metadata", "medical_footer"],
        "count": 2,
    }


def test_runtime_replay_v3_returns_snapshot_after_invoke(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replay endpoint should return persisted invoke snapshot and events."""

    _mock_runtime_run(
        monkeypatch,
        result=CapabilityResult(
            name="legacy_triage",
            success=True,
            payload={
                "status": "final",
                "session_id": "sess-replay-v3",
                "response": "mocked replay response",
            },
            provenance={"source": "legacy_graph"},
            errors=[],
        ),
        runtime_events=[
            {
                "event_type": "runtime_started",
                "request_id": "req-replay-v3",
                "session_id": "sess-replay-v3",
                "data": {},
            },
            {
                "event_type": "runtime_finished",
                "request_id": "req-replay-v3",
                "session_id": "sess-replay-v3",
                "data": {"capabilities_executed": 1, "success": True},
            },
        ],
    )

    invoke = client.post(
        "/assistant/v3/invoke",
        json={
            "request_id": "req-replay-v3",
            "session_id": "sess-replay-v3",
            "trace_id": "trace-replay-v3",
            "text": "持续咳嗽三天",
        },
        headers={"Content-Type": "application/json"},
    )
    assert invoke.status_code == 200

    replay = client.get("/assistant/v3/runtime/sessions/sess-replay-v3/replay")

    assert replay.status_code == 200
    body = replay.json()
    assert body["session_id"] == "sess-replay-v3"
    assert body["can_resume"] is True
    assert "resume_cursor" in body
    assert body["snapshot"]["status"] == "final"
    assert body["snapshot"]["response"] == "mocked replay response"
    assert isinstance(body["runtime_events"], list)
    assert body["runtime_events"][-1]["event_type"] == "runtime_finished"


def test_runtime_resume_v3_returns_404_when_session_missing(client: TestClient) -> None:
    """Resume endpoint should reject unknown session ids."""

    response = client.post(
        "/assistant/v3/runtime/sessions/sess-missing/resume",
        json={"text": "继续上次咨询"},
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "session_not_found"}


def test_runtime_resume_v3_delegates_to_v3_invoke(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resume endpoint should invoke v3 with path-derived session id."""

    class _ReplayServiceStub:
        async def replay(self, session_id: str) -> dict[str, Any]:
            return {
                "session_id": session_id,
                "snapshot": {"status": "need_more_info"},
                "runtime_events": [{"event_type": "runtime_finished"}],
                "resume_cursor": {"event_offset": 1},
                "can_resume": True,
            }

        async def resume(self, session_id: str) -> dict[str, Any]:
            return await self.replay(session_id)

    monkeypatch.setattr("src.interfaces.api.runtime_admin_v3._REPLAY_SERVICE", _ReplayServiceStub())

    async def fake_invoke(payload):  # type: ignore[no-untyped-def]
        assert payload.session_id == "sess-resume-v3"
        assert payload.text == "补充信息：没有发热"
        return JSONResponse(
            status_code=200,
            content={
                "status": "need_more_info",
                "session_id": payload.session_id,
                "trace_id": payload.trace_id,
                "response": "请继续补充症状细节",
                "runtime_events": [],
                "provenance": {"source": "assistant_v3"},
                "trace": {"request_id": payload.request_id},
            },
        )

    monkeypatch.setattr("src.interfaces.api.runtime_admin_v3.invoke_assistant_v3", fake_invoke)

    response = client.post(
        "/assistant/v3/runtime/sessions/sess-resume-v3/resume",
        json={"text": "补充信息：没有发热"},
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "need_more_info"
    assert body["session_id"] == "sess-resume-v3"
    assert body["response"] == "请继续补充症状细节"


def test_runtime_replay_v3_returns_404_when_service_reports_missing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replay endpoint should preserve 404 contract on service-layer misses."""

    class _ReplayServiceMissing:
        async def replay(self, session_id: str) -> dict[str, Any]:
            _ = session_id
            raise SessionReplayNotFoundError("session_not_found")

        async def resume(self, session_id: str) -> dict[str, Any]:
            _ = session_id
            raise SessionReplayNotFoundError("session_not_found")

    monkeypatch.setattr(
        "src.interfaces.api.runtime_admin_v3._REPLAY_SERVICE",
        _ReplayServiceMissing(),
    )

    replay = client.get("/assistant/v3/runtime/sessions/sess-missing-service/replay")
    resume = client.post(
        "/assistant/v3/runtime/sessions/sess-missing-service/resume",
        json={"text": "继续"},
        headers={"Content-Type": "application/json"},
    )

    assert replay.status_code == 404
    assert replay.json() == {"detail": "session_not_found"}
    assert resume.status_code == 404
    assert resume.json() == {"detail": "session_not_found"}


def test_runtime_resume_v3_returns_409_when_session_not_resumable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resume endpoint should map non-resumable sessions to a stable 409 response."""

    class _ReplayServiceNotResumable:
        async def replay(self, session_id: str) -> dict[str, Any]:
            _ = session_id
            return {
                "session_id": "sess-no-resume",
                "snapshot": None,
                "runtime_events": [{"event_type": "runtime_finished"}],
                "resume_cursor": {"event_offset": 1},
                "can_resume": False,
            }

        async def resume(self, session_id: str) -> dict[str, Any]:
            _ = session_id
            raise SessionNotResumableError("session_not_resumable")

    monkeypatch.setattr(
        "src.interfaces.api.runtime_admin_v3._REPLAY_SERVICE",
        _ReplayServiceNotResumable(),
    )

    response = client.post(
        "/assistant/v3/runtime/sessions/sess-no-resume/resume",
        json={"text": "继续"},
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "session_not_resumable"}
