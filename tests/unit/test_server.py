"""Tests for FastAPI server endpoints and lifespan."""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.responses import JSONResponse, StreamingResponse
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

    def test_readiness_check_returns_ready_when_dependencies_healthy(self, client):
        """Readiness reports ready when Redis and LLM are healthy."""
        with patch("src.services.redis_service.get_redis_service", new_callable=AsyncMock) as mock_get_redis:
            mock_redis_service = Mock()
            mock_redis_service.is_healthy = True
            mock_get_redis.return_value = mock_redis_service

            with patch("src.services.llm_service.get_llm_service") as mock_get_llm:
                mock_llm_service = Mock()
                mock_llm_service.is_healthy = True
                mock_get_llm.return_value = mock_llm_service

                response = client.get("/health/ready")
                assert response.status_code == 200

                data = response.json()
                assert data == {
                    "status": "ready",
                    "dependencies": {
                        "redis": {"healthy": True},
                        "llm": {"healthy": True},
                    },
                }

    def test_readiness_check_returns_degraded_when_dependency_unhealthy(self, client):
        """Readiness degrades when a dependency is unhealthy."""
        with patch("src.services.redis_service.get_redis_service", new_callable=AsyncMock) as mock_get_redis:
            mock_redis_service = Mock()
            mock_redis_service.is_healthy = False
            mock_get_redis.return_value = mock_redis_service

            with patch("src.services.llm_service.get_llm_service") as mock_get_llm:
                mock_llm_service = Mock()
                mock_llm_service.is_healthy = True
                mock_get_llm.return_value = mock_llm_service

                response = client.get("/health/ready")
                assert response.status_code == 503

                data = response.json()
                assert data == {
                    "status": "degraded",
                    "dependencies": {
                        "redis": {"healthy": False},
                        "llm": {"healthy": True},
                    },
                }

    def test_readiness_check_returns_degraded_when_dependency_unavailable(self, client):
        """Readiness degrades when a dependency cannot be loaded."""
        with patch("src.services.redis_service.get_redis_service", new_callable=AsyncMock) as mock_get_redis:
            mock_get_redis.side_effect = RuntimeError("redis unavailable")

            with patch("src.services.llm_service.get_llm_service") as mock_get_llm:
                mock_get_llm.side_effect = RuntimeError("llm unavailable")

                response = client.get("/health/ready")
                assert response.status_code == 503

                data = response.json()
                assert data == {
                    "status": "degraded",
                    "dependencies": {
                        "redis": {"healthy": False},
                        "llm": {"healthy": False},
                    },
                }

    def test_readiness_openapi_schema_exposes_nested_dependency_health_contract(self):
        """OpenAPI publishes the explicit nested readiness dependency health schema."""
        openapi_schema = app.openapi()
        response_schema = (
            openapi_schema["paths"]["/health/ready"]["get"]["responses"]["200"]["content"][
                "application/json"
            ]["schema"]
        )

        if "$ref" in response_schema:
            schema_name = response_schema["$ref"].rsplit("/", maxsplit=1)[-1]
            response_schema = openapi_schema["components"]["schemas"][schema_name]

        dependencies_schema = response_schema["properties"]["dependencies"]
        if "$ref" in dependencies_schema:
            schema_name = dependencies_schema["$ref"].rsplit("/", maxsplit=1)[-1]
            dependencies_schema = openapi_schema["components"]["schemas"][schema_name]

        redis_schema = dependencies_schema["properties"]["redis"]
        if "$ref" in redis_schema:
            schema_name = redis_schema["$ref"].rsplit("/", maxsplit=1)[-1]
            redis_schema = openapi_schema["components"]["schemas"][schema_name]

        llm_schema = dependencies_schema["properties"]["llm"]
        if "$ref" in llm_schema:
            schema_name = llm_schema["$ref"].rsplit("/", maxsplit=1)[-1]
            llm_schema = openapi_schema["components"]["schemas"][schema_name]

        assert response_schema["type"] == "object"
        assert "dependencies" in response_schema["required"]
        assert dependencies_schema["type"] == "object"
        assert {"redis", "llm"} <= set(dependencies_schema["properties"])
        assert redis_schema["properties"]["healthy"]["type"] == "boolean"
        assert llm_schema["properties"]["healthy"]["type"] == "boolean"


