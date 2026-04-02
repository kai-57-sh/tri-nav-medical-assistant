"""Redis-backed persistence adapter for TriNav v3 runtime events."""

from __future__ import annotations

import json
from typing import Any

from typing import TYPE_CHECKING

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
        if await self._append_atomically(session_id=session_id, event=event):
            return

        await self._append_with_read_modify_write(session_id=session_id, event=event)

    async def _append_atomically(self, session_id: str, event: dict[str, Any]) -> bool:
        redis_client = getattr(self._redis, "redis", None)
        is_healthy = bool(getattr(self._redis, "is_healthy", False))
        if not is_healthy or redis_client is None:
            return False

        redis_key = f"cache:events:{session_id}"
        encoded_event = json.dumps(dict(event), ensure_ascii=False)
        try:
            pipeline = redis_client.pipeline()
            pipeline.rpush(redis_key, encoded_event)
            pipeline.ltrim(redis_key, -self._MAX_EVENTS_PER_SESSION, -1)
            pipeline.expire(redis_key, self._TTL_SECONDS)
            await pipeline.execute()
            return True
        except Exception:
            # Graceful degradation: fall back to non-atomic adapter API.
            return False

    async def _append_with_read_modify_write(self, session_id: str, event: dict[str, Any]) -> None:
        cache_key = f"events:{session_id}"
        cached = await self._redis.load_cached_result(cache_key)
        history: list[dict[str, Any]] = []
        if isinstance(cached, dict):
            events = cached.get("events")
            if isinstance(events, list):
                history = [dict(item) for item in events if isinstance(item, dict)]
        history.append(dict(event))
        if len(history) > self._MAX_EVENTS_PER_SESSION:
            history = history[-self._MAX_EVENTS_PER_SESSION :]

        await self._redis.cache_external_result(
            cache_key=cache_key,
            result={"events": history},
            ttl=self._TTL_SECONDS,
        )
