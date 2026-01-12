"""Unit tests for Redis service."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from redis.exceptions import RedisError
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
            service.redis = mock_redis
            service._healthy = True

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
            service.redis = mock_redis
            service._healthy = True

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
            service.redis = mock_redis
            service._healthy = True

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
            service.redis = mock_redis
            service._healthy = True

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
            service.redis = mock_redis
            service._healthy = True

            await service.cache_external_result("test:key", sample_cache_result, ttl=1800)

            # Verify cache storage
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args
            assert call_args[0][0] == "cache:test:key"
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
            service.redis = mock_redis
            service._healthy = True

            result = await service.load_cached_result("test:key")

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
            service.redis = mock_redis
            service._healthy = True

            result = await service.load_cached_result("test:miss")

            # Should return None
            assert result is None

    async def test_connect_healthy(self, mock_redis_pool):
        """Test connect marks Redis healthy when ping succeeds."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)

            with patch('src.services.redis_service.Redis', return_value=mock_redis):
                service = RedisService()
                await service.connect()

        assert service.is_healthy is True
        mock_redis.ping.assert_called_once()

    async def test_connect_unhealthy(self, mock_redis_pool):
        """Test connect marks Redis unhealthy when ping fails."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(side_effect=RedisError("Connection lost"))

            with patch('src.services.redis_service.Redis', return_value=mock_redis):
                service = RedisService()
                await service.connect()

        assert service.is_healthy is False

    async def test_is_healthy_property(self):
        """Test is_healthy property reflects health status."""
        service = RedisService()
        service.redis = MagicMock()
        service._healthy = True
        assert service.is_healthy is True

        service._healthy = False
        assert service.is_healthy is False


@pytest.mark.asyncio
async def test_get_redis_service_singleton():
    """Test that get_redis_service returns singleton instance."""
    with patch('src.services.redis_service.RedisService') as mock_service_class:
        mock_instance = MagicMock()
        mock_instance.is_healthy = True
        mock_instance.connect = AsyncMock()
        mock_service_class.return_value = mock_instance

        with patch('src.services.redis_service._redis_service', None):
            service1 = await get_redis_service()
            service2 = await get_redis_service()

        # Should return same instance (cached)
        assert service1 is service2

        # Should only create once
        mock_service_class.assert_called_once()


@pytest.mark.asyncio
class TestRedisServiceErrorPaths:
    """Test Redis service error handling paths."""

    async def test_save_session_redis_error(self, mock_redis_pool, sample_session_state):
        """Test save_session when Redis raises error."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.setex = AsyncMock(side_effect=RedisError("Connection lost"))
            mock_redis_pool.get_connection.return_value = mock_redis

            service = RedisService()
            service.redis = mock_redis
            service._healthy = True

            result = await service.save_session("test-123", sample_session_state)

            # Should return False on error
            assert result is False
            # Note: Service doesn't mark itself unhealthy on error in current implementation

    async def test_save_session_unhealthy_service(self, mock_redis_pool, sample_session_state):
        """Test save_session when service is unhealthy."""
        service = RedisService()
        service._healthy = False

        result = await service.save_session("test-123", sample_session_state)

        # Should return False without trying
        assert result is False

    async def test_save_session_no_redis(self, mock_redis_pool, sample_session_state):
        """Test save_session when redis is None."""
        service = RedisService()
        service._healthy = True
        service.redis = None

        result = await service.save_session("test-123", sample_session_state)

        # Should return False
        assert result is False

    async def test_load_session_redis_error(self, mock_redis_pool):
        """Test load_session when Redis raises error."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(side_effect=RedisError("Connection lost"))
            mock_redis_pool.get_connection.return_value = mock_redis

            service = RedisService()
            service.redis = mock_redis
            service._healthy = True

            result = await service.load_session("test-123")

            # Should return None on error
            assert result is None

    async def test_load_session_json_decode_error(self, mock_redis_pool):
        """Test load_session when JSON parsing fails."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value="invalid json{")
            mock_redis_pool.get_connection.return_value = mock_redis

            service = RedisService()
            service.redis = mock_redis
            service._healthy = True

            result = await service.load_session("test-123")

            # Should return None on JSON error
            assert result is None

    async def test_cache_external_result_redis_error(self, mock_redis_pool, sample_cache_result):
        """Test cache_external_result when Redis raises error."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.setex = AsyncMock(side_effect=RedisError("Connection lost"))
            mock_redis_pool.get_connection.return_value = mock_redis

            service = RedisService()
            service.redis = mock_redis
            service._healthy = True

            await service.cache_external_result("test:key", sample_cache_result)

            # Should not raise, just log error
            mock_redis.setex.assert_called_once()

    async def test_load_cached_result_json_decode_error(self, mock_redis_pool):
        """Test load_cached_result when JSON parsing fails."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value="invalid json{")
            mock_redis_pool.get_connection.return_value = mock_redis

            service = RedisService()
            service.redis = mock_redis
            service._healthy = True

            result = await service.load_cached_result("test:key")

            # Should return None on JSON error
            assert result is None

    async def test_disconnect_closes_pool(self, mock_redis_pool):
        """Test disconnect closes connection pool."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool = AsyncMock()
            mock_pool.aclose = AsyncMock()
            mock_pool_class.from_url.return_value = mock_pool

            service = RedisService()
            service.pool = mock_pool
            service._healthy = True

            await service.disconnect()

            # Verify pool was closed
            mock_pool.aclose.assert_called_once()
            assert service._healthy is False
            # Note: pool is not set to None in current implementation

    async def test_close_redis_service(self, mock_redis_pool):
        """Test close_redis_service closes connection and clears singleton."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool = AsyncMock()
            mock_pool.aclose = AsyncMock()
            mock_pool_class.from_url.return_value = mock_pool

            service = RedisService()
            service.pool = mock_pool
            service._healthy = True

            with patch('src.services.redis_service._redis_service', service):
                from src.services.redis_service import close_redis_service
                await close_redis_service()

            # Verify pool was closed
            mock_pool.aclose.assert_called_once()

    async def test_delete_session_redis_error(self, mock_redis_pool):
        """Test delete_session when Redis raises error."""
        with patch('src.services.redis_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.from_url.return_value = mock_redis_pool
            mock_redis = AsyncMock()
            mock_redis.delete = AsyncMock(side_effect=RedisError("Connection lost"))
            mock_redis_pool.get_connection.return_value = mock_redis

            service = RedisService()
            service.redis = mock_redis
            service._healthy = True

            # Should not raise
            await service.delete_session("test-123")

            # Verify delete was attempted
            mock_redis.delete.assert_called_once()
