"""Assistant v3 API routes (phase 1 delegates to v2 behavior)."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from src.interfaces.api.assistant_v2 import (
    AssistantV2InvokePayload,
    invoke_assistant_v2,
    stream_assistant_v2,
)

router = APIRouter(prefix="/assistant/v3", tags=["assistant-v3"])


@router.post("/invoke")
async def invoke_assistant_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
    """Invoke assistant v3 using the existing v2 runtime contract."""

    return await invoke_assistant_v2(payload)


@router.post("/stream")
async def stream_assistant_v3(payload: AssistantV2InvokePayload) -> StreamingResponse:
    """Stream assistant v3 responses using existing v2 SSE behavior."""

    return await stream_assistant_v2(payload)
