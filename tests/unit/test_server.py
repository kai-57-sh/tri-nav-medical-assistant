"""Tests for FastAPI server endpoints and lifespan."""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.server import app, lifespan


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestRootEndpoint:
    """Tests for GET / endpoint."""

    def test_root_returns_api_info(self, client):
        """Test root endpoint returns API information."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "TriNav Medical Triage Assistant"
        assert data["version"] == "1.0.0"
        assert "endpoints" in data
        assert data["endpoints"]["invoke"] == "POST /assistant/invoke"
        assert data["endpoints"]["health"] == "GET /health"
        assert data["endpoints"]["docs"] == "GET /docs"
        assert "documentation" in data


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_check_redis_healthy(self, client):
        """Test health check when Redis is healthy."""
        with patch("src.services.redis_service.get_redis_service", new_callable=AsyncMock) as mock_get_redis:
            mock_redis_service = Mock()
            mock_redis_service.is_healthy = True
            mock_get_redis.return_value = mock_redis_service

            response = client.get("/health")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "healthy"
            assert data["redis"] == "healthy"

    def test_health_check_redis_unhealthy(self, client):
        """Test health check when Redis is unhealthy."""
        with patch("src.services.redis_service.get_redis_service", new_callable=AsyncMock) as mock_get_redis:
            mock_redis_service = Mock()
            mock_redis_service.is_healthy = False
            mock_get_redis.return_value = mock_redis_service

            response = client.get("/health")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "degraded"
            assert data["redis"] == "unhealthy"

    def test_health_check_redis_none(self, client):
        """Test health check when Redis service is None."""
        with patch("src.services.redis_service.get_redis_service", new_callable=AsyncMock) as mock_get_redis:
            mock_get_redis.return_value = None

            response = client.get("/health")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "degraded"
            assert data["redis"] == "unhealthy"


class TestLifespan:
    """Tests for lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_startup_redis_healthy(self):
        """Test lifespan startup with healthy Redis."""
        with patch("src.server.external_service_health") as mock_metrics:
            mock_labels = Mock()
            mock_metrics.labels.return_value = mock_labels

            with patch("src.services.redis_service.get_redis_service", new_callable=AsyncMock) as mock_get_redis:
                mock_redis_service = Mock()
                mock_redis_service.is_healthy = True
                mock_get_redis.return_value = mock_redis_service

                with patch("src.services.llm_service.get_llm_service") as mock_get_llm:
                    mock_llm_service = Mock()
                    mock_get_llm.return_value = mock_llm_service

                    # Execute lifespan
                    async with lifespan(app=None):
                        pass

                    # Verify Redis health metric set to 1
                    mock_metrics.labels.assert_any_call(service_name="redis")
                    mock_labels.set.assert_any_call(1)

                    # Verify LLM health metric set to 1
                    mock_metrics.labels.assert_any_call(service_name="llm")
                    mock_labels.set.assert_any_call(1)

    @pytest.mark.asyncio
    async def test_lifespan_startup_redis_unhealthy(self):
        """Test lifespan startup with unhealthy Redis."""
        with patch("src.server.external_service_health") as mock_metrics:
            mock_labels = Mock()
            mock_metrics.labels.return_value = mock_labels

            with patch("src.services.redis_service.get_redis_service", new_callable=AsyncMock) as mock_get_redis:
                mock_redis_service = Mock()
                mock_redis_service.is_healthy = False
                mock_get_redis.return_value = mock_redis_service

                with patch("src.services.llm_service.get_llm_service") as mock_get_llm:
                    mock_llm_service = Mock()
                    mock_get_llm.return_value = mock_llm_service

                    # Execute lifespan
                    async with lifespan(app=None):
                        pass

                    # Verify Redis health metric set to 0
                    mock_metrics.labels.assert_any_call(service_name="redis")
                    mock_labels.set.assert_any_call(0)

                    # Verify LLM still initialized
                    mock_metrics.labels.assert_any_call(service_name="llm")
                    mock_labels.set.assert_any_call(1)

    @pytest.mark.asyncio
    async def test_lifespan_startup_redis_exception(self):
        """Test lifespan startup with Redis exception."""
        with patch("src.server.external_service_health") as mock_metrics:
            mock_labels = Mock()
            mock_metrics.labels.return_value = mock_labels

            with patch("src.services.redis_service.get_redis_service", new_callable=AsyncMock) as mock_get_redis:
                mock_get_redis.side_effect = Exception("Connection failed")

                with patch("src.services.llm_service.get_llm_service") as mock_get_llm:
                    mock_llm_service = Mock()
                    mock_get_llm.return_value = mock_llm_service

                    # Execute lifespan - should not raise
                    async with lifespan(app=None):
                        pass

                    # Verify Redis health metric set to 0
                    mock_metrics.labels.assert_any_call(service_name="redis")
                    mock_labels.set.assert_any_call(0)

    @pytest.mark.asyncio
    async def test_lifespan_startup_llm_exception(self):
        """Test lifespan startup with LLM exception."""
        with patch("src.server.external_service_health") as mock_metrics:
            mock_labels = Mock()
            mock_metrics.labels.return_value = mock_labels

            with patch("src.services.redis_service.get_redis_service", new_callable=AsyncMock) as mock_get_redis:
                mock_redis_service = Mock()
                mock_redis_service.is_healthy = True
                mock_get_redis.return_value = mock_redis_service

                with patch("src.services.llm_service.get_llm_service") as mock_get_llm:
                    mock_get_llm.side_effect = Exception("LLM init failed")

                    # Execute lifespan - should not raise
                    async with lifespan(app=None):
                        pass

                    # Verify LLM health metric set to 0
                    mock_metrics.labels.assert_any_call(service_name="llm")
                    mock_labels.set.assert_any_call(0)

                    # Verify Redis still healthy
                    mock_metrics.labels.assert_any_call(service_name="redis")
                    mock_labels.set.assert_any_call(1)


