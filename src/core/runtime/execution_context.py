"""Execution context model shared by v2 runtime components."""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from src.core.runtime.types import JSONValue

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ExecutionContext(BaseModel):
    """Normalized runtime input context."""

    request_id: NonEmptyStr
    session_id: NonEmptyStr
    text: NonEmptyStr
    image_base64: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    metadata: dict[str, JSONValue] = Field(default_factory=dict)
