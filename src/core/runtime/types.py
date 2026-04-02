"""Runtime result and event models for TriNav v2."""

from typing import Annotated

from pydantic import BaseModel, Field, JsonValue, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
JSONValue = JsonValue


class CapabilityResult(BaseModel):
    """Normalized output returned by each capability execution."""

    name: str
    success: bool
    payload: dict[str, JSONValue]
    provenance: dict[str, JSONValue] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class RuntimeEvent(BaseModel):
    """Event emitted during runtime execution."""

    event_type: NonEmptyStr
    request_id: NonEmptyStr
    session_id: NonEmptyStr
    data: dict[str, JSONValue] = Field(default_factory=dict)
