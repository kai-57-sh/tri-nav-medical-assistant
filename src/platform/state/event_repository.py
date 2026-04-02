"""Redis-first runtime event repository with in-memory fallback."""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from typing import Any

from src.core.state.event_store import InMemoryEventStore

RedisServiceProvider = Callable[[], Any | Awaitable[Any]]

_EVENT_KEY_PREFIX = "cache:events:"
_DEFAULT_TTL_SECONDS = 3600
_DEFAULT_MAX_EVENTS_PER_SESSION = 200
_DEFAULT_MEMORY_EVENT_STORE = InMemoryEventStore()


async def _default_redis_service_provider() -> Any | None:
    try:
        from src.services import redis_service as redis_service_module
    except Exception:
        return None
    return getattr(redis_service_module, "_redis_service", None)


class RuntimeEventRepository:
    """Persist runtime events using redis first and memory fallback."""

    def __init__(
        self,
        *,
        memory_store: InMemoryEventStore | None = None,
        redis_service_provider: RedisServiceProvider | None = None,
        key_prefix: str = _EVENT_KEY_PREFIX,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        max_events_per_session: int = _DEFAULT_MAX_EVENTS_PER_SESSION,
    ) -> None:
        self._memory_store = memory_store or InMemoryEventStore(
            max_events_per_session=max_events_per_session
        )
        self._redis_service_provider = redis_service_provider or _default_redis_service_provider
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds
        self._max_events_per_session = max_events_per_session

    async def append(self, session_id: str, event: dict[str, Any]) -> None:
        """Append one event for a session id."""

        redis_client = await self._get_redis_client()
        if redis_client is not None:
            key = self._session_key(session_id)
            try:
                encoded = json.dumps(dict(event), ensure_ascii=False)
                await redis_client.rpush(key, encoded)
                await redis_client.ltrim(key, -self._max_events_per_session, -1)
                await redis_client.expire(key, self._ttl_seconds)
                return
            except (AttributeError, RuntimeError, TypeError, ValueError):
                pass

        self._memory_store.append(session_id, event)

    async def list(self, session_id: str) -> list[dict[str, Any]]:
        """Return events for one session in append order."""

        redis_client = await self._get_redis_client()
        if redis_client is not None:
            try:
                encoded_items = await redis_client.lrange(self._session_key(session_id), 0, -1)
                if isinstance(encoded_items, list) and encoded_items:
                    parsed_events: list[dict[str, Any]] = []
                    for raw_item in encoded_items:
                        if not isinstance(raw_item, str):
                            continue
                        try:
                            item = json.loads(raw_item)
                        except (TypeError, ValueError):
                            continue
                        if isinstance(item, dict):
                            parsed_events.append(item)
                    if parsed_events:
                        return parsed_events
            except (AttributeError, RuntimeError, TypeError, ValueError):
                pass

        return self._memory_store.list(session_id)

    async def session_count(self) -> int:
        """Return total number of sessions currently tracked."""

        redis_count = await self._count_redis_sessions()
        if redis_count is not None and redis_count > 0:
            return redis_count
        return self._memory_store.session_count()

    async def event_count(self) -> int:
        """Return total number of persisted events."""

        redis_client = await self._get_redis_client()
        if redis_client is not None:
            keys = await self._list_redis_keys(redis_client)
            if keys:
                total = 0
                for key in keys:
                    try:
                        total += int(await redis_client.llen(key))
                    except (AttributeError, RuntimeError, TypeError, ValueError):
                        return self._memory_store.event_count()
                return total

        return self._memory_store.event_count()

    async def _get_redis_client(self) -> Any | None:
        provider = self._redis_service_provider
        if provider is None:
            return None

        try:
            service_or_awaitable = provider()
        except Exception:
            return None

        service = service_or_awaitable
        if inspect.isawaitable(service):
            try:
                service = await service
            except Exception:
                return None

        if service is None:
            return None
        if not bool(getattr(service, "is_healthy", False)):
            return None
        return getattr(service, "redis", None)

    async def _count_redis_sessions(self) -> int | None:
        redis_client = await self._get_redis_client()
        if redis_client is None:
            return None

        keys = await self._list_redis_keys(redis_client)
        if keys is None:
            return None
        return len(keys)

    async def _list_redis_keys(self, redis_client: Any) -> list[str] | None:
        scan_iter = getattr(redis_client, "scan_iter", None)
        if not callable(scan_iter):
            return None

        pattern = f"{self._key_prefix}*"
        try:
            iterator = scan_iter(match=pattern)
        except Exception:
            return None

        keys: list[str] = []
        try:
            if hasattr(iterator, "__aiter__"):
                async for raw_key in iterator:
                    if isinstance(raw_key, str):
                        keys.append(raw_key)
            else:
                for raw_key in iterator:
                    if isinstance(raw_key, str):
                        keys.append(raw_key)
        except Exception:
            return None
        return keys

    def _session_key(self, session_id: str) -> str:
        return f"{self._key_prefix}{session_id}"


def build_event_repository(
    *,
    memory_store: InMemoryEventStore | None = None,
    redis_service_provider: RedisServiceProvider | None = None,
) -> RuntimeEventRepository:
    """Build event repository with shared in-memory fallback by default."""

    return RuntimeEventRepository(
        memory_store=memory_store or _DEFAULT_MEMORY_EVENT_STORE,
        redis_service_provider=redis_service_provider,
    )
