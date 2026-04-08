#!/usr/bin/env python3
"""Smoke-check the assistant v3 runtime doctor endpoint."""

from __future__ import annotations

import json
import sys
from typing import Any
from urllib import error, request


def _fetch_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
    with request.urlopen(url, timeout=timeout) as response:
        status = getattr(response, "status", response.getcode())
        payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object from {url}, got {type(payload).__name__}")
        return status, payload


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
    health_url = f"{base_url}/health"

    try:
        status, doctor = _fetch_json(doctor_url, timeout)
        _expect(status == 200, f"Expected 200 from {doctor_url}, got {status}")
        _expect(isinstance(doctor.get("status"), str), "doctor.status must be a string")

        runtime = doctor.get("runtime")
        _expect(isinstance(runtime, dict), "doctor.runtime must be an object")
        _expect(
            isinstance(runtime.get("v3_runtime_enabled"), bool),
            "doctor.runtime.v3_runtime_enabled must be a boolean",
        )
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
    except (AssertionError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL {doctor_url}: {exc}", file=sys.stderr)
        return 1
    except error.URLError as exc:
        print(f"FAIL {doctor_url}: {exc}", file=sys.stderr)
        return 1

    print(
        "OK doctor"
        f" status={doctor['status']}"
        f" v3_runtime_enabled={doctor['runtime']['v3_runtime_enabled']}"
        f" v3_shadow_compare_enabled={doctor['runtime']['v3_shadow_compare_enabled']}"
        f" redis_healthy={doctor['dependencies']['redis']['healthy']}"
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
