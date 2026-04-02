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
from src.core.coordinator.task_coordinator import TaskCoordinator, TaskSpec
from src.core.plugins.builtin import create_builtin_plugins
from src.core.plugins.registry import RuntimePluginRegistry
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult
from src.core.state.event_store import InMemoryEventStore
from src.core.state.session_snapshot_store import InMemorySnapshotStore
from src.platform.runtime.kernel import (
    RuntimeKernel,
    RuntimeKernelInvokeError,
    build_runtime_kernel as _build_runtime_kernel,
)
from src.policy.safety.medical_guard import enforce_output_guard

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


def build_runtime_kernel() -> RuntimeKernel:
    """Build runtime kernel used by assistant_v2 invoke path."""

    return _build_runtime_kernel(
        event_store=_RUNTIME_EVENT_STORE,
        plugins=_build_runtime_plugin_registry(),
    )


def _is_v3_task_runtime(payload: AssistantV2InvokePayload) -> bool:
    """Return whether this request should use v3 task coordinator path."""

    metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
    runtime_mode = metadata.get("runtime_mode")
    if runtime_mode != "v3":
        return False
    try:
        settings = get_settings()
    except Exception:
        return False
    return bool(getattr(settings, "v3_task_coordinator_enabled", False))


def _record_runtime_events(session_id: str, events: list[dict[str, Any]]) -> None:
    for event in events:
        _RUNTIME_EVENT_STORE.append(session_id, event)


def _extract_error_message(value: Any) -> str:
    return value if isinstance(value, str) else "task_failed"


def _recommended_departments_from_triage(triage_level: str | None) -> list[str]:
    if triage_level == "EMERGENCY":
        return ["急诊科"]
    if triage_level == "URGENT":
        return ["急诊科", "内科"]
    if triage_level == "ROUTINE":
        return ["全科", "内科"]
    return ["全科"]


def _possible_causes_from_text(text: str) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return ["症状相关不适（疑似）"]
    excerpt = normalized[:20]
    return [f"{excerpt}相关不适（疑似）"]


def _red_flags_from_triage(triage_level: str | None) -> list[str]:
    if triage_level == "EMERGENCY":
        return ["疑似紧急情况，请立即前往急诊或呼叫急救。"]
    if triage_level == "URGENT":
        return ["症状存在加重风险，建议尽快线下就医。"]
    return ["如出现呼吸困难、胸痛、意识改变等情况，请立即急诊。"]


async def _run_v3_capability_task(
    capability: Any,
    context: ExecutionContext,
) -> dict[str, Any]:
    """Run one v3 capability as a task payload."""

    try:
        plan = await capability.plan(context)
        if isinstance(plan, dict):
            enabled = plan.get("enabled", True)
            if enabled is False:
                return {
                    "status": "skipped",
                    "payload": {"status": "skipped"},
                    "provenance": {"source": "v3_task_coordinator"},
                    "errors": [],
                }
        result = await capability.run(context, plan if isinstance(plan, dict) else None)
    except Exception as exc:
        fallback = await capability.fallback(context, reason=f"task_failed: {exc}", error=exc)
        if not fallback.success:
            message = "; ".join(fallback.errors) if fallback.errors else str(exc)
            raise RuntimeError(message) from exc
        result = fallback

    return {
        "status": "ok",
        "payload": result.payload if isinstance(result.payload, dict) else {},
        "provenance": result.provenance if isinstance(result.provenance, dict) else {},
        "errors": list(result.errors),
    }


def _enrich_v3_task_context(
    context: ExecutionContext,
    *,
    task_name: str,
    task_payload: dict[str, Any],
) -> ExecutionContext:
    metadata = dict(context.metadata)
    payload = task_payload.get("payload")
    if not isinstance(payload, dict):
        return context

    if task_name == "consultation":
        summary = payload.get("summary")
        if isinstance(summary, str) and summary:
            metadata["consultation_summary"] = summary
    elif task_name == "triage":
        triage_level = payload.get("triage_level")
        if isinstance(triage_level, str) and triage_level:
            metadata["triage_level"] = triage_level
        triage_reason = payload.get("triage_reason")
        if isinstance(triage_reason, str) and triage_reason:
            metadata["triage_reason"] = triage_reason
        recommended_departments = payload.get("recommended_departments")
        if isinstance(recommended_departments, list):
            metadata["recommended_departments"] = recommended_departments
        red_flags = payload.get("red_flags")
        if isinstance(red_flags, list):
            metadata["red_flags"] = red_flags
    elif task_name == "evidence":
        evidence_selected = payload.get("evidence_selected")
        if isinstance(evidence_selected, list):
            metadata["evidence_selected"] = evidence_selected
    elif task_name == "navigation":
        navigation_result = payload.get("navigation_result")
        if isinstance(navigation_result, dict):
            metadata["navigation_result"] = navigation_result
        weather_alert = payload.get("weather_alert")
        if isinstance(weather_alert, dict):
            metadata["weather_alert"] = weather_alert

    return context.model_copy(update={"metadata": metadata})


