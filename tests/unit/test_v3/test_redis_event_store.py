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
                await self._redis.rpush(key, value)
            elif op == "ltrim":
                key, start, end = args
                await self._redis.ltrim(key, start, end)
            elif op == "expire":
                key, ttl = args
                await self._redis.expire(key, ttl)
        return [True for _ in self._ops]


class _FakeRedisClient:
    def __init__(self) -> None:
        self._lists: dict[str, list[str]] = {}
        self._string_values: dict[str, str] = {}
        self._ttl_by_key: dict[str, int] = {}
        self.fail_pipeline_execute = False
        self.eval_supported = True
        self.fail_eval = False
        self.eval_calls: list[tuple[str, int, str, str]] = []
        self.get_calls: list[str] = []

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self, fail_execute=self.fail_pipeline_execute)

    def set_string(self, key: str, value: str) -> None:
        self._string_values[key] = value

    async def set(
        self, key: str, value: str, *, nx: bool = False, ex: int | None = None
    ) -> bool | None:
        if nx and (key in self._string_values or key in self._lists):
            return None
        self._string_values[key] = value
        if ex is not None:
            self._ttl_by_key[key] = ex
        return True

    async def get(self, key: str) -> str | None:
        self.get_calls.append(key)
        return self._string_values.get(key)

    async def eval(self, script: str, numkeys: int, key: str, token: str) -> int:
        if not self.eval_supported:
            raise AttributeError("eval unsupported")
        if self.fail_eval:
            raise RuntimeError("eval failed")
        self.eval_calls.append((script, numkeys, key, token))
        if self._string_values.get(key) == token:
            del self._string_values[key]
            return 1
        return 0

    async def delete(self, key: str) -> int:
        deleted = 0
        if key in self._lists:
            del self._lists[key]
            deleted += 1
        if key in self._string_values:
            del self._string_values[key]
            deleted += 1
        return deleted

    async def rpush(self, key: str, value: str) -> int:
        if key in self._string_values:
            raise RuntimeError("WRONGTYPE Operation against a key holding the wrong kind of value")
        self._lists.setdefault(key, []).append(value)
        return len(self._lists[key])

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        if key in self._string_values:
            raise RuntimeError("WRONGTYPE Operation against a key holding the wrong kind of value")
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


class _SimpleRedisService(_BaseFakeRedisService):
    pass


class _LegacyMigrationRedisService(_BaseFakeRedisService):
    def __init__(self) -> None:
        super().__init__()
        self.load_cached_result_calls: list[str] = []
        self._legacy_payload = {
            "events": [{"event_type": "runtime_started", "id": "legacy-a"}]
        }

    async def load_cached_result(self, cache_key: str) -> dict[str, Any] | None:
        self.load_cached_result_calls.append(cache_key)
        return self._legacy_payload


class _ContendedLegacyMigrationRedisService(_LegacyMigrationRedisService):
    def __init__(self) -> None:
        super().__init__()
        self._load_call_count = 0
        self._second_load_called = asyncio.Event()
        self._migration_hold_timeout_seconds = 0.35

    async def load_cached_result(self, cache_key: str) -> dict[str, Any] | None:
        self.load_cached_result_calls.append(cache_key)
        self._load_call_count += 1
        if self._load_call_count == 1:
            try:
                await asyncio.wait_for(
                    self._second_load_called.wait(),
                    timeout=self._migration_hold_timeout_seconds,
                )
            except TimeoutError:
                pass
        else:
            self._second_load_called.set()
        return self._legacy_payload


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
async def test_redis_event_store_migrates_legacy_string_key_and_appends() -> None:
    fake = _LegacyMigrationRedisService()
    fake.redis.set_string("cache:events:sess-1", '{"events":[{"event_type":"legacy"}]}')
    store = RedisEventStore(fake)

    await store.append("sess-1", {"event_type": "capability_completed", "id": "new-b"})

    encoded_events = fake.redis._lists.get("cache:events:sess-1", [])
    persisted_events = [json.loads(item) for item in encoded_events]
    assert [event["id"] for event in persisted_events] == ["legacy-a", "new-b"]
    assert fake.redis._ttl_by_key["cache:events:sess-1"] == 3600
    assert "cache:events:sess-1" not in fake.redis._string_values
    assert fake.load_cached_result_calls == ["events:sess-1"]


@pytest.mark.asyncio
async def test_redis_event_store_uses_eval_for_atomic_lock_release() -> None:
    fake = _LegacyMigrationRedisService()
    fake.redis.set_string("cache:events:sess-1", '{"events":[{"event_type":"legacy"}]}')
    store = RedisEventStore(fake)

    await store.append("sess-1", {"event_type": "capability_completed", "id": "new-b"})

    assert any(call[2] == "lock:events:migrate:sess-1" for call in fake.redis.eval_calls)
    assert "lock:events:migrate:sess-1" not in fake.redis.get_calls


@pytest.mark.asyncio
async def test_redis_event_store_migration_is_concurrency_safe() -> None:
    fake = _ContendedLegacyMigrationRedisService()
    fake.redis.set_string("cache:events:sess-1", '{"events":[{"event_type":"legacy"}]}')
    store = RedisEventStore(fake)

    await asyncio.gather(
        store.append("sess-1", {"event_type": "capability_completed", "id": "new-a"}),
        store.append("sess-1", {"event_type": "capability_completed", "id": "new-b"}),
    )

    encoded_events = fake.redis._lists.get("cache:events:sess-1", [])
    persisted_events = [json.loads(item) for item in encoded_events]
    assert len(persisted_events) == 3
    assert {event["id"] for event in persisted_events} == {"legacy-a", "new-a", "new-b"}


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
