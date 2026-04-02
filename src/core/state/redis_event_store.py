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

        if await self._append_atomically(redis_client=redis_client, session_id=session_id, event=event):
            return

        await self._append_without_pipeline(redis_client=redis_client, session_id=session_id, event=event)

    async def _append_atomically(self, redis_client: Any, session_id: str, event: dict[str, Any]) -> bool:
        redis_key = f"cache:events:{session_id}"
        encoded_event = json.dumps(dict(event), ensure_ascii=False)
        try:
            pipeline = redis_client.pipeline()
            pipeline.rpush(redis_key, encoded_event)
            pipeline.ltrim(redis_key, -self._MAX_EVENTS_PER_SESSION, -1)
            pipeline.expire(redis_key, self._TTL_SECONDS)
            await pipeline.execute()
            return True
        except (RedisError, RuntimeError, AttributeError, TypeError):
            # Graceful degradation: attempt non-pipeline list operations.
            return False

    async def _append_without_pipeline(self, redis_client: Any, session_id: str, event: dict[str, Any]) -> bool:
        redis_key = f"cache:events:{session_id}"
        encoded_event = json.dumps(dict(event), ensure_ascii=False)
        try:
            await redis_client.rpush(redis_key, encoded_event)
            await redis_client.ltrim(redis_key, -self._MAX_EVENTS_PER_SESSION, -1)
            await redis_client.expire(redis_key, self._TTL_SECONDS)
            return True
        except (RedisError, RuntimeError, AttributeError, TypeError):
            # Final graceful degradation: drop this event rather than risk corrupting key type.
            return False
