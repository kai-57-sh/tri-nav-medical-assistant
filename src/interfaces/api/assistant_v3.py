"""Assistant v3 API routes (phase 1 delegates to v2 behavior)."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from src.interfaces.api.assistant_v2 import (
    AssistantV2InvokePayload,
)
from src.interfaces.api.runtime_v3 import invoke_runtime_v3, stream_runtime_v3

router = APIRouter(prefix="/assistant/v3", tags=["assistant-v3"])


def _with_v3_runtime_mode(payload: AssistantV2InvokePayload) -> AssistantV2InvokePayload:
    metadata = dict(payload.metadata)
    metadata["runtime_mode"] = "v3"
    return payload.model_copy(update={"metadata": metadata})


@router.post("/invoke")
async def invoke_assistant_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
    """Invoke assistant v3 using the existing v2 runtime contract."""

    return await invoke_runtime_v3(_with_v3_runtime_mode(payload))


@router.post("/stream")
async def stream_assistant_v3(payload: AssistantV2InvokePayload) -> StreamingResponse:
    """Stream assistant v3 responses using existing v2 SSE behavior."""

    return await stream_runtime_v3(_with_v3_runtime_mode(payload))
