"""Shadow compare API route and helper for v1/v3 output diffs."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from src.config.settings import get_settings

Runner = Callable[[dict[str, Any]], Awaitable[Any]]

router = APIRouter(prefix="/assistant/v3/shadow", tags=["assistant-v3-shadow"])


class ShadowComparePayload(BaseModel):
    """Payload accepted by shadow compare route."""

    model_config = ConfigDict(extra="allow")

    session_id: str | None = None
    text: str
    image_base64: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _to_payload_dict(raw_result: Any) -> dict[str, Any]:
    """Convert runner output to a dictionary payload."""

    if isinstance(raw_result, dict):
        return raw_result
    if not isinstance(raw_result, JSONResponse):
        return {}
    try:
        decoded = json.loads(raw_result.body.decode("utf-8"))
    except Exception:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _to_summary(raw_result: Any) -> dict[str, Any]:
    """Normalize one runner result to compare fields."""

    if isinstance(raw_result, Exception):
        return {
            "status": "error",
            "triage_level": None,
            "failed": True,
            "invalid_payload": False,
            "error_type": type(raw_result).__name__,
            "error_message": str(raw_result),
        }

    payload = _to_payload_dict(raw_result)
    status = payload.get("status")
    triage_level = payload.get("triage_level")
    invalid_payload = (
        not payload
        or not isinstance(status, str)
        or (triage_level is not None and not isinstance(triage_level, str))
    )

    error_type = None
    error_message = None
    if invalid_payload:
        error_type = "InvalidPayload"
        error_message = "runner returned payload missing valid status/triage_level"

    return {
        "status": status if isinstance(status, str) else None,
        "triage_level": triage_level if isinstance(triage_level, str) else None,
        "failed": False,
        "invalid_payload": invalid_payload,
        "error_type": error_type,
        "error_message": error_message,
    }


async def compare_v1_v3(payload: dict[str, Any], v1_runner: Runner, v3_runner: Runner) -> dict[str, Any]:
    """Compare v1/v3 outputs and return normalized diff summary."""

    v1_raw, v3_raw = await asyncio.gather(
        v1_runner(payload),
        v3_runner(payload),
        return_exceptions=True,
    )
    v1_summary = _to_summary(v1_raw)
    v3_summary = _to_summary(v3_raw)
    force_mismatch = (
        bool(v1_summary["failed"])
        or bool(v3_summary["failed"])
        or bool(v1_summary["invalid_payload"])
        or bool(v3_summary["invalid_payload"])
    )
    return {
        "same_status": False if force_mismatch else v1_summary["status"] == v3_summary["status"],
        "same_triage": False
        if force_mismatch
        else v1_summary["triage_level"] == v3_summary["triage_level"],
        "v1": v1_summary,
        "v3": v3_summary,
    }


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    """Read optional string field from payload."""

    value = payload.get(key)
    return value if isinstance(value, str) else None


def _optional_float(payload: dict[str, Any], key: str) -> float | None:
    """Read optional float field from payload."""

    value = payload.get(key)
    return value if isinstance(value, float) else None


async def _run_v1(payload: dict[str, Any]) -> dict[str, Any]:
    """Invoke v1 chain for shadow comparison."""

    from src.chains.triage_chain import invoke_chain

    session_id = (_optional_str(payload, "session_id") or "").strip() or str(uuid4())
    text = (_optional_str(payload, "text") or "").strip()
    if not text:
        return {"status": "error", "triage_level": None}

    return await invoke_chain(
        session_id=session_id,
        text=text,
        image_base64=_optional_str(payload, "image_base64"),
        gps_lat=_optional_float(payload, "gps_lat"),
        gps_lng=_optional_float(payload, "gps_lng"),
    )


async def _run_v3(payload: dict[str, Any]) -> dict[str, Any]:
    """Invoke v3 endpoint logic for shadow comparison."""

    from src.interfaces.api.assistant_v2 import AssistantV2InvokePayload
    from src.interfaces.api.assistant_v3 import invoke_assistant_v3

    validated = AssistantV2InvokePayload.model_validate(payload)
    response = await invoke_assistant_v3(validated)
    return _to_payload_dict(response)


@router.post("/compare")
async def shadow_compare(payload: ShadowComparePayload) -> dict[str, Any]:
    """Run lightweight v1/v3 shadow compare when explicitly enabled."""

    settings = get_settings()
    if not (settings.v3_runtime_enabled and settings.v3_shadow_compare_enabled):
        raise HTTPException(status_code=404, detail="shadow_compare_disabled")
    return await compare_v1_v3(payload.model_dump(), v1_runner=_run_v1, v3_runner=_run_v3)
