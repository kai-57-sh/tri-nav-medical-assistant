"""Shared runtime entrypoints for assistant v3."""

from typing import Any
from uuid import uuid4

from fastapi.responses import JSONResponse, StreamingResponse

from src.config.settings import get_settings
from src.interfaces.api.assistant_v2 import (
    AssistantV2InvokePayload,
    _enforce_response_safety,
    _error_response,
    _invoke_v3_task_coordinator,
    _normalize_status,
    _persist_runtime_snapshot,
    _record_runtime_events,
    _serialize_safety_result,
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


async def _normalized_legacy_fallback_response(
    legacy_payload: dict[str, object],
    *,
    request_id: str,
    session_id: str,
    trace_id: str,
    primary_error: Exception,
) -> JSONResponse:
    """Wrap legacy fallback output in the public v3 response envelope."""

    runtime_status = legacy_payload.get("status")
    response_status = _normalize_status(runtime_status)
    safety_result = _enforce_response_safety(
        status=response_status,
        response_text=legacy_payload.get("response"),
    )
    resolved_session_id = legacy_payload.get("session_id")
    output_session_id = (
        resolved_session_id.strip()
        if isinstance(resolved_session_id, str) and resolved_session_id.strip()
        else session_id
    )
    response_text = legacy_payload.get("response")
    error_message = legacy_payload.get("error_message")
    provenance_payload = legacy_payload.get("provenance")
    provenance: dict[str, Any] = {
        "source": "legacy_graph",
        "fallback": "v3_legacy",
    }
    if isinstance(provenance_payload, dict):
        provenance = {
            **{str(key): value for key, value in provenance_payload.items()},
            **provenance,
        }

    runtime_events = [
        {
            "event_type": "runtime_fallback_triggered",
            "request_id": request_id,
            "session_id": output_session_id,
            "data": {
                "path": "legacy_fallback",
                "primary_error_type": type(primary_error).__name__,
            },
        },
        {
            "event_type": "runtime_finished",
            "request_id": request_id,
            "session_id": output_session_id,
            "data": {
                "path": "legacy_fallback",
                "success": response_status in {"final", "need_more_info"},
            },
        },
    ]

    body: dict[str, Any] = {
        "status": response_status,
        "session_id": output_session_id,
        "trace_id": trace_id,
        "response": safety_result.text,
        "safety": _serialize_safety_result(safety_result),
        "runtime_events": runtime_events,
        "provenance": provenance,
        "trace": {
            "request_id": request_id,
            "path": "legacy_fallback",
            "primary_error_type": type(primary_error).__name__,
            "primary_error_message": str(primary_error),
        },
    }

    if response_status in {"final", "need_more_info"}:
        await _record_runtime_events(output_session_id, runtime_events)
        await _persist_runtime_snapshot(
            request_id=request_id,
            session_id=output_session_id,
            trace_id=trace_id,
            status=response_status,
            response=body["response"],
            runtime_events=runtime_events,
            provenance=body["provenance"],
            trace=body["trace"],
        )
        return JSONResponse(status_code=200, content=body)

    body["error_message"] = (
        error_message if isinstance(error_message, str) and error_message else "assistant_v3_legacy_fallback_failed"
    )
    await _record_runtime_events(output_session_id, runtime_events)
    await _persist_runtime_snapshot(
        request_id=request_id,
        session_id=output_session_id,
        trace_id=trace_id,
        status="error",
        response=body["response"],
        runtime_events=runtime_events,
        provenance=body["provenance"],
        trace=body["trace"],
        error_message=body["error_message"],
    )
    return JSONResponse(status_code=503, content=body)


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
    settings: Any | None = None
    try:
        settings = get_settings()
        return await _invoke_primary_v3(resolved_payload)
    except Exception as exc:
        if settings is not None and bool(getattr(settings, "v3_legacy_fallback_enabled", False)):
            try:
                legacy_payload = await _invoke_legacy_fallback(resolved_payload)
            except Exception as fallback_exc:
                return await _error_response(
                    session_id=session_id,
                    request_id=request_id,
                    trace_id=trace_id,
                    message="assistant_v3_task_runtime_failed",
                    trace={
                        "request_id": request_id,
                        "error_stage": "task_orchestration",
                        "error_type": type(fallback_exc).__name__,
                        "error_message": str(fallback_exc),
                        "primary_error_type": type(exc).__name__,
                        "primary_error_message": str(exc),
                    },
                )
            return await _normalized_legacy_fallback_response(
                legacy_payload,
                request_id=request_id,
                session_id=session_id,
                trace_id=trace_id,
                primary_error=exc,
            )
        return await _error_response(
            session_id=session_id,
            request_id=request_id,
            trace_id=trace_id,
            message="assistant_v3_task_runtime_failed",
            trace={
                "request_id": request_id,
                "error_stage": "settings" if settings is None else "task_orchestration",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )


async def stream_runtime_v3(payload: AssistantV2InvokePayload) -> StreamingResponse:
    """Stream the current v3 runtime through the existing v2 coordinator path."""

    return await stream_assistant_v2(payload)
