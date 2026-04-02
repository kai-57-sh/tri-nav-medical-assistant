"""Tests for assistant v3 invoke route."""

import os

from fastapi.testclient import TestClient
import pytest

os.environ.setdefault("QWEN_API_KEY", "test-key")

from src.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_assistant_v3_invoke_route_exists(client: TestClient) -> None:
    response = client.post(
        "/assistant/v3/invoke",
        json={
            "request_id": "req-test-v3",
            "session_id": "sess-test-v3",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code in (200, 503)
