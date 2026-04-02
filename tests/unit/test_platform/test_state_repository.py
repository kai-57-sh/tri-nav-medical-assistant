"""Unit tests for redis-first state repositories with memory fallback."""

from __future__ import annotations

import fnmatch
import json
from typing import Any

import pytest

from src.core.state.event_store import InMemoryEventStore
from src.core.state.session_snapshot_store import InMemorySnapshotStore
from src.platform.state.event_repository import RuntimeEventRepository, build_event_repository
from src.platform.state.snapshot_repository import RuntimeSnapshotRepository, build_snapshot_repository


class _FakeRedisClient:
    def __init__(self) -> None:
        self._lists: dict[str, list[str]] = {}
        self._strings: dict[str, str] = {}
        self._ttl: dict[str, int] = {}

    async def rpush(self, key: str, value: str) -> int:
        self._lists.setdefault(key, []).append(value)
        return len(self._lists[key])

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        values = self._lists.get(key, [])
        self._lists[key] = values[start : end + 1 if end != -1 else None]
        return True

    async def expire(self, key: str, ttl: int) -> bool:
        self._ttl[key] = ttl
        return True

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        values = self._lists.get(key, [])
        if end == -1:
            return values[start:]
        return values[start : end + 1]

    async def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        self._strings[key] = value
        self._ttl[key] = ttl
        return True

    async def get(self, key: str) -> str | None:
        return self._strings.get(key)

    async def scan_iter(self, *, match: str) -> Any:
        keys = set(self._lists) | set(self._strings)
        for key in keys:
            if fnmatch.fnmatch(key, match):
                yield key


class _FakeRedisService:
    def __init__(self, *, healthy: bool, client: _FakeRedisClient | None) -> None:
        self.is_healthy = healthy
        self.redis = client


@pytest.mark.asyncio
async def test_event_repository_falls_back_to_memory_when_redis_unavailable() -> None:
    fallback = InMemoryEventStore()
    repository = RuntimeEventRepository(
        memory_store=fallback,
        redis_service_provider=lambda: _FakeRedisService(healthy=False, client=None),
    )

    await repository.append("sess-fallback", {"event_type": "runtime_started", "seq": 1})

    assert await repository.list("sess-fallback") == [{"event_type": "runtime_started", "seq": 1}]
    assert await repository.session_count() == 1
    assert await repository.event_count() == 1


@pytest.mark.asyncio
async def test_event_repository_persists_across_instances_with_shared_backing_store() -> None:
    shared_memory = InMemoryEventStore()
    repository_a = build_event_repository(
        memory_store=shared_memory,
        redis_service_provider=lambda: None,
    )
    repository_b = build_event_repository(
        memory_store=shared_memory,
        redis_service_provider=lambda: None,
    )

    await repository_a.append("sess-shared", {"event_type": "runtime_finished", "seq": 9})

    assert await repository_b.list("sess-shared") == [{"event_type": "runtime_finished", "seq": 9}]


@pytest.mark.asyncio
async def test_event_repository_prefers_redis_data_over_memory_copy() -> None:
    shared_memory = InMemoryEventStore()
    shared_memory.append("sess-redis-first", {"event_type": "memory_only", "seq": 0})

    redis_client = _FakeRedisClient()
    redis_client._lists["cache:events:sess-redis-first"] = [
        json.dumps({"event_type": "redis", "seq": 1})
    ]

    repository = RuntimeEventRepository(
        memory_store=shared_memory,
        redis_service_provider=lambda: _FakeRedisService(healthy=True, client=redis_client),
    )

    assert await repository.list("sess-redis-first") == [{"event_type": "redis", "seq": 1}]


@pytest.mark.asyncio
async def test_snapshot_repository_round_trips_with_fallback_memory() -> None:
    shared_memory = InMemorySnapshotStore()
    repository_a = build_snapshot_repository(
        memory_store=shared_memory,
        redis_service_provider=lambda: _FakeRedisService(healthy=False, client=None),
    )
    repository_b = build_snapshot_repository(
        memory_store=shared_memory,
        redis_service_provider=lambda: _FakeRedisService(healthy=False, client=None),
    )

    await repository_a.upsert("sess-snapshot", {"status": "final", "response": "ok"})

    assert await repository_b.load("sess-snapshot") == {"status": "final", "response": "ok"}
    assert await repository_b.count() == 1


@pytest.mark.asyncio
async def test_snapshot_repository_prefers_redis_data_over_memory_copy() -> None:
    shared_memory = InMemorySnapshotStore()
    shared_memory.upsert("sess-snapshot-redis", {"status": "memory"})

    redis_client = _FakeRedisClient()
    redis_client._strings["cache:snapshot:sess-snapshot-redis"] = json.dumps({"status": "redis"})

    repository = RuntimeSnapshotRepository(
        memory_store=shared_memory,
        redis_service_provider=lambda: _FakeRedisService(healthy=True, client=redis_client),
    )

    assert await repository.load("sess-snapshot-redis") == {"status": "redis"}
