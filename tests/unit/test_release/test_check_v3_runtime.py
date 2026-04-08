"""Regression tests for the v3 runtime smoke CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
CLI_PATH = REPO_ROOT / "scripts" / "smoke" / "check_v3_runtime.py"


@contextmanager
def _serve_runtime_stub(
    *,
    doctor_payload: dict[str, Any],
    invoke_status: int = 200,
    invoke_payload: dict[str, Any] | None = None,
    health_status: int = 200,
    health_payload: dict[str, Any] | None = None,
) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """Serve deterministic runtime doctor/invoke responses for CLI subprocess tests."""

    requests_seen: list[dict[str, Any]] = []
    invoke_response = invoke_payload or {
        "status": "final",
        "session_id": "smoke-v3",
        "response": "ok",
    }
    health_response = health_payload or {"status": "ready", "redis": "healthy"}

    class Handler(BaseHTTPRequestHandler):
        def _write_json(self, status_code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            requests_seen.append({"method": "GET", "path": self.path})
            if self.path == "/assistant/v3/runtime/doctor":
                self._write_json(200, doctor_payload)
                return
            if self.path == "/health":
                self._write_json(health_status, health_response)
                return
            self._write_json(404, {"detail": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            body = json.loads(raw_body.decode("utf-8")) if raw_body else None
            requests_seen.append({"method": "POST", "path": self.path, "body": body})
            if self.path == "/assistant/v3/invoke":
                self._write_json(invoke_status, invoke_response)
                return
            self._write_json(404, {"detail": "not found"})

        def log_message(self, format: str, *args: object) -> None:
            _ = format
            _ = args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        yield base_url, requests_seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_check_v3_runtime_cli_fails_when_runtime_disabled() -> None:
    """Smoke CLI must fail when the runtime doctor reports v3 disabled."""

    with _serve_runtime_stub(
        doctor_payload={
            "status": "disabled",
            "runtime": {
                "v3_runtime_enabled": False,
                "v3_shadow_compare_enabled": False,
            },
            "dependencies": {"redis": {"healthy": True}},
            "observability": {"sessions_with_events": 0},
        }
    ) as (base_url, _requests_seen):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), base_url],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 1
    assert "doctor.status must be 'ok'" in result.stderr


def test_check_v3_runtime_cli_calls_invoke_when_runtime_ready() -> None:
    """Successful smoke runs must hit the invoke route, not just the doctor route."""

    with _serve_runtime_stub(
        doctor_payload={
            "status": "ok",
            "runtime": {
                "v3_runtime_enabled": True,
                "v3_shadow_compare_enabled": False,
            },
            "dependencies": {"redis": {"healthy": True}},
            "observability": {"sessions_with_events": 0},
        }
    ) as (base_url, requests_seen):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), base_url],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 0, result.stderr
    invoke_requests = [
        item for item in requests_seen if item["method"] == "POST" and item["path"] == "/assistant/v3/invoke"
    ]
    assert len(invoke_requests) == 1
    assert invoke_requests[0]["body"] == {
        "session_id": "smoke-v3",
        "text": "持续头痛两天",
    }
    assert "OK invoke" in result.stdout


def test_check_v3_runtime_cli_accepts_structured_503_from_invoke() -> None:
    """Structured invoke failures should still count as a reachable runtime."""

    with _serve_runtime_stub(
        doctor_payload={
            "status": "ok",
            "runtime": {
                "v3_runtime_enabled": True,
                "v3_shadow_compare_enabled": False,
            },
            "dependencies": {"redis": {"healthy": True}},
            "observability": {"sessions_with_events": 0},
        },
        invoke_status=503,
        invoke_payload={
            "status": "error",
            "session_id": "smoke-v3",
            "error_message": "downstream unavailable",
        },
    ) as (base_url, requests_seen):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), base_url],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 0, result.stderr
    invoke_requests = [
        item for item in requests_seen if item["method"] == "POST" and item["path"] == "/assistant/v3/invoke"
    ]
    assert len(invoke_requests) == 1
    assert "OK invoke http_status=503 status=error session_id=smoke-v3" in result.stdout
