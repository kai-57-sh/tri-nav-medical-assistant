"""Redis-backed persistence adapter for TriNav v3 runtime events."""

from __future__ import annotations

import json
from typing import Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services import RedisService


class RedisEventStore:
    """Persist the latest runtime event for a session in Redis cache."""

    def __init__(self, redis_service: "RedisService") -> None:
        self._redis = redis_service

    async def append(self, session_id: str, event: dict[str, Any]) -> None:
        """Append one event by caching the latest serialized event payload."""

        await self._redis.cache_external_result(
            cache_key=f"events:{session_id}",
            result={"last_event": json.dumps(event, ensure_ascii=False)},
            ttl=3600,
        )
