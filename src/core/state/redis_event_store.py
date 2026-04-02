"""Redis-backed persistence adapter for TriNav v3 runtime events."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import TYPE_CHECKING, Any

from redis.exceptions import RedisError

if TYPE_CHECKING:
    from src.services import RedisService


class RedisEventStore:
    """Persist session runtime events in Redis cache with append semantics."""

    _TTL_SECONDS = 3600
    _MAX_EVENTS_PER_SESSION = 200
    _MIGRATION_LOCK_SECONDS = 5
    _MIGRATION_RETRY_DELAY_SECONDS = 0.01
    _MIGRATION_RETRY_TIMEOUT_BUFFER_SECONDS = 1.0
    _LOCK_RELEASE_CAS_LUA = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "return redis.call('del', KEYS[1]) "
        "else return 0 end"
    )

    def __init__(self, redis_service: RedisService) -> None:
        self._redis = redis_service

    async def append(self, session_id: str, event: dict[str, Any]) -> None:
        """Append one event into the cached session history."""
        redis_client = getattr(self._redis, "redis", None)
        is_healthy = bool(getattr(self._redis, "is_healthy", False))
        if not is_healthy or redis_client is None:
            return

        atomic_ok, atomic_error = await self._append_atomically(
            redis_client=redis_client, session_id=session_id, event=event
        )
        if atomic_ok:
            return

        fallback_ok, fallback_error = await self._append_without_pipeline(
            redis_client=redis_client, session_id=session_id, event=event
        )
        if fallback_ok:
            return

        if self._is_wrongtype_error(atomic_error) or self._is_wrongtype_error(fallback_error):
            await self._migrate_legacy_key_and_append(
                redis_client=redis_client, session_id=session_id, event=event
            )

    async def _append_atomically(
        self, redis_client: Any, session_id: str, event: dict[str, Any]
    ) -> tuple[bool, Exception | None]:
        redis_key = f"cache:events:{session_id}"
        encoded_event = json.dumps(dict(event), ensure_ascii=False)
        try:
            pipeline = redis_client.pipeline()
            pipeline.rpush(redis_key, encoded_event)
            pipeline.ltrim(redis_key, -self._MAX_EVENTS_PER_SESSION, -1)
            pipeline.expire(redis_key, self._TTL_SECONDS)
            await pipeline.execute()
            return True, None
        except (RedisError, RuntimeError, AttributeError, TypeError) as exc:
            # Graceful degradation: attempt non-pipeline list operations.
            return False, exc

    async def _append_without_pipeline(
        self, redis_client: Any, session_id: str, event: dict[str, Any]
    ) -> tuple[bool, Exception | None]:
        redis_key = f"cache:events:{session_id}"
        encoded_event = json.dumps(dict(event), ensure_ascii=False)
        try:
            await redis_client.rpush(redis_key, encoded_event)
            await redis_client.ltrim(redis_key, -self._MAX_EVENTS_PER_SESSION, -1)
            await redis_client.expire(redis_key, self._TTL_SECONDS)
            return True, None
        except (RedisError, RuntimeError, AttributeError, TypeError) as exc:
            # Final graceful degradation: drop this event rather than risk corrupting key type.
            return False, exc

    async def _migrate_legacy_key_and_append(
        self, redis_client: Any, session_id: str, event: dict[str, Any]
    ) -> bool:
        lock_key = f"lock:events:migrate:{session_id}"
        lock_token = await self._acquire_migration_lock(redis_client=redis_client, lock_key=lock_key)
        if lock_token is None:
            return await self._retry_append_after_migration(
                redis_client=redis_client, session_id=session_id, event=event
            )

        load_cached_result = getattr(self._redis, "load_cached_result", None)
        if not callable(load_cached_result):
            await self._release_migration_lock(
                redis_client=redis_client, lock_key=lock_key, lock_token=lock_token
            )
            return False

        try:
            legacy_payload = await load_cached_result(f"events:{session_id}")
        except (RedisError, RuntimeError, AttributeError, TypeError):
            await self._release_migration_lock(
                redis_client=redis_client, lock_key=lock_key, lock_token=lock_token
            )
            return False

        history: list[dict[str, Any]] = []
        if isinstance(legacy_payload, dict):
            legacy_events = legacy_payload.get("events")
            if isinstance(legacy_events, list):
                history = [dict(item) for item in legacy_events if isinstance(item, dict)]

        history.append(dict(event))
        if len(history) > self._MAX_EVENTS_PER_SESSION:
            history = history[-self._MAX_EVENTS_PER_SESSION :]

        redis_key = f"cache:events:{session_id}"
        encoded_events = [json.dumps(item, ensure_ascii=False) for item in history]
        try:
            await redis_client.delete(redis_key)
            for encoded_event in encoded_events:
                await redis_client.rpush(redis_key, encoded_event)
            await redis_client.ltrim(redis_key, -self._MAX_EVENTS_PER_SESSION, -1)
            await redis_client.expire(redis_key, self._TTL_SECONDS)
            return True
        except (RedisError, RuntimeError, AttributeError, TypeError):
            return False
        finally:
            await self._release_migration_lock(
                redis_client=redis_client, lock_key=lock_key, lock_token=lock_token
            )

    def _is_wrongtype_error(self, error: Exception | None) -> bool:
        if error is None:
            return False
        return "WRONGTYPE" in str(error).upper()

    async def _acquire_migration_lock(self, redis_client: Any, lock_key: str) -> str | None:
        lock_set = getattr(redis_client, "set", None)
        if not callable(lock_set):
            return None

        lock_token = str(uuid.uuid4())
        try:
            acquired = await lock_set(
                lock_key,
                lock_token,
                nx=True,
                ex=self._MIGRATION_LOCK_SECONDS,
            )
        except (RedisError, RuntimeError, AttributeError, TypeError):
            return None

        if not acquired:
            return None
        return lock_token

    async def _release_migration_lock(
        self, redis_client: Any, lock_key: str, lock_token: str
    ) -> None:
        lock_eval = getattr(redis_client, "eval", None)
        if not callable(lock_eval):
            # Avoid non-atomic get+delete unlock; rely on lock TTL expiry.
            return

        try:
            await lock_eval(self._LOCK_RELEASE_CAS_LUA, 1, lock_key, lock_token)
        except (RedisError, RuntimeError, AttributeError, TypeError):
            # If CAS unlock fails, keep safety by waiting for TTL expiry.
            return

    async def _retry_append_after_migration(
        self, redis_client: Any, session_id: str, event: dict[str, Any]
    ) -> bool:
        retry_deadline = (
            asyncio.get_running_loop().time()
            + self._MIGRATION_LOCK_SECONDS
            + self._MIGRATION_RETRY_TIMEOUT_BUFFER_SECONDS
        )
        while True:
            append_ok, append_error = await self._append_without_pipeline(
                redis_client=redis_client, session_id=session_id, event=event
            )
            if append_ok:
                return True
            if not self._is_wrongtype_error(append_error):
                return False
            if asyncio.get_running_loop().time() >= retry_deadline:
                return False
            await asyncio.sleep(self._MIGRATION_RETRY_DELAY_SECONDS)
