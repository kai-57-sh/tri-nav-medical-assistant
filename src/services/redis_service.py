"""Redis service for session management."""
import json
from typing import Optional, Dict, Any
from datetime import datetime
import asyncio
from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError
from ..config.settings import get_settings
from ..utils.logging_config import get_logger
from ..utils.metrics import set_external_service_health

logger = get_logger(__name__)

settings = get_settings()


class RedisService:
    """Redis service for session state management with graceful degradation."""

    def __init__(self):
        """Initialize Redis service with connection pooling."""
        self.pool: Optional[ConnectionPool] = None
        self.redis: Optional[Redis] = None
        self._healthy = False

    async def connect(self) -> None:
        """Establish Redis connection pool."""
        try:
            self.pool = ConnectionPool.from_url(
                settings.redis_url,
                max_connections=20,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            self.redis = Redis(connection_pool=self.pool)

            # Test connection
            await self.redis.ping()
            self._healthy = True
            set_external_service_health("redis", True)
            logger.info("Redis connection established")

        except RedisError as e:
            self._healthy = False
            set_external_service_health("redis", False)
            logger.error(f"Redis connection failed: {e}")
            # Don't raise - graceful degradation per constitution Principle V

    async def disconnect(self) -> None:
        """Close Redis connection pool."""
        if self.pool:
            await self.pool.aclose()
            self._healthy = False
            logger.info("Redis connection closed")

    async def save_session(
        self,
        session_id: str,
        state: Dict[str, Any],
        ttl: int = None
    ) -> bool:
        """Save session state to Redis.

        Only stores structured data (no raw images/text) per CT-007, CT-008.

        Args:
            session_id: Session identifier
            state: Current session state
            ttl: Time to live in seconds (default: 60 minutes from settings)

        Returns:
            True if save successful, False otherwise
        """
        if not self._healthy or not self.redis:
            logger.warning("Redis unhealthy, skipping session save")
            return False

        try:
            # Minimal state storage per privacy constraints
            minimal_state = {
                "session_id": session_id,
                "turn_count": state.get("turn_count", 1),
                "last_updated_at": datetime.now().isoformat(),
                "symptom_schema": state.get("symptom_schema"),
                "clarify_questions": state.get("clarify_questions", []),
                "triage_level": state.get("triage_level"),
                "case_domain": state.get("case_domain"),
                "evidence_cache_key": state.get("evidence_cache_key"),
                "navigation_cache_key": state.get("navigation_cache_key")
            }

            # Remove None values to save space
            minimal_state = {k: v for k, v in minimal_state.items() if v is not None}

            key = f"session:{session_id}"
            ttl = ttl or settings.redis_session_ttl

            await self.redis.setex(key, ttl, json.dumps(minimal_state))
            logger.debug(f"Session saved: {session_id}", extra={"session_id": session_id})
            return True

        except RedisError as e:
            set_external_service_health("redis", False)
            logger.error(f"Failed to save session {session_id}: {e}")
            return False

    async def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session state from Redis.

        Args:
            session_id: Session identifier

        Returns:
            Session state dict or None if not found/error
        """
        if not self._healthy or not self.redis:
            logger.debug(f"Redis unhealthy, treating {session_id} as new session")
            return None

        try:
            key = f"session:{session_id}"
            data = await self.redis.get(key)

            if not data:
                logger.debug(f"Session not found: {session_id}")
                return None

            session_state = json.loads(data)
            logger.debug(f"Session loaded: {session_id}", extra={"session_id": session_id})
            return session_state

        except RedisError as e:
            set_external_service_health("redis", False)
            logger.error(f"Failed to load session {session_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse session data for {session_id}: {e}")
            return None

    async def delete_session(self, session_id: str) -> bool:
        """Delete session from Redis.

        Args:
            session_id: Session identifier

        Returns:
            True if deletion successful, False otherwise
        """
        if not self._healthy or not self.redis:
            return False

        try:
            key = f"session:{session_id}"
            await self.redis.delete(key)
            logger.debug(f"Session deleted: {session_id}", extra={"session_id": session_id})
            return True

        except RedisError as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    async def cache_external_result(
        self,
        cache_key: str,
        result: Dict[str, Any],
        ttl: int = 1800
    ) -> bool:
        """Cache external API result in Redis.

        Short-lived caching for external service responses per FR-056.

        Args:
            cache_key: Cache key (e.g., "amap:lat,lng")
            result: Result data to cache
            ttl: Time to live in seconds (default: 30 minutes)

        Returns:
            True if cache successful, False otherwise
        """
        if not self._healthy or not self.redis:
            return False

        try:
            key = f"cache:{cache_key}"
            await self.redis.setex(key, ttl, json.dumps(result))
            logger.debug(f"External result cached: {cache_key}")
            return True

        except RedisError as e:
            logger.error(f"Failed to cache external result {cache_key}: {e}")
            return False

    async def load_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Load cached external API result.

        Args:
            cache_key: Cache key

        Returns:
            Cached result or None if not found/expired
        """
        if not self._healthy or not self.redis:
            return None

        try:
            key = f"cache:{cache_key}"
            data = await self.redis.get(key)

            if not data:
                return None

            return json.loads(data)

        except RedisError as e:
            logger.error(f"Failed to load cached result {cache_key}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse cached data for {cache_key}: {e}")
            return None

    @property
    def is_healthy(self) -> bool:
        """Check if Redis connection is healthy."""
        return self._healthy and self.redis is not None


# Global Redis service instance
_redis_service: Optional[RedisService] = None


async def get_redis_service() -> RedisService:
    """Get or create global Redis service instance.

    Returns:
        RedisService instance
    """
    global _redis_service

    if _redis_service is None:
        _redis_service = RedisService()
        await _redis_service.connect()

    return _redis_service


async def close_redis_service() -> None:
    """Close global Redis service connection."""
    global _redis_service

    if _redis_service:
        await _redis_service.disconnect()
        _redis_service = None
