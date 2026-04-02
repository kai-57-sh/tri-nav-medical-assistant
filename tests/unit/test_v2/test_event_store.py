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


def test_event_store_prunes_old_events_and_sessions_when_caps_exceeded() -> None:
    """Store should retain newest data when retention caps are reached."""

    store = InMemoryEventStore(max_sessions=2, max_events_per_session=2)

    store.append("sess-a", {"idx": 1})
    store.append("sess-a", {"idx": 2})
    store.append("sess-a", {"idx": 3})
    assert store.list("sess-a") == [{"idx": 2}, {"idx": 3}]

    store.append("sess-b", {"idx": 10})
    store.append("sess-c", {"idx": 20})

    assert store.list("sess-a") == []
    assert store.list("sess-b") == [{"idx": 10}]
    assert store.list("sess-c") == [{"idx": 20}]