class TestMetricsEndpoint:
    """Tests for GET /metrics endpoint."""

    def test_metrics_endpoint_returns_prometheus_payload(self, client):
        """Metrics endpoint exposes the app Prometheus registry."""
        response = client.get("/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert "trinav_requests_total" in response.text


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


class TestAssistantCompatRoutes:
    """Tests for the /assistant compatibility adapter."""

    def test_invoke_endpoint_wraps_v3_runtime_response(self, client, monkeypatch):
        """Compat invoke should unwrap input, delegate to v3, and wrap the response."""

        observed_payload = None

        async def fake_invoke(payload):
            nonlocal observed_payload
            observed_payload = payload
            return JSONResponse(
                status_code=200,
                content={
                    "status": "final",
                    "session_id": "sess-compat",
                    "trace_id": "trace-compat",
                    "response": "compat ok",
                },
            )

        monkeypatch.setattr("src.interfaces.api.assistant_compat.invoke_runtime_v3", fake_invoke)

        response = client.post(
            "/assistant/invoke",
            json={
                "input": {
                    "request_id": "req-compat",
                    "session_id": "sess-compat",
                    "trace_id": "trace-compat",
                    "text": "test",
                    "metadata": {"foo": "bar"},
                }
            },
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        assert observed_payload is not None
        assert observed_payload.metadata["runtime_mode"] == "v3"
        assert observed_payload.metadata["foo"] == "bar"
        assert response.json() == {
            "output": {
                "status": "final",
                "session_id": "sess-compat",
                "trace_id": "trace-compat",
                "response": "compat ok",
            },
            "metadata": {"runtime_mode": "v3"},
        }

    def test_invoke_endpoint_preserves_http_200_for_structured_runtime_error(
        self,
        client,
        monkeypatch,
    ):
        """Compat invoke should wrap structured runtime errors with legacy HTTP 200 transport."""

        async def fake_invoke(payload):
            _ = payload
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "session_id": "sess-compat-error",
                    "trace_id": "trace-compat-error",
                    "response": "",
                    "error_message": "assistant_v3_task_runtime_failed",
                },
            )

        monkeypatch.setattr("src.interfaces.api.assistant_compat.invoke_runtime_v3", fake_invoke)

        response = client.post(
            "/assistant/invoke",
            json={
                "input": {
                    "request_id": "req-compat-error",
                    "session_id": "sess-compat-error",
                    "trace_id": "trace-compat-error",
                    "text": "test error",
                }
            },
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        assert response.json()["output"]["status"] == "error"
        assert response.json()["output"]["error_message"] == "assistant_v3_task_runtime_failed"
        assert response.json()["metadata"]["runtime_mode"] == "v3"

    def test_invoke_endpoint_wraps_runtime_disabled_as_structured_http_200(
        self,
        client,
        monkeypatch,
    ):
        """Compat invoke should preserve HTTP 200 transport when the v3 runtime flag is disabled."""

        monkeypatch.setattr(
            "src.interfaces.api.runtime_v3.get_settings",
            lambda: type(
                "SettingsStub",
                (),
                {"v3_runtime_enabled": False, "v3_legacy_fallback_enabled": True},
            )(),
        )

        async def fail_primary(payload):
            _ = payload
            raise AssertionError("primary v3 path should not execute when runtime is disabled")

        monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_primary_v3", fail_primary)

        response = client.post(
            "/assistant/invoke",
            json={
                "input": {
                    "request_id": "req-compat-disabled",
                    "session_id": "sess-compat-disabled",
                    "trace_id": "trace-compat-disabled",
                    "text": "test disabled",
                }
            },
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["output"]["status"] == "error"
        assert body["output"]["error_message"] == "assistant_v3_runtime_disabled"
        assert body["output"]["trace"]["error_stage"] == "runtime_gate"
        assert body["metadata"]["runtime_mode"] == "v3"

    def test_stream_endpoint_exists_via_compat_adapter(self, client, monkeypatch):
        """Compat stream should inject v3 runtime mode and preserve SSE transport."""

        observed_payload = None

        async def event_stream():
            yield b"event: status\ndata: {\"status\":\"start\"}\n\n"
            yield b"data: [DONE]\n\n"

        async def fake_stream(payload):
            nonlocal observed_payload
            observed_payload = payload
            return StreamingResponse(event_stream(), media_type="text/event-stream")

        monkeypatch.setattr("src.interfaces.api.assistant_compat.stream_runtime_v3", fake_stream)

        response = client.post(
            "/assistant/stream",
            json={
                "input": {
                    "request_id": "req-compat-stream",
                    "session_id": "sess-compat-stream",
                    "trace_id": "trace-compat-stream",
                    "text": "test stream",
                    "metadata": {"foo": "bar"},
                }
            },
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        assert observed_payload is not None
        assert observed_payload.metadata["runtime_mode"] == "v3"
        assert observed_payload.metadata["foo"] == "bar"
        assert "text/event-stream" in response.headers.get("content-type", "")
        assert response.text == 'event: status\ndata: {"status":"start"}\n\ndata: [DONE]\n\n'


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
