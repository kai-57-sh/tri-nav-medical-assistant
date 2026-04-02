from src.core.state.session_snapshot_store import InMemorySnapshotStore


def test_snapshot_store_upsert_and_load() -> None:
    store = InMemorySnapshotStore()
    store.upsert("sess-1", {"triage_level": "URGENT"})
    assert store.load("sess-1") == {"triage_level": "URGENT"}


def test_snapshot_store_returns_copies() -> None:
    store = InMemorySnapshotStore()
    payload = {"triage_level": "URGENT"}

    store.upsert("sess-1", payload)
    payload["triage_level"] = "LOW"

    loaded = store.load("sess-1")
    assert loaded == {"triage_level": "URGENT"}

    loaded["triage_level"] = "LOW"
    assert store.load("sess-1") == {"triage_level": "URGENT"}
