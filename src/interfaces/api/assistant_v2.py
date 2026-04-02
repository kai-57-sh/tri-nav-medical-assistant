"""Assistant v2 API routes."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from copy import deepcopy
from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from src.config.settings import get_settings
from src.core.coordinator.runtime_coordinator import RuntimeCoordinator
from src.core.plugins.builtin import create_builtin_plugins
from src.core.plugins.registry import RuntimePluginRegistry
from src.core.state.event_store import InMemoryEventStore
from src.core.state.session_snapshot_store import InMemorySnapshotStore

router = APIRouter(prefix="/assistant/v2", tags=["assistant-v2"])
_ALLOWED_STATUSES = frozenset({"final", "need_more_info", "error"})
_RUNTIME_EVENT_STORE = InMemoryEventStore()
_RUNTIME_SNAPSHOT_STORE = InMemorySnapshotStore()


class AssistantV2InvokePayload(BaseModel):
    """Input payload for assistant v2 invocation."""

    model_config = ConfigDict(extra="allow")

    request_id: str | None = None
    session_id: str | None = None
    trace_id: str | None = None
    text: str
    image_base64: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _copy_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    return {}


def _copy_events(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [deepcopy(item) for item in value if isinstance(item, dict)]


def _persist_runtime_snapshot(
    *,
    request_id: str,
    session_id: str,
    trace_id: str,
    status: str,
    response: str,
    runtime_events: list[dict[str, Any]],
    provenance: dict[str, Any],
    trace: dict[str, Any],
    error_message: str | None = None,
) -> None:
    snapshot = {
        "request_id": request_id,
        "session_id": session_id,
        "trace_id": trace_id,
        "status": status,
        "response": response,
        "runtime_events": _copy_events(runtime_events),
        "provenance": _copy_dict(provenance),
        "trace": _copy_dict(trace),
    }
    if error_message is not None:
        snapshot["error_message"] = error_message
    _RUNTIME_SNAPSHOT_STORE.upsert(session_id, snapshot)


def get_runtime_session_state(session_id: str) -> dict[str, Any]:
    """Expose runtime replay data for one session."""

    snapshot = _RUNTIME_SNAPSHOT_STORE.load(session_id)
    runtime_events = _RUNTIME_EVENT_STORE.list(session_id)
    if not runtime_events and isinstance(snapshot, dict):
        runtime_events = _copy_events(snapshot.get("runtime_events"))
    return {
        "session_id": session_id,
        "snapshot": snapshot,
        "runtime_events": runtime_events,
    }


def list_runtime_plugins() -> list[str]:
    """Expose registered runtime plugin names for diagnostics."""

    return _build_runtime_plugin_registry().list_names()


def get_runtime_store_summary() -> dict[str, int]:
    """Expose runtime event/snapshot buffer summary for diagnostics."""

    return {
        "sessions_with_events": _RUNTIME_EVENT_STORE.session_count(),
        "total_runtime_events": _RUNTIME_EVENT_STORE.event_count(),
        "sessions_with_snapshots": _RUNTIME_SNAPSHOT_STORE.count(),
    }


def _build_runtime_plugin_registry() -> RuntimePluginRegistry:
    """Build a runtime plugin registry from current feature flags."""

    registry = RuntimePluginRegistry()
    try:
        settings = get_settings()
    except Exception:
        return registry

    if not bool(getattr(settings, "v3_builtin_plugins_enabled", False)):
        return registry

    trace_enabled = bool(getattr(settings, "v3_plugin_trace_enabled", True))
    medical_footer_enabled = bool(getattr(settings, "v3_plugin_medical_footer_enabled", True))
    for plugin in create_builtin_plugins(
        trace_enabled=trace_enabled,
        medical_footer_enabled=medical_footer_enabled,
    ):
        registry.register(plugin)
    return registry


def _error_response(
    *,
    session_id: str,
    request_id: str,
    trace_id: str,
    message: str,
    runtime_events: list[dict[str, Any]] | None = None,
    trace: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build a structured runtime error response."""

    content = {
        "status": "error",
        "session_id": session_id,
        "trace_id": trace_id,
        "response": "",
        "runtime_events": runtime_events or [],
        "provenance": provenance or {"source": "assistant_v2"},
        "trace": trace or {"request_id": request_id, "error_message": message},
        "error_message": message,
    }
    _persist_runtime_snapshot(
        request_id=request_id,
        session_id=session_id,
        trace_id=trace_id,
        status="error",
        response="",
        runtime_events=content["runtime_events"],
        provenance=content["provenance"],
        trace=content["trace"],
        error_message=message,
    )
    return JSONResponse(status_code=503, content=content)


def _normalize_status(runtime_status: Any) -> str:
    """Normalize runtime status to the public assistant-v2 contract."""

    if isinstance(runtime_status, str) and runtime_status in _ALLOWED_STATUSES:
        return runtime_status
    return "error"


