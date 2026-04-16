#!/usr/bin/env python3
"""Smoke-check the assistant v3 runtime doctor endpoint."""

from __future__ import annotations

import json
import sys
from typing import Any
from urllib import error, request


def _read_json_response(response: Any, url: str) -> tuple[int, dict[str, Any]]:
    status = getattr(response, "status", response.getcode())
    payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object from {url}, got {type(payload).__name__}")
    return status, payload


def _fetch_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
    try:
        with request.urlopen(url, timeout=timeout) as response:
            return _read_json_response(response, url)
    except error.HTTPError as exc:
        return _read_json_response(exc, url)


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, dict[str, Any]]:
    encoded_payload = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        url,
        data=encoded_payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            return _read_json_response(response, url)
    except error.HTTPError as exc:
        return _read_json_response(exc, url)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print("usage: check_v3_runtime.py [base_url]", file=sys.stderr)
        return 2

    base_url = (argv[1] if len(argv) == 2 else "http://127.0.0.1:8000").rstrip("/")
    timeout = 5.0
    doctor_url = f"{base_url}/assistant/v3/runtime/doctor"
    invoke_url = f"{base_url}/assistant/v3/invoke"
    health_url = f"{base_url}/health"
    smoke_payload = {
        "session_id": "smoke-v3",
        "text": "持续头痛两天",
    }
    current_url = doctor_url

    try:
        current_url = doctor_url
        status, doctor = _fetch_json(doctor_url, timeout)
        _expect(status == 200, f"Expected 200 from {doctor_url}, got {status}")
        _expect(doctor.get("status") == "ok", "doctor.status must be 'ok'")

        runtime = doctor.get("runtime")
        _expect(isinstance(runtime, dict), "doctor.runtime must be an object")
        _expect(
            isinstance(runtime.get("v3_runtime_enabled"), bool),
            "doctor.runtime.v3_runtime_enabled must be a boolean",
        )
        _expect(runtime.get("v3_runtime_enabled") is True, "v3 runtime must be enabled")
        _expect(
            isinstance(runtime.get("v3_shadow_compare_enabled"), bool),
            "doctor.runtime.v3_shadow_compare_enabled must be a boolean",
        )

        dependencies = doctor.get("dependencies")
        _expect(isinstance(dependencies, dict), "doctor.dependencies must be an object")
        redis = dependencies.get("redis")
        _expect(isinstance(redis, dict), "doctor.dependencies.redis must be an object")
        _expect(
            isinstance(redis.get("healthy"), bool),
            "doctor.dependencies.redis.healthy must be a boolean",
        )

        observability = doctor.get("observability")
        _expect(
            observability is None or isinstance(observability, dict),
            "doctor.observability must be an object when present",
        )

        current_url = invoke_url
        invoke_status, invoke = _post_json(invoke_url, smoke_payload, timeout=15.0)
        _expect(
            invoke_status in {200, 503},
            f"Expected 200 or 503 from {invoke_url}, got {invoke_status}",
        )
        _expect(isinstance(invoke.get("status"), str), "invoke.status must be a string")
        _expect(
            isinstance(invoke.get("session_id"), str) and invoke.get("session_id"),
            "invoke.session_id must be a non-empty string",
        )
    except (AssertionError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL {current_url}: {exc}", file=sys.stderr)
        return 1
    except error.URLError as exc:
        print(f"FAIL {current_url}: {exc}", file=sys.stderr)
        return 1

    print(
        "OK doctor"
        f" status={doctor['status']}"
        f" v3_runtime_enabled={doctor['runtime']['v3_runtime_enabled']}"
        f" v3_shadow_compare_enabled={doctor['runtime']['v3_shadow_compare_enabled']}"
        f" redis_healthy={doctor['dependencies']['redis']['healthy']}"
    )
    print(
        "OK invoke"
        f" http_status={invoke_status}"
        f" status={invoke['status']}"
        f" session_id={invoke['session_id']}"
    )

    try:
        health_status, health = _fetch_json(health_url, timeout)
        print(
            "INFO health"
            f" http_status={health_status}"
            f" status={health.get('status')}"
            f" redis={health.get('redis')}"
        )
    except Exception as exc:  # pragma: no cover - best-effort context only
        print(f"INFO health unavailable: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
