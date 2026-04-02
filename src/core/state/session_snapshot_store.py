"""In-memory session snapshot persistence for TriNav v3."""

from __future__ import annotations

from typing import Any


class InMemorySnapshotStore:
    """Store last known session snapshot in process memory."""

    def __init__(self) -> None:
        self._snapshots: dict[str, dict[str, Any]] = {}

    def upsert(self, session_id: str, snapshot: dict[str, Any]) -> None:
        """Insert or replace one session snapshot using copy-on-write semantics."""

        self._snapshots[session_id] = dict(snapshot)

    def load(self, session_id: str) -> dict[str, Any] | None:
        """Load one snapshot by session id, returning a copy when present."""

        snapshot = self._snapshots.get(session_id)
        if snapshot is None:
            return None
        return dict(snapshot)
