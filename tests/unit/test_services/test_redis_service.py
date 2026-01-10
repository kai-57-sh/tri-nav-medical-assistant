"""Unit tests for Redis service."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.redis_service import RedisService, get_redis_service


@pytest.mark.asyncio
class TestRedisService:
    """Test Redis service operations."""

    async def test_save_session_success(self, mock_redis_pool, sample_session_state):
        """Test successful session save."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.setex = AsyncMock()
            mock_redis_pool.get_connection.return_value = mock_redis

            service = RedisService()
            service._redis = mock_redis

            await service.save_session("test-123", sample_session_state, ttl=3600)

            # Verify setex was called
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args
            assert call_args[0][0] == "session:test-123"  # key
            assert call_args[0][1] == 3600  # ttl
            # Verify minimal state (no raw data)
            saved_data = json.loads(call_args[0][2])
            assert saved_data["session_id"] == "test-123"
            assert saved_data["symptom_schema"] is not None
            assert "text" not in saved_data  # Raw text should not be stored

    async def test_load_session_success(self, mock_redis_pool, sample_session_state):
        """Test successful session load."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=json.dumps(sample_session_state))
            mock_redis_pool.get_connection.return_value = mock_redis

            service = RedisService()
            service._redis = mock_redis

            result = await service.load_session("test-123")

            # Verify get was called
            mock_redis.get.assert_called_once_with("session:test-123")
            assert result["session_id"] == "test-123"
            assert result["symptom_schema"]["body_part"] == "手臂"

    async def test_load_session_not_found(self, mock_redis_pool):
        """Test session load when session doesn't exist."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis_pool.get_connection.return_value = mock_redis

            service = RedisService()
            service._redis = mock_redis

            result = await service.load_session("nonexistent")

            # Should return None
            assert result is None

    async def test_delete_session_success(self, mock_redis_pool):
        """Test successful session deletion."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.delete = AsyncMock()
            mock_redis_pool.get_connection.return_value = mock_redis

            service = RedisService()
            service._redis = mock_redis

            await service.delete_session("test-123")

            # Verify delete was called
            mock_redis.delete.assert_called_once_with("session:test-123")

    async def test_cache_external_result(self, mock_redis_pool, sample_cache_result):
        """Test caching external API result."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.setex = AsyncMock()
            mock_redis_pool.get_connection.return_value = mock_redis

            service = RedisService()
            service._redis = mock_redis

            await service.cache_external_result("cache:key", sample_cache_result, ttl=1800)

            # Verify cache storage
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args
            assert call_args[0][0] == "cache:key"
            assert call_args[0][1] == 1800
            cached_data = json.loads(call_args[0][2])
            assert cached_data["hospitals"][0]["name"] == "Test Hospital"

    async def test_load_cached_result_hit(self, mock_redis_pool, sample_cache_result):
        """Test loading cached result when cache hit."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=json.dumps(sample_cache_result))
            mock_redis_pool.get_connection.return_value = mock_redis

            service = RedisService()
            service._redis = mock_redis

            result = await service.load_cached_result("cache:key")

            # Should return cached data
            assert result is not None
            assert result["hospitals"][0]["name"] == "Test Hospital"

    async def test_load_cached_result_miss(self, mock_redis_pool):
        """Test loading cached result when cache miss."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis_pool.get_connection.return_value = mock_redis

            service = RedisService()
            service._redis = mock_redis

            result = await service.load_cached_result("cache:miss")

            # Should return None
            assert result is None

    async def test_health_check_healthy(self, mock_redis_pool):
        """Test health check returns True when Redis is healthy."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis_pool.get_connection.return_value = mock_redis

            service = RedisService()
            service._redis = mock_redis

            is_healthy = await service.check_health()

            # Should be healthy
            assert is_healthy is True

    async def test_health_check_unhealthy(self, mock_redis_pool):
        """Test health check returns False when Redis is unhealthy."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(side_effect=Exception("Connection lost"))
            mock_redis_pool.get_connection.return_value = mock_redis

            service = RedisService()
            service._redis = mock_redis

            is_healthy = await service.check_health()

            # Should be unhealthy
            assert is_healthy is False

    def test_is_healthy_property(self):
        """Test is_healthy property reflects health status."""
        service = RedisService()
        service._is_healthy = True
        assert service.is_healthy is True

        service._is_healthy = False
        assert service.is_healthy is False


@pytest.mark.asyncio
async def test_get_redis_service_singleton():
    """Test that get_redis_service returns singleton instance."""
    with patch('src.services.redis_service.RedisService') as mock_service_class:
        mock_instance = MagicMock()
        mock_instance.is_healthy = True
        mock_service_class.return_value = mock_instance

        service1 = await get_redis_service()
        service2 = await get_redis_service()

        # Should return same instance (cached)
        assert service1 is service2

        # Should only create once
        mock_service_class.assert_called_once()
