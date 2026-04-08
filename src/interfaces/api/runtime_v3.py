"""Shared runtime entrypoints for assistant v3."""

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

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
    _sse_event,
    _stream_error_payload,
)

_LEGACY_SESSION_NAMESPACE = uuid5(NAMESPACE_URL, "trinav.runtime_v3.legacy_session")


def _resolve_payload_ids(
    payload: AssistantV2InvokePayload,
) -> tuple[str, str, str, AssistantV2InvokePayload]:
    """Normalize request/session/trace IDs and return them with a resolved payload copy."""

    request_id = (payload.request_id or "").strip() or f"req-{uuid4()}"
    session_id = (payload.session_id or "").strip() or str(uuid4())
    trace_id = (payload.trace_id or "").strip() or str(uuid4())
    resolved = payload.model_copy(
        update={
            "request_id": request_id,
            "session_id": session_id,
            "trace_id": trace_id,
        }
    )
    return request_id, session_id, trace_id, resolved


async def _invoke_primary_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
    """Invoke the explicit v3 task coordinator path."""

    request_id, session_id, trace_id, resolved_payload = _resolve_payload_ids(payload)
    return await _invoke_v3_task_coordinator(
        resolved_payload,
        request_id=request_id,
        session_id=session_id,
        trace_id=trace_id,
    )


def _legacy_session_id_for_public_session(session_id: str) -> str:
    """Return a stable UUID for legacy graph usage."""

    try:
        parsed_uuid = UUID(session_id)
    except (ValueError, TypeError, AttributeError):
        return str(uuid5(_LEGACY_SESSION_NAMESPACE, session_id))
    canonical_uuid = str(parsed_uuid)
    if session_id == canonical_uuid:
        return canonical_uuid
    return str(uuid5(_LEGACY_SESSION_NAMESPACE, session_id))


async def _invoke_legacy_fallback(payload: AssistantV2InvokePayload) -> dict[str, object]:
    """Invoke the legacy chain directly for v3 fallback."""

    from src.chains.triage_chain import invoke_chain

    session_id = (payload.session_id or "").strip() or str(uuid4())
    return await invoke_chain(
        session_id=_legacy_session_id_for_public_session(session_id),
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
    primary_error_type: str,
    primary_error_message: str,
) -> JSONResponse:
    """Wrap legacy fallback output in the public v3 response envelope."""

    extra_snapshot_fields: dict[str, Any] = {}
    runtime_status = legacy_payload.get("status")
    response_status = _normalize_status(runtime_status)
    safety_result = _enforce_response_safety(
        status=response_status,
        response_text=legacy_payload.get("response"),
    )
    output_session_id = session_id
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
                "primary_error_type": primary_error_type,
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
            "primary_error_type": primary_error_type,
            "primary_error_message": primary_error_message,
        },
    }
    triage_level = legacy_payload.get("triage_level")
    if isinstance(triage_level, str):
        body["triage_level"] = triage_level
        extra_snapshot_fields["triage_level"] = triage_level
    recommended_departments = legacy_payload.get("recommended_departments")
    if isinstance(recommended_departments, list) and all(
        isinstance(item, str) for item in recommended_departments
    ):
        body["recommended_departments"] = recommended_departments
        extra_snapshot_fields["recommended_departments"] = recommended_departments
    possible_causes = legacy_payload.get("possible_causes")
    if isinstance(possible_causes, list) and all(isinstance(item, str) for item in possible_causes):
        body["possible_causes"] = possible_causes
        extra_snapshot_fields["possible_causes"] = possible_causes
    red_flags = legacy_payload.get("red_flags")
    if isinstance(red_flags, list) and all(isinstance(item, str) for item in red_flags):
        body["red_flags"] = red_flags
        extra_snapshot_fields["red_flags"] = red_flags
    disclaimer = legacy_payload.get("disclaimer")
    if isinstance(disclaimer, str):
        body["disclaimer"] = disclaimer
        extra_snapshot_fields["disclaimer"] = disclaimer

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
            extra_snapshot_fields=extra_snapshot_fields,
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
        extra_snapshot_fields=extra_snapshot_fields,
    )
    return JSONResponse(status_code=503, content=body)


def _decoded_response_body(response: JSONResponse) -> dict[str, Any]:
    """Decode JSONResponse content for fallback gating."""

    try:
        decoded = json.loads(bytes(response.body).decode("utf-8"))
    except Exception:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _should_fallback_from_primary_response(response: JSONResponse) -> bool:
    """Return whether a structured primary response should trigger legacy fallback."""

    body = _decoded_response_body(response)
    return response.status_code >= 500 or body.get("status") == "error"


