"""Medical output safety guard compatibility wrapper."""

from __future__ import annotations

from src.platform.policy.medical_safety_engine import MedicalSafetyEngine, SafetyResult

_MEDICAL_SAFETY_ENGINE = MedicalSafetyEngine()


def enforce_output_guard_result(text: str) -> SafetyResult:
    """Return structured output safety enforcement result."""

    return _MEDICAL_SAFETY_ENGINE.enforce(text)


def enforce_output_guard(text: str) -> str:
    """Return rewritten output text for legacy guard callers."""

    guarded = enforce_output_guard_result(text).text
    if "尽快就医" not in guarded:
        if guarded and guarded[-1] not in {"。", "！", "？"}:
            guarded = f"{guarded}。"
        guarded = f"{guarded}建议尽快就医"
    return guarded
