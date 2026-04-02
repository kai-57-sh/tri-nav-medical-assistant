"""In-memory store for runtime events keyed by session."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any


class InMemoryEventStore:
    """Persist runtime event snapshots in process memory."""

    def __init__(
        self,
        *,
        max_sessions: int = 1000,
        max_events_per_session: int = 200,
    ) -> None:
        self._max_sessions = max_sessions
        self._max_events_per_session = max_events_per_session
        self._events_by_session: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()

    def append(self, session_id: str, event: dict[str, Any]) -> None:
        """Append one event for a session."""

        session_events = self._events_by_session.get(session_id)
        if session_events is None:
            session_events = []
            self._events_by_session[session_id] = session_events
        else:
            self._events_by_session.move_to_end(session_id)

        session_events.append(dict(event))
        if len(session_events) > self._max_events_per_session:
            del session_events[: len(session_events) - self._max_events_per_session]

        while len(self._events_by_session) > self._max_sessions:
            self._events_by_session.popitem(last=False)

    def list(self, session_id: str) -> list[dict[str, Any]]:
        """Return a copy of session events in append order."""

        return [dict(event) for event in self._events_by_session.get(session_id, [])]

    def session_count(self) -> int:
        """Return number of sessions currently tracked in memory."""

        return len(self._events_by_session)

    def event_count(self) -> int:
        """Return total number of buffered runtime events."""

        return sum(len(events) for events in self._events_by_session.values())
