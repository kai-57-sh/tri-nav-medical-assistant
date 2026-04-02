"""Runtime result and event models for TriNav v2."""

from typing import Any

from pydantic import BaseModel, Field


class CapabilityResult(BaseModel):
    """Normalized output returned by each capability execution."""

    name: str
    success: bool
    payload: dict[str, Any]
    provenance: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class RuntimeEvent(BaseModel):
    """Event emitted during runtime execution."""

    event_type: str
    request_id: str
    session_id: str
    data: dict[str, Any] = Field(default_factory=dict)
