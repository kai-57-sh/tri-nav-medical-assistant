"""Redis-backed persistence adapter for TriNav v3 runtime events."""

from __future__ import annotations

from typing import Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services import RedisService


class RedisEventStore:
    """Persist session runtime events in Redis cache with append semantics."""

    def __init__(self, redis_service: "RedisService") -> None:
        self._redis = redis_service

    async def append(self, session_id: str, event: dict[str, Any]) -> None:
        """Append one event into the cached session history."""

        cache_key = f"events:{session_id}"
        cached = await self._redis.load_cached_result(cache_key)
        history: list[dict[str, Any]] = []
        if isinstance(cached, dict):
            events = cached.get("events")
            if isinstance(events, list):
                history = [dict(item) for item in events if isinstance(item, dict)]
        history.append(dict(event))

        await self._redis.cache_external_result(
            cache_key=cache_key,
            result={"events": history},
            ttl=3600,
        )
