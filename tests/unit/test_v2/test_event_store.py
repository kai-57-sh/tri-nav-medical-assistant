"""Unit tests for runtime event storage."""

from src.core.state.event_store import InMemoryEventStore


def test_event_store_append_and_list_by_session() -> None:
    """Store should keep append order and isolate events per session."""

    store = InMemoryEventStore()

    first = {"event_type": "runtime_started", "request_id": "req-1"}
    second = {"event_type": "runtime_finished", "request_id": "req-1"}
    other = {"event_type": "runtime_started", "request_id": "req-2"}

    store.append("sess-a", first)
    store.append("sess-a", second)
    store.append("sess-b", other)

    assert store.list("sess-a") == [first, second]
    assert store.list("sess-b") == [other]


def test_event_store_list_unknown_session_returns_empty_list() -> None:
    """Unknown session should return an empty list."""

    store = InMemoryEventStore()

    assert store.list("missing-session") == []
