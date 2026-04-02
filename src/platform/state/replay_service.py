"""Runtime replay/resume service backed by snapshot/event repositories."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.platform.state.event_repository import RuntimeEventRepository, build_event_repository
from src.platform.state.snapshot_repository import (
    RuntimeSnapshotRepository,
    build_snapshot_repository,
)


class SessionReplayNotFoundError(LookupError):
    """Raised when replay/resume is requested for an unknown session."""


class ReplayService:
    """Build replay payloads and validate session resume eligibility."""

    def __init__(
        self,
        *,
        event_repo: RuntimeEventRepository | None = None,
        snapshot_repo: RuntimeSnapshotRepository | None = None,
    ) -> None:
        self._event_repo = event_repo or build_event_repository()
        self._snapshot_repo = snapshot_repo or build_snapshot_repository()

    async def replay(self, session_id: str) -> dict[str, Any]:
        """Return replay data required by runtime admin endpoints."""

        snapshot = await self._snapshot_repo.load(session_id)
        runtime_events = await self._event_repo.list(session_id)
        if not runtime_events and isinstance(snapshot, dict):
            runtime_events = _copy_events(snapshot.get("runtime_events"))

        if snapshot is None and not runtime_events:
            raise SessionReplayNotFoundError(session_id)

        return {
            "session_id": session_id,
            "runtime_events": runtime_events,
            "snapshot": _copy_dict(snapshot),
            "resume_cursor": _build_resume_cursor(snapshot=snapshot, runtime_events=runtime_events),
            "can_resume": snapshot is not None,
        }

    async def resume(self, session_id: str) -> dict[str, Any]:
        """Validate one session can be resumed and return replay metadata."""

        return await self.replay(session_id)


def _copy_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return deepcopy(value)
    return None


def _copy_events(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [deepcopy(item) for item in value if isinstance(item, dict)]


def _build_resume_cursor(*, snapshot: dict[str, Any] | None, runtime_events: list[dict[str, Any]]) -> dict[str, Any]:
    last_event = runtime_events[-1] if runtime_events else {}
    request_id = None
    trace_id = None
    snapshot_status = None
    if isinstance(snapshot, dict):
        request_id = snapshot.get("request_id") if isinstance(snapshot.get("request_id"), str) else None
        trace_id = snapshot.get("trace_id") if isinstance(snapshot.get("trace_id"), str) else None
        snapshot_status = snapshot.get("status") if isinstance(snapshot.get("status"), str) else None

    return {
        "event_offset": len(runtime_events),
        "last_event_type": last_event.get("event_type") if isinstance(last_event, dict) else None,
        "request_id": request_id,
        "trace_id": trace_id,
        "snapshot_status": snapshot_status,
    }


def build_replay_service(
    *,
    event_repo: RuntimeEventRepository | None = None,
    snapshot_repo: RuntimeSnapshotRepository | None = None,
) -> ReplayService:
    """Build replay service with shared repositories by default."""

    return ReplayService(
        event_repo=event_repo or build_event_repository(),
        snapshot_repo=snapshot_repo or build_snapshot_repository(),
    )
