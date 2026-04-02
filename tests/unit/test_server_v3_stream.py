"""Tests for assistant v3 SSE stream route."""

import os

from fastapi.testclient import TestClient
import pytest

os.environ.setdefault("QWEN_API_KEY", "test-key")

from src.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_assistant_v3_stream_emits_done_marker(client: TestClient) -> None:
    response = client.post(
        "/assistant/v3/stream",
        json={
            "request_id": "req-test-v3",
            "session_id": "sess-test-v3",
            "text": "头痛两天",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert "data: [DONE]" in response.text
