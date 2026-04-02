"""In-memory store for runtime events keyed by session."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class InMemoryEventStore:
    """Persist runtime event snapshots in process memory."""

    def __init__(self) -> None:
        self._events_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def append(self, session_id: str, event: dict[str, Any]) -> None:
        """Append one event for a session."""

        self._events_by_session[session_id].append(dict(event))

    def list(self, session_id: str) -> list[dict[str, Any]]:
        """Return a copy of session events in append order."""

        return [dict(event) for event in self._events_by_session.get(session_id, [])]
