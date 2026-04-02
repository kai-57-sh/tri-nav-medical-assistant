"""Unit tests for medical output safety guard."""

from src.policy.safety import enforce_output_guard


def test_enforce_output_guard_rewrites_risky_medical_wording() -> None:
    original = "根据症状可以确诊流感，先观察，别去医院。"

    guarded = enforce_output_guard(original)

    assert "确诊" not in guarded
    assert "疑似" in guarded
    assert "别去医院" not in guarded
    assert "建议尽快就医" in guarded
    assert "尽快就医" in guarded


def test_enforce_output_guard_appends_safety_guidance_when_missing() -> None:
    original = "目前考虑是轻微不适，请注意休息。"

    guarded = enforce_output_guard(original)

    assert "尽快就医" in guarded
