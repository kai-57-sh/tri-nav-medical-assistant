"""Execution context model shared by v2 runtime components."""

from typing import Any

from pydantic import BaseModel, Field


class ExecutionContext(BaseModel):
    """Normalized runtime input context."""

    request_id: str
    session_id: str
    text: str
    image_base64: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
