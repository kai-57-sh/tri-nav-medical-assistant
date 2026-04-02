"""Runtime administration endpoints for assistant v3."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from src.config.settings import get_settings
from src.interfaces.api.assistant_v2 import (
    AssistantV2InvokePayload,
    get_runtime_session_state,
    list_runtime_plugins,
)
from src.interfaces.api.assistant_v3 import invoke_assistant_v3

router = APIRouter(prefix="/assistant/v3/runtime", tags=["assistant-v3-runtime"])


class RuntimeResumePayload(BaseModel):
    """Payload for resuming an existing v3 session."""

    model_config = ConfigDict(extra="allow")

    request_id: str | None = None
    trace_id: str | None = None
    text: str
    image_base64: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/doctor")
async def runtime_doctor_v3() -> dict[str, Any]:
    """Report runtime flags and key dependency health for v3 rollout checks."""

    settings = get_settings()
    redis_healthy = False
    try:
        from src.services.redis_service import get_redis_service

        redis = await get_redis_service()
        redis_healthy = bool(redis and redis.is_healthy)
    except Exception:
        redis_healthy = False

    return {
        "status": "ok" if settings.v3_runtime_enabled else "disabled",
        "runtime": {
            "v3_runtime_enabled": settings.v3_runtime_enabled,
            "v3_shadow_compare_enabled": settings.v3_shadow_compare_enabled,
        },
        "dependencies": {
            "redis": {"healthy": redis_healthy},
        },
    }


@router.get("/sessions/{session_id}/replay")
async def replay_session_v3(session_id: str) -> dict[str, Any]:
    """Return replay data for one session from runtime stores."""

    state = get_runtime_session_state(session_id)
    snapshot = state.get("snapshot")
    runtime_events = state.get("runtime_events", [])
    if snapshot is None and not runtime_events:
        raise HTTPException(status_code=404, detail="session_not_found")
    return {
        "session_id": session_id,
        "snapshot": snapshot,
        "runtime_events": runtime_events,
        "can_resume": snapshot is not None,
    }


@router.get("/plugins")
async def list_plugins_v3() -> dict[str, Any]:
    """List registered runtime plugins used by v2/v3 coordinator."""

    plugins = list_runtime_plugins()
    return {
        "plugins": plugins,
        "count": len(plugins),
    }


@router.post("/sessions/{session_id}/resume")
async def resume_session_v3(session_id: str, payload: RuntimeResumePayload) -> JSONResponse:
    """Resume an existing session by re-invoking v3 on the same session id."""

    state = get_runtime_session_state(session_id)
    snapshot = state.get("snapshot")
    runtime_events = state.get("runtime_events", [])
    if snapshot is None and not runtime_events:
        raise HTTPException(status_code=404, detail="session_not_found")

    invoke_payload = AssistantV2InvokePayload(
        request_id=(payload.request_id or "").strip() or f"req-{uuid4()}",
        session_id=session_id,
        trace_id=(payload.trace_id or "").strip() or str(uuid4()),
        text=payload.text,
        image_base64=payload.image_base64,
        gps_lat=payload.gps_lat,
        gps_lng=payload.gps_lng,
        metadata=dict(payload.metadata),
    )
    return await invoke_assistant_v3(invoke_payload)