def _primary_failure_details_from_response(response: JSONResponse) -> tuple[str, str]:
    """Extract fallback trace details from a structured primary error response."""

    body = _decoded_response_body(response)
    trace = body.get("trace")
    error_type = trace.get("error_type") if isinstance(trace, dict) else None
    error_message = body.get("error_message")
    return (
        error_type if isinstance(error_type, str) and error_type else "PrimaryErrorResponse",
        error_message if isinstance(error_message, str) and error_message else "primary returned structured error",
    )


async def _runtime_disabled_error_response(
    *,
    request_id: str,
    session_id: str,
    trace_id: str,
) -> JSONResponse:
    """Return the canonical structured error when the v3 runtime gate is off."""

    return await _error_response(
        session_id=session_id,
        request_id=request_id,
        trace_id=trace_id,
        message="assistant_v3_runtime_disabled",
        trace={
            "request_id": request_id,
            "error_stage": "runtime_gate",
            "error_type": "RuntimeDisabled",
            "error_message": "v3 runtime disabled by configuration",
        },
    )


def _runtime_disabled_stream_response(
    *,
    request_id: str,
    session_id: str,
    trace_id: str,
) -> StreamingResponse:
    """Return a stream-final error payload when the v3 runtime gate is off."""

    async def event_stream() -> AsyncIterator[str]:
        yield _sse_event(
            "status",
            {
                "status": "start",
                "request_id": request_id,
                "session_id": session_id,
                "trace_id": trace_id,
            },
        )
        yield _sse_event(
            "final",
            _stream_error_payload(
                session_id=session_id,
                request_id=request_id,
                trace_id=trace_id,
                message="assistant_v3_runtime_disabled",
                trace={
                    "request_id": request_id,
                    "error_stage": "runtime_gate",
                    "error_type": "RuntimeDisabled",
                    "error_message": "v3 runtime disabled by configuration",
                },
            ),
        )
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def invoke_runtime_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
    """Invoke v3 primary runtime and optionally fall back to legacy chain."""

    request_id, session_id, trace_id, resolved_payload = _resolve_payload_ids(payload)
    settings: Any | None = None
    try:
        settings = get_settings()
        if not bool(getattr(settings, "v3_runtime_enabled", True)):
            return await _runtime_disabled_error_response(
                request_id=request_id,
                session_id=session_id,
                trace_id=trace_id,
            )
        primary_response = await _invoke_primary_v3(resolved_payload)
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
                primary_error_type=type(exc).__name__,
                primary_error_message=str(exc),
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

    if settings is None or not bool(getattr(settings, "v3_legacy_fallback_enabled", False)):
        return primary_response
    if not _should_fallback_from_primary_response(primary_response):
        return primary_response

    primary_error_type, primary_error_message = _primary_failure_details_from_response(primary_response)
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
                "primary_error_type": primary_error_type,
                "primary_error_message": primary_error_message,
            },
        )
    return await _normalized_legacy_fallback_response(
        legacy_payload,
        request_id=request_id,
        session_id=session_id,
        trace_id=trace_id,
        primary_error_type=primary_error_type,
        primary_error_message=primary_error_message,
    )


async def stream_runtime_v3(payload: AssistantV2InvokePayload) -> StreamingResponse:
    """Stream v3 runtime results as SSE, sharing the same primary/fallback/disabled logic as invoke_runtime_v3."""

    request_id, session_id, trace_id, resolved_payload = _resolve_payload_ids(payload)

    try:
        settings = get_settings()
    except Exception:
        settings = None

    if settings is not None and not bool(getattr(settings, "v3_runtime_enabled", True)):
        return _runtime_disabled_stream_response(
            request_id=request_id,
            session_id=session_id,
            trace_id=trace_id,
        )

    async def event_stream() -> AsyncIterator[str]:
        yield _sse_event(
            "status",
            {
                "status": "start",
                "request_id": request_id,
                "session_id": session_id,
                "trace_id": trace_id,
            },
        )
        final_payload: dict[str, Any] | None = None
        try:
            invoke_response = await invoke_runtime_v3(resolved_payload)
            final_payload = _decoded_response_body(invoke_response)
        except Exception as exc:
            final_payload = _stream_error_payload(
                session_id=session_id,
                request_id=request_id,
                trace_id=trace_id,
                message="assistant_v3_stream_failed",
                trace={
                    "request_id": request_id,
                    "error_stage": "stream",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
        finally:
            if final_payload is None:
                final_payload = _stream_error_payload(
                    session_id=session_id,
                    request_id=request_id,
                    trace_id=trace_id,
                    message="assistant_v3_stream_missing_final",
                    trace={
                        "request_id": request_id,
                        "error_stage": "stream",
                        "error_type": "MissingFinalPayload",
                        "error_message": "final payload not generated",
                    },
                )
            yield _sse_event("final", final_payload)
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
