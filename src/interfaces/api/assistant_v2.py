"""Assistant v2 API routes."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/assistant/v2", tags=["assistant-v2"])


class AssistantV2InvokePayload(BaseModel):
    """Input payload for assistant v2 invocation."""

    model_config = ConfigDict(extra="allow")

    request_id: str | None = None
    session_id: str | None = None
    text: str
    image_base64: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _error_response(
    *,
    session_id: str,
    request_id: str,
    message: str,
    runtime_events: list[dict[str, Any]] | None = None,
    trace: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build a structured runtime error response."""

    return JSONResponse(
        status_code=503,
        content={
            "status": "error",
            "session_id": session_id,
            "response": "",
            "runtime_events": runtime_events or [],
            "provenance": provenance or {"source": "assistant_v2"},
            "trace": trace or {"request_id": request_id, "error_message": message},
            "error_message": message,
        },
    )


@router.post("/invoke")
async def invoke_assistant_v2(payload: AssistantV2InvokePayload) -> JSONResponse:
    """Invoke TriNav v2 runtime with legacy triage capability."""

    request_id = (payload.request_id or "").strip() or f"req-{uuid4()}"
    session_id = (payload.session_id or "").strip() or str(uuid4())

    try:
        from src.capabilities.legacy_triage.capability import LegacyTriageCapability
        from src.core.runtime.event_bus import EventBus
        from src.core.runtime.execution_context import ExecutionContext
        from src.core.runtime.query_engine import QueryEngine
    except Exception as exc:  # pragma: no cover - defensive import guard
        return _error_response(
            session_id=session_id,
            request_id=request_id,
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
        context = ExecutionContext(
            request_id=request_id,
            session_id=session_id,
            text=payload.text,
            image_base64=payload.image_base64,
            gps_lat=payload.gps_lat,
            gps_lng=payload.gps_lng,
            metadata=payload.metadata,
        )
        event_bus = EventBus()
        engine = QueryEngine([LegacyTriageCapability()], event_bus=event_bus)
        results = await engine.run(context)
    except Exception as exc:
        runtime_events = [] if event_bus is None else event_bus.dump()
        return _error_response(
            session_id=session_id,
            request_id=request_id,
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
            message="assistant_v2_runtime_failed_no_results",
            runtime_events=runtime_events,
            trace={"request_id": request_id, "error_stage": "invoke", "error_type": "NoResults"},
        )

    primary = results[0]
    output_payload = primary.payload if isinstance(primary.payload, dict) else {}
    runtime_status = output_payload.get("status")
    response_status = runtime_status if isinstance(runtime_status, str) else ("ok" if primary.success else "error")
    response_text = output_payload.get("response")
    resolved_session_id = output_payload.get("session_id")
    error_message = output_payload.get("error_message")

    body = {
        "status": response_status,
        "session_id": resolved_session_id if isinstance(resolved_session_id, str) else session_id,
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

    if primary.success and response_status != "error":
        return JSONResponse(status_code=200, content=body)

    message = error_message if isinstance(error_message, str) else "; ".join(primary.errors)
    body["error_message"] = message or "assistant_v2_runtime_failed"
    return JSONResponse(status_code=503, content=body)