async def _invoke_v3_task_coordinator(
    payload: AssistantV2InvokePayload,
    *,
    request_id: str,
    session_id: str,
    trace_id: str,
) -> JSONResponse:
    """Run deterministic v3 capability task orchestration path."""

    from src.capabilities.consultation.capability import ConsultationCapability
    from src.capabilities.evidence.capability import EvidenceCapability
    from src.capabilities.navigation.capability import NavigationCapability
    from src.capabilities.response.capability import ResponseCapability
    from src.capabilities.triage.capability import TriageCapability

    metadata = dict(payload.metadata)
    metadata["trace_id"] = trace_id
    context = ExecutionContext(
        request_id=request_id,
        session_id=session_id,
        text=payload.text,
        image_base64=payload.image_base64,
        gps_lat=payload.gps_lat,
        gps_lng=payload.gps_lng,
        metadata=metadata,
    )

    plugin_registry = _build_runtime_plugin_registry()
    context = await plugin_registry.apply_before_execute(context)

    consultation = ConsultationCapability()
    triage = TriageCapability()
    evidence = EvidenceCapability()
    navigation = NavigationCapability()
    response = ResponseCapability()

    task_context = context

    async def _run_task_with_enriched_context(task_name: str, capability: Any) -> dict[str, Any]:
        nonlocal task_context
        task_payload = await _run_v3_capability_task(capability, task_context)
        task_context = _enrich_v3_task_context(
            task_context,
            task_name=task_name,
            task_payload=task_payload,
        )
        return task_payload

    task_specs = [
        TaskSpec(
            name=consultation.name,
            required=True,
            runner=lambda _ctx, name=consultation.name, cap=consultation: _run_task_with_enriched_context(name, cap),
        ),
        TaskSpec(
            name=triage.name,
            required=True,
            runner=lambda _ctx, name=triage.name, cap=triage: _run_task_with_enriched_context(name, cap),
        ),
        TaskSpec(
            name=evidence.name,
            required=False,
            runner=lambda _ctx, name=evidence.name, cap=evidence: _run_task_with_enriched_context(name, cap),
        ),
        TaskSpec(
            name=navigation.name,
            required=False,
            runner=lambda _ctx, name=navigation.name, cap=navigation: _run_task_with_enriched_context(name, cap),
        ),
        TaskSpec(
            name=response.name,
            required=True,
            runner=lambda _ctx, name=response.name, cap=response: _run_task_with_enriched_context(name, cap),
        ),
    ]
    task_results = await TaskCoordinator(task_specs).run(context)

    capability_results: list[CapabilityResult] = []
    for task_name, task_result in task_results.items():
        raw_payload = task_result.get("payload")
        wrapped_payload = raw_payload if isinstance(raw_payload, dict) else {}
        payload_dict = (
            wrapped_payload.get("payload")
            if isinstance(wrapped_payload.get("payload"), dict)
            else {}
        )
        if not payload_dict and isinstance(raw_payload, dict):
            payload_dict = raw_payload

        raw_provenance = wrapped_payload.get("provenance")
        provenance = raw_provenance if isinstance(raw_provenance, dict) else {}

        raw_errors = wrapped_payload.get("errors")
        cap_errors = [str(item) for item in raw_errors] if isinstance(raw_errors, list) else []
        if not task_result.get("success", False) and not cap_errors:
            cap_errors = [_extract_error_message(task_result.get("error"))]
        capability_results.append(
            CapabilityResult(
                name=task_name,
                success=bool(task_result.get("success", False)),
                payload=payload_dict,
                provenance={
                    "source": "v3_task_coordinator",
                    "task": task_name,
                    **provenance,
                },
                errors=cap_errors,
            )
        )

    capability_results = await plugin_registry.apply_after_execute(task_context, capability_results)
    primary = next((item for item in capability_results if item.name == "response"), None)
    if primary is None and capability_results:
        primary = capability_results[-1]
    if primary is None:
        return _error_response(
            session_id=session_id,
            request_id=request_id,
            trace_id=trace_id,
            message="assistant_v3_task_runtime_failed_no_results",
            trace={"request_id": request_id, "error_stage": "task_orchestration"},
        )

    triage_result = next((item for item in capability_results if item.name == "triage"), None)
    triage_level_raw = None if triage_result is None else triage_result.payload.get("triage_level")
    triage_level = triage_level_raw if isinstance(triage_level_raw, str) else None

    runtime_events: list[dict[str, Any]] = [
        {
            "event_type": "runtime_started",
            "request_id": request_id,
            "session_id": session_id,
            "data": {"path": "v3_task_coordinator", "task_count": len(task_results)},
        }
    ]
    for task_name, task_result in task_results.items():
        runtime_events.append(
            {
                "event_type": "task_completed",
                "request_id": request_id,
                "session_id": session_id,
                "data": {
                    "task": task_name,
                    "success": bool(task_result.get("success", False)),
                },
            }
        )
    runtime_events.append(
        {
            "event_type": "runtime_finished",
            "request_id": request_id,
            "session_id": session_id,
            "data": {
                "path": "v3_task_coordinator",
                "success": bool(primary.success),
                "tasks_executed": len(task_results),
            },
        }
    )
    _record_runtime_events(session_id, runtime_events)

    output_payload = primary.payload if isinstance(primary.payload, dict) else {}
    runtime_status = output_payload.get("status")
    response_status = _normalize_status(runtime_status)
    if not primary.success:
        response_status = "error"
    response_text = output_payload.get("response")
    normalized_response = response_text if isinstance(response_text, str) else ""
    if response_status in {"final", "need_more_info"} and normalized_response:
        normalized_response = enforce_output_guard(normalized_response)

    body: dict[str, Any] = {
        "status": response_status,
        "session_id": session_id,
        "trace_id": trace_id,
        "response": normalized_response,
        "runtime_events": runtime_events,
        "provenance": primary.provenance,
        "trace": {
            "request_id": request_id,
            "path": "v3_task_coordinator",
            "tasks": {
                name: {
                    "success": bool(task_result.get("success", False)),
                    "error": task_result.get("error"),
                }
                for name, task_result in task_results.items()
            },
        },
    }
    if triage_level is not None:
        body["triage_level"] = triage_level
    body["recommended_departments"] = _recommended_departments_from_triage(triage_level)
    body["possible_causes"] = _possible_causes_from_text(payload.text)
    body["red_flags"] = _red_flags_from_triage(triage_level)
    body["disclaimer"] = "本建议仅供参考，不替代专业医疗诊断。"

    if primary.success and response_status in {"final", "need_more_info"}:
        _persist_runtime_snapshot(
            request_id=request_id,
            session_id=session_id,
            trace_id=trace_id,
            status=response_status,
            response=body["response"],
            runtime_events=runtime_events,
            provenance=body["provenance"],
            trace=body["trace"],
        )
        return JSONResponse(status_code=200, content=body)

    message = "; ".join(primary.errors) if primary.errors else "assistant_v3_task_runtime_failed"
    body["error_message"] = message
    _persist_runtime_snapshot(
        request_id=request_id,
        session_id=session_id,
        trace_id=trace_id,
        status="error",
        response=body["response"],
        runtime_events=runtime_events,
        provenance=body["provenance"],
        trace=body["trace"],
        error_message=message,
    )
    return JSONResponse(status_code=503, content=body)


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

    if _is_v3_task_runtime(payload):
        try:
            return await _invoke_v3_task_coordinator(
                payload,
                request_id=request_id,
                session_id=session_id,
                trace_id=trace_id,
            )
        except Exception as exc:
            return _error_response(
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

    try:
        kernel = build_runtime_kernel()
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

    try:
        kernel_result = await kernel.invoke(
            payload=payload,
            request_id=request_id,
            session_id=session_id,
            trace_id=trace_id,
        )
    except RuntimeKernelInvokeError as exc:
        error = exc.error
        return _error_response(
            session_id=session_id,
            request_id=request_id,
            trace_id=trace_id,
            message="assistant_v2_runtime_failed",
            runtime_events=exc.runtime_events,
            trace={
                "request_id": request_id,
                "error_stage": "invoke",
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
        )
    except Exception as exc:
        runtime_events = getattr(exc, "runtime_events", [])
        if not isinstance(runtime_events, list):
            runtime_events = []
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

    results = kernel_result.results
    runtime_events = kernel_result.runtime_events
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
