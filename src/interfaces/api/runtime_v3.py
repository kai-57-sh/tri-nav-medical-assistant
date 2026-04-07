"""Shared runtime entrypoints for assistant v3."""

from fastapi.responses import JSONResponse, StreamingResponse

from src.interfaces.api.assistant_v2 import (
    AssistantV2InvokePayload,
    invoke_assistant_v2,
    stream_assistant_v2,
)


async def invoke_runtime_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
    """Invoke the current v3 runtime through the existing v2 coordinator path."""

    return await invoke_assistant_v2(payload)


async def stream_runtime_v3(payload: AssistantV2InvokePayload) -> StreamingResponse:
    """Stream the current v3 runtime through the existing v2 coordinator path."""

    return await stream_assistant_v2(payload)
