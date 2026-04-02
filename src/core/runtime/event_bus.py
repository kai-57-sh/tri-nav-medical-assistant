"""In-memory runtime event bus for TriNav v2 orchestration."""

from typing import cast

from src.core.runtime.types import JSONValue, RuntimeEvent


class EventBus:
    """Collect runtime events and expose serializable snapshots."""

    def __init__(self) -> None:
        self._events: list[RuntimeEvent] = []

    def emit(self, event: RuntimeEvent) -> None:
        """Append a runtime event to the bus."""

        self._events.append(event)

    def emit_runtime_event(
        self,
        *,
        event_type: str,
        request_id: str,
        session_id: str,
        data: dict[str, JSONValue] | None = None,
    ) -> RuntimeEvent:
        """Create and emit a runtime event in one call."""

        event = RuntimeEvent(
            event_type=event_type,
            request_id=request_id,
            session_id=session_id,
            data={} if data is None else data,
        )
        self.emit(event)
        return event

    def dump(self) -> list[dict[str, JSONValue]]:
        """Return all events as plain dictionaries."""

        return cast(
            list[dict[str, JSONValue]],
            [event.model_dump(mode="json") for event in self._events],
        )
