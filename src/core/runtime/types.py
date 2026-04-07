"""Runtime result and event models for TriNav v2."""

from typing import Annotated

from pydantic import BaseModel, Field, JsonValue, StringConstraints, model_validator

from src.core.runtime.medical_state import MedicalTurnState
from src.core.runtime.stop_reason import StopReason

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
JSONValue = JsonValue


class CapabilityResult(BaseModel):
    """Normalized output returned by each capability execution."""

    name: str
    success: bool
    payload: dict[str, JSONValue]
    provenance: dict[str, JSONValue] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    state_patch: dict[str, JSONValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_state_patch_shape(self) -> "CapabilityResult":
        for section_name, section_patch in self.state_patch.items():
            section_field = MedicalTurnState.model_fields.get(section_name)
            if section_field is None:
                raise ValueError(f"unknown state patch section: {section_name}")
            if not isinstance(section_patch, dict):
                raise ValueError(
                    f"state patch section '{section_name}' must be an object payload"
                )
            section_model = section_field.annotation
            section_model.model_validate(section_patch)
        return self


class RuntimeEvent(BaseModel):
    """Event emitted during runtime execution."""

    event_type: NonEmptyStr
    request_id: NonEmptyStr
    session_id: NonEmptyStr
    data: dict[str, JSONValue] = Field(default_factory=dict)


class RuntimeStop(BaseModel):
    """Structured reason for runtime stop events."""

    reason: StopReason
