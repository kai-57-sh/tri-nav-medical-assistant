"""Redis-first runtime snapshot repository with in-memory fallback."""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Any

from src.core.state.session_snapshot_store import InMemorySnapshotStore

try:
    from redis.exceptions import RedisError
except Exception:  # pragma: no cover - redis import fallback
    RedisError = RuntimeError

RedisServiceProvider = Callable[[], Any | Awaitable[Any]]

_SNAPSHOT_KEY_PREFIX = "cache:snapshot:"
_DEFAULT_TTL_SECONDS = 3600
_DEFAULT_MEMORY_SNAPSHOT_STORE = InMemorySnapshotStore()


async def _default_redis_service_provider() -> Any | None:
    try:
        from src.services import redis_service as redis_service_module
    except Exception:
        return None
    return getattr(redis_service_module, "_redis_service", None)


class RuntimeSnapshotRepository:
    """Persist runtime snapshots using redis first and memory fallback."""

    def __init__(
        self,
        *,
        memory_store: InMemorySnapshotStore | None = None,
        redis_service_provider: RedisServiceProvider | None = None,
        key_prefix: str = _SNAPSHOT_KEY_PREFIX,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        self._memory_store = memory_store or InMemorySnapshotStore()
        self._redis_service_provider = redis_service_provider or _default_redis_service_provider
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds

    async def upsert(self, session_id: str, snapshot: dict[str, Any]) -> None:
        """Insert or replace one session snapshot."""

        # Keep in-memory mirror updated even when Redis is healthy so failover can replay state.
        self._memory_store.upsert(session_id, snapshot)

        serialized = json.dumps(deepcopy(snapshot), ensure_ascii=False)
        redis_client = await self._get_redis_client()
        if redis_client is not None:
            try:
                await redis_client.setex(self._session_key(session_id), self._ttl_seconds, serialized)
            except (RedisError, Exception):
                pass

    async def load(self, session_id: str) -> dict[str, Any] | None:
        """Load one snapshot by session id."""

        redis_client = await self._get_redis_client()
        if redis_client is not None:
            try:
                encoded = await redis_client.get(self._session_key(session_id))
                if isinstance(encoded, str) and encoded:
                    decoded = json.loads(encoded)
                    if isinstance(decoded, dict):
                        self._memory_store.upsert(session_id, decoded)
                        return decoded
            except (RedisError, Exception):
                pass

        return self._memory_store.load(session_id)

    async def count(self) -> int:
        """Return total number of snapshots currently tracked."""

        redis_count = await self._count_redis_snapshots()
        if redis_count is not None and redis_count > 0:
            return redis_count
        return self._memory_store.count()

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

    async def _count_redis_snapshots(self) -> int | None:
        redis_client = await self._get_redis_client()
        if redis_client is None:
            return None

        scan_iter = getattr(redis_client, "scan_iter", None)
        if not callable(scan_iter):
            return None

        pattern = f"{self._key_prefix}*"
        try:
            iterator = scan_iter(match=pattern)
        except Exception:
            return None

        count = 0
        try:
            if hasattr(iterator, "__aiter__"):
                async for _ in iterator:
                    count += 1
            else:
                for _ in iterator:
                    count += 1
        except Exception:
            return None
        return count

    def _session_key(self, session_id: str) -> str:
        return f"{self._key_prefix}{session_id}"


def build_snapshot_repository(
    *,
    memory_store: InMemorySnapshotStore | None = None,
    redis_service_provider: RedisServiceProvider | None = None,
) -> RuntimeSnapshotRepository:
    """Build snapshot repository with shared in-memory fallback by default."""

    return RuntimeSnapshotRepository(
        memory_store=memory_store or _DEFAULT_MEMORY_SNAPSHOT_STORE,
        redis_service_provider=redis_service_provider,
    )