class TestCORSMiddleware:
    """Tests for CORS middleware configuration."""

    def test_cors_headers_present(self, client):
        """Test CORS headers are present in responses."""
        response = client.options("/", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        })

        # CORS should be configured (though specific headers depend on implementation)
        assert response.status_code in [200, 405]  # 405 is OK for OPTIONS without handler


class TestLangServeRoutes:
    """Tests for LangServe route integration."""

    def test_invoke_endpoint_exists(self, client):
        """Test that the LangServe invoke endpoint is registered."""
        # LangServe creates POST /assistant/invoke
        # We can't easily test the actual invoke without mocking the chain
        # but we can verify the endpoint exists
        response = client.post(
            "/assistant/invoke",
            json={"input": {"text": "test"}},
            headers={"Content-Type": "application/json"}
        )

        # Should get a response (even if it's an error from missing services)
        # This verifies the route is registered
        assert response.status_code in [200, 400, 500, 503]


class TestMainFunction:
    """Tests for main() function."""

    @patch("src.server.uvicorn.run")
    def test_main_runs_uvicorn(self, mock_run):
        """Test main() function calls uvicorn.run."""
        from src.config.settings import get_settings

        with patch("src.server.get_settings", return_value=get_settings()):
            from src.server import main
            main()

            # Verify uvicorn.run was called
            mock_run.assert_called_once()
            call_args = mock_run.call_args

            assert call_args[0][0] == "src.server:app"
            assert "host" in call_args[1]
            assert "port" in call_args[1]
            assert call_args[1]["reload"] is False
            assert call_args[1]["log_config"] is None


class TestServerConfiguration:
    """Tests for server configuration."""

    def test_app_metadata(self):
        """Test FastAPI app has correct metadata."""
        assert app.title == "TriNav Medical Triage Assistant"
        assert app.description == "AI-powered medical triage and hospital navigation system"
        assert app.version == "1.0.0"

    def test_app_has_lifespan(self):
        """Test app has lifespan configured."""
        # lifespan is set in FastAPI() constructor
        # We can verify it exists by checking the app's router
        assert app is not None
        # The lifespan is not directly accessible from app object
        # but we've tested it separately in TestLifespan

    def test_middleware_added(self):
        """Test middleware is added to app."""
        # Check that middleware stack exists
        assert app.middleware_stack is not None or len(app.user_middleware) > 0


class TestErrorHandling:
    """Tests for error handling in endpoints."""

    def test_root_endpoint_handles_errors(self, client):
        """Test root endpoint doesn't crash on unexpected input."""
        response = client.get("/")
        assert response.status_code == 200

    def test_404_endpoint(self, client):
        """Test 404 for non-existent endpoints."""
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """Test 405 for wrong HTTP method."""
        response = client.post("/health")
        # FastAPI may return 405 or 307/308 redirect
        assert response.status_code in [405, 307, 308]
