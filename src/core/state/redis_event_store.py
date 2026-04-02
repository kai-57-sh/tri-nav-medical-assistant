"""Redis-backed persistence adapter for TriNav v3 runtime events."""

from __future__ import annotations

import json
from typing import Any

from typing import TYPE_CHECKING

from redis.exceptions import RedisError

if TYPE_CHECKING:
    from src.services import RedisService


class RedisEventStore:
    """Persist session runtime events in Redis cache with append semantics."""

    _TTL_SECONDS = 3600
    _MAX_EVENTS_PER_SESSION = 200

    def __init__(self, redis_service: "RedisService") -> None:
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
        load_cached_result = getattr(self._redis, "load_cached_result", None)
        if not callable(load_cached_result):
            return False

        try:
            legacy_payload = await load_cached_result(f"events:{session_id}")
        except (RedisError, RuntimeError, AttributeError, TypeError):
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

    def _is_wrongtype_error(self, error: Exception | None) -> bool:
        if error is None:
            return False
        return "WRONGTYPE" in str(error).upper()
