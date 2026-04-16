"""Helpers for applying capability state patches to execution context."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.medical_state import MedicalTurnState
from src.core.runtime.types import CapabilityResult


def _deep_merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, patch_value in patch.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(patch_value, dict):
            merged[key] = _deep_merge_dict(base_value, patch_value)
        else:
            merged[key] = deepcopy(patch_value)
    return merged


def apply_state_patch(context: ExecutionContext, result: CapabilityResult) -> ExecutionContext:
    """Apply a capability result state patch onto the current turn state."""

    if not result.state_patch:
        return context

    existing_state = context.turn_state.model_dump(mode="json")
    merged_state_payload = _deep_merge_dict(existing_state, result.state_patch)
    merged_state = MedicalTurnState.model_validate(merged_state_payload)
    return context.model_copy(update={"turn_state": merged_state})
