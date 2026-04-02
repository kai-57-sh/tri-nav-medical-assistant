import asyncio
import json
from typing import Any

import pytest

from src.core.state.redis_event_store import RedisEventStore


class _FakePipeline:
    def __init__(self, redis: "_FakeRedisClient", *, fail_execute: bool = False) -> None:
        self._redis = redis
        self._fail_execute = fail_execute
        self._ops: list[tuple[str, tuple[Any, ...]]] = []

    def rpush(self, key: str, value: str) -> "_FakePipeline":
        self._ops.append(("rpush", (key, value)))
        return self

    def ltrim(self, key: str, start: int, end: int) -> "_FakePipeline":
        self._ops.append(("ltrim", (key, start, end)))
        return self

    def expire(self, key: str, ttl: int) -> "_FakePipeline":
        self._ops.append(("expire", (key, ttl)))
        return self

    async def execute(self) -> list[bool]:
        if self._fail_execute:
            raise RuntimeError("pipeline execute failed")

        for op, args in self._ops:
            if op == "rpush":
                key, value = args
                self._redis._lists.setdefault(key, []).append(value)
            elif op == "ltrim":
                key, start, end = args
                values = self._redis._lists.get(key, [])
                self._redis._lists[key] = values[start : end + 1 if end != -1 else None]
            elif op == "expire":
                key, ttl = args
                self._redis._ttl_by_key[key] = ttl
        return [True for _ in self._ops]


class _FakeRedisClient:
    def __init__(self) -> None:
        self._lists: dict[str, list[str]] = {}
        self._ttl_by_key: dict[str, int] = {}
        self.fail_pipeline_execute = False

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self, fail_execute=self.fail_pipeline_execute)

    async def rpush(self, key: str, value: str) -> int:
        self._lists.setdefault(key, []).append(value)
        return len(self._lists[key])

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        values = self._lists.get(key, [])
        self._lists[key] = values[start : end + 1 if end != -1 else None]
        return True

    async def expire(self, key: str, ttl: int) -> bool:
        self._ttl_by_key[key] = ttl
        return True


class _BaseFakeRedisService:
    def __init__(self) -> None:
        self.redis = _FakeRedisClient()
        self.is_healthy = True
        self.load_cached_result = None
        self.cache_external_result = None


class _SimpleRedisService(_BaseFakeRedisService):
    pass


@pytest.mark.asyncio
async def test_redis_event_store_append_is_atomic_under_concurrency() -> None:
    fake = _SimpleRedisService()
    store = RedisEventStore(fake)

    await asyncio.gather(
        store.append("sess-1", {"event_type": "runtime_started", "id": "a"}),
        store.append("sess-1", {"event_type": "capability_completed", "id": "b"}),
    )

    encoded_events = fake.redis._lists.get("cache:events:sess-1", [])
    persisted_events = [json.loads(item) for item in encoded_events]
    assert len(persisted_events) == 2
    assert {event["id"] for event in persisted_events} == {"a", "b"}


@pytest.mark.asyncio
async def test_redis_event_store_trims_event_history_to_default_cap() -> None:
    fake = _SimpleRedisService()
    store = RedisEventStore(fake)

    for idx in range(205):
        await store.append("sess-1", {"event_type": "runtime_progress", "seq": idx})

    encoded_events = fake.redis._lists.get("cache:events:sess-1", [])
    persisted_events = [json.loads(item) for item in encoded_events]

    assert len(persisted_events) == 200
    assert persisted_events[0]["seq"] == 5
    assert persisted_events[-1]["seq"] == 204
    assert fake.redis._ttl_by_key["cache:events:sess-1"] == 3600


@pytest.mark.asyncio
async def test_redis_event_store_preserves_list_history_when_pipeline_fails() -> None:
    fake = _SimpleRedisService()
    store = RedisEventStore(fake)

    await store.append("sess-1", {"event_type": "runtime_started", "id": "a"})
    fake.redis.fail_pipeline_execute = True
    await store.append("sess-1", {"event_type": "capability_completed", "id": "b"})

    encoded_events = fake.redis._lists.get("cache:events:sess-1", [])
    persisted_events = [json.loads(item) for item in encoded_events]
    assert len(persisted_events) == 2
    assert [event["id"] for event in persisted_events] == ["a", "b"]


@pytest.mark.asyncio
async def test_redis_event_store_falls_back_gracefully_when_redis_unavailable(mocker) -> None:
    fake = mocker.AsyncMock()
    fake.redis = None
    fake.is_healthy = False
    fake.load_cached_result.side_effect = AssertionError("should not read string cache fallback")
    fake.cache_external_result.side_effect = AssertionError("should not write string cache fallback")
    store = RedisEventStore(fake)

    await store.append("sess-1", {"event_type": "runtime_started", "message": "启动"})

    fake.load_cached_result.assert_not_called()
    fake.cache_external_result.assert_not_called()
