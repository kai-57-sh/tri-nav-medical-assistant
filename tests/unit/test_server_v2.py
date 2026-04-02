"""Tests for assistant v2 server routes."""

import os

from fastapi.testclient import TestClient

os.environ.setdefault("QWEN_API_KEY", "test-key")

from src.server import app


def test_assistant_v2_invoke_endpoint_exists_and_returns_runtime_status() -> None:
    """POST /assistant/v2/invoke should be registered and reachable."""

    client = TestClient(app)
    response = client.post(
        "/assistant/v2/invoke",
        json={
            "request_id": "req-test-v2",
            "session_id": "sess-test-v2",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code in (200, 503)