def _sse_event(event: str, data: Any) -> str:
    """Serialize one SSE event frame."""

    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream_error_payload(
    *,
    session_id: str,
    request_id: str,
    trace_id: str,
    message: str,
    trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build invoke-like error payload used by stream fallback paths."""

    return {
        "status": "error",
        "session_id": session_id,
        "trace_id": trace_id,
        "response": "",
        "runtime_events": [],
        "provenance": {"source": "assistant_v2"},
        "trace": trace or {"request_id": request_id, "error_message": message},
        "error_message": message,
    }


def _response_json(
    response: JSONResponse,
    *,
    session_id: str,
    request_id: str,
    trace_id: str,
) -> dict[str, Any]:
    """Decode JSONResponse content for SSE final payload emission."""

    try:
        decoded = json.loads(response.body.decode("utf-8"))
    except Exception as exc:
        return _stream_error_payload(
            session_id=session_id,
            request_id=request_id,
            trace_id=trace_id,
            message="assistant_v2_stream_invalid_payload",
            trace={
                "request_id": request_id,
                "error_stage": "stream_decode",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
    if isinstance(decoded, dict):
        decoded.setdefault("trace_id", trace_id)
        return decoded
    return _stream_error_payload(
        session_id=session_id,
        request_id=request_id,
        trace_id=trace_id,
        message="assistant_v2_stream_invalid_payload",
        trace={
            "request_id": request_id,
            "error_stage": "stream_decode",
            "error_type": "InvalidPayloadType",
            "error_message": "decoded payload is not an object",
        },
    )


@router.post("/invoke")
async def invoke_assistant_v2(payload: AssistantV2InvokePayload) -> JSONResponse:
    """Invoke TriNav v2 runtime with legacy triage capability."""

    request_id = (payload.request_id or "").strip() or f"req-{uuid4()}"
    session_id = (payload.session_id or "").strip() or str(uuid4())
    trace_id = (payload.trace_id or "").strip() or str(uuid4())

    try:
        from src.capabilities.legacy_triage.capability import LegacyTriageCapability
        from src.core.runtime.event_bus import EventBus
        from src.core.runtime.execution_context import ExecutionContext
        from src.core.runtime.query_engine import QueryEngine
    except Exception as exc:  # pragma: no cover - defensive import guard
        return _error_response(
            session_id=session_id,
            request_id=request_id,
            trace_id=trace_id,
            message="assistant_v2_runtime_unavailable",
            trace={
                "request_id": request_id,
                "error_stage": "bootstrap",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )

    event_bus: Any = None
    try:
        context_metadata = dict(payload.metadata)
        context_metadata["trace_id"] = trace_id
        context = ExecutionContext(
            request_id=request_id,
            session_id=session_id,
            text=payload.text,
            image_base64=payload.image_base64,
            gps_lat=payload.gps_lat,
            gps_lng=payload.gps_lng,
            metadata=context_metadata,
        )
        event_bus = EventBus()
        engine = QueryEngine(
            [LegacyTriageCapability()],
            event_bus=event_bus,
            event_store=_RUNTIME_EVENT_STORE,
        )
        coordinator = RuntimeCoordinator(engine=engine, plugins=_build_runtime_plugin_registry())
        results = await coordinator.run(context)
    except Exception as exc:
        runtime_events = [] if event_bus is None else event_bus.dump()
        return _error_response(
            session_id=session_id,
            request_id=request_id,
            trace_id=trace_id,
            message="assistant_v2_runtime_failed",
            runtime_events=runtime_events,
            trace={
                "request_id": request_id,
                "error_stage": "invoke",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )

    runtime_events = event_bus.dump()
    if not results:
        return _error_response(
            session_id=session_id,
            request_id=request_id,
            trace_id=trace_id,
            message="assistant_v2_runtime_failed_no_results",
            runtime_events=runtime_events,
            trace={"request_id": request_id, "error_stage": "invoke", "error_type": "NoResults"},
        )

    primary = results[0]
    output_payload = primary.payload if isinstance(primary.payload, dict) else {}
    runtime_status = output_payload.get("status")
    response_status = _normalize_status(runtime_status)
    if not primary.success:
        response_status = "error"
    response_text = output_payload.get("response")
    resolved_session_id = output_payload.get("session_id")
    error_message = output_payload.get("error_message")

    body = {
        "status": response_status,
        "session_id": resolved_session_id if isinstance(resolved_session_id, str) else session_id,
        "trace_id": trace_id,
        "response": response_text if isinstance(response_text, str) else "",
        "runtime_events": runtime_events,
        "provenance": primary.provenance,
        "trace": {
            "request_id": request_id,
            "capability": primary.name,
            "success": primary.success,
            "errors": primary.errors,
        },
    }

    if primary.success and response_status in {"final", "need_more_info"}:
        _persist_runtime_snapshot(
            request_id=request_id,
            session_id=body["session_id"],
            trace_id=trace_id,
            status=response_status,
            response=body["response"],
            runtime_events=body["runtime_events"],
            provenance=body["provenance"],
            trace=body["trace"],
        )
        return JSONResponse(status_code=200, content=body)

    message = error_message if isinstance(error_message, str) else "; ".join(primary.errors)
    body["error_message"] = message or "assistant_v2_runtime_failed"
    _persist_runtime_snapshot(
        request_id=request_id,
        session_id=body["session_id"],
        trace_id=trace_id,
        status="error",
        response=body["response"],
        runtime_events=body["runtime_events"],
        provenance=body["provenance"],
        trace=body["trace"],
        error_message=body["error_message"],
    )
    return JSONResponse(status_code=503, content=body)


@router.post("/stream")
async def stream_assistant_v2(payload: AssistantV2InvokePayload) -> StreamingResponse:
    """Stream invoke result as SSE status/final events and [DONE] marker."""

    request_id = (payload.request_id or "").strip() or f"req-{uuid4()}"
    session_id = (payload.session_id or "").strip() or str(uuid4())
    trace_id = (payload.trace_id or "").strip() or str(uuid4())
    resolved_payload = payload.model_copy(
        update={"request_id": request_id, "session_id": session_id, "trace_id": trace_id}
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
            final_response = await invoke_assistant_v2(resolved_payload)
            final_payload = _response_json(
                final_response,
                session_id=session_id,
                request_id=request_id,
                trace_id=trace_id,
            )
        except Exception as exc:
            final_payload = _stream_error_payload(
                session_id=session_id,
                request_id=request_id,
                trace_id=trace_id,
                message="assistant_v2_stream_failed",
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
                    message="assistant_v2_stream_missing_final",
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
