"""Unit tests for runtime replay/resume service."""

from __future__ import annotations

from typing import Any

import pytest

from src.platform.state.replay_service import ReplayService, SessionReplayNotFoundError


class _FakeEventRepo:
    def __init__(self, events_by_session: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self._events_by_session = events_by_session or {}

    async def list(self, session_id: str) -> list[dict[str, Any]]:
        return list(self._events_by_session.get(session_id, []))


class _FakeSnapshotRepo:
    def __init__(self, snapshots_by_session: dict[str, dict[str, Any]] | None = None) -> None:
        self._snapshots_by_session = snapshots_by_session or {}

    async def load(self, session_id: str) -> dict[str, Any] | None:
        return self._snapshots_by_session.get(session_id)


@pytest.mark.asyncio
async def test_replay_service_returns_resume_cursor() -> None:
    service = ReplayService(
        event_repo=_FakeEventRepo(
            {
                "sess-1": [
                    {"event_type": "runtime_started", "request_id": "req-1"},
                    {"event_type": "runtime_finished", "request_id": "req-1"},
                ]
            }
        ),
        snapshot_repo=_FakeSnapshotRepo(
            {
                "sess-1": {
                    "request_id": "req-1",
                    "trace_id": "trace-1",
                    "status": "final",
                }
            }
        ),
    )

    replay = await service.replay("sess-1")

    assert replay["session_id"] == "sess-1"
    assert replay["can_resume"] is True
    assert "resume_cursor" in replay
    assert replay["resume_cursor"]["event_offset"] == 2
    assert replay["resume_cursor"]["request_id"] == "req-1"


@pytest.mark.asyncio
async def test_replay_service_uses_snapshot_events_when_event_store_empty() -> None:
    service = ReplayService(
        event_repo=_FakeEventRepo(),
        snapshot_repo=_FakeSnapshotRepo(
            {
                "sess-2": {
                    "status": "need_more_info",
                    "runtime_events": [
                        {"event_type": "runtime_started"},
                        {"event_type": "runtime_finished"},
                    ],
                }
            }
        ),
    )

    replay = await service.replay("sess-2")

    assert [event["event_type"] for event in replay["runtime_events"]] == [
        "runtime_started",
        "runtime_finished",
    ]


@pytest.mark.asyncio
async def test_replay_service_raises_not_found_when_session_missing() -> None:
    service = ReplayService(event_repo=_FakeEventRepo(), snapshot_repo=_FakeSnapshotRepo())

    with pytest.raises(SessionReplayNotFoundError):
        await service.replay("sess-missing")


@pytest.mark.asyncio
async def test_resume_service_raises_not_found_when_session_missing() -> None:
    service = ReplayService(event_repo=_FakeEventRepo(), snapshot_repo=_FakeSnapshotRepo())

    with pytest.raises(SessionReplayNotFoundError):
        await service.resume("sess-missing")
