"""Shared runtime entrypoints for assistant v3."""

from uuid import uuid4

from fastapi.responses import JSONResponse, StreamingResponse

from src.config.settings import get_settings
from src.interfaces.api.assistant_v2 import (
    AssistantV2InvokePayload,
    _error_response,
    _invoke_v3_task_coordinator,
    stream_assistant_v2,
)


async def _invoke_primary_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
    """Invoke the explicit v3 task coordinator path."""

    request_id = (payload.request_id or "").strip() or f"req-{uuid4()}"
    session_id = (payload.session_id or "").strip() or str(uuid4())
    trace_id = (payload.trace_id or "").strip() or str(uuid4())
    resolved_payload = payload.model_copy(
        update={
            "request_id": request_id,
            "session_id": session_id,
            "trace_id": trace_id,
        }
    )
    return await _invoke_v3_task_coordinator(
        resolved_payload,
        request_id=request_id,
        session_id=session_id,
        trace_id=trace_id,
    )


async def _invoke_legacy_fallback(payload: AssistantV2InvokePayload) -> dict[str, object]:
    """Invoke the legacy chain directly for v3 fallback."""

    from src.chains.triage_chain import invoke_chain

    session_id = (payload.session_id or "").strip() or str(uuid4())
    return await invoke_chain(
        session_id=session_id,
        text=payload.text,
        image_base64=payload.image_base64,
        gps_lat=payload.gps_lat,
        gps_lng=payload.gps_lng,
    )


async def invoke_runtime_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
    """Invoke v3 primary runtime and optionally fall back to legacy chain."""

    request_id = (payload.request_id or "").strip() or f"req-{uuid4()}"
    session_id = (payload.session_id or "").strip() or str(uuid4())
    trace_id = (payload.trace_id or "").strip() or str(uuid4())
    resolved_payload = payload.model_copy(
        update={
            "request_id": request_id,
            "session_id": session_id,
            "trace_id": trace_id,
        }
    )
    settings = get_settings()

    try:
        return await _invoke_primary_v3(resolved_payload)
    except Exception as exc:
        if bool(getattr(settings, "v3_legacy_fallback_enabled", False)):
            return JSONResponse(status_code=200, content=await _invoke_legacy_fallback(resolved_payload))
        return await _error_response(
            session_id=session_id,
            request_id=request_id,
            trace_id=trace_id,
            message="assistant_v3_task_runtime_failed",
            trace={
                "request_id": request_id,
                "error_stage": "task_orchestration",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )


async def stream_runtime_v3(payload: AssistantV2InvokePayload) -> StreamingResponse:
    """Stream the current v3 runtime through the existing v2 coordinator path."""

    return await stream_assistant_v2(payload)
