"""Compatibility adapter for the legacy public /assistant surface."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from src.interfaces.api.assistant_v2 import AssistantV2InvokePayload
from src.interfaces.api.runtime_v3 import invoke_runtime_v3, stream_runtime_v3

router = APIRouter(prefix="/assistant", tags=["assistant-compat"])


class AssistantCompatEnvelope(BaseModel):
    """LangServe-style request envelope kept for compatibility."""

    input: AssistantV2InvokePayload


def _with_v3_runtime_mode(payload: AssistantV2InvokePayload) -> AssistantV2InvokePayload:
    """Mark compat payloads to follow the public v3 runtime path."""

    metadata = dict(payload.metadata)
    metadata["runtime_mode"] = "v3"
    return payload.model_copy(update={"metadata": metadata})


def _decode_json_response_body(response: JSONResponse) -> dict[str, Any]:
    """Decode the delegated JSONResponse body for compatibility wrapping."""

    try:
        decoded = json.loads(bytes(response.body).decode("utf-8"))
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


@router.post("/invoke")
async def invoke_assistant_compat(payload: AssistantCompatEnvelope) -> JSONResponse:
    """Delegate invoke calls to runtime v3 and preserve the legacy envelope."""

    delegated = await invoke_runtime_v3(_with_v3_runtime_mode(payload.input))
    output = _decode_json_response_body(delegated)
    return JSONResponse(
        status_code=200 if output else delegated.status_code,
        content={
            "output": output,
            "metadata": {"runtime_mode": "v3"},
        },
    )


@router.post("/stream")
async def stream_assistant_compat(payload: AssistantCompatEnvelope) -> StreamingResponse:
    """Delegate stream calls to runtime v3 while keeping SSE transport behavior."""

    return await stream_runtime_v3(_with_v3_runtime_mode(payload.input))
